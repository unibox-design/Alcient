import React from "react";

export default function TemplateCard({ id, title, desc, color, onClick }) {
  return (
    <div
      onClick={onClick}
      className="group relative cursor-pointer rounded-xl overflow-hidden bg-white border border-gray-200 hover:shadow-lg hover:-translate-y-1 transition-all duration-300"
    >
      <div
        className={`absolute inset-0 bg-gradient-to-br ${color} opacity-0 group-hover:opacity-10 transition-opacity`}
      />
      <div className="p-6 flex flex-col justify-between h-40">
        <div>
          <h2 className="text-lg font-semibold mb-2 text-gray-800">{title}</h2>
          <p className="text-sm text-gray-500">{desc}</p>
        </div>
        <span className="text-xs uppercase tracking-wide text-gray-400 mt-4">
          Click to start →
        </span>
      </div>
    </div>
  );
}
