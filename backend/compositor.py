"""FFmpeg-based video rendering helpers."""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

from captions import DEFAULT_CAPTION_STYLE, generate_ass_subtitles

TARGET_RESOLUTIONS = {
    "portrait": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}


class RenderError(RuntimeError):
    """Raised when ffmpeg returns a non-zero exit code."""


class RenderCancelled(RuntimeError):
    """Raised when rendering is cancelled mid-process."""


logger = logging.getLogger(__name__)


def run_ffmpeg(args: List[str]) -> None:
    """Run ffmpeg with the given argument list, raising on failure."""

    process = subprocess.run(
        ["ffmpeg", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise RenderError(process.stderr.strip() or "ffmpeg failed")


def probe_duration(path: Path) -> Optional[float]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def ensure_local_clip(url: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    ext = os.path.splitext(url.split("?")[0])[1] or ".mp4"
    path = cache_dir / f"{key}{ext}"
    if path.exists():
        return path

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    path.write_bytes(resp.content)
    return path


def _build_scene_video(
    media_path: Optional[Path],
    audio_path: Path,
    duration: float,
    orientation: str,
    dest_path: Path,
) -> None:
    width, height = TARGET_RESOLUTIONS.get(orientation, TARGET_RESOLUTIONS["landscape"])
    duration_str = f"{max(duration, 0.1):.3f}"

    vf_filters = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )

    encode_tail = [
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-ar",
        "24000",
        "-ac",
        "1",
        "-shortest",
        str(dest_path),
    ]

    if media_path and media_path.exists():
        filters = vf_filters
        source_duration = probe_duration(media_path)
        if source_duration is not None and source_duration < duration:
            pad = duration - source_duration
            filters = filters + f",tpad=stop_mode=clone:stop_duration={pad:.3f}"

        args = [
            "-y",
            "-t",
            duration_str,
            "-i",
            str(media_path),
            "-i",
            str(audio_path),
            "-vf",
            filters,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
        ] + encode_tail
        run_ffmpeg(args)
    else:
        color = "0x141414"
        color_video = [
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={width}x{height}:d={duration_str}",
        ]
        args = [
            "-y",
            "-i",
            str(audio_path),
            *color_video,
            "-map",
            "1:v:0",
            "-map",
            "0:a:0",
            "-vf",
            vf_filters,
        ] + encode_tail
        run_ffmpeg(args)


def _escape_subtitle_path(path: Path) -> str:
    escaped = path.as_posix().replace("\\", "\\\\")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("'", r"\'")
    escaped = escaped.replace(",", "\\,")
    return escaped


def _burn_subtitles(video_path: Path, subtitle_path: Path, output_path: Path) -> None:
    filter_arg = f"subtitles='{_escape_subtitle_path(subtitle_path)}'"
    run_ffmpeg(
        [
            "-y",
            "-i",
            str(video_path),
            "-vf",
            filter_arg,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )


def render_project(
    project_id: str,
    scenes: List[Dict],
    orientation: str,
    output_dir: Path,
    cache_dir: Path,
    cancel_checker: Optional[Callable[[], bool]] = None,
    caption_style: Optional[str] = None,
) -> Path:
    """Render the final video by normalising scenes then concatenating."""

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(tempfile.mkdtemp(prefix=f"render_{project_id}_", dir=output_dir))

    scene_paths: List[Path] = []
    timeline_scenes: List[Dict] = []
    target_resolution = TARGET_RESOLUTIONS.get(orientation, TARGET_RESOLUTIONS["landscape"])
    selected_style = caption_style or DEFAULT_CAPTION_STYLE
    try:
        for idx, scene in enumerate(scenes):
            if cancel_checker and cancel_checker():
                raise RenderCancelled("Render cancelled before processing scene")
            duration_value = scene.get("audioDuration") or scene.get("duration") or 3.0
            try:
                duration = float(duration_value)
            except (TypeError, ValueError):
                duration = 3.0
            duration = max(duration, 0.1)
            audio_path = Path(scene.get("audioPath"))
            if not audio_path.exists():
                raise RenderError(f"Audio track missing for scene {scene.get('id')}")

            media_url = (scene.get("media") or {}).get("url")
            media_path = None
            if media_url:
                try:
                    media_path = ensure_local_clip(media_url, cache_dir)
                except requests.RequestException as exc:
                    raise RenderError(f"Media download failed for {media_url}") from exc

            dest = temp_dir / f"scene_{idx:03d}.mp4"
            _build_scene_video(media_path, audio_path, duration, orientation, dest)

            scene_paths.append(dest)
            timeline_scenes.append(
                {
                    "id": scene.get("id"),
                    "order": scene.get("order"),
                    "captions": scene.get("captions"),
                    "script": scene.get("script"),
                    "text": scene.get("text"),
                    "audioDuration": round(duration, 3),
                    "duration": round(duration, 3),
                }
            )
            if cancel_checker and cancel_checker():
                raise RenderCancelled("Render cancelled during scene assembly")

        if not scene_paths:
            raise RenderError("No scene clips were generated")

        subtitle_file = generate_ass_subtitles(
            project_id,
            timeline_scenes,
            selected_style,
            resolution=target_resolution,
        )

        list_file = temp_dir / "concat.txt"
        with list_file.open("w", encoding="utf-8") as fh:
            for path in scene_paths:
                fh.write(f"file '{path.as_posix()}'\n")

        concat_path = temp_dir / f"{project_id}_concat.mp4"

        if cancel_checker and cancel_checker():
            raise RenderCancelled("Render cancelled before final assembly")
        run_ffmpeg(
            [
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(concat_path),
            ]
        )

        if cancel_checker and cancel_checker():
            raise RenderCancelled("Render cancelled before subtitle burn-in")

        final_path = output_dir / f"{project_id}_final.mp4"
        if subtitle_file and subtitle_file.exists() and subtitle_file.stat().st_size > 0:
            logger.info(
                "Burning subtitles for project %s using style %s", project_id, selected_style
            )
            logger.debug("Subtitle source: %s", subtitle_file)
            _burn_subtitles(concat_path, subtitle_file, final_path)
        else:
            if subtitle_file and subtitle_file.exists() and subtitle_file.stat().st_size == 0:
                logger.warning("Subtitle file %s was empty; skipping burn-in", subtitle_file)
            elif subtitle_file is None:
                logger.info("No subtitles generated for project %s", project_id)
            if final_path.exists():
                final_path.unlink()
            concat_path.replace(final_path)

        return final_path
    finally:
        # No explicit cleanup of temp_dir to assist with debugging; callers
        # may remove it later if desired.
        pass
