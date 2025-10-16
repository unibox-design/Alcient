# backend/app.py
import math
import os
import re
import uuid
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from database import adjust_tokens, get_session, get_or_create_user, init_db, log_usage
from llm import enrich_scene_metadata, generate_narration, generate_storyboard
from model_registry import get_model
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

# Initialise database (idempotent)
init_db()

DEFAULT_USER_EMAIL = os.getenv("DEFAULT_USER_EMAIL", "demo@alcient.local")


@contextmanager
def _user_session():
    email = (
        request.headers.get("X-User-Email")
        or request.args.get("userEmail")
        or DEFAULT_USER_EMAIL
    )
    session = get_session()
    try:
        user = get_or_create_user(session, email=email, default_plan_id="starter")
        yield session, user
    finally:
        session.close()


def _attach_usage_headers(response, user):
    response.headers["X-Tokens-Balance"] = str(user.tokens_balance)
    if user.plan_id:
        response.headers["X-Plan-Id"] = user.plan_id
    return response


def _log_usage_entry(session, user, action_type, usage_info, extra_payload=None):
    if not usage_info:
        return None
    usage_data = usage_info.get("usage") or {}
    tokens_input = (
        usage_data.get("prompt_tokens")
        or usage_data.get("input_tokens")
        or 0
    )
    tokens_output = (
        usage_data.get("completion_tokens")
        or usage_data.get("output_tokens")
        or 0
    )
    tokens_total = usage_data.get("total_tokens")
    if not tokens_input and not tokens_output and tokens_total:
        tokens_input = tokens_total

    payload = dict(extra_payload or {})
    for key, value in usage_data.items():
        payload.setdefault(key, value)

    entry = log_usage(
        session,
        user=user,
        action_type=action_type,
        provider=usage_info.get("provider", "unknown"),
        model=usage_info.get("model", "unknown"),
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        payload=payload,
    )
    session.refresh(user)
    return entry


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
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "")
    if not prompt.strip():
        return jsonify({"error": "Prompt is required"}), 400

    with _user_session() as (session, user):
        result = generate_narration(prompt)
        usage_info = result.pop("_usage", None)
        if result.get("error"):
            response = jsonify(result)
            return _attach_usage_headers(response, user), 500

        model_info = get_model("openai-gpt4o-mini")
        usage_entry = _log_usage_entry(
            session,
            user,
            "narration.generate",
            usage_info,
            extra_payload={
                "prompt_length": len(prompt or ""),
                "model_id": model_info.id,
            },
        )

        usage_stats = (usage_info or {}).get("usage", {})
        total_tokens = usage_stats.get("total_tokens")
        if total_tokens is None:
            total_tokens = (usage_stats.get("prompt_tokens", 0) + usage_stats.get("completion_tokens", 0))
        platform_tokens = math.ceil(max(total_tokens, 0) * model_info.cost_multiplier / 1000) if total_tokens else 0
        if platform_tokens:
            reference = usage_entry.id if usage_entry else "narration"
            adjust_tokens(
                session,
                user=user,
                delta=-platform_tokens,
                reason="platform:llm",
                reference=reference,
            )
            session.refresh(user)
        response = jsonify(result)
        return _attach_usage_headers(response, user)


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


