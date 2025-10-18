import React, { useMemo } from "react";
import { CAPTION_TEMPLATE_MAP } from "../../lib/captions";

export default function CaptionOverlay({ enabled, templateId, captions, segments, currentTime }) {
  const captionWords = Array.isArray(captions) ? captions : Array.isArray(segments) ? segments : [];

  const template = CAPTION_TEMPLATE_MAP[templateId] || CAPTION_TEMPLATE_MAP["calm-lower"];

  // 🧠 find the active word for current timestamp
  const activeWord = useMemo(() => {
    if (captionWords.length === 0) return null;
    const t = typeof currentTime === "number" ? currentTime : 0;
    return captionWords.find(w => t >= w.start && t <= w.end);
  }, [captionWords, currentTime]);

  if (!enabled || captionWords.length === 0) return null;

  // Helper function to check if a token is punctuation
  const isPunctuation = (token) => /^[.,!?;:]+$/.test(token);

  return (
    <div className="pointer-events-none absolute inset-0 flex items-end justify-center pb-10 px-6">
      <div
        className="max-w-xl w-full flex flex-col items-center"
        style={{ color: template.textColor }}
      >
        <div
          className="rounded-full px-6 py-3 text-sm font-semibold shadow-lg backdrop-blur flex flex-wrap justify-center"
          style={{
            background: `linear-gradient(135deg, ${template.gradient[0]}, ${template.gradient[1]})`,
            boxShadow: "0 18px 45px rgba(15, 23, 42, 0.25)",
          }}
        >
          {captionWords.map((wordObj, index) => {
            const isActive = activeWord && wordObj.start === activeWord.start && wordObj.end === activeWord.end;
            const nextToken = captionWords[index + 1]?.word || "";
            const addSpace = !isPunctuation(nextToken);
            return (
              <span
                key={index}
                className={isActive ? "font-bold" : ""}
                style={isActive ? {
                  textShadow: `0 0 8px ${template.gradient[1]}`,
                  WebkitTextFillColor: 'transparent',
                  background: `linear-gradient(135deg, ${template.gradient[0]}, ${template.gradient[1]})`,
                  WebkitBackgroundClip: 'text',
                  opacity: 1,
                  transform: 'translateY(0)',
                  transition: 'opacity 0.3s ease, transform 0.3s ease',
                  animation: 'pulseGlow 1.2s infinite ease-in-out, fadeIn 0.5s ease forwards',
                } : {
                  opacity: 0.7,
                  transform: 'translateY(2px)',
                  transition: 'opacity 0.3s ease, transform 0.3s ease',
                }}
              >
                {wordObj.word}{addSpace ? ' ' : ''}
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