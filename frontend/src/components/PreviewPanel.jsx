import React, { useEffect, useRef } from "react";
import { useDispatch, useSelector } from "react-redux";
import { cancelRenderJob, fetchRenderStatus, pauseRenderJob } from "../store/projectSlice";

const ASPECT_CLASS = {
  landscape: "aspect-video",
  portrait: "aspect-[9/16]",
  square: "aspect-square",
};
const POLLING_STATUSES = ["queued", "rendering", "cancelling", "pausing"];

export default function PreviewPanel() {
  const dispatch = useDispatch();
  const format = useSelector((state) => state.project.format) || "landscape";
  const aspectClass = ASPECT_CLASS[format] || ASPECT_CLASS.landscape;
  const widthClass = format === "portrait" ? "w-1/2 max-w-[360px]" : "w-full";
  const renderState = useSelector((state) => state.project.render);
  const projectId = useSelector((state) => state.project.id);
  const videoRef = useRef(null);

  useEffect(() => {
    if (POLLING_STATUSES.includes(renderState.status) && renderState.jobId) {
      const payload = { jobId: renderState.jobId, projectId };
      dispatch(fetchRenderStatus(payload));
      const interval = setInterval(() => {
        dispatch(fetchRenderStatus(payload));
      }, 2000);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [dispatch, projectId, renderState.jobId, renderState.status]);

  const statusText = () => {
    switch (renderState.status) {
      case "queued":
        return "Render queued…";
      case "rendering":
        return "Rendering in progress…";
      case "cancelling":
        return "Stopping render…";
      case "cancelled":
        return "Render stopped";
      case "pausing":
        return "Pausing render…";
      case "paused":
        return "Render paused";
      case "failed":
        return renderState.error || "Render failed";
      case "dirty":
        return "Preview needs regeneration";
      default:
        return "Video Preview";
    }
  };

  const isControlInProgress = ["cancelling", "pausing"].includes(renderState.status);
  const canStop =
    !!renderState.jobId &&
    ["queued", "rendering", "cancelling", "pausing"].includes(renderState.status);
  const canPause =
    !!renderState.jobId && ["rendering", "pausing"].includes(renderState.status);

  const isRenderingActive = ["queued", "rendering"].includes(renderState.status);
  const calmMessage =
    "This may take a minute. Inhale, exhale—we're assembling your preview.";

  const handleStop = () => {
    if (!renderState.jobId) return;
    dispatch(cancelRenderJob());
  };

  const handlePause = () => {
    if (!renderState.jobId) return;
    dispatch(pauseRenderJob());
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-6">
      <style>
        {`@keyframes previewBlobSpin {
            0% { transform: rotate(0deg) scale(1); }
            50% { transform: rotate(90deg) scale(1.05); }
            100% { transform: rotate(180deg) scale(1); }
          }
          @keyframes previewBlobPulse {
            0%,100% { transform: scale(1); opacity: 0.8; }
            50% { transform: scale(1.08); opacity: 1; }
          }`}
      </style>
      {renderState.status === "completed" && renderState.videoUrl ? (
        <div className={`relative ${aspectClass} ${widthClass}`}>
          <video
            key={renderState.videoUrl}
            ref={videoRef}
            controls
            className="absolute inset-0 h-full w-full rounded-lg shadow-lg bg-black"
          >
            <source src={renderState.videoUrl} type="video/mp4" />
            Your browser does not support the video tag.
          </video>
        </div>
      ) : (
        <div
          className={`${aspectClass} ${widthClass} bg-gray-50 rounded-lg shadow-inner relative overflow-hidden flex flex-col`}
        >
          {isRenderingActive && (
            <>
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div
                  className="h-32 w-32 rounded-[40%] bg-gradient-to-br from-indigo-400 via-sky-300 to-purple-400 opacity-70 blur-md"
                  style={{ animation: "previewBlobPulse 4s ease-in-out infinite" }}
                />
              </div>
              <div
                className="absolute inset-0 flex items-center justify-center pointer-events-none"
                style={{ animation: "previewBlobSpin 10s linear infinite" }}
              >
                <div className="h-24 w-24 rounded-[45%] bg-gradient-to-br from-purple-500 via-rose-400 to-amber-300 opacity-60 blur-sm" />
              </div>
            </>
          )}
          {isRenderingActive ? (
            <div className="flex-1 w-full flex items-end justify-center px-6 pb-6">
              <div className="relative z-10 text-center text-sm text-gray-600">
                {calmMessage}
              </div>
            </div>
          ) : (
            <div className="relative z-10 flex-1 flex items-center justify-center px-4 text-gray-600 text-sm text-center">
              {statusText()}
            </div>
          )}
        </div>
      )}
      <div className="mt-3 text-xs text-gray-500 text-center">
        {renderState.status === "completed" && renderState.videoUrl
          ? "Rendered preview"
          : renderState.status === "failed"
            ? "Please adjust the storyboard and try again."
            : renderState.status === "paused"
              ? "Resume when you’re ready by regenerating the preview."
              : renderState.status === "cancelled"
                ? "Render was stopped. Adjust your storyboard and start again."
                : "Regenerate the video after edits to update the preview."}
      </div>
      {canStop && (
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={handleStop}
            disabled={isControlInProgress}
            className={`rounded-md px-3 py-1.5 text-xs font-medium border transition ${
              isControlInProgress
                ? "border-gray-200 bg-gray-100 text-gray-400 cursor-not-allowed"
                : "border-red-300 bg-white text-red-600 hover:bg-red-50"
            }`}
          >
            {renderState.status === "cancelling" ? "Stopping…" : "Stop render"}
          </button>
          <button
            type="button"
            onClick={handlePause}
            disabled={isControlInProgress || !canPause}
            className={`rounded-md px-3 py-1.5 text-xs font-medium border transition ${
              isControlInProgress || !canPause
                ? "border-gray-200 bg-gray-100 text-gray-400 cursor-not-allowed"
                : "border-amber-300 bg-white text-amber-600 hover:bg-amber-50"
            }`}
          >
            {renderState.status === "pausing" ? "Pausing…" : "Pause render"}
          </button>
        </div>
      )}
    </div>
  );
}
