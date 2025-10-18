export async function generateCaptions(audioUrl, text) {
  try {
    const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/captions/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ audioUrl, text }),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Caption generation failed");
    return data.captions || [];
  } catch (err) {
    console.error("❌ Caption generation error:", err);
    return [];
  }
}