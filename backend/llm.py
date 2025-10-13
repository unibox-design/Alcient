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
         { "text": "...", "duration": 5, "keywords": ["..."], "ttsVoice": "Default" }
      ]
    }
    """
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert video director planning a narrated video. "
                        "Respond ONLY with valid JSON. The JSON must include keys: "
                        "'title' (string <= 80 chars), 'narration' (2-3 short paragraphs), "
                        f"'scenes' (array of around {scene_hint} scenes). Each scene object "
                        "needs 'text' (<= 2 sentences), 'duration' (integer seconds), and "
                        "'keywords' (array of 2-4 concise search terms). Include 'ttsVoice' if "
                        "a specific voice is suggested. Ensure the narration flows naturally "
                        "through the scene order."
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
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            try:
                duration = int(scene.get("duration", 5))
            except (ValueError, TypeError):
                duration = 5
            scene["duration"] = max(3, min(duration, 12))
            if "keywords" not in scene or not isinstance(scene["keywords"], list):
                scene["keywords"] = []
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
