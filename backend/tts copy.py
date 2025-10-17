"""Text-to-speech helpers with OpenAI synthesis and caching."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import wave
from pathlib import Path
from typing import Optional, Tuple

from openai import OpenAI

AUDIO_SAMPLE_RATE = 24000
AUDIO_SAMPLE_WIDTH = 2  # 16-bit
AUDIO_CHANNELS = 1

DEFAULT_WORDS_PER_MINUTE = {
    "lady holiday": 150,
    "golden narrator": 145,
    "calm documentary": 140,
    "energetic host": 170,
    "warm storyteller": 155,
}

OPENAI_VOICE_MAP = {
    "lady holiday": "alloy",
    "golden narrator": "verse",
    "calm documentary": "haru",
    "energetic host": "bleep",
    "warm storyteller": "serenity",
}


def _normalize_voice_key(voice: Optional[str]) -> str:
    if not voice:
        return "default"
    return re.sub(r"\s+", " ", voice.strip().lower()) or "default"


def estimate_tts_duration(text: str, voice_model: Optional[str] = None) -> float:
    """Estimate speech duration (seconds) for a given text and voice profile."""
    if not text:
        return 2.0

    words = re.findall(r"[\w']+", text)
    word_count = len(words) or 1

    voice_key = _normalize_voice_key(voice_model)
    wpm = DEFAULT_WORDS_PER_MINUTE.get(voice_key, 155)
    wpm = max(100, min(200, wpm))

    base_seconds = word_count / wpm * 60.0
    sentence_breaks = max(1, len(re.findall(r"[.!?]", text)))
    pause_seconds = min(3.0, sentence_breaks * 0.35)
    duration = base_seconds + pause_seconds
    return max(2.0, duration)


def _tts_cache_key(text: str, voice_model: Optional[str]) -> str:
    voice_key = _normalize_voice_key(voice_model)
    return hashlib.sha256(f"{voice_key}::{text}".encode("utf-8")).hexdigest()


def _write_silent_wav(path: Path, duration: float) -> None:
    frames = max(1, int(AUDIO_SAMPLE_RATE * duration))
    silence = b"\x00" * AUDIO_SAMPLE_WIDTH * frames
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(AUDIO_SAMPLE_WIDTH)
        wf.setframerate(AUDIO_SAMPLE_RATE)
        wf.writeframes(silence)


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate() or AUDIO_SAMPLE_RATE
        return frames / float(rate)


def _mp3_to_wav(src: Path, dest: Path) -> None:
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-ar",
            str(AUDIO_SAMPLE_RATE),
            "-ac",
            str(AUDIO_CHANNELS),
            str(dest),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0 or not dest.exists():
        raise RuntimeError(f"ffmpeg mp3->wav failed: {result.stderr}")


def _synthesize_openai_tts(text: str, voice_model: Optional[str], dest: Path) -> bool:
    voice_key = _normalize_voice_key(voice_model)
    openai_voice = OPENAI_VOICE_MAP.get(voice_key, "alloy")
    try:
        client = OpenAI()
        response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice=openai_voice,
            response_format="mp3",
            input=text.strip() or " ",
        )
        mp3_bytes = getattr(response, "content", None)
        if mp3_bytes is None:
            mp3_bytes = bytes(response)
        mp3_path = dest.with_suffix(".mp3")
        mp3_path.write_bytes(mp3_bytes)
        _mp3_to_wav(mp3_path, dest)
        mp3_path.unlink(missing_ok=True)
        return True
    except Exception as exc:  # noqa: broad-except
        print("TTS synthesis failed; falling back to silence:", exc)
        return False


def ensure_tts_audio(
    text: str,
    voice_model: Optional[str],
    cache_dir: str | Path,
) -> Tuple[Path, float]:
    """Return path to cached TTS audio, synthesizing with OpenAI when possible."""

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_key = _tts_cache_key(text, voice_model)
    audio_path = cache_dir / f"{cache_key}.wav"

    if not audio_path.exists():
        if not _synthesize_openai_tts(text, voice_model, audio_path):
            duration = estimate_tts_duration(text, voice_model)
            _write_silent_wav(audio_path, duration)

    duration_seconds = _wav_duration(audio_path)
    return audio_path, duration_seconds
