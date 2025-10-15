# backend/llm.py
import json
import os
import re

import openai
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_narration(prompt: str):
    """Generate a narration and keywords from a text prompt."""
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a creative video scriptwriter."},
                {"role": "user", "content": f"Write a short, engaging narration (30 seconds) for: {prompt}. After the narration, add ';' followed by a list of comma-separated keywords."}
            ],
            temperature=0.7,
            max_tokens=500
        )

        text = response.choices[0].message.content.strip()
        if ';' in text:
            narration, keywords = text.split(';', 1)
            keywords = [k.strip() for k in keywords.split(',') if k.strip()]
        else:
            narration, keywords = text, []

        return {"narration": narration.strip(), "keywords": keywords}

    except Exception as e:
        print("Error in generate_narration:", e)
        return {"error": str(e)}


def _extract_json_block(text: str):
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt to locate first JSON object in the string.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    snippet = match.group(0)
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return None


def _scale_scene_durations(scenes, target_seconds: int):
    if not scenes or not target_seconds:
        return scenes

    durations = []
    for scene in scenes:
        try:
            durations.append(int(scene.get("duration", 5)))
        except (TypeError, ValueError):
            durations.append(5)

    total = sum(durations)
    if total <= 0:
        return scenes

    scaled = []
    remaining = target_seconds
    max_per_scene = max(10, min(30, int(target_seconds / max(len(scenes), 1)) + 6))
    min_per_scene = 3

    for idx, scene in enumerate(scenes):
        base = durations[idx]
        if idx == len(scenes) - 1:
            new_duration = max(min_per_scene, min(max_per_scene, remaining))
        else:
            projected = int(round(base * target_seconds / total))
            new_duration = max(min_per_scene, min(max_per_scene, projected))
            remaining -= new_duration
        scene["duration"] = new_duration
        scaled.append(scene)
    return scaled


def generate_storyboard(
    prompt: str,
    aspect: str = "landscape",
    voice_model: str = "Default",
    target_seconds: int = 60,
    scene_hint: int = 6,
):
    """
    Use the LLM to produce structured project data including title, narration, and scenes.
    Expected schema:
    {
      "title": "...",
      "narration": "...",
      "scenes": [
         { "section": "...", "text": "...", "duration": 5, "keywords": ["..."], "ttsVoice": "Default" }
      ]
    }
    """
    try:
        target_seconds = max(30, int(target_seconds or 60))
        target_words = max(120, int(target_seconds * 3.0))
        lower_words = int(target_words * 0.9)
        upper_words = int(target_words * 1.1)
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert short-form video content creator and scriptwriter, "
                        "crafting fast-paced, high-retention scripts for TikTok, Instagram Reels, "
                        "and YouTube Shorts. Transform the provided idea and keywords into a compelling "
                        "narrative that flows through these beats in order: THE HOOK, PROBLEM/CONTEXT, "
                        "SOLUTION/VALUE DROP. You may add supporting beats between them "
                        "when helpful, but the story must start with a hook and end with summarizing the main point, offering a final thought or insight, or providing a call to reflection on the topic. "
                        "Write in punchy, conversational language with vivid imagery, keeping each scene "
                        "to one or two crisp sentences. Respond ONLY with valid JSON containing: "
                        "'title' (<= 80 characters), 'narration' (2-3 short energetic paragraphs), and "
                        f"'scenes' (array of around {scene_hint} scenes). Each scene object must include "
                        "'section' (one of \"THE HOOK\", \"PROBLEM/CONTEXT\", \"SOLUTION/VALUE DROP\", "
                        "\"CALL TO ACTION\", or a concise supporting beat label), 'text' (<= 2 sentences), "
                        "'duration' (integer seconds), and 'keywords' (array of 2-4 high-signal search terms). "
                        "Include 'ttsVoice' if a specific voice is essential. Ensure scene durations sum close "
                        "to the target runtime."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Create a storyboard for the following idea.\n"
                        f"Idea prompt: {prompt}\n"
                        f"Target aspect ratio: {aspect}.\n"
                        f"Target runtime: {int(target_seconds)} seconds.\n"
                        f"Desired voice style: {voice_model}.\n"
                        f"Total narration length should stay between {lower_words} and {upper_words} words so that the voiceover fits the runtime, averaging about {target_words} words overall.\n"
                        f"Plan for roughly {scene_hint} scenes so that the pacing feels even. "
                        "Scene durations should add up close to the target runtime. "
                        "Remember: respond strictly with JSON."
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        data = _extract_json_block(raw)
        if not isinstance(data, dict):
            raise ValueError("LLM did not return valid storyboard JSON")
        scenes = data.get("scenes") or []
        # Normalise scene fields.
        default_sections = ["THE HOOK", "PROBLEM/CONTEXT", "SOLUTION/VALUE DROP", "CALL TO ACTION"]
        for idx, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                continue
            try:
                duration = int(scene.get("duration", 5))
            except (ValueError, TypeError):
                duration = 5
            scene["duration"] = max(3, min(duration, 12))
            if "keywords" not in scene or not isinstance(scene["keywords"], list):
                scene["keywords"] = []
            if not scene.get("section"):
                if idx < len(default_sections):
                    scene["section"] = default_sections[idx]
                else:
                    scene["section"] = "Supporting Beat"
        scenes = _scale_scene_durations(scenes, target_seconds)

        return {
            "title": data.get("title"),
            "narration": data.get("narration"),
            "scenes": scenes,
            "voiceModel": voice_model,
            "durationSeconds": target_seconds,
        }
    except Exception as e:
        print("Error in generate_storyboard:", e)
        return {"error": str(e)}


