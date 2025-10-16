import React from "react";
import { useDispatch, useSelector } from "react-redux";
import { CAPTION_TEMPLATES } from "../../lib/captions";
import { setCaptionTemplate } from "../../store/projectSlice";

export default function CaptionTemplatePicker() {
  const dispatch = useDispatch();
  const activeTemplate = useSelector((state) => state.project.captionTemplate);

  const handleSelect = (templateId) => {
    if (templateId !== activeTemplate) {
      dispatch(setCaptionTemplate(templateId));
    }
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
      {CAPTION_TEMPLATES.map((template) => {
        const isActive = template.id === activeTemplate;
        return (
          <button
            key={template.id}
            type="button"
            onClick={() => handleSelect(template.id)}
            className={`relative rounded-xl border p-4 text-left transition ${
              isActive
                ? "border-indigo-500 ring-2 ring-indigo-200 bg-white"
                : "border-gray-200 hover:border-gray-300 bg-white"
            }`}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-800">{template.name}</h3>
              {isActive && (
                <span className="text-[11px] font-medium text-indigo-600 uppercase tracking-wide">
                  Selected
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-gray-500 leading-snug">{template.description}</p>
            <div className="mt-4 h-16 rounded-lg overflow-hidden relative">
              <div
                className="absolute inset-0"
                style={{
                  background: `linear-gradient(135deg, ${template.gradient[0]}, ${template.gradient[1]})`,
                  opacity: 0.85,
                }}
              />
              <div className="absolute inset-0 flex items-center justify-center px-3">
                <span
                  className="text-sm font-semibold"
                  style={{ color: template.textColor }}
                >
                  Your caption preview
                </span>
              </div>
              <div
                className="absolute bottom-2 left-1/2 -translate-x-1/2 px-3 py-1 text-[10px] rounded-full shadow-sm"
                style={{
                  backgroundColor: template.accentColor,
                  color: template.textColor,
                  opacity: 0.88,
                }}
              >
                00:05 – 00:08
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