@app.route('/api/scenes/enrich', methods=['POST', 'OPTIONS'])
def api_scenes_enrich():
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response, 204

    data = request.get_json(silent=True) or {}
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list):
        return jsonify({"error": "scenes array is required"}), 400

    orientation = _map_aspect_to_orientation(data.get("format") or "landscape")
    char_limit = int(os.getenv("MANUAL_SCRIPT_CHAR_LIMIT", "4000"))

    processed = []
    total_chars = 0
    for idx, scene in enumerate(raw_scenes):
        if not isinstance(scene, dict):
            continue
        text = str(scene.get("text") or "").strip()
        if not text:
            continue
        scene_id = str(scene.get("id") or idx)
        processed.append({"id": scene_id, "text": text})
        total_chars += len(text)

    if total_chars > char_limit:
        return (
            jsonify(
                {
                    "error": "Script is too long for enrichment.",
                    "limit": char_limit,
                    "length": total_chars,
                }
            ),
            400,
        )

    if not processed:
        return jsonify({"scenes": [], "source": "empty", "limit": char_limit})

    with _user_session() as (session, user):
        usage_info = None
        model_info = get_model("openai-gpt4o-mini")
        try:
            llm_result = enrich_scene_metadata(processed, orientation)
            if isinstance(llm_result, dict):
                llm_items = llm_result.get("items", [])
                usage_info = llm_result.get("_usage")
            else:
                llm_items = llm_result
            llm_map = {item["id"]: item for item in llm_items if isinstance(item, dict) and item.get("id")}
            source = "llm"
        except Exception as exc:
            app.logger.warning("scene_enrich_llm_failed error=%s", exc)
            llm_map = {}
            source = "fallback"

        response_items = []
        fallback_used = source != "llm"

        for scene in processed:
            sid = scene["id"]
            text = scene["text"]
            info = llm_map.get(sid, {})
            keywords = info.get("keywords")
            if not isinstance(keywords, list):
                keywords = []
            keywords = [str(kw).strip() for kw in keywords if isinstance(kw, str) and kw.strip()]
            if not keywords:
                keywords = extract_keywords(text, limit=4)
                fallback_used = True
            image_prompt = info.get("imagePrompt")
            if not isinstance(image_prompt, str) or not image_prompt.strip():
                image_prompt = text[:180]
                fallback_used = True
            response_items.append(
                {
                    "id": sid,
                    "keywords": keywords[:6],
                    "imagePrompt": image_prompt,
                }
            )

        if usage_info:
            usage_entry = _log_usage_entry(
                session,
                user,
                "scene.enrich",
                usage_info,
                extra_payload={
                    "scene_count": len(processed),
                    "model_id": model_info.id,
                },
            )
            usage_stats = usage_info.get("usage", {})
            total_tokens = usage_stats.get("total_tokens")
            if total_tokens is None:
                total_tokens = (usage_stats.get("prompt_tokens", 0) + usage_stats.get("completion_tokens", 0))
            platform_tokens = math.ceil(max(total_tokens, 0) * model_info.cost_multiplier / 1000) if total_tokens else 0
            if platform_tokens:
                reference = usage_entry.id if usage_entry else "scene.enrich"
                adjust_tokens(
                    session,
                    user=user,
                    delta=-platform_tokens,
                    reason="platform:llm",
                    reference=reference,
                )
                session.refresh(user)

        if source == "llm" and fallback_used:
            source = "mixed"

        response = jsonify({"scenes": response_items, "source": source, "limit": char_limit})
        return _attach_usage_headers(response, user)


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

    with _user_session() as (session, user):
        storyboard = generate_storyboard(
            prompt,
            orientation,
            voice_model=voice_model,
            target_seconds=duration_seconds,
            scene_hint=scene_hint,
        )
        usage_info = storyboard.pop("_usage", None)
        if storyboard.get("error"):
            response = jsonify({"error": storyboard["error"]})
            return _attach_usage_headers(response, user), 500

        model_info = get_model("openai-gpt4o-mini")
        usage_entry = _log_usage_entry(
            session,
            user,
            "storyboard.generate",
            usage_info,
            extra_payload={
                "prompt_length": len(prompt),
                "requested_duration_seconds": duration_seconds,
                "model_id": model_info.id,
            },
        )

        usage_stats = (usage_info or {}).get("usage", {})
        total_tokens = usage_stats.get("total_tokens")
        if total_tokens is None:
            total_tokens = (usage_stats.get("prompt_tokens", 0) + usage_stats.get("completion_tokens", 0))
        platform_tokens = math.ceil(max(total_tokens, 0) * model_info.cost_multiplier / 1000) if total_tokens else 0
        if platform_tokens:
            reference = usage_entry.id if usage_entry else "storyboard"
            adjust_tokens(
                session,
                user=user,
                delta=-platform_tokens,
                reason="platform:llm",
                reference=reference,
            )
            session.refresh(user)

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
        response = jsonify(payload)
        return _attach_usage_headers(response, user)


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

    app.logger.info(
        "render_status_request job=%s projectHint=%s", job_id, project_hint
    )

    job = orchestrator.get(job_id)
    if job:
        app.logger.info("render_status_hit via job_id status=%s", job.get("status"))
    if not job and project_hint:
        app.logger.info("render_status_miss trying project_hint")
        job = orchestrator.get_by_project(project_hint)
        if job:
            app.logger.info(
                "render_status_hit via project_hint job=%s status=%s",
                job.get("id"),
                job.get("status"),
            )
    if not job:
        app.logger.warning(
            "render_status_not_found job=%s projectHint=%s", job_id, project_hint
        )
        job = orchestrator.get_by_project(job_id)
    if not job:
        return jsonify({"error": "job not found"}), 404
    app.logger.info(
        "render_status_response job=%s status=%s videoUrl=%s",
        job.get("id"),
        job.get("status"),
        job.get("videoUrl"),
    )
    return jsonify(job)


@app.route('/api/project/render/<job_id>/cancel', methods=['POST', 'OPTIONS'])
def api_project_render_cancel(job_id):
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response, 204

    orchestrator = get_orchestrator(OUTPUT_BASE)
    job = orchestrator.request_stop(job_id, "cancelled")
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)


@app.route('/api/project/render/<job_id>/pause', methods=['POST', 'OPTIONS'])
def api_project_render_pause(job_id):
    if request.method == "OPTIONS":
        response = jsonify({})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
        return response, 204

    orchestrator = get_orchestrator(OUTPUT_BASE)
    job = orchestrator.request_stop(job_id, "paused")
    if not job:
        return jsonify({"error": "job not found"}), 404
    return jsonify(job)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
