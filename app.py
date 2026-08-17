import os
import tempfile
from flask import Flask, render_template, request, jsonify
import fal_client

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

STANDARD = "fal-ai/kling-video/v3/standard/motion-control"
PRO = "fal-ai/kling-video/v3/pro/motion-control"

@app.route("/")
def home():
    return render_template("index.html")

@app.post("/api/generate")
def generate():
    key = os.getenv("FAL_KEY")
    if not key:
        return jsonify(error="FAL_KEY is not configured in Vercel."), 500

    image = request.files.get("image")
    video = request.files.get("video")
    prompt = request.form.get("prompt", "").strip()
    orientation = request.form.get("orientation", "video")
    quality = request.form.get("quality", "standard")

    if not image or not video:
        return jsonify(error="Upload both image and motion video."), 400

    model = PRO if quality == "pro" else STANDARD

    try:
        with tempfile.TemporaryDirectory() as td:
            image_path = os.path.join(td, "character" + os.path.splitext(image.filename or ".png")[1])
            video_path = os.path.join(td, "motion" + os.path.splitext(video.filename or ".mp4")[1])
            image.save(image_path)
            video.save(video_path)

            image_url = fal_client.upload_file(image_path)
            video_url = fal_client.upload_file(video_path)

        args = {
            "image_url": image_url,
            "video_url": video_url,
            "character_orientation": orientation,
            "keep_original_sound": True,
        }
        if prompt:
            args["prompt"] = prompt

        job = fal_client.submit(model, arguments=args)
        return jsonify(request_id=job.request_id, model=model)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.get("/api/status/<request_id>")
def status(request_id):
    model = request.args.get("model", STANDARD)
    if model not in (STANDARD, PRO):
        model = STANDARD

    try:
        s = fal_client.status(model, request_id, with_logs=False)
        name = s.__class__.__name__

        if name == "Completed":
            result = fal_client.result(model, request_id)
            url = result.get("video", {}).get("url")
            return jsonify(status="COMPLETED", video_url=url)

        if name == "InProgress":
            return jsonify(status="IN_PROGRESS")

        return jsonify(status="IN_QUEUE")
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.get("/health")
def health():
    return jsonify(ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
