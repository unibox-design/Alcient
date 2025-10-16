import React from "react";
import { useSelector } from "react-redux";
import CaptionTemplatePicker from "./elements/CaptionTemplatePicker";

export default function ElementsPanel() {
  const captionsEnabled = useSelector((state) => state.project.captionsEnabled);

  return (
    <div className="p-4 text-sm text-gray-700 space-y-6 h-full overflow-y-auto">
      <header>
        <h2 className="text-base font-semibold text-gray-800">Elements</h2>
        <p className="text-xs text-gray-500 mt-1">
          Configure overlays that will appear across your generated scenes.
        </p>
      </header>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-gray-800">Caption templates</h3>
            <p className="text-xs text-gray-500">
              Choose how on-video captions should appear.
            </p>
          </div>
          <span
            className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-medium ${
              captionsEnabled
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : "bg-gray-100 text-gray-500 border border-gray-200"
            }`}
          >
            {captionsEnabled ? "Captions enabled" : "Captions disabled"}
          </span>
        </div>

        {captionsEnabled ? (
          <CaptionTemplatePicker />
        ) : (
          <p className="text-xs text-gray-500">
            Enable captions from the Script panel to customize templates.
          </p>
        )}
      </section>
    </div>
  );
}
