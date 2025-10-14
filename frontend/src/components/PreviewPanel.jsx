import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { fetchRenderStatus } from "../store/projectSlice";

const ASPECT_CLASS = {
  landscape: "aspect-video",
  portrait: "aspect-[9/16]",
  square: "aspect-square",
};

export default function PreviewPanel() {
  const dispatch = useDispatch();
  const format = useSelector((state) => state.project.format) || "landscape";
  const aspectClass = ASPECT_CLASS[format] || ASPECT_CLASS.landscape;
  const widthClass = format === "portrait" ? "w-2/3 max-w-[260px]" : "w-full";
  const renderState = useSelector((state) => state.project.render);
  const projectId = useSelector((state) => state.project.id);

  useEffect(() => {
    if (["queued", "rendering"].includes(renderState.status) && renderState.jobId) {
      const payload = { jobId: renderState.jobId, projectId };
      dispatch(fetchRenderStatus(payload));
      const interval = setInterval(() => {
        dispatch(fetchRenderStatus(payload));
      }, 2000);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [dispatch, projectId, renderState.status, renderState.jobId]);

  const statusText = () => {
    switch (renderState.status) {
      case "queued":
        return "Render queued…";
      case "rendering":
        return `Rendering… ${renderState.progress ?? 0}%`;
      case "failed":
        return renderState.error || "Render failed";
      case "dirty":
        return "Preview needs regeneration";
      default:
        return "Video Preview";
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-full p-6">
      {renderState.status === "completed" && renderState.videoUrl ? (
        <video
          key={renderState.videoUrl}
          controls
          className={`${aspectClass} ${widthClass} rounded-lg shadow-lg bg-black`}
        >
          <source src={renderState.videoUrl} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      ) : (
        <div
          className={`${aspectClass} ${widthClass} bg-gray-200 rounded-lg shadow-inner flex items-center justify-center text-gray-500 text-sm text-center px-4`}
        >
          {statusText()}
        </div>
      )}
      <div className="mt-3 text-xs text-gray-500 text-center">
        {renderState.status === "completed" && renderState.videoUrl
          ? "Rendered preview"
          : renderState.status === "failed"
            ? "Please adjust the storyboard and try again."
            : "Regenerate the video after edits to update the preview."}
      </div>
    </div>
  );
}
