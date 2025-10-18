import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import openai
openai.api_key = os.getenv("OPENAI_API_KEY")

# Make sure your API key is loaded (from env)
client = openai.OpenAI()

AUDIO_PATH = "test.wav"  # or test.mp3 — place a small clip (<20s)
OUTPUT_PATH = Path("output.json")

with open(AUDIO_PATH, "rb") as f:
    print("🎧 Uploading audio to Whisper API...")
    result = client.audio.transcriptions.create(
        model="whisper-1",  # this must be the new Whisper endpoint
        file=f,
        response_format="verbose_json",
        timestamp_granularities=["word"],  # 👈 key flag
    )

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
print(f"✅ Output saved to {OUTPUT_PATH}")
print(json.dumps(result.model_dump(), indent=2)[:2000])