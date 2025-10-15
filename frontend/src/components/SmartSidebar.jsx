import React, { useEffect, useMemo, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import {
  enrichSceneMetadata,
  autofillSceneMedia,
  generateProjectFromPrompt,
  initProject,
  setDurationSeconds,
  setVoiceModel,
} from "../store/projectSlice";
import { estimateSpeechDuration } from "../lib/speech";

const tabCopy = {
  scenes: "Manage your scenes — order, duration, thumbnails.",
  elements: "Add overlays, titles, or graphics.",
  music: "Select and preview background tracks.",
};

const MANUAL_SCRIPT_CHAR_LIMIT = 4000;

export default function SmartSidebar({ active }) {
  const dispatch = useDispatch();
  const project = useSelector((state) => state.project);
  const format = project.format;
  const projectId = project.id;
  const status = useSelector((state) => state.project.status);
  const error = useSelector((state) => state.project.error);
  const promptFromState = useSelector((state) => state.project.prompt);
  const voiceModel = useSelector((state) => state.project.voiceModel);
  const durationSeconds = useSelector((state) => state.project.durationSeconds);
  const [prompt, setPrompt] = useState(promptFromState || "");
  const [mode, setMode] = useState("generate"); // generate | manual
  const [selectedFormat, setSelectedFormat] = useState(format);
  const [manualError, setManualError] = useState("");

  useEffect(() => {
    setPrompt(promptFromState || "");
    setManualError("");
  }, [promptFromState]);

  useEffect(() => {
    setSelectedFormat(format || "landscape");
  }, [format]);

  const aspectOptions = useMemo(
      () => [
        { label: "16:9", value: "landscape" },
        { label: "9:16", value: "portrait" },
      ],
      []
    );

  const voiceOptions = useMemo(
    () => [
      "Lady Holiday",
      "Golden Narrator",
      "Calm Documentary",
      "Energetic Host",
      "Warm Storyteller",
    ],
    []
  );

  const baseDurationOptions = useMemo(
    () => [
      { label: "1 min", value: 60 },
      { label: "3 min", value: 180 },
      { label: "5 min", value: 300 },
    ],
    []
  );

  const handleAspectChange = (value) => {
    setSelectedFormat(value);
  };

  const handleVoiceChange = (value) => {
    dispatch(setVoiceModel(value));
  };

  const handleDurationChange = (value) => {
    dispatch(setDurationSeconds(value));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    const trimmed = prompt.trim();
    setManualError("");
    if (!trimmed || status === "loading") return;

    if (mode === "generate") {
      dispatch(
        generateProjectFromPrompt({
          prompt: trimmed,
          format: selectedFormat,
          projectId,
          voiceModel,
          durationSeconds,
        })
      );
    } else {
      if (trimmed.length > MANUAL_SCRIPT_CHAR_LIMIT) {
        setManualError(
          `Script is too long. Please limit to ${MANUAL_SCRIPT_CHAR_LIMIT} characters (~5 minutes of narration).`
        );
        return;
      }

      const blocks = trimmed.split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
      const segments = blocks.length > 0 ? blocks : [trimmed];
      let totalEstimate = 0;
      const scenes = segments.map((text, idx) => {
        const estimated = estimateSpeechDuration(text, voiceModel);
        totalEstimate += estimated;
        return {
          text,
          duration: Math.max(3, Math.round(estimated)),
          audioDuration: Math.round(estimated * 100) / 100,
          ttsVoice: voiceModel,
          media: null,
          keywords: [],
          order: idx,
          visual: null,
          script: text,
        };
      });
      dispatch(
        initProject({
          id: projectId,
          title: project.title,
          format: selectedFormat,
          prompt: trimmed,
          narration: trimmed,
          keywords: [],
          voiceModel,
          durationSeconds,
          runtimeSeconds: Math.round(totalEstimate * 100) / 100,
          scenes,
        })
      );
      dispatch(enrichSceneMetadata())
        .unwrap()
        .catch(() => null)
        .finally(() => {
          dispatch(autofillSceneMedia());
        });
    }
  };

  if (active !== "script") {
    return (
      <div className="p-4 text-sm text-gray-600">
        <h2 className="text-gray-800 font-semibold mb-2 capitalize">
          {active}
        </h2>
        <p className="text-gray-500">{tabCopy[active]}</p>
      </div>
    );
  }

  const isLoading = status === "loading";
  const durationOptions = useMemo(() => {
    if (baseDurationOptions.some((opt) => opt.value === durationSeconds)) {
      return baseDurationOptions;
    }
    const minutes = Math.round((durationSeconds / 60) * 10) / 10;
    return [
      ...baseDurationOptions,
      {
        label: `${minutes} min`,
        value: durationSeconds,
      },
    ];
  }, [baseDurationOptions, durationSeconds]);

  return (
    <div className="p-4 text-sm text-gray-600 flex flex-col h-3/4 space-y-5">
      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">Aspect ratio</h2>
          <div className="mt-2 flex gap-2">
            {aspectOptions.map((option) => {
              const isActive = selectedFormat === option.value;
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleAspectChange(option.value)}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                    isActive
                      ? "border-gray-900 bg-gray-900 text-white"
                      : "border-gray-200 bg-white text-gray-600 hover:border-gray-400"
                  }`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>

        <nav className="flex gap-2 text-xs font-medium text-gray-500">
          {["generate", "manual"].map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => {
                setMode(key);
                setManualError("");
              }}
              className={`rounded-lg px-3 py-1.5 transition ${
                mode === key
                  ? "bg-slate-800 text-white"
                  : "bg-slate-100 text-gray-600 hover:bg-slate-200"
              }`}
            >
              {key === "generate" ? "Generate script" : "Enter script"}
            </button>
          ))}
        </nav>
      </section>

      <form onSubmit={handleSubmit} className="space-y-4 flex-1 flex flex-col">
        <textarea
          value={prompt}
          onChange={(e) => {
            setPrompt(e.target.value);
            setManualError("");
          }}
          placeholder={
            mode === "generate"
              ? "Enter your topic or talking points. We’ll turn them into a script."
              : "Paste your ready-made script here. Separate scenes with blank lines."
          }
          className="w-full flex-1 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700 shadow-inner focus:border-gray-400 focus:outline-none focus:ring-0 min-h-[10px]"
        />
        {mode === "manual" && manualError && (
          <p className="text-xs text-red-500">{manualError}</p>
        )}

        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <label className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
              Voice
            </label>
            <select
              value={voiceModel}
              onChange={(e) => handleVoiceChange(e.target.value)}
              className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 focus:border-gray-400 focus:outline-none focus:ring-0"
            >
              {voiceOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-3">
            <label className="text-xs font-semibold text-gray-600 uppercase tracking-wide">
              Duration
            </label>
            <select
              value={durationSeconds}
              onChange={(e) => handleDurationChange(Number(e.target.value))}
              className="flex-1 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 focus:border-gray-400 focus:outline-none focus:ring-0"
            >
              {durationOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button
          type="submit"
          disabled={isLoading || !prompt.trim()}
          className="w-full rounded-md bg-gray-900 px-3 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-400"
        >
          {mode === "generate"
            ? isLoading
              ? "Generating…"
              : "Generate scenes"
            : "Generate script"}
        </button>
      </form>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
          {error}
        </div>
      )}
    </div>
  );
}
