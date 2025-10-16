const BASE = import.meta.env.VITE_BACKEND || "http://localhost:5000";

function absoluteUrl(path) {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${BASE}${path}`;
}

async function jsonRequest(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
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

async function controlRender(jobId, action) {
  if (!jobId) {
    throw new Error("job id is required");
  }
  const endpoint = action === "cancel" ? "cancel" : "pause";
  const data = await jsonRequest(`${BASE}/api/project/render/${jobId}/${endpoint}`, {
    method: "POST",
  });
  if (data.videoUrl) data.videoUrl = absoluteUrl(data.videoUrl);
  return data;
}

export function cancelRender(jobId) {
  return controlRender(jobId, "cancel");
}

export function pauseRender(jobId) {
  return controlRender(jobId, "pause");
}

export async function saveProject(project) {
  const body = await jsonRequest(`${BASE}/api/project/save`, {
    method: "POST",
    body: JSON.stringify({ project }),
  });
  return body?.project;
}

export async function fetchProject(projectId) {
  const body = await jsonRequest(`${BASE}/api/project/${projectId}`);
  return body?.project;
}

export async function estimateRenderCost(project) {
  const body = await jsonRequest(`${BASE}/api/project/estimate-cost`, {
    method: "POST",
    body: JSON.stringify({ project }),
  });
  return body;
}
