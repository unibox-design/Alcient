"""Utilities for generating per-word caption timestamps and subtitle files."""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import openai
from dotenv import load_dotenv
import pysubs2

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI()

logger = logging.getLogger(__name__)


@dataclass
class CaptionWord:
    text: str
    start: float
    end: float

    def as_dict(self) -> dict:
        return {"text": self.text, "start": self.start, "end": self.end}


@dataclass(frozen=True)
class CaptionStyleDefinition:
    """Configuration for subtitle style presets."""

    style_name: str
    mode: str  # "word" or "line"
    fontname: str
    fontsize: float
    primary: str
    outline_color: str
    border_style: int
    outline: float
    shadow: float
    margin_v: int
    margin_h: int = 60
    alignment: int = pysubs2.Alignment.BOTTOM_CENTER
    secondary: Optional[str] = None
    back_color: Optional[str] = None
    bold: bool = False
    karaoke: bool = False
    max_words_per_line: int = 8
    blur: float = 0.0
    spacing: float = 0.0
    uppercase: bool = False
    word_color_cycle: Optional[Tuple[str, ...]] = None
    word_tags: Tuple[str, ...] = ()
    line_tags: Tuple[str, ...] = ()


SUBTITLE_CACHE_DIR = Path(__file__).resolve().parent / "outputs" / "cache" / "subtitles"


STYLE_PRESETS: Dict[str, CaptionStyleDefinition] = {
    "Classic Clean": CaptionStyleDefinition(
        style_name="ClassicClean",
        mode="line",
        fontname="Arial",
        fontsize=40,
        primary="&H00FFFFFF",
        outline_color="&H00000000",
        border_style=1,
        outline=2.0,
        shadow=1.0,
        margin_v=60,
        margin_h=80,
        secondary="&H00FFFFFF",
        karaoke=False,
        max_words_per_line=10,
    ),
    "Kinetic Pop": CaptionStyleDefinition(
        style_name="KineticPop",
        mode="word",
        fontname="Impact",
        fontsize=52,
        primary="&H0000DDFF",
        outline_color="&H00000000",
        border_style=1,
        outline=4.0,
        shadow=0.0,
        margin_v=84,
        margin_h=90,
        secondary="&H0000DDFF",
        bold=True,
        max_words_per_line=1,
        spacing=1.8,
        uppercase=True,
        word_color_cycle=(
            "&H0000DDFF",  # warm yellow
            "&H00FFC600",  # aqua blue
            "&H009D55FF",  # hot pink
        ),
        word_tags=(
            "\\bord7",
            "\\shad0",
            "\\fscx112",
            "\\fscy110",
        ),
    ),
    "Highlight Bar": CaptionStyleDefinition(
        style_name="HighlightBar",
        mode="line",
        fontname="Helvetica Neue Bold",
        fontsize=42,
        primary="&H0060FFE8",
        outline_color="&H00000000",
        border_style=3,
        outline=1.0,
        shadow=0.0,
        margin_v=70,
        margin_h=90,
        secondary="&H0000D5FF",
        back_color="&H99000000",
        karaoke=True,
        max_words_per_line=9,
        uppercase=True,
        line_tags=(
            "\\bord0",
            "\\shad0",
        ),
    ),
    "Outline Glow": CaptionStyleDefinition(
        style_name="OutlineGlow",
        mode="word",
        fontname="Arial Black",
        fontsize=48,
        primary="&H00E4FDFF",
        outline_color="&H007D3DFF",
        border_style=1,
        outline=5.0,
        shadow=0.0,
        margin_v=80,
        margin_h=100,
        secondary="&H00E4FDFF",
        bold=True,
        blur=3.5,
        spacing=0.6,
        uppercase=True,
        word_color_cycle=(
            "&H008040FF",  # neon purple
            "&H00FFFFFF",  # crisp white
        ),
        word_tags=(
            "\\bord6",
            "\\blur4",
        ),
        max_words_per_line=1,
    ),
    "Subtitle Boxed": CaptionStyleDefinition(
        style_name="SubtitleBoxed",
        mode="line",
        fontname="Gill Sans Bold",
        fontsize=44,
        primary="&H00F5F5F5",
        outline_color="&H00000000",
        border_style=3,
        outline=0.0,
        shadow=0.0,
        margin_v=64,
        margin_h=85,
        secondary="&H003CFFE0",
        back_color="&HB0000000",
        karaoke=True,
        max_words_per_line=9,
        bold=True,
        uppercase=True,
        line_tags=(
            "\\bord0",
            "\\shad0",
        ),
    ),
    "Simple Minimal": CaptionStyleDefinition(
        style_name="SimpleMinimal",
        mode="line",
        fontname="Helvetica Neue",
        fontsize=36,
        primary="&H00F5F5F5",
        outline_color="&H00202020",
        border_style=1,
        outline=1.0,
        shadow=0.4,
        margin_v=70,
        margin_h=90,
        secondary="&H00F5F5F5",
        karaoke=False,
        max_words_per_line=10,
        spacing=0.4,
        line_tags=(
            "\\bord1",
            "\\shad0",
        ),
    ),
}

