"""Central catalogue of AI providers, models, and platform token pricing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class ModelInfo:
    id: str
    provider: str
    category: str  # text | tts | image | video
    human_name: str
    cost_multiplier: float  # platform tokens per base unit (see comments below)
    metadata: Dict[str, str] = field(default_factory=dict)


# cost_multiplier convention:
# - text models: multiplier applies to 1,000 OpenAI tokens (or provider equivalent)
# - tts models: multiplier applies per finished minute of narration
# - image models: multiplier applies per generated image/clip
# - video models: multiplier applies per second of video

MODEL_REGISTRY: Dict[str, ModelInfo] = {
    # --- Text / LLM ---
    "openai-gpt4o-mini": ModelInfo(
        id="openai-gpt4o-mini",
        provider="openai",
        category="text",
        human_name="OpenAI GPT-4o mini",
        cost_multiplier=0.2,  # 0.2 platform tokens per 1K tokens (~low cost)
        metadata={"base_model": "gpt-4o-mini"},
    ),
    "openai-gpt4o": ModelInfo(
        id="openai-gpt4o",
        provider="openai",
        category="text",
        human_name="OpenAI GPT-4o",
        cost_multiplier=1.0,  # 1 token per 1K tokens (pricier)
        metadata={"base_model": "gpt-4o"},
    ),
    # --- TTS ---
    "google-studio": ModelInfo(
        id="google-studio",
        provider="google",
        category="tts",
        human_name="Google Studio TTS",
        cost_multiplier=1.5,  # 1.5 tokens per minute of narration
        metadata={"supports_alignment": "true"},
    ),
    "openai-mini-tts": ModelInfo(
        id="openai-mini-tts",
        provider="openai",
        category="tts",
        human_name="OpenAI mini TTS",
        cost_multiplier=1.0,
    ),
    # --- Image ---
    "openai-dalle": ModelInfo(
        id="openai-dalle",
        provider="openai",
        category="image",
        human_name="OpenAI DALL·E",
        cost_multiplier=3.0,
    ),
    "gemini-nano-image": ModelInfo(
        id="gemini-nano-image",
        provider="google",
        category="image",
        human_name="Gemini 1.5 Nano", 
        cost_multiplier=2.0,
    ),
    "flux-image": ModelInfo(
        id="flux-image",
        provider="flux",
        category="image",
        human_name="Flux (future)",
        cost_multiplier=4.0,
    ),
    # --- Video ---
    "render-stock": ModelInfo(
        id="render-stock",
        provider="internal",
        category="video",
        human_name="Stock-based render",
        cost_multiplier=1.0,  # 1 token per second
    ),
    "veo3-fast": ModelInfo(
        id="veo3-fast",
        provider="google",
        category="video",
        human_name="Veo 3 Fast",
        cost_multiplier=10.0,  # premium cost per second
    ),
    "sora": ModelInfo(
        id="sora",
        provider="openai",
        category="video",
        human_name="OpenAI Sora",
        cost_multiplier=12.0,
    ),
}


def list_models(category: str | None = None):
    if category:
        return [model for model in MODEL_REGISTRY.values() if model.category == category]
    return list(MODEL_REGISTRY.values())


def get_model(model_id: str) -> ModelInfo:
    return MODEL_REGISTRY[model_id]
