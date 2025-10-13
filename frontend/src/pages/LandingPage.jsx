import React from "react";
import { useNavigate } from "react-router-dom";
import TemplateCard from "../components/TemplateCard";

const templates = [
  {
    id: "instant",
    title: "Instant",
    desc: "Auto-select clips from Pexels",
    color: "from-cyan-400 to-emerald-400",
  },
  {
    id: "generative",
    title: "Generative",
    desc: "AI-generated visuals & scenes",
    color: "from-indigo-400 to-purple-500",
  },
  {
    id: "upload",
    title: "Upload",
    desc: "Use your own footage",
    color: "from-pink-400 to-rose-500",
  },
  {
    id: "custom",
    title: "Custom",
    desc: "Build from scratch",
    color: "from-gray-400 to-gray-600",
  },
];

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 flex flex-col items-center justify-center px-6">
      <h1 className="text-4xl font-bold mb-12 text-gray-800">
        Alcient Video Studio
      </h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-8 w-full max-w-6xl">
        {templates.map((t) => (
          <TemplateCard
            key={t.id}
            {...t}
            onClick={() => navigate(`/project/${t.id}`)}
          />
        ))}
      </div>

      <footer className="mt-12 text-sm text-gray-400">
        © {new Date().getFullYear()} Alcient. All rights reserved.
      </footer>
    </div>
  );
}
