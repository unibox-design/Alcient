// src/components/ReplaceClipModal.jsx
import React, { useCallback, useEffect, useRef, useState } from "react";

/**
 * Props:
 *  - open: boolean
 *  - scene: { id, text, duration, media }
 *  - onClose(): void
 *  - onUse(mediaItem): void
 *  - projectId?: string
 *  - format?: "landscape" | "portrait" | "square"
 *  - backend: optional base url (defaults to env)
 */
export default function ReplaceClipModal({
  open,
  scene,
  onClose,
  onUse,
  projectId,
  format,
  backend,
}) {
  const BASE = backend || (import.meta.env.VITE_BACKEND || "http://localhost:5000");
  const targetFormat = format || "landscape";
  const thumbAspectClass =
    targetFormat === "portrait"
      ? "aspect-[9/16]"
      : targetFormat === "square"
        ? "aspect-square"
        : "aspect-video";
  const thumbHeightClass =
    targetFormat === "portrait"
      ? "max-h-48"
      : targetFormat === "square"
        ? "max-h-44"
        : "max-h-36";
  const thumbWidthClass =
    targetFormat === "portrait"
      ? "max-w-[180px]"
      : targetFormat === "square"
        ? "max-w-[220px]"
        : "max-w-[260px]";
  const [tab, setTab] = useState("suggested"); // suggested | stock | upload
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [page, setPage] = useState(1);
  const suggestAbortRef = useRef(null);
  const stockAbortRef = useRef(null);
  const [hoveredClipId, setHoveredClipId] = useState(null);
  const scenePrompt = scene?.visual || scene?.text || "";
  const sceneKeywords = scene?.keywords || [];

  useEffect(() => {
    if (!open) return;
    const initialQuery = scenePrompt;
    setQuery(initialQuery);
    setSelected(null);
    setResults([]);
    setPage(1);
    setTab("suggested");
  }, [open, scene, scenePrompt]);

  useEffect(() => {
    if (!open) return;
    const handleKey = (evt) => {
      if (evt.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  useEffect(() => () => {
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    if (stockAbortRef.current) stockAbortRef.current.abort();
  }, []);

  const changeTab = useCallback((nextTab) => {
    if (nextTab === tab) return;
    setTab(nextTab);
    setSelected(null);
    setResults([]);
    setPage(1);
  }, [tab]);

  const fetchSuggested = useCallback(async (rawQuery, p = 1, append = false) => {
    const q = (rawQuery || "").trim();
    if (!q && !scenePrompt) {
      setResults([]);
      setPage(1);
      return;
    }
    if (suggestAbortRef.current) suggestAbortRef.current.abort();
    const controller = new AbortController();
    suggestAbortRef.current = controller;
    setLoading(true);
    try {
      const res = await fetch(`${BASE}/api/media/suggest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sceneText: q || scenePrompt || "",
          keywords: sceneKeywords,
          format: targetFormat,
          page: p,
          projectId,
        }),
        signal: controller.signal,
      });
      const json = await res.json();
      const items = json.results || [];
      setResults((prev) => (append ? [...prev, ...items] : items));
      setHoveredClipId(null);
      setPage(p);
    } catch (e) {
      if (e.name === "AbortError") return;
      console.error("suggest fetch", e);
    } finally {
      if (suggestAbortRef.current === controller) {
        setLoading(false);
        suggestAbortRef.current = null;
      }
    }
  }, [BASE, projectId, sceneKeywords, scenePrompt, targetFormat]);

  const fetchStock = useCallback(async (rawQuery, p = 1, append = false) => {
    const q = (rawQuery || "").trim();
    if (!q || !q.trim()) {
      setResults([]);
      setPage(1);
      return;
    }
    if (stockAbortRef.current) stockAbortRef.current.abort();
    const controller = new AbortController();
    stockAbortRef.current = controller;
    setLoading(true);
    try {
      const res = await fetch(`${BASE}/api/media/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q,
          format: targetFormat,
          page: p,
        }),
        signal: controller.signal,
      });
      const json = await res.json();
      const items = json.results || [];
      setResults((prev) => (append ? [...prev, ...items] : items));
      setHoveredClipId(null);
      setPage(p);
    } catch (e) {
      if (e.name === "AbortError") return;
      console.error("stock fetch", e);
    } finally {
      if (stockAbortRef.current === controller) {
        setLoading(false);
        stockAbortRef.current = null;
      }
    }
  }, [BASE, targetFormat]);

  useEffect(() => {
    if (!open) return;
    if (tab === "suggested") {
      fetchSuggested(scenePrompt || query, 1, false);
    } else if (tab === "stock") {
      fetchStock(query || scenePrompt || "", 1, false);
    }
  }, [tab, open, scene, scenePrompt, query, fetchSuggested, fetchStock]);

  function onSearch(e) {
    e && e.preventDefault();
    if (tab === "stock") fetchStock(query || scenePrompt, 1);
    else fetchSuggested(query || scenePrompt, 1);
  }

  function handleSelect(item) {
    setSelected(item);
  }

  async function handleUse() {
    if (!selected) return;
    onUse(selected);
    onClose();
  }

  // Upload
  const handleFileUpload = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    setLoading(true);
    try {
      const res = await fetch(`${BASE}/api/media/upload`, { method: "POST", body: fd });
      const json = await res.json();
      if (json.mediaItem) {
        setResults(prev => [json.mediaItem, ...(prev || [])]);
        setSelected(json.mediaItem);
        if (json.mediaItem.id) setHoveredClipId(json.mediaItem.id);
      }
    } catch (e) {
      console.error("upload", e);
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-5xl bg-white rounded-lg shadow-xl max-h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b bg-white sticky top-0 z-10">
          <div>
            <div className="text-lg font-semibold">Replace clip</div>
            <div className="text-sm text-slate-500">{scene?.text}</div>
          </div>
          <div className="flex gap-2 items-center">
            <nav className="flex gap-2">
              <button
                type="button"
                onClick={() => changeTab("suggested")}
                className={`px-3 py-1 rounded ${tab === "suggested" ? "bg-slate-100" : ""}`}
              >
                Suggested
              </button>
              <button
                type="button"
                onClick={() => changeTab("stock")}
                className={`px-3 py-1 rounded ${tab === "stock" ? "bg-slate-100" : ""}`}
              >
                Stock
              </button>
              <button
                type="button"
                onClick={() => changeTab("upload")}
                className={`px-3 py-1 rounded ${tab === "upload" ? "bg-slate-100" : ""}`}
              >
                Upload
              </button>
            </nav>
            <button
              type="button"
              onClick={onClose}
              className="text-slate-500 hover:text-slate-700"
            >
              Close
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <form onSubmit={onSearch} className="flex gap-2 mb-4">
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search clips..."
              className="flex-1 border p-2 rounded"
            />
            <button
              type="submit"
              className="px-4 py-2 bg-gray-900 text-white rounded hover:bg-gray-700 transition"
            >
              Search
            </button>
          </form>

          {tab === "upload" ? (
            <div className="border border-dashed rounded p-6 text-center">
              <p className="mb-4">Upload a video file (mp4, webm)</p>
              <input type="file" accept="video/*,image/*" onChange={e => handleFileUpload(e.target.files[0])} />
              {loading && <div className="mt-4 text-sm text-slate-500">Uploading…</div>}
            </div>
          ) : (
            <div>
              <div className="flex flex-wrap gap-4 justify-start">
                {results.length === 0 && !loading && (
                  <div className="text-slate-500 text-center py-12 w-full">
                    No results yet. Try Search or switch tabs.
                  </div>
                )}
                {results.map((it) => {
                  const videoSrc = it.previewUrl || it.url;
                  const externalLink = it.pageUrl || it.attribution?.url || it.url;
                  const isHovered = hoveredClipId === it.id;
                  const hasExternalLink = Boolean(externalLink);
                  return (
                    <div
                      key={it.id}
                      className={`bg-slate-50 rounded overflow-hidden border transition hover:border-gray-300 flex flex-col ${thumbWidthClass} w-full sm:w-auto`}
                      onMouseEnter={() => setHoveredClipId(it.id)}
                      onMouseLeave={() => setHoveredClipId(null)}
                    >
                      <div
                        className={`relative w-full ${thumbAspectClass} ${thumbHeightClass} bg-black overflow-hidden`}
                      >
                        <img
                          src={it.thumbnail || it.url}
                          alt=""
                          className={`w-full h-full object-cover transition-opacity duration-200 ${
                            isHovered && videoSrc ? "opacity-0" : "opacity-100"
                          }`}
                          loading="lazy"
                        />
                        {isHovered && videoSrc && (
                          <video
                            key={`${it.id}-preview`}
                            src={videoSrc}
                            className="absolute inset-0 w-full h-full object-cover"
                            autoPlay
                            muted
                            loop
                            playsInline
                            preload="metadata"
                          />
                        )}
                        <div className="absolute top-2 right-2 bg-white/80 text-xs px-2 py-1 rounded">
                          {Math.round(it.duration || 0)}s
                        </div>
                        {selected?.id === it.id && (
                          <div className="absolute left-2 top-2 bg-emerald-600 text-white px-2 py-1 rounded text-xs">
                            Selected
                          </div>
                        )}
                      </div>
                      <div className="p-2 flex items-center justify-between gap-2 flex-wrap">
                        <div className="text-sm text-slate-700 truncate flex-1 min-w-[0]">
                          {it.attribution?.name || it.id}
                        </div>
                        <div className="flex gap-2 flex-shrink-0">
                          <button
                            type="button"
                            onClick={() => handleSelect(it)}
                            className={`px-2 py-1 text-sm rounded transition ${
                              selected?.id === it.id
                                ? "bg-emerald-600 text-white hover:bg-emerald-700"
                                : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                            }`}
                          >
                            {selected?.id === it.id ? "Using" : "Use"}
                          </button>
                          {hasExternalLink ? (
                            <a
                              href={externalLink}
                              target="_blank"
                              rel="noreferrer"
                              className="px-2 py-1 text-sm rounded bg-slate-100 text-slate-700 hover:bg-slate-200 transition"
                            >
                              Open
                            </a>
                          ) : (
                            <span className="px-2 py-1 text-sm rounded bg-slate-100 text-slate-400 cursor-not-allowed">
                              Open
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-4 flex justify-center">
                {loading ? (
                  <div className="text-sm text-slate-500">Loading...</div>
                ) : results.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => {
                      const next = page + 1;
                      if (tab === "stock") fetchStock(query || scenePrompt || "", next, true);
                      else fetchSuggested(query || scenePrompt || "", next, true);
                    }}
                    className="px-4 py-2 bg-slate-200 rounded hover:bg-slate-300 transition"
                  >
                    Load more
                  </button>
                ) : null}
              </div>
            </div>
          )}
        </div>

        <div className="px-5 py-4 border-t bg-white flex items-center justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 rounded border border-gray-300 hover:bg-gray-50 transition">Cancel</button>
          <button onClick={handleUse} disabled={!selected} className="px-4 py-2 bg-emerald-600 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-emerald-700 transition">Use clip</button>
        </div>
      </div>
    </div>
  );
}
