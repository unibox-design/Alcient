export const DEFAULT_CAPTION_TEMPLATE = "calm-lower";

export const CAPTION_TEMPLATE_MAP = {
  "calm-lower": {
    id: "calm-lower",
    name: "Calm Lower",
    gradient: ["rgba(30, 64, 175, 0.65)", "rgba(147, 197, 253, 0.85)"],
    textColor: "#ffffff",
  },
  "bold-center": {
    id: "bold-center",
    name: "Bold Center",
    gradient: ["rgba(236, 72, 153, 0.7)", "rgba(253, 186, 116, 0.85)"],
    textColor: "#ffffff",
  },
};

export const CAPTION_TEMPLATES = Object.values(CAPTION_TEMPLATE_MAP);

const COALESCE_TIME = (value, fallback = 0) => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const parsed = parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normaliseCaption = (caption, idx, listLength) => {
  if (!caption) return null;
  const text = (caption.text || caption.word || "").trim();
  if (!text) return null;

  const start = COALESCE_TIME(caption.start, 0);
  let end = COALESCE_TIME(caption.end, null);
  if (end == null || end <= start) {
    const nextStart = listLength > idx + 1 ? COALESCE_TIME(caption.nextStart, null) : null;
    if (nextStart != null && nextStart > start) {
      end = nextStart;
    } else {
      end = start + 0.2;
    }
  }

  return {
    id: caption.id || `caption-${idx}`,
    text,
    start,
    end,
    sceneId: caption.sceneId || null,
  };
};

export const normaliseCaptionWords = (captions = []) => {
  if (!Array.isArray(captions)) return [];
  const enriched = captions
    .map((current, index) => {
      const nextStart = captions[index + 1]?.start ?? null;
      return normaliseCaption({ ...current, nextStart }, index, captions.length);
    })
    .filter(Boolean)
    .map((cap) => ({
      ...cap,
      start: Math.max(0, Math.round(cap.start * 1000) / 1000),
      end: Math.max(0, Math.round(cap.end * 1000) / 1000),
    }))
    .sort((a, b) => a.start - b.start);
  return enriched;
};

export const buildProjectCaptionTimeline = (scenes = []) => {
  if (!Array.isArray(scenes) || !scenes.length) return [];
  const orderedScenes = [...scenes]
    .filter(Boolean)
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

  let offset = 0;
  const timeline = [];

  orderedScenes.forEach((scene, idx) => {
    const sceneCaptions = normaliseCaptionWords(scene.captions || []);

    sceneCaptions.forEach((caption, capIdx) => {
      const start = caption.start + offset;
      const end = caption.end + offset;
      timeline.push({
        id: `${scene.id || idx}-${capIdx}`,
        text: caption.text,
        start,
        end,
        sceneId: scene.id,
        order: scene.order ?? idx,
      });
    });

    const lastCaptionEnd = sceneCaptions.length
      ? sceneCaptions[sceneCaptions.length - 1].end
      : 0;
    const sceneDuration =
      typeof scene.duration === "number" && scene.duration > 0
        ? scene.duration
        : typeof scene.audioDuration === "number" && scene.audioDuration > 0
          ? scene.audioDuration
          : lastCaptionEnd;
    offset += Math.max(sceneDuration, lastCaptionEnd);
  });

  return timeline.sort((a, b) => a.start - b.start);
};