DEFAULT_CAPTION_STYLE = "Classic Clean"

_STYLE_KEY_LOOKUP: Dict[str, str] = {}
_STYLE_SLUG_LOOKUP: Dict[str, str] = {}
for display_name, definition in STYLE_PRESETS.items():
    lowered_display = display_name.lower()
    _STYLE_KEY_LOOKUP[lowered_display] = display_name
    display_slug = re.sub(r"[^a-z0-9]+", "", lowered_display)
    if display_slug:
        _STYLE_SLUG_LOOKUP[display_slug] = display_name
    style_name_lower = definition.style_name.lower()
    _STYLE_KEY_LOOKUP[style_name_lower] = display_name
    style_slug = re.sub(r"[^a-z0-9]+", "", style_name_lower)
    if style_slug and style_slug not in _STYLE_SLUG_LOOKUP:
        _STYLE_SLUG_LOOKUP[style_slug] = display_name


def _resolve_caption_style(style_name: Optional[str]) -> str:
    if not style_name:
        return DEFAULT_CAPTION_STYLE
    token = str(style_name).strip()
    if not token:
        return DEFAULT_CAPTION_STYLE
    if token in STYLE_PRESETS:
        return token
    lowered = token.lower()
    if lowered in _STYLE_KEY_LOOKUP:
        return _STYLE_KEY_LOOKUP[lowered]
    slug = re.sub(r"[^a-z0-9]+", "", lowered)
    if slug and slug in _STYLE_SLUG_LOOKUP:
        return _STYLE_SLUG_LOOKUP[slug]
    return DEFAULT_CAPTION_STYLE


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


def _parse_ass_color(value: Optional[str]) -> Optional[pysubs2.Color]:
    if not value:
        return None
    token = value.strip().upper()
    if not token.startswith("&H"):
        return None
    hex_part = token[2:]
    if len(hex_part) > 8:
        hex_part = hex_part[-8:]
    hex_part = hex_part.rjust(8, "0")
    try:
        alpha = int(hex_part[0:2], 16)
        blue = int(hex_part[2:4], 16)
        green = int(hex_part[4:6], 16)
        red = int(hex_part[6:8], 16)
    except ValueError:
        return None
    return pysubs2.Color(red, green, blue, alpha)


def _sanitize_ass_text(text: str) -> str:
    if not text:
        return ""
    cleaned = []
    for char in text:
        category = unicodedata.category(char)
        if category and category[0] == "C" and char not in {"\t", "\n", "\r"}:
            continue
        cleaned.append(char)
    value = "".join(cleaned)
    value = value.replace("\\", r"\\")
    value = value.replace("{", "{{").replace("}", "}}")
    value = value.replace("\r", "")
    value = value.replace("\n", r"\N")
    return value


def _transform_token(text: str, style_definition: CaptionStyleDefinition) -> str:
    token = text or ""
    if style_definition.uppercase:
        token = token.upper()
    return _sanitize_ass_text(token)


