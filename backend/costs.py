"""Cost estimation helpers built on top of the model registry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from model_registry import ModelInfo, get_model
from tts import synthesize_tts  # ✅ updated import

# Voice model hints so we can map friendly names to registry IDs.
VOICE_MODEL_REGISTRY_MAP: Dict[str, str] = {
    "lady holiday": "openai-mini-tts",
    "golden narrator": "openai-mini-tts",
    "calm documentary": "openai-mini-tts",
    "energetic host": "openai-mini-tts",
    "warm storyteller": "openai-mini-tts",
}

DEFAULT_TTS_MODEL_ID = "openai-mini-tts"
DEFAULT_VIDEO_MODEL_ID = "render-stock"


@dataclass
class CostBreakdown:
    total_platform_tokens: int
    tts_tokens: int
    video_tokens: int
    tts_seconds: float
    video_seconds: float
    models: Dict[str, ModelInfo]

    def as_dict(self) -> Dict[str, object]:
        # Always return numbers, never None, to avoid frontend UI breakage
        return {
            "totalTokens": int(self.total_platform_tokens or 0),
            "ttsTokens": int(self.tts_tokens or 0),
            "videoTokens": int(self.video_tokens or 0),
            "ttsSeconds": round(float(self.tts_seconds or 0), 2),
            "videoSeconds": round(float(self.video_seconds or 0), 2),
            "models": {
                key: {
                    "id": getattr(model, "id", None),
                    "provider": getattr(model, "provider", None),
                    "category": getattr(model, "category", None),
                    "humanName": getattr(model, "human_name", None),
                    "costMultiplier": getattr(model, "cost_multiplier", None),
                }
                for key, model in (self.models or {}).items()
            },
        }


def _resolve_tts_model_id(voice_model: Optional[str]) -> str:
    if not voice_model:
        return DEFAULT_TTS_MODEL_ID
    key = voice_model.strip().lower()
    return VOICE_MODEL_REGISTRY_MAP.get(key, DEFAULT_TTS_MODEL_ID)


def _normalise_scene_duration(scene: Dict[str, object]) -> float:
    duration = scene.get("audioDuration") or scene.get("duration")
    try:
        duration_value = float(duration)
        if duration_value > 0:
            return duration_value
    except (TypeError, ValueError):
        pass

    script = scene.get("script") or scene.get("text") or ""
    voice_model = scene.get("ttsVoice")

    # ✅ Use Gemini TTS synthesis for accurate duration
    tts_info = synthesize_tts(str(script), str(voice_model) if voice_model else None)
    return float(tts_info.get("duration", 0.0))


def _iter_scene_durations(scenes: Iterable[Dict[str, object]]) -> Iterable[float]:
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        yield _normalise_scene_duration(scene)


def estimate_render_platform_tokens(project: Dict[str, object]) -> CostBreakdown:
    """Estimate platform token burn for a render job.

    The helper looks at the scripted duration for TTS and the total runtime for the
    video render. Each model's cost multiplier is sourced from the registry so the
    frontend can display a trustworthy preview before the user spends tokens.
    """

    scenes = project.get("scenes") if isinstance(project.get("scenes"), list) else []
    voice_model = project.get("voiceModel")

    total_scene_seconds = sum(_iter_scene_durations(scenes))
    total_scene_seconds = max(total_scene_seconds, 0.0)

    tts_model_id = _resolve_tts_model_id(str(voice_model) if voice_model else None)
    video_model_id = project.get("videoModel") or DEFAULT_VIDEO_MODEL_ID

    tts_model = get_model(tts_model_id)
    video_model = get_model(video_model_id)

    tts_minutes = total_scene_seconds / 60.0
    tts_tokens = int(math.ceil(tts_minutes * tts_model.cost_multiplier)) if tts_minutes > 0 else 0

    # Use declared runtime if present; otherwise fall back to scene durations.
    runtime_seconds = project.get("durationSeconds") or project.get("runtimeSeconds")
    try:
        runtime_seconds_value = float(runtime_seconds)
        if runtime_seconds_value <= 0:
            runtime_seconds_value = total_scene_seconds
    except (TypeError, ValueError):
        runtime_seconds_value = total_scene_seconds

    runtime_seconds_value = max(runtime_seconds_value, 0.0)
    video_tokens = int(math.ceil(runtime_seconds_value * video_model.cost_multiplier)) if runtime_seconds_value > 0 else 0

    total_tokens = tts_tokens + video_tokens

    return CostBreakdown(
        total_platform_tokens=total_tokens,
        tts_tokens=tts_tokens,
        video_tokens=video_tokens,
        tts_seconds=total_scene_seconds,
        video_seconds=runtime_seconds_value,
        models={
            "tts": tts_model,
            "video": video_model,
        },
    )


__all__ = [
    "CostBreakdown",
    "estimate_render_platform_tokens",
]