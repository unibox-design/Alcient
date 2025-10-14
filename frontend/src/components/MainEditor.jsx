import React, { useEffect, useMemo, useState } from "react";
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
  const format = useSelector((state) => state.project.format);
  const voiceModel = useSelector((state) => state.project.voiceModel);
  const durationSeconds = useSelector((state) => state.project.durationSeconds);
  const runtimeSeconds = useSelector((state) => state.project.runtimeSeconds);
  const scenes = useSelector((state) => state.project.scenes);
  const selectedSceneId = useSelector((state) => state.project.selectedSceneId);
  const renderState = useSelector((state) => state.project.render);
  const isDirty = useSelector((state) => state.project.isDirty);
  const [replaceSceneId, setReplaceSceneId] = useState(null);
  const [hoveredSceneId, setHoveredSceneId] = useState(null);

  const replaceScene = useMemo(
    () => scenes.find((s) => s.id === replaceSceneId) || null,
    [replaceSceneId, scenes]
  );

  const isScriptOrScenes = active === "script" || active === "scenes";
  const isRendering = ["queued", "rendering"].includes(renderState.status);

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

  const handleTextChange = (id, text) => {
    dispatch(updateSceneText({ id, text }));
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
    <div className="flex h-full min-h-0 flex-col gap-4 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">Storyboard</h2>
          <p className="text-sm text-gray-500">
            Aspect {formattedAspect} · Voice {voiceModel} · Target {formatDuration(durationSeconds)}
            {actualRuntime ? ` · Planned runtime ${formatDuration(actualRuntime)}` : ""}
          </p>
          {renderState.status === "dirty" && (
            <p className="text-xs text-amber-600 mt-1">
              Preview out of date. Regenerate to view latest changes.
            </p>
          )}
          {renderState.status === "failed" && renderState.error && (
            <p className="text-xs text-red-600 mt-1">{renderState.error}</p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleAddScene}
            className="px-3 py-1.5 text-sm bg-gray-900 text-white rounded-lg hover:bg-gray-700 transition"
          >
            + Add Scene
          </button>
          <button
            onClick={handleRegenerate}
            disabled={
              isRendering || (!isDirty && !["failed", "dirty"].includes(renderState.status))
            }
            className={`px-3 py-1.5 text-sm rounded-lg transition border ${
              isRendering || (!isDirty && !["failed", "dirty"].includes(renderState.status))
                ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed"
                : "bg-white text-gray-700 border-gray-300 hover:bg-gray-100"
            }`}
          >
            {isRendering ? "Rendering…" : "Regenerate video"}
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-4">
        {scenes.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center text-gray-500">
            No scenes yet. Click “Add Scene” to begin.
          </div>
        ) : (
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
                    onChange={(e) => handleTextChange(scene.id, e.target.value)}
                    className="w-full text-sm text-gray-700 border-none bg-transparent focus:outline-none resize-none"
                    rows={2}
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

                    {/* {scene.keywords?.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {scene.keywords.map((kw) => (
                        <span
                          key={`${scene.id}-${kw}`}
                          className="rounded-full bg-gray-100 px-2.5 py-1 text-[11px] text-gray-600"
                        >
                          {kw}
                        </span>
                      ))}
                    </div>
                  )}

                  {scene.visual && (
                    <p
                      className="mt-3 text-xs text-gray-400"
                      onClick={(e) => e.stopPropagation()}
                    >
                      Visual cue: {scene.visual}
                    </p>
                  )} */}
                </div>
              </div>
            );
          })
        )}
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
  );
}
