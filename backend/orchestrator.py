"""Simple background render queue for project videos."""

from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Optional

from compositor import render_project
from tts import ensure_tts_audio


class RenderOrchestrator:
    def __init__(self, base_output: Path):
        self.base_output = Path(base_output)
        self.render_dir = self.base_output / "renders"
        self.audio_cache = self.base_output / "cache" / "audio"
        self.video_cache = self.base_output / "cache" / "video"
        self.render_dir.mkdir(parents=True, exist_ok=True)
        self.audio_cache.mkdir(parents=True, exist_ok=True)
        self.video_cache.mkdir(parents=True, exist_ok=True)

        self.executor = ThreadPoolExecutor(max_workers=1)
        self.jobs: Dict[str, Dict] = {}
        self.lock = threading.Lock()

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
            self._persist_job(job)

        future = self.executor.submit(self._run_render, job_id, project_payload)
        future.add_done_callback(lambda _f: None)
        return job

    def get(self, job_id: str) -> Optional[Dict]:
        with self.lock:
            job = self.jobs.get(job_id)
        if job:
            return job

        job_path = self._job_path(job_id)
        if job_path.exists():
            try:
                return json.loads(job_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
        return None

    # ------------------------------------------------------------------

    def _run_render(self, job_id: str, project_payload: Dict) -> None:
        self._update(job_id, status="rendering", progress=5)

        try:
            scenes = project_payload.get("scenes") or []
            orientation = project_payload.get("format", "landscape")
            voice_model = project_payload.get("voiceModel")
            project_id = project_payload.get("id") or uuid.uuid4().hex

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

            relative_url = f"/videos/{project_id}/{final_path.name}?v={uuid.uuid4().hex[:6]}"
            self._update(
                job_id,
                status="completed",
                progress=100,
                videoUrl=relative_url,
                projectId=project_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
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
            self._persist_job(job)

    def _persist_job(self, job: Dict) -> None:
        job_path = self._job_path(job["id"])
        job_path.parent.mkdir(parents=True, exist_ok=True)
        job_path.write_text(json.dumps(job), encoding="utf-8")

    def _job_path(self, job_id: str) -> Path:
        return self.render_dir / f"{job_id}.json"


_orchestrator: Optional[RenderOrchestrator] = None


def get_orchestrator(base_output: Path) -> RenderOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = RenderOrchestrator(base_output)
    return _orchestrator
