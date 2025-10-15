const BASE = import.meta.env.VITE_BACKEND || "http://localhost:5000";

export async function enrichScenesMetadata({ format = "landscape", scenes = [] }) {
  const res = await fetch(`${BASE}/api/scenes/enrich`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ format, scenes }),
  });
  const body = await res.json();
  if (!res.ok) {
    const error = body?.error || `Failed to enrich scenes (${res.status})`;
    throw new Error(error);
  }
  return body;
}
