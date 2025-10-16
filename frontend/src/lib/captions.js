export const CAPTION_TEMPLATES = [
  {
    id: "calm-lower",
    name: "Calm lower-third",
    description: "Soft rounded bar near the lower third with subtle gradient.",
    gradient: ["#6366f1", "#22d3ee"],
    textColor: "#ffffff",
    accentColor: "#1e293b",
  },
  {
    id: "bold-center",
    name: "Bold center highlight",
    description: "Pill-shaped highlight centered over the video with punchy colors.",
    gradient: ["#f97316", "#ec4899"],
    textColor: "#0f172a",
    accentColor: "#fdf2f8",
  },
];

export const DEFAULT_CAPTION_TEMPLATE = CAPTION_TEMPLATES[0].id;

export const CAPTION_TEMPLATE_MAP = CAPTION_TEMPLATES.reduce((map, template) => {
  map[template.id] = template;
  return map;
}, {});

/**
 * Convert per-scene caption arrays into a single timeline in project order.
 * Each scene is expected to have `order`, `duration`, and `captions` fields.
 */
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

    const sceneCaptions = Array.isArray(scene.captions) ? scene.captions : [];
    sceneCaptions.forEach((caption, capIdx) => {
      if (!caption || typeof caption.text !== "string") return;
      const start = (caption.start ?? 0) + offset;
      const end =
        (caption.end ?? caption.start ?? 0) + offset > start
          ? (caption.end ?? caption.start ?? 0) + offset
          : start + Math.max(sceneDuration / Math.max(sceneCaptions.length, 1), 0.5);
      timeline.push({
        id: `${scene.id || idx}-${caption.id || capIdx}`,
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
