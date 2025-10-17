"""Text-to-speech helpers with Google Cloud Chirp3-HD synthesis, caching, and usage tracking."""

from __future__ import annotations
import hashlib
import os
import re
import wave
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from google.oauth2 import service_account
from google.cloud import texttospeech_v1 as texttospeech

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
AUDIO_SAMPLE_RATE = 48000
AUDIO_SAMPLE_WIDTH = 2  # 16-bit
AUDIO_CHANNELS = 1
CACHE_DIR = Path("cache/tts")

# Approx billing: $16 per 1M characters (Chirp3-HD)
USD_PER_MILLION_CHARS = 16.0

VOICE_PROFILES = {
    "documentary": {"name": "en-US-Chirp3-HD-Kore", "lang": "en-US"},
    "news": {"name": "en-US-Chirp3-HD-Fenrir", "lang": "en-US"},
    "entertainment": {"name": "en-US-Chirp3-HD-Zephyr", "lang": "en-US"},
    "satire": {"name": "en-US-Chirp3-HD-Orus", "lang": "en-US"},
    "serious": {"name": "en-US-Chirp3-HD-Pulcherrima", "lang": "en-US"},
    "corporate": {"name": "en-US-Chirp3-HD-Rasalgethi", "lang": "en-US"},
    "kids": {"name": "en-US-Chirp3-HD-Laomedeia", "lang": "en-US"},
    "tech": {"name": "en-US-Chirp3-HD-Iapetus", "lang": "en-US"},
    "motivational": {"name": "en-US-Chirp3-HD-Vindemiatrix", "lang": "en-US"},
    "indian_doc": {"name": "hi-IN-Chirp3-HD-Kore", "lang": "hi-IN"},
    "hindi_serious": {"name": "hi-IN-Chirp3-HD-Fenrir", "lang": "hi-IN"},
    "kannada_doc": {"name": "kn-IN-Chirp3-HD-Kore", "lang": "kn-IN"},
}


def _normalize_voice_key(voice_key: str) -> str:
    if not voice_key:
        return "documentary"

    key = voice_key.lower().strip()

    mapping = {
        "chirp3hd-kore": "documentary",
        "chirp3hd-fenrir": "news",
        "chirp3hd-zephyr": "entertainment",
        "chirp3hd-orus": "satire",
        "chirp3hd-pulcherrima": "serious",
        "chirp3hd-rasalgethi": "corporate",
        "chirp3hd-laomedeia": "kids",
        "chirp3hd-iapetus": "tech",
        "chirp3hd-vindemiatrix": "motivational",
        "chirp3hd-hi-in-kore": "indian_doc",
        "chirp3hd-hi-in-fenrir": "hindi_serious",
        "chirp3hd-kn-in-kore": "kannada_doc",
    }

    for k, v in mapping.items():
        if k in key:
            return v

    return "documentary"


def estimate_tts_duration(text: str, voice_model: Optional[str] = None) -> float:
    """Estimate TTS duration based on word count (legacy helper)."""
    words = len(text.split())
    return max(2.0, words / 2.5)


def _cache_key(text: str, voice_profile: str) -> str:
    return hashlib.sha256(f"{voice_profile}::{text}".encode("utf-8")).hexdigest()


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


def _estimate_cost(chars: int) -> float:
    return round((chars / 1_000_000) * USD_PER_MILLION_CHARS, 5)


def synthesize_tts(
    text: str,
    voice_profile: str = "documentary",
    output_dir: Path = CACHE_DIR,
) -> Dict[str, Any]:
    """
    Generate or load TTS audio for given text and voice style.
    Returns: dict { 'audio_path', 'duration', 'timestamps', 'usage' }
    """

       # --- Limit text length for testing ---
    MAX_CHARS = int(os.getenv("TTS_MAX_CHARS", "500"))
    if len(text) > MAX_CHARS:
        print(f"⚠️ Trimming text from {len(text)} → {MAX_CHARS} characters (testing limit)")
        text = text[:MAX_CHARS]

    output_dir.mkdir(parents=True, exist_ok=True)
    voice_profile = _normalize_voice_key(voice_profile)
    key = _cache_key(text, voice_profile)
    audio_path = output_dir / f"{key}.wav"
    timestamps = []

    if audio_path.exists():
        print(f"🔁 Cached TTS used: {audio_path}")
        return {
            "audio_path": audio_path,
            "duration": _wav_duration(audio_path),
            "timestamps": [],
            "usage": {"chars": len(text), "usd": _estimate_cost(len(text))},
        }
    
    
    try:
        settings = VOICE_PROFILES.get(voice_profile, VOICE_PROFILES["documentary"])
        print(f"🔊 Using Google voice: {settings['name']} ({settings['lang']})")
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./keys/tts-runner.json")
        credentials = service_account.Credentials.from_service_account_file(
            cred_path, scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        client = texttospeech.TextToSpeechClient(credentials=credentials)

        settings = VOICE_PROFILES.get(voice_profile, VOICE_PROFILES["documentary"])
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=settings["lang"],
            name=settings["name"]
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=AUDIO_SAMPLE_RATE,
        )

        print(f"🎙️ Generating {voice_profile} voice ({settings['name']})...")

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        audio_path.write_bytes(response.audio_content)
        print(f"✅ Audio saved: {audio_path}")

        # Extract timestamps if available
        # if response.timepoints:
        #     timestamps = [
        #         {"mark": tp.mark_name, "time": tp.time_seconds}
        #         for tp in response.timepoints
        #     ]
        #     print(f"🕒 Extracted {len(timestamps)} timepoints")

        duration = _wav_duration(audio_path)
        usage = {"chars": len(text), "usd": _estimate_cost(len(text))}

        return {
            "audio_path": audio_path,
            "duration": duration,
            "timestamps": timestamps,
            "usage": usage,
        }

    except Exception as e:
        print(f"❌ Google TTS synthesis failed: {e}")
        duration = max(2.0, len(text.split()) / 2.5)
        _write_silent_wav(audio_path, duration)
        return {
            "audio_path": audio_path,
            "duration": duration,
            "timestamps": [],
            "usage": {"chars": len(text), "usd": 0.0},
        }


def ensure_tts_audio(text: str, voice_model: str = "documentary", cache_dir: Path = CACHE_DIR) -> Tuple[Path, float]:
    """
    Compatibility wrapper for legacy code.
    Calls synthesize_tts and returns (audio_path, duration).
    """
    result = synthesize_tts(text, voice_model, cache_dir)
    return result["audio_path"], result["duration"]