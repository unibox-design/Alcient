export async function generateCaptions(audioUrl, text) {
  const response = await fetch("/api/captions/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ audioUrl, text }),
  });
  const data = await response.json();
  if (response.ok) return data;
  throw new Error(data.error || "Caption generation failed");
}