// src/components/SceneItem.jsx
import React from "react";

export default function SceneItem({ scene, onOpenReplace }) {
  // scene: { id, text, duration, media }
  return (
    <div className="bg-white rounded-lg shadow-sm border p-3 mb-3 flex items-start gap-3">
      <div className="w-36 h-20 bg-slate-100 rounded overflow-hidden flex-shrink-0 flex items-center justify-center">
        {scene.media?.thumbnail ? (
          <img src={scene.media.thumbnail} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="text-slate-400 text-sm">No clip</div>
        )}
      </div>

      <div className="flex-1">
        <div className="text-slate-800 font-medium">{scene.text}</div>
        <div className="text-xs text-slate-500 mt-2">
          {scene.duration}s • Voice: {scene.ttsVoice || "Default"}
        </div>
      </div>

      <div className="flex flex-col items-end gap-2">
        <button
          onClick={() => onOpenReplace(scene)}
          className="px-3 py-1 bg-slate-800 text-white rounded text-sm"
        >
          Replace clip
        </button>
        <div className="text-slate-400 text-xs">⋮</div>
      </div>
    </div>
  );
}
