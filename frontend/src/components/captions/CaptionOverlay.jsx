import React, { useMemo } from "react";
import { CAPTION_TEMPLATE_MAP, DEFAULT_CAPTION_TEMPLATE, normaliseCaptionWords } from "../../lib/captions";

const isPunctuation = (token = "") => /^[.,!?;:]+$/.test(token);

export default function CaptionOverlay({ enabled, templateId, captions, segments, currentTime }) {
  const isEnabled = enabled !== false;

  const captionWords = useMemo(() => {
    if (Array.isArray(segments) && segments.length) {
      return segments
        .map((word, index) => ({
          ...word,
          text: (word.text || word.word || "").trim(),
          start: typeof word.start === "number" ? word.start : parseFloat(word.start) || 0,
          end: typeof word.end === "number" ? word.end : parseFloat(word.end) || 0,
          key: word.id || `${word.sceneId || "segment"}-${index}`,
        }))
        .filter((word) => word.text)
        .sort((a, b) => a.start - b.start);
    }
    if (Array.isArray(captions) && captions.length) {
      return normaliseCaptionWords(captions);
    }
    return [];
  }, [segments, captions]);

  const template = CAPTION_TEMPLATE_MAP[templateId] || CAPTION_TEMPLATE_MAP[DEFAULT_CAPTION_TEMPLATE];

  const activeWord = useMemo(() => {
    if (!captionWords.length) return null;
    const t = typeof currentTime === "number" && !Number.isNaN(currentTime) ? currentTime : 0;
    return (
      captionWords.find((word) => {
        const start = word.start ?? 0;
        const end = word.end ?? start;
        if (t < start) return false;
        if (t >= end) return false;
        return true;
      }) || null
    );
  }, [captionWords, currentTime]);

  if (!isEnabled || !captionWords.length) {
    return null;
  }

  return (
    <div className="pointer-events-none absolute inset-0 flex items-end justify-center pb-10 px-6">
      <div className="max-w-xl w-full flex flex-col items-center" style={{ color: template.textColor }}>
        <div
          className="rounded-full px-6 py-3 text-sm font-semibold shadow-lg backdrop-blur flex flex-wrap justify-center"
          style={{
            background: `linear-gradient(135deg, ${template.gradient[0]}, ${template.gradient[1]})`,
            boxShadow: "0 18px 45px rgba(15, 23, 42, 0.25)",
          }}
        >
          {captionWords.map((wordObj, index) => {
            const nextToken = captionWords[index + 1]?.text;
            const addSpace = nextToken && !isPunctuation(nextToken);
            const isActive =
              activeWord && wordObj.start === activeWord.start && wordObj.end === activeWord.end;
            return (
              <span
                key={wordObj.key || `${index}-${wordObj.start}`}
                className={isActive ? "font-bold" : ""}
                style={
                  isActive
                    ? {
                        textShadow: `0 0 8px ${template.gradient[1]}`,
                        WebkitTextFillColor: "transparent",
                        background: `linear-gradient(135deg, ${template.gradient[0]}, ${template.gradient[1]})`,
                        WebkitBackgroundClip: "text",
                        opacity: 1,
                        transform: "translateY(0)",
                        transition: "opacity 0.3s ease, transform 0.3s ease",
                        animation: "pulseGlow 1.2s infinite ease-in-out, fadeIn 0.5s ease forwards",
                      }
                    : {
                        opacity: 0.7,
                        transform: "translateY(2px)",
                        transition: "opacity 0.3s ease, transform 0.3s ease",
                      }
                }
              >
                {wordObj.text}
                {addSpace ? " " : ""}
              </span>
            );
          })}
        </div>
      </div>
      <style>{`
        @keyframes pulseGlow {
          0%, 100% {
            text-shadow: 0 0 8px ${template.gradient[1]}, 0 0 12px ${template.gradient[1]};
          }
          50% {
            text-shadow: 0 0 12px ${template.gradient[1]}, 0 0 18px ${template.gradient[1]};
          }
        }
        @keyframes fadeIn {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}