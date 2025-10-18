const BASE = import.meta.env.VITE_BACKEND || "http://localhost:5000";

export async function enrichScenesMetadata({ format = "landscape", scenes = [] }) {
  const res = await fetch(`${BASE}/api/scenes/enrich`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format, scenes }),
  });
  const body = await res.json();
  if (!res.ok) {
    const error = body?.error || `Failed to enrich scenes (${res.status})`;
    throw new Error(error);
  }
  return body;
}

export async function generateSceneAudioAndCaptions({ sceneId, text, voiceModel }) {
  try {
    // Step 1: Generate TTS audio
    const ttsRes = await fetch(`${BASE}/api/project/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voiceModel }),
    });
    const ttsBody = await ttsRes.json();
    if (!ttsRes.ok) throw new Error(ttsBody.error || "TTS failed");

    const audioUrl = ttsBody.audioUrl || ttsBody.path;

    return {
      audioUrl,
      duration: ttsBody.duration || 0,
    };
  } catch (err) {
    console.error("❌ Scene audio/captions generation failed:", err);
    return null;
  }
}