def _format_override_color(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    token = str(value).strip().upper()
    if not token.startswith("&H"):
        return None
    hex_part = token[2:]
    if not hex_part:
        return None
    if len(hex_part) > 8:
        hex_part = hex_part[-8:]
    if len(hex_part) < 6:
        hex_part = hex_part.rjust(6, "0")
    # ASS override tags expect BBGGRR (alpha handled by underlying style)
    color = hex_part[-6:]
    return f"&H{color}&"


def _wrap_with_tags(text: str, tags: Sequence[str]) -> str:
    if not text:
        return ""
    filtered = [
        tag
        for tag in tags
        if isinstance(tag, str) and tag.strip() and tag.strip().startswith("\\")
    ]
    if not filtered:
        return text
    joined = "".join(tag.strip() for tag in filtered)
    return f"{{{joined}}}{text}"


def _requires_space(prev_text: str, next_text: Optional[str]) -> bool:
    if not next_text:
        return False
    next_stripped = (next_text or "").strip()
    if not next_stripped:
        return False
    if next_stripped[0] in ",.!?:;)]}»”′":
        return False
    return True


def _group_words_into_lines(words: Sequence[CaptionWord], max_words: int) -> List[List[CaptionWord]]:
    if not words:
        return []
    lines: List[List[CaptionWord]] = []
    current: List[CaptionWord] = []
    for word in words:
        current.append(word)
        stripped = word.text.strip() if word.text else ""
        is_sentence_end = stripped.endswith((".", "!", "?"))
        is_clause_break = stripped.endswith((";", ":"))
        if len(current) >= max_words or is_sentence_end or (is_clause_break and len(current) >= max_words // 2):
            lines.append(current)
            current = []
    if current:
        lines.append(current)
    return lines


def _build_plain_line(
    words: Sequence[CaptionWord], style_definition: CaptionStyleDefinition
) -> str:
    if not words:
        return ""
    pieces: List[str] = []
    for idx, word in enumerate(words):
        token = _transform_token(word.text or "", style_definition)
        if not token:
            continue
        pieces.append(token)
        next_text = words[idx + 1].text if idx + 1 < len(words) else None
        if _requires_space(word.text or "", next_text):
            pieces.append(" ")
    return "".join(pieces).strip()


def _build_karaoke_line(
    words: Sequence[CaptionWord], style_definition: CaptionStyleDefinition
) -> str:
    if not words:
        return ""
    fragments: List[str] = []
    for idx, word in enumerate(words):
        token = _transform_token(word.text or "", style_definition)
        if not token:
            continue
        duration = max(word.end - word.start, 0.01)
        centiseconds = max(1, int(round(duration * 100)))
        fragments.append(f"{{\\k{centiseconds}}}{token}")
        next_text = words[idx + 1].text if idx + 1 < len(words) else None
        if _requires_space(word.text or "", next_text):
            fragments.append("\\h")
    return "".join(fragments)


def _scene_duration(scene: Dict, words: Sequence[CaptionWord]) -> float:
    explicit = _coerce_time(scene.get("audioDuration"))
    if explicit is None:
        explicit = _coerce_time(scene.get("duration"))
    last_end = max((word.end for word in words), default=0.0)
    if explicit is None or explicit < last_end:
        explicit = last_end
    if explicit is None:
        return 0.0
    return max(0.0, round(float(explicit), 3))


def generate_ass_subtitles(
    project_id: str,
    scenes: Sequence[Dict],
    caption_style: Optional[str],
    resolution: tuple[int, int] | None = None,
) -> Optional[Path]:
    """Generate an ASS subtitle file for the project timeline."""

    style_key = _resolve_caption_style(caption_style)
    if caption_style and caption_style != style_key:
        logger.info("Resolved caption style '%s' to preset '%s'", caption_style, style_key)
    style_definition = STYLE_PRESETS[style_key]

    safe_project_id = "".join(
        ch if str(ch).isalnum() or ch in {"-", "_"} else "_" for ch in str(project_id or "project")
    ).strip("_")
    if not safe_project_id:
        safe_project_id = "project"
    output_path = SUBTITLE_CACHE_DIR / f"{safe_project_id}.ass"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    subs = pysubs2.SSAFile()
    width, height = resolution if resolution else (1920, 1080)
    subs.info.update({"PlayResX": int(width), "PlayResY": int(height)})

    style = pysubs2.SSAStyle()
    style.fontname = style_definition.fontname
    style.fontsize = style_definition.fontsize
    style.borderstyle = style_definition.border_style
    style.outline = style_definition.outline
    style.shadow = style_definition.shadow
    style.marginl = style_definition.margin_h
    style.marginr = style_definition.margin_h
    style.marginv = style_definition.margin_v
    style.alignment = style_definition.alignment
    style.bold = -1 if style_definition.bold else 0
    if style_definition.blur:
        style.blur = float(style_definition.blur)
    if style_definition.spacing:
        style.spacing = float(style_definition.spacing)

    primary = _parse_ass_color(style_definition.primary)
    if primary:
        style.primarycolor = primary
    secondary = _parse_ass_color(style_definition.secondary)
    if secondary:
        style.secondarycolor = secondary
    outline = _parse_ass_color(style_definition.outline_color)
    if outline:
        style.outlinecolor = outline
    back = _parse_ass_color(style_definition.back_color)
    if back:
        style.backcolor = back

    subs.styles[style_definition.style_name] = style

    timeline_offset = 0.0
    event_count = 0
    word_event_index = 0
    for scene in scenes:
        local_words = _normalise_caption_payload(scene.get("captions"))
        if not local_words:
            fallback_text = scene.get("script") or scene.get("text") or ""
            fallback_duration = _coerce_time(scene.get("audioDuration"))
            if fallback_duration is None:
                fallback_duration = _coerce_time(scene.get("duration"))
            local_words = _fallback_words_from_text(fallback_text, fallback_duration)

        absolute_words: List[CaptionWord] = []
        for word in local_words:
            absolute_words.append(
                CaptionWord(
                    text=word.text,
                    start=round(word.start + timeline_offset, 3),
                    end=round(word.end + timeline_offset, 3),
                )
            )

        if style_definition.mode == "word":
            for word in absolute_words:
                text = _transform_token(word.text or "", style_definition)
                if not text:
                    continue
                tags: List[str] = list(style_definition.word_tags or ())
                color_cycle = style_definition.word_color_cycle or ()
                if color_cycle:
                    color_value = color_cycle[word_event_index % len(color_cycle)]
                    override_color = _format_override_color(color_value)
                    if override_color:
                        tags.append(f"\\1c{override_color}")
                start_ms = max(0, int(round(word.start * 1000)))
                end_ms = int(round(word.end * 1000))
                if end_ms <= start_ms:
                    end_ms = start_ms + 1
                decorated = _wrap_with_tags(text, tags)
                subs.events.append(
                    pysubs2.SSAEvent(
                        start=start_ms,
                        end=end_ms,
                        text=decorated,
                        style=style_definition.style_name,
                    )
                )
                event_count += 1
                word_event_index += 1
        else:
            line_groups = _group_words_into_lines(absolute_words, style_definition.max_words_per_line)
            for line_words in line_groups:
                if not line_words:
                    continue
                if style_definition.karaoke:
                    text = _build_karaoke_line(line_words, style_definition)
                else:
                    text = _build_plain_line(line_words, style_definition)
                if not text:
                    continue
                text = _wrap_with_tags(text, style_definition.line_tags or ())
                start = min(word.start for word in line_words)
                end = max(word.end for word in line_words)
                start_ms = max(0, int(round(start * 1000)))
                end_ms = int(round((end + 0.05) * 1000))
                if end_ms <= start_ms:
                    end_ms = start_ms + 1
                subs.events.append(
                    pysubs2.SSAEvent(
                        start=start_ms,
                        end=end_ms,
                        text=text,
                        style=style_definition.style_name,
                    )
                )
                event_count += 1

        scene_duration = _scene_duration(scene, local_words)
        timeline_offset = round(timeline_offset + scene_duration, 3)

    if not event_count:
        logger.info("No caption events generated for project %s", project_id)
        if output_path.exists():
            try:
                output_path.unlink()
            except OSError:
                pass
        return None

    subs.events.sort(key=lambda evt: (evt.start, evt.end))
    subs.save(str(output_path), encoding="utf-8")
    logger.info(
        "Generated subtitle file %s with %s events using style %s",
        output_path,
        event_count,
        style_key,
    )
    return output_path
