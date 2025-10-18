import React from "react";
import { useDispatch, useSelector } from "react-redux";

import { setCaptionStyle } from "../store/projectSlice";

const STYLES = [
  {
    name: "Classic Clean",
    description: "Calm, highly readable line-by-line captions.",
  },
  {
    name: "Kinetic Pop",
    description: "Bold word-by-word bursts with strong outlines.",
  },
  {
    name: "Highlight Bar",
    description: "Karaoke-style line highlight with a soft bar.",
  },
  {
    name: "Outline Glow",
    description: "Neon word-by-word glow with dramatic borders.",
  },
  {
    name: "Subtitle Boxed",
    description: "Boxed lines with animated word emphasis.",
  },
];

export default function CaptionTemplatePicker({ className = "" }) {
  const dispatch = useDispatch();
  const selectedStyle =
    useSelector((state) => state.project.captionStyle) || "Classic Clean";

  const handleSelect = (name) => {
    dispatch(setCaptionStyle(name));
  };

  return (
    <div className={`flex flex-col gap-2 ${className}`.trim()}>
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        Caption Style
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {STYLES.map((style) => {
          const isActive = style.name === selectedStyle;
          return (
            <button
              key={style.name}
              type="button"
              onClick={() => handleSelect(style.name)}
              aria-pressed={isActive}
              className={`rounded-lg border px-3 py-2 text-left transition focus:outline-none focus:ring-2 focus:ring-indigo-400 ${
                isActive
                  ? "border-gray-900 bg-gray-900/5 shadow-sm"
                  : "border-gray-200 bg-white hover:border-gray-400"
              }`}
            >
              <div className="text-sm font-semibold text-gray-800">
                {style.name}
              </div>
              <div className="mt-1 text-xs text-gray-500 line-clamp-2">
                {style.description}
              </div>
              <div
                className={`mt-2 rounded-md px-2 py-1 text-[11px] font-medium ${
                  isActive
                    ? "bg-indigo-50 text-indigo-600"
                    : "bg-gray-50 text-gray-500"
                }`}
              >
                {isActive ? "Selected" : "Select"}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