def enrich_scene_metadata(scenes, aspect: str = "landscape", max_keywords: int = 4):
    """
    Ask the LLM to suggest search keywords and optional generative prompts for each scene.
    `scenes` should be an iterable of dicts with keys: id, text.
    """
    cleaned_scenes = []
    for idx, scene in enumerate(scenes or []):
        if not isinstance(scene, dict):
            continue
        text = (scene.get("text") or scene.get("script") or "").strip()
        if not text:
            continue
        scene_id = str(scene.get("id") or idx)
        cleaned_scenes.append(
            {
                "id": scene_id,
                "text": text[:700],
            }
        )

    if not cleaned_scenes:
        return []

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert short-form video content strategist. "
                        "Given scene descriptions you return high-signal search keywords and concise image prompts. "
                        "Respond ONLY with valid JSON of the form: "
                        "{\"scenes\":[{\"id\":\"...\",\"keywords\":[\"k1\",\"k2\"],\"imagePrompt\":\"...\"}, ...]}. "
                        "Each keywords array must contain 2-4 short search phrases optimised for stock or generative lookup. "
                        "Each imagePrompt should be <=160 characters, vivid, and suitable for text-to-image/video models. "
                        "If unsure, still provide best-effort keywords and prompts. "
                        "Do not include explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "aspect": aspect,
                            "scenes": cleaned_scenes,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.4,
            max_tokens=600,
        )
        raw = response.choices[0].message.content.strip()
        data = _extract_json_block(raw)
        if not isinstance(data, dict):
            raise ValueError("LLM did not return JSON")
        items = data.get("scenes")
        if not isinstance(items, list):
            raise ValueError("LLM JSON missing 'scenes'")
    except Exception as exc:
        raise RuntimeError(f"LLM scene enrichment failed: {exc}") from exc

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        scene_id = str(item.get("id") or "")
        if not scene_id:
            continue
        raw_keywords = item.get("keywords") or []
        if isinstance(raw_keywords, str):
            raw_keywords = [raw_keywords]
        keywords = []
        for kw in raw_keywords:
            if isinstance(kw, str):
                cleaned_kw = kw.strip()
                if cleaned_kw:
                    keywords.append(cleaned_kw)
        keywords = keywords[:max_keywords]
        image_prompt = item.get("imagePrompt")
        if isinstance(image_prompt, str):
            image_prompt = image_prompt.strip()
        else:
            image_prompt = None
        results.append(
            {
                "id": scene_id,
                "keywords": keywords,
                "imagePrompt": image_prompt,
            }
        )
    return results
