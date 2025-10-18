export const buildProjectCaptionTimeline = (scenes = []) => {
  if (!Array.isArray(scenes) || !scenes.length) return [];
  const orderedScenes = [...scenes]
    .filter(Boolean)
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

  let offset = 0;
  const timeline = [];

  orderedScenes.forEach((scene, idx) => {
    const sceneDuration =
      typeof scene.duration === "number" && scene.duration > 0
        ? scene.duration
        : typeof scene.audioDuration === "number" && scene.audioDuration > 0
          ? scene.audioDuration
          : 0;

    // 🧠 Normalize captions for both sentence-level and Whisper word-level data
    let sceneCaptions = Array.isArray(scene.captions) ? scene.captions : [];
    sceneCaptions = sceneCaptions.map((cap, i) => {
      if (!cap) return null;
      return {
        text: cap.text || cap.word || "",
        start: typeof cap.start === "number" ? cap.start : 0,
        end:
          typeof cap.end === "number"
            ? cap.end
            : i < sceneCaptions.length - 1
              ? sceneCaptions[i + 1]?.start ?? 0
              : (cap.start ?? 0) + 0.3, // fallback duration
      };
    }).filter(c => c && c.text);

    sceneCaptions.forEach((caption, capIdx) => {
      const start = caption.start + offset;
      const end = caption.end + offset;
      timeline.push({
        id: `${scene.id || idx}-${capIdx}`,
        text: caption.text.trim(),
        start,
        end,
        sceneId: scene.id,
        order: scene.order ?? idx,
      });
    });

    offset += sceneDuration;
  });

  return timeline;
};
