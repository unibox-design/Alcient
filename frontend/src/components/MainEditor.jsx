import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { MoreVertical, Trash2, Image, Volume2 } from "lucide-react";

import {
  addScene,
  removeScene,
  selectScene,
  setSceneMedia,
  updateSceneText,
  triggerRender,
} from "../store/projectSlice";
import ReplaceClipModal from "./ReplaceClipModal";

export default function MainEditor({ active }) {
  const dispatch = useDispatch();
  const projectId = useSelector((state) => state.project.id);
  const projectTitle = useSelector((state) => state.project.title);
  const format = useSelector((state) => state.project.format);
  const voiceModel = useSelector((state) => state.project.voiceModel);
  const runtimeSeconds = useSelector((state) => state.project.runtimeSeconds);
  const scenes = useSelector((state) => state.project.scenes);
  const projectStatus = useSelector((state) => state.project.status);
  const selectedSceneId = useSelector((state) => state.project.selectedSceneId);
  const renderState = useSelector((state) => state.project.render);
  const mediaSuggest = useSelector((state) => state.project.mediaSuggest);
  const sceneEnrich = useSelector((state) => state.project.sceneEnrich);
  const isDirty = useSelector((state) => state.project.isDirty);
  const [replaceSceneId, setReplaceSceneId] = useState(null);
  const [hoveredSceneId, setHoveredSceneId] = useState(null);
  const textareaRefs = useRef({});

  const replaceScene = useMemo(
    () => scenes.find((s) => s.id === replaceSceneId) || null,
    [replaceSceneId, scenes]
  );

  const isScriptOrScenes = active === "script" || active === "scenes";
  const isRendering = ["queued", "rendering"].includes(renderState.status);
  const hasRendered = Boolean(renderState.videoUrl);
  const isFailed = renderState.status === "failed";
  const isScenePipelineRunning =
    projectStatus === "loading" ||
    sceneEnrich.status === "loading" ||
    mediaSuggest.status === "loading";
  const showGeneratingState = isScenePipelineRunning;
  const showSceneList = !showGeneratingState && scenes.length > 0;
  const showEmptyState = !showGeneratingState && scenes.length === 0;
  const generateButtonDisabled =
    isRendering ||
    isScenePipelineRunning ||
    scenes.length === 0 ||
    (!isDirty && !["failed", "dirty"].includes(renderState.status));
  const buttonLabel = isRendering
    ? "Rendering…"
    : isFailed
      ? "Retry render"
      : hasRendered
        ? "Regenerate video"
        : "Generate video";

  useEffect(() => {
    if (renderState.autoTrigger && scenes.length > 0 && !isRendering) {
      dispatch(triggerRender());
    }
  }, [renderState.autoTrigger, scenes.length, isRendering, dispatch]);

  const handleAddScene = () => {
    dispatch(
      addScene({
        text: "New scene text here...",
        duration: 5,
      })
    );
  };

  const handleDeleteScene = (id) => {
    dispatch(removeScene(id));
  };

  const handleSelectScene = (id) => {
    dispatch(selectScene(id));
  };

  const handleOpenReplace = (sceneId) => {
    setReplaceSceneId(sceneId);
  };

  const handleRegenerate = () => {
    dispatch(triggerRender());
  };

  const handleHoverStart = (sceneId) => setHoveredSceneId(sceneId);
  const handleHoverEnd = () => setHoveredSceneId(null);

  const adjustTextareaHeight = useCallback((textarea) => {
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }, []);

  const getTextareaRef = useCallback(
    (sceneId) => (el) => {
      if (!el) {
        delete textareaRefs.current[sceneId];
        return;
      }
      textareaRefs.current[sceneId] = el;
      adjustTextareaHeight(el);
    },
    [adjustTextareaHeight]
  );

  const handleSceneTextChange = useCallback(
    (sceneId) => (e) => {
      adjustTextareaHeight(e.target);
      dispatch(updateSceneText({ id: sceneId, text: e.target.value }));
    },
    [adjustTextareaHeight, dispatch]
  );

  useEffect(() => {
    scenes.forEach((scene) => {
      const textarea = textareaRefs.current[scene.id];
      if (textarea) {
        adjustTextareaHeight(textarea);
      }
    });
  }, [scenes, adjustTextareaHeight]);

  const handleUseClip = (media) => {
    if (!replaceSceneId) return;
    dispatch(setSceneMedia({ id: replaceSceneId, media }));
    setReplaceSceneId(null);
  };

  const handleCloseModal = () => setReplaceSceneId(null);

  if (!isScriptOrScenes) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        Select "Script" or "Scenes" to start editing.
      </div>
    );
  }

  const totalSceneDuration = scenes.reduce(
    (sum, scene) => sum + (Number(scene.duration) || 0),
    0
  );
  const actualRuntime = runtimeSeconds ?? totalSceneDuration;

  const formattedAspect =
    format === "portrait" ? "9:16" : format === "square" ? "1:1" : "16:9";
  const thumbAspectClass =
    format === "portrait" ? "aspect-[9/16]" : format === "square" ? "aspect-square" : "aspect-video";
  const thumbWidthClass = format === "portrait" ? "w-22" : "w-32";

  const formatDuration = (seconds) => {
    if (!seconds) return "0s";
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return secs ? `${mins}m ${secs}s` : `${mins}m`;
  };

  return (
    <>
      <style>
        {`@keyframes alcientGradientBorder {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
          }`}
      </style>
      <div className="flex h-full min-h-0 flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="min-w-[200px]">
            <h2 className="text-lg font-semibold text-gray-800">Storyboard</h2>
            <p className="text-sm text-gray-500">
              Aspect {formattedAspect} · Voice {voiceModel}
              {actualRuntime ? ` · Runtime ${formatDuration(actualRuntime)}` : ""}
            </p>
            {projectTitle && (
              <p className="text-sm text-gray-700 mt-1">{projectTitle}</p>
            )}
            {renderState.status === "dirty" && (
              <p className="text-xs text-amber-600 mt-2">
                Preview out of date. Regenerate to view latest changes.
              </p>
            )}
            {renderState.status === "failed" && renderState.error && (
              <p className="text-xs text-red-600 mt-2">{renderState.error}</p>
            )}
            {sceneEnrich.status === "loading" && (
              <p className="text-xs text-gray-400 mt-2">Optimizing scene keywords…</p>
            )}
            {sceneEnrich.status === "failed" && sceneEnrich.error && (
              <p className="text-xs text-red-500 mt-2">{sceneEnrich.error}</p>
            )}
            {sceneEnrich.status === "succeeded" && sceneEnrich.source && (
              <p className="text-xs text-gray-400 mt-2">
                Keyword source: {sceneEnrich.source === "llm" ? "LLM" : sceneEnrich.source === "mixed" ? "LLM + fallback" : "fallback"}
              </p>
            )}
            {mediaSuggest.status === "loading" && (
              <p className="text-xs text-gray-400 mt-2">Selecting stock clips…</p>
            )}
            {mediaSuggest.status === "failed" && mediaSuggest.error && (
              <p className="text-xs text-red-500 mt-2">
                {mediaSuggest.error}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRegenerate}
            disabled={generateButtonDisabled}
            className={`px-3 py-1.5 text-sm rounded-lg transition ${
              generateButtonDisabled
                ? "bg-gray-200 text-gray-400 cursor-not-allowed"
                : "bg-gray-900 text-white hover:bg-gray-700"
            }`}
          >
            {buttonLabel}
          </button>
          <button
            onClick={handleAddScene}
            className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-100 transition"
          >
            + Add Scene
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-4">
        {showGeneratingState && (
          <div className="relative rounded-xl">
            <div
              className="rounded-xl p-[2px]"
              style={{
                background: "linear-gradient(120deg, #6366f1, #ec4899, #22d3ee, #6366f1)",
                backgroundSize: "300% 300%",
                animation: "alcientGradientBorder 6s linear infinite",
              }}
            >
              <div className="rounded-[0.7rem] bg-white/95 p-8 text-center text-gray-600 shadow-sm">
                <p className="text-base font-medium">Generating scenes…</p>
                <p className="mt-2 text-sm text-gray-500">
                  Crafting storyboard · Optimizing keywords · Sourcing reference clips
                </p>
                <div className="mt-4 flex items-center justify-center gap-2 text-xs text-gray-400">
                  <span className="inline-block h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
                  <span>Working with the scene generator…</span>
                </div>
              </div>
            </div>
          </div>
        )}
        {showEmptyState && (
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center text-gray-500">
            No scenes yet. Use the script sidebar to generate them.
          </div>
        )}
        {showSceneList ? (
          scenes.map((scene) => {
            const isSelected = scene.id === selectedSceneId;
            return (
              <div
                key={scene.id}
                onClick={() => handleSelectScene(scene.id)}
                className={`bg-white border rounded-lg shadow-sm p-4 flex items-start gap-4 transition hover:border-gray-300 cursor-pointer ${
                  isSelected ? "border-gray-900" : "border-gray-200"
                }`}
              >
                <div
                  className={`${thumbWidthClass} ${thumbAspectClass} bg-gray-100 rounded-md flex items-center justify-center text-gray-400 text-xs relative overflow-hidden`}
                  onMouseEnter={() => handleHoverStart(scene.id)}
                  onMouseLeave={handleHoverEnd}
                >
                  {scene.media?.thumbnail ? (
                    <>
                      <img
                        src={scene.media.thumbnail}
                        alt=""
                        className={`w-full h-full object-cover transition-opacity ${
                          hoveredSceneId === scene.id ? "opacity-0" : "opacity-100"
                        }`}
                        loading="lazy"
                      />
                      {hoveredSceneId === scene.id && scene.media?.url && (
                        <video
                          key={scene.media.id || scene.id}
                          src={scene.media.previewUrl || scene.media.url}
                          className="absolute inset-0 w-full h-full object-cover"
                          autoPlay
                          muted
                          loop
                          playsInline
                          preload="metadata"
                        />
                      )}
                    </>
                  ) : (
                    <>
                      <Image size={20} />
                      <span className="absolute bottom-1 text-[10px] text-gray-400">
                        No clip
                      </span>
                    </>
                  )}
                </div>

                <div className="flex-1">
                  <textarea
                    value={scene.text || ""}
                    onChange={handleSceneTextChange(scene.id)}
                    ref={getTextareaRef(scene.id)}
                    className="w-full text-sm text-gray-700 border-none bg-transparent focus:outline-none resize-none overflow-hidden"
                    rows={1}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
                    <div className="flex items-center gap-4">
                      <span>{`${scene.duration ?? 0}s`}</span>
                      <span className="flex items-center gap-1">
                        <Volume2 size={14} /> {scene.ttsVoice || voiceModel || "Default"}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenReplace(scene.id);
                        }}
                        className="text-gray-400 hover:text-gray-700"
                        title="Replace clip"
                      >
                        <Image size={16} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteScene(scene.id);
                        }}
                        className="text-gray-400 hover:text-red-500"
                        title="Delete scene"
                      >
                        <Trash2 size={16} />
                      </button>
                      <button
                        onClick={(e) => e.stopPropagation()}
                        className="text-gray-400 hover:text-gray-700"
                        title="More options"
                      >
                        <MoreVertical size={16} />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            );
          })
        ) : null}
      </div>

      <ReplaceClipModal
        open={Boolean(replaceScene)}
        scene={replaceScene}
        projectId={projectId}
        format={format}
        onClose={handleCloseModal}
        onUse={handleUseClip}
      />
      </div>
    </>
  );
}
