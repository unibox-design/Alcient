import React from "react";
import CaptionTemplatePicker from "./CaptionTemplatePicker";

export default function ElementsPanel() {
  return (
    <div className="p-4 text-sm text-gray-700 space-y-6 h-full overflow-y-auto">
      <header>
        <h2 className="text-base font-semibold text-gray-800">Elements</h2>
        <p className="text-xs text-gray-500 mt-1">
          Captions are now rendered directly into your final video.
        </p>
      </header>

      <section className="space-y-3 text-xs text-gray-500 bg-white border border-gray-200 rounded-lg p-4">
        <p>
          Styling and timing are handled automatically during rendering using the
          generated subtitle tracks. Choose a preset below to update the look.
        </p>
        <CaptionTemplatePicker />
      </section>
    </div>
  );
}
