// src/lib/mediaApi.js
const BASE = import.meta.env.VITE_BACKEND || "http://localhost:5000";

async function jsonFetch(url, opts = {}) {
  const res = await fetch(url, opts);
  const txt = await res.text();
  try { return { ok: res.ok, status: res.status, body: JSON.parse(txt) }; }
  catch (e) { return { ok: res.ok, status: res.status, body: txt }; }
}

export async function suggestClips({ sceneText = "", keywords = [], format = "landscape", page = 1 }) {
  // fallback to mock if backend not ready
  try {
    const { ok, body } = await jsonFetch(`${BASE}/api/media/suggest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sceneText, keywords, format, page }),
    });
    return ok ? (body.results || []) : [];
  } catch (err) {
    console.warn("suggestClips fallback", err);
    return []; // caller can handle empty
  }
}

export async function searchStock({ query = "", format = "landscape", page = 1 }) {
  try {
    const { ok, body } = await jsonFetch(`${BASE}/api/media/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, format, page }),
    });
    return ok ? (body.results || []) : [];
  } catch (err) {
    console.warn("searchStock fallback", err);
    return [];
  }
}

export async function uploadFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${BASE}/api/media/upload`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`upload failed ${res.status}`);
  return res.json(); // expects { mediaItem: {...} }
}

export async function attachMediaToScene({ projectId, sceneId, media }) {
  try {
    const res = await fetch(`${BASE}/api/project/${projectId}/scene/${sceneId}/media`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ media }),
    });
    return res.ok;
  } catch (e) {
    console.warn("attachMediaToScene failed", e);
    return false;
  }
}
