"""Simple background render queue for project videos."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Optional

from compositor import render_project
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
        self.logger.debug("render_get job=%s", job_id)
        with self.lock:
            job = self.jobs.get(job_id)
        if job:
            self.logger.debug("render_get hit_memory job=%s status=%s", job_id, job.get("status"))
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
            self.logger.info(
                "render_get restored job=%s project=%s status=%s",
                job_id,
                project_id,
                job.get("status"),
            )
            return job
        self.logger.warning("render_get miss job=%s", job_id)
        return None

    # ------------------------------------------------------------------

    def _run_render(self, job_id: str, project_payload: Dict) -> None:
        self._update(job_id, status="rendering", progress=5)

        try:
            scenes = project_payload.get("scenes") or []
            orientation = project_payload.get("format", "landscape")
            voice_model = project_payload.get("voiceModel")
            project_id = project_payload.get("id") or uuid.uuid4().hex
            self.logger.info(
                "render_run_start job=%s project=%s scenes=%s",
                job_id,
                project_id,
                len(scenes),
            )

            prepared_scenes = []
            for scene in scenes:
                script_text = scene.get("script") or scene.get("text") or ""
                audio_path, audio_duration = ensure_tts_audio(
                    script_text,
                    scene.get("ttsVoice") or voice_model,
                    self.audio_cache,
                )
                prepared_scenes.append({
                    **scene,
                    "audioPath": str(audio_path),
                    "audioDuration": round(audio_duration, 2),
                })

            output_dir = self.render_dir / project_id
            cache_dir = self.video_cache

            final_path = render_project(
                project_id=project_id,
                scenes=prepared_scenes,
                orientation=orientation,
                output_dir=output_dir,
                cache_dir=cache_dir,
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
            self.logger.info(
                "render_run_complete job=%s project=%s",
                job_id,
                project_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.logger.exception(
                "render_run_error job=%s project=%s error=%s",
                job_id,
                project_payload.get("id"),
                exc,
            )
            self._update(job_id, status="failed", progress=100, error=str(exc))

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
            self.logger.debug(
                "render_update job=%s project=%s updates=%s",
                job_id,
                project_id,
                list(updates.keys()),
            )

    def _persist_job(self, job: Dict, sync_remote: bool = True) -> None:
        job_path = self._job_path(job["id"])
        job_path.parent.mkdir(parents=True, exist_ok=True)
        job_path.write_text(json.dumps(job), encoding="utf-8")
        if sync_remote:
            persist_job_metadata(job)

    def _job_path(self, job_id: str) -> Path:
        return self.render_dir / f"{job_id}.json"

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
