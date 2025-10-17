import React, { useMemo, useState, useEffect } from "react";
import { CAPTION_TEMPLATE_MAP } from "../../lib/captions";

export default function CaptionOverlay({
  enabled,
  templateId,
  segments,
  currentTime,
  audioUrl,
}) {
  console.log("🧠 CaptionOverlay mounted", { enabled, audioUrl, segments });

  const template = CAPTION_TEMPLATE_MAP[templateId] || CAPTION_TEMPLATE_MAP["calm-lower"];
  const [wordTimestamps, setWordTimestamps] = useState(null);

  useEffect(() => {
    if (!audioUrl || !segments || !segments.length) {
      setWordTimestamps(null);
      return;
    }

    const text = segments.map(s => s.text).join(" ");

    async function fetchWordTimestamps() {
      try {
        const response = await fetch(`${process.env.REACT_APP_API_URL}/api/captions/generate`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ audioUrl, text }),
        });
        if (!response.ok) {
          setWordTimestamps(null);
          return;
        }
        const data = await response.json();
        if (Array.isArray(data) && data.length > 0) {
          setWordTimestamps(data);
        } else {
          setWordTimestamps(null);
        }
      } catch {
        setWordTimestamps(null);
      }
    }

    console.log("🎯 Fetching captions for", { audioUrl, segments });
    fetchWordTimestamps();
  }, [audioUrl, segments]);

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

  const activeWord = useMemo(() => {
    if (!wordTimestamps || !Array.isArray(wordTimestamps) || wordTimestamps.length === 0) return null;
    const time = typeof currentTime === "number" ? currentTime : 0;
    return wordTimestamps.find(({ start, end }) => time >= start && time <= end) || null;
  }, [wordTimestamps, currentTime]);

  if (!enabled || !activeSegment || !activeSegment.text) {
    return null;
  }

  // If word-level timestamps are available, highlight the current word within the full text
  if (wordTimestamps && activeWord) {
    // Build the caption with the active word highlighted
    // We will join all words with spaces, wrapping the active word in a span with highlight style
    const caption = wordTimestamps.map(({ word, start, end }, index) => {
      const isActive = activeWord.word === word && activeWord.start === start && activeWord.end === end;
      return (
        <span
          key={index}
          style={{
            fontWeight: isActive ? "700" : "400",
            color: isActive ? template.textColor : "inherit",
            textShadow: isActive ? "0 0 8px rgba(255, 255, 255, 0.75)" : "none",
          }}
        >
          {word + (index < wordTimestamps.length - 1 ? " " : "")}
        </span>
      );
    });

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
            {caption}
          </div>
        </div>
      </div>
    );
  }

  // Fallback to phrase-level captions if word-level timestamps are not available
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
