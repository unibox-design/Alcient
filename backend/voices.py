import os
from pathlib import Path
from google.oauth2 import service_account
from google.cloud import texttospeech_v1 as texttospeech

# --------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "alcient-prod")
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./keys/tts-runner.json")

OUTPUT_DIR = Path("public/voices")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"🔧 Using project: {GOOGLE_CLOUD_PROJECT}")
print(f"🔐 Using credentials: {CREDENTIALS_PATH}")

# --------------------------------------------------------------------
# VOICE PROFILES
# --------------------------------------------------------------------
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

SAMPLE_TEXTS = {
    "documentary": "In the quiet heart of the forest, life thrives unseen.",
    "news": "Breaking news from around the world — stay tuned.",
    "entertainment": "Get ready for a night full of laughter and music.",
    "satire": "Oh sure, because that always works perfectly.",
    "serious": "In moments of silence, truth often speaks loudest.",
    "corporate": "At Alcient, innovation meets responsibility.",
    "kids": "Hey there, little explorer! Let's go on an adventure!",
    "tech": "AI tools are redefining how we create and connect.",
    "motivational": "Believe in yourself. The next step begins now.",
    "indian_doc": "प्रकृति की हर सांस में एक कहानी छिपी है।",
    "hindi_serious": "कभी-कभी सच्चाई सबसे भारी आवाज़ होती है।",
    "kannada_doc": "ಪ್ರಕೃತಿಯ ಮೌನದಲ್ಲಿದೆ ಬದುಕಿನ ನಾದ.",
}

# --------------------------------------------------------------------
# AUTHENTICATE
# --------------------------------------------------------------------
credentials = service_account.Credentials.from_service_account_file(
    CREDENTIALS_PATH, scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
client = texttospeech.TextToSpeechClient(credentials=credentials)

# --------------------------------------------------------------------
# GENERATE SAMPLES
# --------------------------------------------------------------------
for key, info in VOICE_PROFILES.items():
    output_file = OUTPUT_DIR / f"{key}.wav"
    if output_file.exists():
        print(f"🔁 Skipping (already exists): {output_file.name}")
        continue

    text = SAMPLE_TEXTS.get(key, "This is a sample voice from Alcient.")
    print(f"🎙️ Generating sample for: {key} ({info['name']})...")

    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=info["lang"], name=info["name"]
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=48000,
    )

    try:
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        output_file.write_bytes(response.audio_content)
        print(f"✅ Saved: {output_file}")
    except Exception as e:
        print(f"❌ Failed to generate {key}: {e}")

print("\n🎧 All samples processed. Check 'public/voices/' for results.")