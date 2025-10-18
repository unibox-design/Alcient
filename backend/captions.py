"""Utilities for generating per-word caption timestamps and subtitle files."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI()


@dataclass
class CaptionWord:
    text: str
    start: float
    end: float

    def as_dict(self) -> dict:
        return {"text": self.text, "start": self.start, "end": self.end}


def _coerce_time(value, fallback: float | None = None) -> float | None:
    """Safely convert timestamps coming back from Whisper into floats."""
    if value is None:
        return fallback
    try:
        # Some providers return strings, some return Decimal-ish types
        numeric = float(value)
    except (TypeError, ValueError):
        return fallback
    return round(numeric, 3)


def _fallback_words_from_text(text: str, duration: float | None) -> List[CaptionWord]:
    tokens = [token for token in (text or "").split() if token]
    if not tokens:
        return []
    total_duration = duration if duration and duration > 0 else len(tokens) * 0.4
    slice_length = total_duration / len(tokens)
    words: List[CaptionWord] = []
    for idx, token in enumerate(tokens):
        start = round(idx * slice_length, 3)
        end = round(start + slice_length, 3)
        words.append(CaptionWord(text=token, start=start, end=end))
    return words


def _normalise_whisper_words(words_payload) -> List[CaptionWord]:
    words: List[CaptionWord] = []
    if not isinstance(words_payload, list):
        return words

    previous_end: float | None = None
    for raw in words_payload:
        if not raw:
            continue
        token = raw.get("word") if isinstance(raw, dict) else None
        if not token and isinstance(raw, dict):
            token = raw.get("text") or raw.get("token")
        if not token:
            continue
        start = _coerce_time(raw.get("start")) if isinstance(raw, dict) else None
        end = _coerce_time(raw.get("end")) if isinstance(raw, dict) else None
        if start is None:
            start = previous_end if previous_end is not None else 0.0
        if end is None or end <= start:
            inferred = start + 0.2
            end = round(inferred, 3)
        previous_end = end
        words.append(CaptionWord(text=token.strip(), start=start, end=end))
    return words


def generate_word_timestamps(audio_path: str, text: str):
    """Use OpenAI Whisper API to get word-level timestamps from audio."""
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    print(f"🎧 Generating timestamps for {audio_path} ...")

    with open(audio_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )

    # Convert the result to a plain Python dict
    data = result.model_dump() if hasattr(result, "model_dump") else json.loads(result.json())

    recognised_text = data.get("text") or (text or "")
    words = _normalise_whisper_words(data.get("words"))

    # Determine a reasonable total duration from the payload for fallbacks
    payload_duration = None
    if words:
        payload_duration = max((word.end for word in words), default=None)
    elif isinstance(data.get("segments"), list):
        durations = [
            _coerce_time(segment.get("end"), 0.0)
            for segment in data["segments"]
            if isinstance(segment, dict)
        ]
        if durations:
            payload_duration = max(durations)

    if not words:
        words = _fallback_words_from_text(recognised_text, payload_duration)

    print(f"✅ Found {len(words)} words with timestamps")

    return {
        "text": recognised_text,
        "words": [word.as_dict() for word in words],
    }


def _normalise_caption_payload(captions) -> List[CaptionWord]:
    words: List[CaptionWord] = []
    if not captions:
        return words

    payload: Iterable
    if isinstance(captions, dict):
        payload = captions.get("words") or []
    elif isinstance(captions, list):
        payload = captions
    else:
        payload = []

    previous_end: Optional[float] = None
    for raw in payload:
        if isinstance(raw, CaptionWord):
            word = raw
        elif isinstance(raw, dict):
            token = (raw.get("text") or raw.get("word") or raw.get("token") or "").strip()
            if not token:
                continue
            start = _coerce_time(raw.get("start"))
            if start is None:
                start = previous_end if previous_end is not None else 0.0
            end = _coerce_time(raw.get("end"), start + 0.4)
            if end is None or end <= start:
                end = start + 0.4
            word = CaptionWord(text=token, start=start, end=end)
        else:
            continue
        previous_end = word.end
        words.append(word)

    words.sort(key=lambda w: w.start)
    return words


def _format_srt_timestamp(seconds: float) -> str:
    total_millis = int(round(max(seconds, 0.0) * 1000))
    hours, remainder = divmod(total_millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _chunk_caption_words(words: List[CaptionWord]) -> List[dict]:
    if not words:
        return []

    segments: List[dict] = []
    buffer: List[str] = []
    segment_start: Optional[float] = None
    segment_end: Optional[float] = None

    def flush_segment() -> None:
        nonlocal buffer, segment_start, segment_end
        if buffer and segment_start is not None and segment_end is not None:
            text = " ".join(buffer).strip()
            if text:
                segments.append({
                    "text": text,
                    "start": segment_start,
                    "end": segment_end,
                })
        buffer = []
        segment_start = None
        segment_end = None

    MAX_WORDS = 8
    MAX_DURATION = 4.5
    MAX_GAP = 0.8

    for word in words:
        cleaned = word.text.strip()
        if not cleaned:
            continue

        if buffer:
            current_start = segment_start if segment_start is not None else word.start
            current_end = segment_end if segment_end is not None else current_start
            gap = word.start - current_end
            duration = current_end - current_start
            if (
                gap > MAX_GAP
                or len(buffer) >= MAX_WORDS
                or duration >= MAX_DURATION
                or buffer[-1].endswith((".", "?", "!"))
            ):
                flush_segment()

        if not buffer:
            segment_start = word.start

        buffer.append(cleaned)
        segment_end = max(segment_end or word.end, word.end)

        if cleaned.endswith((".", "?", "!")) and segment_start is not None:
            flush_segment()

    if buffer:
        flush_segment()

    return segments


def export_captions_to_srt(captions, output_path: Path) -> Optional[Path]:
    """Write captions to an SRT file suitable for ffmpeg subtitle burn-in."""

    words = _normalise_caption_payload(captions)
    if not words:
        return None

    segments = _chunk_caption_words(words)
    if not segments:
        return None

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as handle:
        for index, segment in enumerate(segments, start=1):
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start + 0.5))
            if end <= start:
                end = start + 0.5
            text = (segment.get("text") or "").strip()
            if not text:
                continue
            handle.write(f"{index}\n")
            handle.write(
                f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n"
            )
            handle.write(f"{text}\n\n")

    return output_path
