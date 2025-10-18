"""Simple background render queue for project videos."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Optional

from compositor import RenderCancelled, render_project
from captions import generate_word_timestamps
from storage import (
    fetch_job_metadata,
    fetch_project_index,
    persist_job_metadata,
    persist_project_index,
    upload_render_output,
)
from tts import ensure_tts_audio


class RenderOrchestrator:
    def __init__(self, base_output: Path):
        self.base_output = Path(base_output)
        self.render_dir = self.base_output / "renders"
        self.audio_cache = self.base_output / "cache" / "audio"
        self.video_cache = self.base_output / "cache" / "video"
        self.project_index_path = self.render_dir / "_project_index.json"
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self.audio_cache.mkdir(parents=True, exist_ok=True)
        self.video_cache.mkdir(parents=True, exist_ok=True)

        self.executor = ThreadPoolExecutor(max_workers=1)
        self.jobs: Dict[str, Dict] = {}
        self.project_jobs: Dict[str, str] = self._load_index()
        self.cancel_flags: Dict[str, threading.Event] = {}
        self.cancel_targets: Dict[str, str] = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    def submit(self, project_payload: Dict) -> Dict:
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "status": "queued",
            "projectId": project_payload.get("id"),
            "progress": 0,
            "videoUrl": None,
            "error": None,
        }
        with self.lock:
            self.jobs[job_id] = job
            project_id = project_payload.get("id")
            if project_id:
                self.project_jobs[str(project_id)] = job_id
                self._persist_index_locked()
            self._persist_job(job)

        self.logger.info(
            "render_submit job=%s project=%s sceneCount=%s",
            job_id,
            project_payload.get("id"),
            len(project_payload.get("scenes") or []),
        )
        future = self.executor.submit(self._run_render, job_id, project_payload)
        future.add_done_callback(lambda _f: None)
        return job

    def get(self, job_id: str) -> Optional[Dict]:
        with self.lock:
            job = self.jobs.get(job_id)
        if job:
            return job

        job_path = self._job_path(job_id)
        job = None
        if job_path.exists():
            try:
                job = json.loads(job_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                job = None
        if not job:
            job = fetch_job_metadata(job_id)
        if job and isinstance(job, dict):
            with self.lock:
                self.jobs[job_id] = job
                project_id = job.get("projectId")
                if project_id:
                    self.project_jobs[str(project_id)] = job_id
                    self._persist_index_locked()
            self._persist_job(job, sync_remote=False)
            return job
        return None

    def request_stop(self, job_id: str, final_status: str) -> Optional[Dict]:
        if final_status not in {"cancelled", "paused"}:
            raise ValueError(f"Unsupported stop status: {final_status}")

        with self.lock:
            job = self.jobs.get(job_id)
        if not job:
            job = self.get(job_id)
        if not job:
            return None

        with self.lock:
            current_status = job.get("status")
            if current_status in {"completed", "failed", "cancelled", "paused"}:
                return job

            flag = self.cancel_flags.get(job_id)
            if not flag:
                flag = threading.Event()
                self.cancel_flags[job_id] = flag
            self.cancel_targets[job_id] = final_status
            flag.set()

            interim_status = "cancelling" if final_status == "cancelled" else "pausing"
            job["status"] = interim_status
            self.jobs[job_id] = job
            self._persist_job(job)
            return job

    # ------------------------------------------------------------------

    def _process_scene(self, job_id: str, scene: Dict, voice_model: Optional[str]) -> Dict:
        if self._is_cancelled(job_id):
            return None
        script_text = scene.get("script") or scene.get("text") or ""
        audio_path, audio_duration = ensure_tts_audio(
            script_text,
            scene.get("ttsVoice") or voice_model,
            self.audio_cache,
        )
        audio_path = Path(audio_path)
        if audio_path.suffix.lower() != ".wav":
            audio_path = audio_path.with_suffix(".wav")
        updated_scene = {
            **scene,
            "audioPath": str(audio_path),
            "audioDuration": round(audio_duration, 2),
        }
        # 🧠 Generate word-level timestamps using Whisper
        try:
            captions = generate_word_timestamps(audio_path, script_text)
            updated_scene["captions"] = captions
        except Exception as e:
            self.logger.warning(f"⚠️ Caption generation failed for scene: {e}")
            updated_scene["captions"] = []
        return updated_scene

    def _run_render(self, job_id: str, project_payload: Dict) -> None:
        if self._is_cancelled(job_id):
            final_status = self._cancel_target(job_id)
            self._update(job_id, status=final_status)
            self._clear_cancel(job_id)
            return

        self._update(job_id, status="rendering", progress=5)

        try:
            scenes = project_payload.get("scenes") or []
            orientation = project_payload.get("format", "landscape")
            voice_model = project_payload.get("voiceModel")
            project_id = project_payload.get("id") or uuid.uuid4().hex
            caption_style = project_payload.get("captionStyle")
            if not caption_style:
                metadata = project_payload.get("metadata")
                captions_meta = None
                if isinstance(metadata, dict):
                    captions_meta = metadata.get("captions")
                if isinstance(captions_meta, dict):
                    caption_style = captions_meta.get("style") or captions_meta.get("template")

            prepared_scenes = []
            max_workers = min(4, len(scenes)) if scenes else 1
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for idx, scene in enumerate(scenes):
                    scene_payload = {**scene, "_original_index": idx}
                    futures[executor.submit(self._process_scene, job_id, scene_payload, voice_model)] = scene_payload
                for future in as_completed(futures):
                    if self._is_cancelled(job_id):
                        final_status = self._cancel_target(job_id)
                        self._update(job_id, status=final_status)
                        self._clear_cancel(job_id)
                        return
                    result = future.result()
                    if result is not None:
                        prepared_scenes.append(result)

            def _scene_sort_key(item: Dict) -> tuple:
                order_value = item.get("order")
                numeric_order = None
                if isinstance(order_value, (int, float)):
                    numeric_order = float(order_value)
                else:
                    try:
                        numeric_order = float(order_value)
                    except (TypeError, ValueError):
                        numeric_order = None
                fallback_index = item.get("_original_index", 0)
                key_value = numeric_order if numeric_order is not None else fallback_index
                return (key_value, fallback_index)

            prepared_scenes = sorted(prepared_scenes, key=_scene_sort_key)
            scene_order_log = [
                item.get("order") if item.get("order") is not None else item.get("_original_index")
                for item in prepared_scenes
            ]
            self.logger.info("🧩 Scene order before merge: %s", scene_order_log)

            output_dir = self.render_dir / project_id
            cache_dir = self.video_cache

            if self._is_cancelled(job_id):
                final_status = self._cancel_target(job_id)
                self._update(job_id, status=final_status)
                self._clear_cancel(job_id)
                return

            try:
                final_path = render_project(
                    project_id=project_id,
                    scenes=prepared_scenes,
                    orientation=orientation,
                    output_dir=output_dir,
                    cache_dir=cache_dir,
                    cancel_checker=lambda: self._is_cancelled(job_id),
                    caption_style=caption_style,
                )
            except RenderCancelled:
                final_status = self._cancel_target(job_id)
                self._update(job_id, status=final_status)
                self._clear_cancel(job_id)
                return
            if self._is_cancelled(job_id):
                final_status = self._cancel_target(job_id)
                self._update(job_id, status=final_status)
                self._clear_cancel(job_id)
                return
            self.logger.info(
                "render_project_complete job=%s project=%s output=%s",
                job_id,
                project_id,
                final_path,
            )

            uploaded_url = upload_render_output(final_path, project_id)
            if uploaded_url:
                relative_url = uploaded_url
                self.logger.info(
                    "render_uploaded job=%s project=%s url=%s",
                    job_id,
                    project_id,
                    uploaded_url,
                )
            else:
                relative_url = f"/videos/{project_id}/{final_path.name}?v={uuid.uuid4().hex[:6]}"
                self.logger.info(
                    "render_local_output job=%s project=%s file=%s",
                    job_id,
                    project_id,
                    final_path,
                )
            self._update(
                job_id,
                status="completed",
                progress=100,
                videoUrl=relative_url,
                projectId=project_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.exception(
                "render_run_error job=%s project=%s error=%s",
                job_id,
                project_payload.get("id"),
                exc,
            )
            self._update(job_id, status="failed", progress=100, error=str(exc))
        finally:
            self._clear_cancel(job_id)

    def _update(self, job_id: str, **updates) -> None:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                job_path = self._job_path(job_id)
                if job_path.exists():
                    try:
                        job = json.loads(job_path.read_text(encoding="utf-8"))
                    except json.JSONDecodeError:
                        job = None
            if not job:
                return
            self.jobs[job_id] = job
            job.update(updates)
            project_id = job.get("projectId")
            if project_id:
                self.project_jobs[str(project_id)] = job["id"]
                self._persist_index_locked()
            self._persist_job(job)

    def _persist_job(self, job: Dict, sync_remote: bool = True) -> None:
        job_path = self._job_path(job["id"])
        job_path.parent.mkdir(parents=True, exist_ok=True)
        job_path.write_text(json.dumps(job), encoding="utf-8")
        if sync_remote:
            persist_job_metadata(job)

    def _job_path(self, job_id: str) -> Path:
        return self.render_dir / f"{job_id}.json"

    def _is_cancelled(self, job_id: str) -> bool:
        flag = self.cancel_flags.get(job_id)
        return flag.is_set() if flag else False

    def _cancel_target(self, job_id: str) -> str:
        return self.cancel_targets.get(job_id, "cancelled")

    def _clear_cancel(self, job_id: str) -> None:
        flag = self.cancel_flags.pop(job_id, None)
        if flag:
            flag.clear()
        self.cancel_targets.pop(job_id, None)

    def _load_index(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        if self.project_index_path.exists():
            try:
                data = json.loads(self.project_index_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    mapping.update({str(k): str(v) for k, v in data.items() if isinstance(v, str)})
            except json.JSONDecodeError:
                pass
        remote_index = fetch_project_index()
        mapping.update(remote_index)
        return mapping

    def _persist_index_locked(self) -> None:
        self.project_index_path.parent.mkdir(parents=True, exist_ok=True)
        self.project_index_path.write_text(json.dumps(self.project_jobs), encoding="utf-8")
        persist_project_index(self.project_jobs)

    def get_by_project(self, project_id: str) -> Optional[Dict]:
        if not project_id:
            return None
        project_id = str(project_id)
        self.logger.debug("render_get_by_project project=%s", project_id)

        with self.lock:
            job_id = self.project_jobs.get(project_id)
        if job_id:
            job = self.get(job_id)
            if job:
                self.logger.debug(
                    "render_get_by_project direct_hit project=%s job=%s status=%s",
                    project_id,
                    job_id,
                    job.get("status"),
                )
                return job

        for job_path in self.render_dir.glob("*.json"):
            name = job_path.name
            if not name.endswith(".json") or name.startswith("_"):
                continue
            try:
                job_data = json.loads(job_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if job_data.get("projectId") == project_id and job_data.get("id"):
                with self.lock:
                    self.jobs[job_data["id"]] = job_data
                    self.project_jobs[project_id] = job_data["id"]
                    self._persist_index_locked()
                self.logger.info(
                    "render_get_by_project hydrated_from_disk project=%s job=%s",
                    project_id,
                    job_data.get("id"),
                )
                return job_data
        remote_job_id = self.project_jobs.get(project_id)
        if remote_job_id:
            job_data = fetch_job_metadata(remote_job_id)
            if job_data:
                with self.lock:
                    self.jobs[job_data["id"]] = job_data
                    self.project_jobs[project_id] = job_data["id"]
                    self._persist_index_locked()
                self._persist_job(job_data, sync_remote=False)
                self.logger.info(
                    "render_get_by_project hydrated_remote project=%s job=%s",
                    project_id,
                    job_data.get("id"),
                )
                return job_data
        self.logger.warning("render_get_by_project miss project=%s", project_id)
        return None


_orchestrator: Optional[RenderOrchestrator] = None


def get_orchestrator(base_output: Path) -> RenderOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = RenderOrchestrator(base_output)
    return _orchestrator
