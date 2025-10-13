const VOICE_WPM = {
  "lady holiday": 150,
  "golden narrator": 145,
  "calm documentary": 140,
  "energetic host": 170,
  "warm storyteller": 155,
};

export function estimateSpeechDuration(text, voiceModel) {
  if (!text) return 2;
  const words = text.match(/[\w']+/g)?.length || 0;
  const sentences = text.match(/[.!?]/g)?.length || 1;
  const voiceKey = (voiceModel || "").toLowerCase();
  const wpm = Math.min(200, Math.max(100, VOICE_WPM[voiceKey] || 155));
  const base = (words || 1) / wpm * 60;
  const pauses = Math.min(3, sentences * 0.35);
  return Math.max(2, base + pauses);
}

export function estimateSpeechDurationRounded(text, voiceModel) {
  const raw = estimateSpeechDuration(text, voiceModel);
  return {
    raw,
    rounded: Math.max(3, Math.round(raw)),
  };
}
