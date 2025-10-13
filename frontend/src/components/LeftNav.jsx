import React from "react";
import { FileText, Film, Music, Layers } from "lucide-react";

const tabs = [
  { id: "script", icon: FileText, label: "Script" },
  { id: "scenes", icon: Film, label: "Scenes" },
  { id: "elements", icon: Layers, label: "Elements" },
  { id: "music", icon: Music, label: "Music" },
];

export default function LeftNav({ active, onChange }) {
  return (
    <nav className="flex flex-col items-center py-6 space-y-6">
      {tabs.map(({ id, icon: Icon, label }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`p-2 rounded-lg transition ${
            active === id
              ? "bg-gray-900 text-white"
              : "text-gray-500 hover:text-gray-900 hover:bg-gray-100"
          }`}
          title={label}
        >
          <Icon size={20} />
        </button>
      ))}
    </nav>
  );
}
