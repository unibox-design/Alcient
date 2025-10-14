const BASE = import.meta.env.VITE_BACKEND || "http://localhost:5000";

function absoluteUrl(path) {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${BASE}${path}`;
}

async function jsonRequest(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json();
  if (!res.ok) {
    const error = body?.error || res.statusText;
    throw new Error(error);
  }
  return body;
}

export async function triggerRender(project) {
  const data = await jsonRequest(`${BASE}/api/project/render`, {
    method: "POST",
    body: JSON.stringify({ project }),
  });
  if (data.videoUrl) data.videoUrl = absoluteUrl(data.videoUrl);
  return data;
}

export async function fetchRenderStatus(jobId, projectId) {
  if (!jobId) {
    throw new Error("job id is required");
  }
  let url = `${BASE}/api/project/render/${jobId}`;
  if (projectId) {
    const params = new URLSearchParams({ projectId });
    url = `${url}?${params.toString()}`;
  }
  const data = await jsonRequest(url);
  if (data.videoUrl) data.videoUrl = absoluteUrl(data.videoUrl);
  return data;
}
