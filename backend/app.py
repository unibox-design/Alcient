# backend/app.py
import os
import re
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from llm import generate_narration, generate_storyboard
from orchestrator import get_orchestrator
from pexels import search_pexels
from tts import estimate_tts_duration
from utils import extract_keywords


def _map_aspect_to_orientation(value: str) -> str:
    if not value:
        return "landscape"
    value_lower = value.lower()
    if value_lower in {"portrait", "9:16", "vertical"}:
        return "portrait"
    if value_lower in {"square", "1:1"}:
        return "square"
    return "landscape"


def _scene_hint_for_duration(seconds: int) -> int:
    if seconds <= 75:
        return 6
    if seconds <= 150:
        return 8
    if seconds <= 210:
        return 10
    if seconds <= 300:
        return 12
    return min(16, max(10, seconds // 20))


def _normalize_narration_text(narration):
    if narration is None:
        return ""
    if isinstance(narration, (list, tuple)):
        return " ".join(str(part).strip() for part in narration if part).strip()
    return str(narration).strip()


def _split_narration_into_chunks(narration: str, count: int):
    if not narration or count <= 0:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", narration.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return []
    if count >= len(sentences):
        # assign one sentence per scene, combine remaining sentences in last chunk
        chunks = sentences[:]
        while len(chunks) < count:
            chunks.append("")
        return chunks[:count]

    chunks = []
    total = len(sentences)
    for idx in range(count):
        start = round(idx * total / count)
        end = round((idx + 1) * total / count)
        if start == end:
            end = min(start + 1, total)
        segment = " ".join(sentences[start:end]).strip()
        chunks.append(segment)
    # ensure we have count chunks
    if len(chunks) < count:
        chunks.extend([""] * (count - len(chunks)))
    return chunks[:count]

load_dotenv()
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
# File uploads land in backend/outputs/uploads for easy cleanup.
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "outputs", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
OUTPUT_BASE = Path(os.path.dirname(__file__)) / "outputs"


@app.after_request
def apply_cors_headers(response):
    """Attach permissive CORS headers to every response."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return response


@app.route("/", methods=["GET"])
def healthcheck():
    """Simple health endpoint so platform monitors see a 200 OK."""
    return jsonify({"status": "ok"}), 200


def _coerce_positive_int(value, default=1):
    try:
        cast = int(value)
        if cast <= 0:
            return default
        return cast
    except (TypeError, ValueError):
        return default
# ----------------------------

# OpenAI api narration Route---------------------

@app.route("/narration", methods=["POST"])
def narration():
    data = request.get_json()
    prompt = data.get("prompt", "")
    if not prompt.strip():
        return jsonify({"error": "Prompt is required"}), 400

    result = generate_narration(prompt)
    return jsonify(result)


# Pexels Route---------------------

@app.route('/api/media', methods=['POST'])
def api_media():
    """
    POST /api/media
    body: { keywords: ["one", "two"], format: "landscape"|"portrait", per_page: 3 }
    returns: { results: [ { keyword: "one", candidates: [ ... ] }, ... ] }
    """
    data = request.get_json(silent=True) or {}
    keywords = data.get("keywords") or []
    orientation = data.get("format", "landscape")
    per_page = _coerce_positive_int(data.get("per_page"), default=3)

    if not isinstance(keywords, list) or len(keywords) == 0:
        return jsonify({"error": "keywords must be a non-empty array"}), 400

    results = []
    for kw in keywords:
        try:
            candidates = search_pexels(str(kw), orientation, per_page=per_page)
        except Exception as e:
            candidates = []
            print("search_pexels error for", kw, e)
        results.append({
            "keyword": kw,
            "candidates": candidates
        })

    return jsonify({"results": results})


@app.route('/api/media/search', methods=['POST'])
def api_media_search():
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    orientation = data.get("format", "landscape")
    page = _coerce_positive_int(data.get("page"), default=1)
    per_page = _coerce_positive_int(data.get("per_page"), default=6)

    if not query:
        return jsonify({"error": "query is required"}), 400

    try:
        videos = search_pexels(query, orientation=orientation, per_page=per_page, page=page)
    except Exception as exc:
        print("api_media_search error:", exc)
        return jsonify({"results": [], "query": query, "page": page})

    return jsonify({"results": videos, "query": query, "page": page})


def _build_search_terms(scene_text: str, keywords):
    terms = []
    normalized_text = " ".join((scene_text or "").split())
    if normalized_text:
        terms.append(" ".join(normalized_text.split()[:6]))

    for kw in keywords or []:
        if isinstance(kw, str):
            cleaned = kw.strip()
            if cleaned:
                terms.append(cleaned)

    return list(dict.fromkeys(filter(None, terms)))  # preserve order/deduplicate


@app.route('/api/media/suggest', methods=['POST'])
def api_media_suggest():
    data = request.get_json(silent=True) or {}
    scene_text = data.get("sceneText") or ""
    keywords = data.get("keywords") or []
    orientation = data.get("format", "landscape")
    page = _coerce_positive_int(data.get("page"), default=1)
    per_keyword = _coerce_positive_int(data.get("per_page"), default=3)

    if not keywords:
        keywords = extract_keywords(scene_text, limit=4)

    search_terms = _build_search_terms(scene_text, keywords)
    if not search_terms:
        return jsonify({"results": [], "keywords": keywords, "page": page})

    results = []
    seen = set()
    for term in search_terms:
        try:
            clips = search_pexels(term, orientation=orientation, per_page=per_keyword, page=page)
        except Exception as exc:
            print("api_media_suggest search error:", term, exc)
            clips = []

        for clip in clips:
            key = (clip.get("id"), clip.get("url"))
            if key in seen:
                continue
            seen.add(key)
            clip_with_term = dict(clip)
            clip_with_term["keyword"] = term
            results.append(clip_with_term)

    return jsonify({"results": results, "keywords": search_terms, "page": page})


@app.route('/api/media/upload', methods=['POST'])
def api_media_upload():
    if "file" not in request.files:
        return jsonify({"error": "file field is required"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "filename must not be empty"}), 400

    filename = secure_filename(file.filename)
    if not filename:
        return jsonify({"error": "invalid filename"}), 400

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    saved_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)

    try:
        file.save(saved_path)
    except Exception as exc:
        print("api_media_upload save error:", exc)
        return jsonify({"error": "failed to store file"}), 500

    media_item = {
        "id": unique_name,
        "url": f"/uploads/{unique_name}",
        "previewUrl": f"/uploads/{unique_name}",
        "pageUrl": f"/uploads/{unique_name}",
        "thumbnail": None,
        "duration": None,
        "source": "upload",
        "attribution": {"name": "Uploaded Clip"},
    }
    return jsonify({"mediaItem": media_item})


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    if not os.path.exists(app.config["UPLOAD_FOLDER"]):
        return jsonify({"error": "uploads directory missing"}), 404
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route('/videos/<project_id>/<path:filename>')
def serve_rendered_video(project_id, filename):
    project_dir = OUTPUT_BASE / "renders" / project_id
    file_path = project_dir / filename
    if not file_path.exists():
        return jsonify({"error": "video not found"}), 404
    return send_from_directory(str(project_dir), filename)


@app.route('/api/project/generate', methods=['POST', 'OPTIONS'])
def api_project_generate():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response, 204
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    orientation = _map_aspect_to_orientation(data.get("format") or "landscape")
    requested_project_id = data.get("projectId")
    voice_model = (data.get("voiceModel") or "Lady Holiday").strip() or "Lady Holiday"
    try:
        duration_seconds = int(data.get("durationSeconds") or data.get("duration") or 60)
    except (TypeError, ValueError):
        duration_seconds = 60
    duration_seconds = max(30, min(duration_seconds, 600))
    scene_hint = _scene_hint_for_duration(duration_seconds)

    if not prompt:
        return jsonify({"error": "prompt is required"}), 400

    storyboard = generate_storyboard(
        prompt,
        orientation,
        voice_model=voice_model,
        target_seconds=duration_seconds,
        scene_hint=scene_hint,
    )
    if storyboard.get("error"):
        return jsonify({"error": storyboard["error"]}), 500

    project_id = requested_project_id or uuid.uuid4().hex
    title = storyboard.get("title") or "Untitled Project"
    narration = _normalize_narration_text(storyboard.get("narration"))
    scenes = storyboard.get("scenes") or []
    voice_model = storyboard.get("voiceModel") or voice_model
    duration_seconds = int(storyboard.get("durationSeconds") or duration_seconds)
    narration_chunks = _split_narration_into_chunks(narration, len(scenes)) if scenes else []

    prepared_scenes = []
    all_keywords = []
    total_estimated_runtime = 0.0
    max_scene_duration = max(
        18,
        min(45, int(duration_seconds / max(len(scenes), 1)) + 10)
    )
    for index, scene in enumerate(scenes):
        text = (scene.get("text") or "").strip()
        keywords = scene.get("keywords") or extract_keywords(text, limit=3)
        # ensure keywords unique order preserved
        deduped_keywords = list(dict.fromkeys([kw for kw in keywords if isinstance(kw, str) and kw.strip()]))
        if not deduped_keywords and text:
            deduped_keywords = extract_keywords(text, limit=3)

        media = None
        for kw in deduped_keywords:
            try:
                clips = search_pexels(kw, orientation=orientation, per_page=3)
            except Exception as exc:
                print("generate project search error:", kw, exc)
                clips = []
            if clips:
                media = dict(clips[0])
                media["keyword"] = kw
                break

        script_text = narration_chunks[index] if index < len(narration_chunks) else ""
        visual_text = scene.get("text") or text
        final_script = script_text or text
        estimated_duration = estimate_tts_duration(final_script, voice_model)
        total_estimated_runtime += estimated_duration
        scene_duration = max(3, min(int(round(estimated_duration)), max_scene_duration))

        prepared_scenes.append({
            "text": final_script,
            "duration": scene_duration,
            "audioDuration": round(estimated_duration, 2),
            "ttsVoice": scene.get("ttsVoice") or voice_model,
            "keywords": deduped_keywords,
            "media": media,
            "order": index,
            "visual": visual_text,
            "script": final_script,
        })
        all_keywords.extend(deduped_keywords)

    payload = {
        "project": {
            "id": project_id,
            "prompt": prompt,
            "title": title,
            "format": orientation,
            "narration": narration,
            "keywords": list(dict.fromkeys(all_keywords)),
            "scenes": prepared_scenes,
            "voiceModel": voice_model,
            "durationSeconds": duration_seconds,
            "runtimeSeconds": round(total_estimated_runtime, 2) if total_estimated_runtime else duration_seconds,
        }
    }
    return jsonify(payload)


@app.route('/api/project/render', methods=['POST', 'OPTIONS'])
def api_project_render():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response, 204

    payload = request.get_json(silent=True) or {}
    project = payload.get("project") if isinstance(payload.get("project"), dict) else payload
    if not project.get("scenes"):
        return jsonify({"error": "project scenes are required"}), 400

    orchestrator = get_orchestrator(OUTPUT_BASE)
    job = orchestrator.submit(project)
    return jsonify(job), 202


@app.route('/api/project/render/<job_id>', methods=['GET', 'OPTIONS'])
def api_project_render_status(job_id):
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response, 204
    orchestrator = get_orchestrator(OUTPUT_BASE)
    project_hint = request.args.get("projectId")

    job = orchestrator.get(job_id)
    if not job and project_hint:
        job = orchestrator.get_by_project(project_hint)
    if not job:
        job = orchestrator.get_by_project(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
