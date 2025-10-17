import os
from google.oauth2 import service_account
from google.cloud import texttospeech_v1 as texttospeech

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "alcient-prod")
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./keys/tts-runner.json")
OUTPUT_FILE = "vertex_tts_test.wav"

print(f"🔧 Using project: {GOOGLE_CLOUD_PROJECT}")
print(f"🔐 Using credentials: {CREDENTIALS_PATH}")

# ----------------------------------------------------------------------------
# LOAD CREDENTIALS MANUALLY
# ----------------------------------------------------------------------------
credentials = service_account.Credentials.from_service_account_file(
    CREDENTIALS_PATH,
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)

client = texttospeech.TextToSpeechClient(credentials=credentials)

# ----------------------------------------------------------------------------
# BUILD REQUEST
# ----------------------------------------------------------------------------
synthesis_input = texttospeech.SynthesisInput(
    text="Hello! This is a test of Google Cloud Text-to-Speech using manual service account authentication."
)

voice = texttospeech.VoiceSelectionParams(
    language_code="en-US",
    name="en-US-Studio-Q",  # Studio-quality neural voice
)

audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16
)

# ----------------------------------------------------------------------------
# SEND REQUEST
# ----------------------------------------------------------------------------
print("🎙️ Generating speech...")

response = client.synthesize_speech(
    input=synthesis_input,
    voice=voice,
    audio_config=audio_config
)

# ----------------------------------------------------------------------------
# SAVE OUTPUT
# ----------------------------------------------------------------------------
with open(OUTPUT_FILE, "wb") as out:
    out.write(response.audio_content)
    print(f"✅ Audio saved successfully to {OUTPUT_FILE}")

print(f"🎧 Approx audio length: {len(response.audio_content) / 16000:.2f} seconds")