import React, { useMemo } from "react";
import { CAPTION_TEMPLATE_MAP } from "../../lib/captions";

export default function CaptionOverlay({
  enabled,
  templateId,
  segments,
  currentTime,
}) {
  const template = CAPTION_TEMPLATE_MAP[templateId] || CAPTION_TEMPLATE_MAP["calm-lower"];

  const activeSegment = useMemo(() => {
    if (!Array.isArray(segments) || !segments.length) return null;
    const time = typeof currentTime === "number" ? currentTime : 0;
    return (
      segments.find((segment) => {
        if (!segment) return false;
        const start = segment.start ?? 0;
        const end = segment.end ?? start;
        return time >= start && time <= end;
      }) || segments[segments.length - 1]
    );
  }, [segments, currentTime]);

  if (!enabled || !activeSegment || !activeSegment.text) {
    return null;
  }

  return (
    <div className="pointer-events-none absolute inset-0 flex items-end justify-center pb-10 px-6">
      <div
        className="max-w-xl w-full flex flex-col items-center"
        style={{ color: template.textColor }}
      >
        <div
          className="rounded-full px-6 py-3 text-sm font-semibold shadow-lg backdrop-blur"
          style={{
            background: `linear-gradient(135deg, ${template.gradient[0]}, ${template.gradient[1]})`,
            boxShadow: "0 18px 45px rgba(15, 23, 42, 0.25)",
          }}
        >
          {activeSegment.text}
        </div>
      </div>
    </div>
  );
}
