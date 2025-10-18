# backend/captions.py
import os
import openai
import json
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI()

def generate_word_timestamps(audio_path: str, text: str):
    """
    Use OpenAI Whisper API to get word-level timestamps from audio.
    """
    print(f"🎧 Generating timestamps for {audio_path} ...")

    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )

    # Convert the result to plain Python dict
    data = result.model_dump() if hasattr(result, "model_dump") else result
    words = data.get("words", [])
    print(f"✅ Found {len(words)} words with timestamps")

    return {"words": words, "text": data.get("text", "")}