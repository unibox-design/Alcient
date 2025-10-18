// src/store/projectSlice.js
import { createAsyncThunk, createSlice, nanoid } from "@reduxjs/toolkit";
import { estimateSpeechDuration } from "../lib/speech";
import {
  triggerRender as triggerRenderApi,
  fetchRenderStatus as fetchRenderStatusApi,
  cancelRender as cancelRenderApi,
  pauseRender as pauseRenderApi,
  saveProject as saveProjectApi,
  estimateRenderCost as estimateRenderCostApi,
} from "../lib/renderApi";
import { suggestClips } from "../lib/mediaApi";
import { enrichScenesMetadata } from "../lib/sceneApi";

const BASE = import.meta.env.VITE_BACKEND || "http://localhost:5000";

const normalizeNarration = (value) => {
  if (!value) return "";
  if (Array.isArray(value)) {
    return value.map((part) => String(part).trim()).filter(Boolean).join("\n\n");
  }
  if (typeof value === "string") return value;
  return String(value);
};

const markDirty = (state) => {
  state.isDirty = true;
  if (["completed", "idle", "dirty"].includes(state.render.status)) {
    state.render.status = "dirty";
  }
  if (state.render.status === "failed") {
    state.render.status = "dirty";
  }
  state.render.autoTrigger = false;
  state.render.progress = 0;
  if (state.costEstimate) {
    state.costEstimate.status = "stale";
  }
};


const buildProjectPayload = (project) => ({
  id: project.id,
  title: project.title,
  format: project.format,
  voiceModel: project.voiceModel,
  narration: project.narration,
  durationSeconds: project.durationSeconds,
  runtimeSeconds: project.runtimeSeconds,
  captionStyle: project.captionStyle,
  scenes: project.scenes.map((scene) => ({
    id: scene.id,
    text: scene.text,
    script: scene.script,
    media: scene.media,
    keywords: scene.keywords,
    ttsVoice: scene.ttsVoice,
    order: scene.order,
    audioDuration: scene.audioDuration,
  })),
});

export const generateProjectFromPrompt = createAsyncThunk(
  "project/generateFromPrompt",
  async ({ prompt, format, projectId, voiceModel, durationSeconds }, { rejectWithValue }) => {
    try {
      const res = await fetch(`${BASE}/api/project/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, format, projectId, voiceModel, durationSeconds }),
      });
      const body = await res.json();
      if (!res.ok) {
        return rejectWithValue(body);
      }
      return body;
    } catch (err) {
      return rejectWithValue({ error: err.message || "Failed to generate project" });
    }
  }
);

export const triggerRender = createAsyncThunk(
  "project/triggerRender",
  async (_, { getState, rejectWithValue }) => {
    try {
      const state = getState();
      const project = state.project;
      const payload = buildProjectPayload(project);
      if (!payload.scenes.length) {
        throw new Error("Add at least one scene before rendering");
      }
      await saveProjectApi(payload);
      const job = await triggerRenderApi(payload);
      return job;
    } catch (err) {
      return rejectWithValue({ error: err.message || "Render failed" });
    }
  }
);

export const estimateProjectCost = createAsyncThunk(
  "project/estimateProjectCost",
  async (_, { getState, rejectWithValue }) => {
    try {
      const state = getState().project;
      if (!state.scenes.length) {
        return { estimate: null, tokenBalance: state.tokenBalance ?? null };
      }
      const payload = buildProjectPayload(state);
      const result = await estimateRenderCostApi(payload);
      return result;
    } catch (err) {
      return rejectWithValue({ error: err.message || "Failed to estimate render cost" });
    }
  }
);

export const fetchRenderStatus = createAsyncThunk(
  "project/fetchRenderStatus",
  async (jobRef, { getState, rejectWithValue }) => {
    try {
      const state = getState();
      let jobId = null;
      let projectId = null;

      if (typeof jobRef === "string") {
        jobId = jobRef;
      } else if (jobRef && typeof jobRef === "object") {
        jobId = jobRef.jobId ?? null;
        projectId = jobRef.projectId ?? null;
      }

      if (!jobId) {
        jobId = state.project.render.jobId;
      }
      if (!projectId) {
        projectId = state.project.id;
      }

      if (!jobId) {
        throw new Error("Render job id is not available");
      }

      return await fetchRenderStatusApi(jobId, projectId);
    } catch (err) {
      return rejectWithValue({ error: err.message || "Unable to fetch render status" });
    }
  }
);

export const cancelRenderJob = createAsyncThunk(
  "project/cancelRenderJob",
  async (_, { getState, rejectWithValue }) => {
    try {
      const jobId = getState().project.render.jobId;
      if (!jobId) {
        throw new Error("No active render job to cancel");
      }
      const job = await cancelRenderApi(jobId);
      return job;
    } catch (err) {
      return rejectWithValue({ error: err.message || "Failed to cancel render" });
    }
  }
);

export const pauseRenderJob = createAsyncThunk(
  "project/pauseRenderJob",
  async (_, { getState, rejectWithValue }) => {
    try {
      const jobId = getState().project.render.jobId;
      if (!jobId) {
        throw new Error("No active render job to pause");
      }
      const job = await pauseRenderApi(jobId);
      return job;
    } catch (err) {
      return rejectWithValue({ error: err.message || "Failed to pause render" });
    }
  }
);

export const enrichSceneMetadata = createAsyncThunk(
  "project/enrichSceneMetadata",
  async (_, { getState, rejectWithValue }) => {
    try {
      const state = getState().project;
      if (!state.scenes.length) {
        return { scenes: [], source: null };
      }
      const payload = {
        format: state.format,
        scenes: state.scenes.map((scene) => ({
          id: scene.id,
          text: scene.text || scene.script || "",
        })),
      };
      const data = await enrichScenesMetadata(payload);
      return {
        scenes: data.scenes || [],
        source: data.source || null,
      };
    } catch (err) {
      return rejectWithValue({ error: err.message || "Failed to enrich scenes" });
    }
  }
);


export const autofillSceneMedia = createAsyncThunk(
  "project/autofillSceneMedia",
  async (_, { getState, rejectWithValue }) => {
    try {
      const state = getState().project;
      const format = state.format || "landscape";
      const updates = [];
      let processed = 0;
      for (const scene of state.scenes) {
        if (processed >= 8) {
          break;
        }
        const sceneText = (scene.text || scene.script || "").trim();
        if (!sceneText || scene.media) {
          continue;
        }
        const { results, keywords } = await suggestClips({
          sceneText,
          keywords: scene.keywords || [],
          format,
        });
        const chosen = results.find((clip) => clip && clip.url);
        updates.push({
          sceneId: scene.id,
          media: chosen || null,
          keywords: keywords || [],
        });
        processed += 1;
      }
      return updates;
    } catch (err) {
      return rejectWithValue({ error: err.message || "Failed to suggest media" });
    }
  }
);

/**
 * Scene model:
 * {
 *   id: string,
 *   text: string,
 *   section?: string,
 *   duration: number, // seconds
 *   ttsVoice: string|null,
 *   media: { id, url, thumbnail, width, height, duration, source, attribution } | null,
 *   order: number,
 *   keywords: string[],
 *   imagePrompt?: string|null
 * }
 */

const createInitialState = () => ({
  id: null,
  title: "",
  format: "landscape",
  voiceModel: "Lady Holiday",
  durationSeconds: 60,
  runtimeSeconds: null,
  prompt: "",
  narration: "",
  keywords: [],
  captionStyle: "Classic Clean",
  scenes: [],
  selectedSceneId: null,
  status: "idle",
  error: null,
  isDirty: false,
  tokenBalance: null,
  render: {
    status: "idle",
    jobId: null,
    videoUrl: null,
    error: null,
    autoTrigger: false,
    progress: 0,
  },
  mediaSuggest: {
    status: "idle",
    error: null,
  },
  sceneEnrich: {
    status: "idle",
    error: null,
    source: null,
  },
  costEstimate: {
    status: "idle",
    error: null,
    data: null,
    tokenBalance: null,
    updatedAt: null,
  },
});

const initialState = createInitialState();

const projectSlice = createSlice({
  name: "project",
  initialState,
  reducers: {
    initProject(state, action) {
      const {
        id,
        title,
        format,
        scenes,
        prompt,
        narration,
        keywords,
        voiceModel,
        durationSeconds,
      } = action.payload || {};
      state.id = id || state.id;
      state.title = title || state.title;
      state.format = format || state.format;
      state.prompt = prompt || "";
      state.narration = normalizeNarration(narration);
      state.keywords = keywords || [];
      state.voiceModel = voiceModel || state.voiceModel;
      const captionsMetadata =
        action.payload?.metadata && typeof action.payload.metadata === "object"
          ? action.payload.metadata.captions
          : null;
      const incomingStyle =
        typeof action.payload?.captionStyle === "string"
          ? action.payload.captionStyle.trim()
          : "";
      const fallbackStyle =
        captionsMetadata && typeof captionsMetadata === "object"
          ? (captionsMetadata.style || captionsMetadata.template || "").trim()
          : "";
      state.captionStyle = incomingStyle || fallbackStyle || "Classic Clean";
      if (durationSeconds != null) {
        const parsed =
          typeof durationSeconds === "number"
            ? durationSeconds
            : parseInt(durationSeconds, 10);
        if (!Number.isNaN(parsed) && parsed > 0) {
          state.durationSeconds = parsed;
        }
      }
      state.status = "idle";
      state.error = null;
      if (typeof action.payload?.runtimeSeconds === "number") {
        state.runtimeSeconds = action.payload.runtimeSeconds;
      } else {
        state.runtimeSeconds = null;
      }
      state.scenes = (scenes || []).map((s, i) => {
        const textValue = s.text ?? s.script ?? "";
        const audioEstimate =
          typeof s.audioDuration === "number"
            ? s.audioDuration
            : estimateSpeechDuration(textValue, s.ttsVoice || state.voiceModel);
        return {
          ...s,
          id: s.id ?? nanoid(),
          order: s.order ?? i,
          text: textValue,
          script: s.script ?? s.text ?? "",
          visual: s.visual ?? s.description ?? null,
          keywords: s.keywords || [],
          imagePrompt: s.imagePrompt ?? null,
          audioDuration: Math.round(audioEstimate * 100) / 100,
          duration:
            typeof s.duration === "number"
              ? s.duration
              : Math.max(3, Math.round(audioEstimate)),
        };
      });
      state.selectedSceneId = state.scenes[0]?.id ?? null;
      state.isDirty = true;
      state.render = {
        ...state.render,
        status: "idle",
        jobId: null,
        error: null,
        autoTrigger: false,
        videoUrl: null,
      };
      state.mediaSuggest = {
        status: "idle",
        error: null,
      };
      state.sceneEnrich = {
        status: "idle",
        error: null,
        source: null,
      };
      state.costEstimate = {
        status: "stale",
        error: null,
        data: null,
        tokenBalance: state.tokenBalance,
        updatedAt: null,
      };
    },
    setCaptionStyle(state, action) {
      const nextStyle =
        typeof action.payload === "string" && action.payload.trim()
          ? action.payload.trim()
          : state.captionStyle;
      if (nextStyle !== state.captionStyle) {
        state.captionStyle = nextStyle;
        markDirty(state);
      }
    },
    addScene(state, action) {
      const { text = "New scene", duration } = action.payload || {};
      const id = nanoid();
      const order = state.scenes.length;
      const estimated = estimateSpeechDuration(text, state.voiceModel);
      const normalizedDuration =
        typeof duration === "number"
          ? duration
          : Math.max(3, Math.round(estimated));
      state.scenes.push({
        id,
        text,
        duration: normalizedDuration,
        audioDuration: Math.round(estimated * 100) / 100,
        ttsVoice: state.voiceModel,
        media: null,
        keywords: [],
        imagePrompt: null,
        visual: null,
        script: text,
        order,
      });
      state.selectedSceneId = id;
      markDirty(state);
    },
    removeScene(state, action) {
      const id = action.payload;
      state.scenes = state.scenes
        .filter((s) => s.id !== id)
        .map((s, i) => ({ ...s, order: i }));
      if (state.selectedSceneId === id) {
        state.selectedSceneId = state.scenes[0]?.id ?? null;
      }
      markDirty(state);
    },
    updateSceneText(state, action) {
      const { id, text } = action.payload;
      const scene = state.scenes.find((s) => s.id === id);
      if (scene) {
        scene.text = text;
        scene.script = text;
        const estimated = estimateSpeechDuration(text, scene.ttsVoice || state.voiceModel);
        scene.audioDuration = Math.round(estimated * 100) / 100;
        scene.duration = Math.max(3, Math.round(estimated));
        markDirty(state);
      }
    },
    setSceneMedia(state, action) {
      const { id, media } = action.payload;
      const scene = state.scenes.find((s) => s.id === id);
      if (scene) {
        scene.media = media;
        markDirty(state);
      }
    },
    selectScene(state, action) {
      state.selectedSceneId = action.payload;
    },
    reorderScenes(state, action) {
      const newOrder = action.payload;
      if (Array.isArray(newOrder) && newOrder.length) {
        if (typeof newOrder[0] === "string") {
          state.scenes = newOrder.map((id, idx) => {
            const scene = state.scenes.find((s) => s.id === id);
            return { ...scene, order: idx };
          });
        } else {
          state.scenes = newOrder.map((scene, idx) => ({
            ...scene,
            order: idx,
          }));
        }
        markDirty(state);
      }
    },
    setFormat(state, action) {
      state.format = action.payload || "landscape";
      markDirty(state);
    },
    setVoiceModel(state, action) {
      state.voiceModel = action.payload || state.voiceModel;
      markDirty(state);
    },
    setDurationSeconds(state, action) {
      const raw = action.payload;
      if (raw == null) return;
      const numeric = typeof raw === "number" ? raw : parseInt(raw, 10);
      if (!Number.isNaN(numeric) && numeric > 0) {
        state.durationSeconds = numeric;
        markDirty(state);
      }
    },
    resetProject(state) {
      Object.assign(state, createInitialState());
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(generateProjectFromPrompt.pending, (state, action) => {
        state.status = "loading";
        state.error = null;
        state.runtimeSeconds = null;
        const { format, voiceModel, durationSeconds } = action.meta.arg || {};
        if (format) state.format = format;
        if (voiceModel) state.voiceModel = voiceModel;
        if (durationSeconds) state.durationSeconds = durationSeconds;
      })
      .addCase(generateProjectFromPrompt.fulfilled, (state, action) => {
        state.status = "succeeded";
        state.error = null;
        const project = action.payload?.project || {};
        state.id = project.id || state.id || nanoid();
        state.title = project.title || state.title;
        state.format = project.format || state.format;
        state.prompt = project.prompt || state.prompt;
        state.narration = normalizeNarration(project.narration || "");
        state.keywords = project.keywords || [];
        state.voiceModel = project.voiceModel || state.voiceModel;
        const generatedCaptionsMeta =
          project.metadata && typeof project.metadata === "object"
            ? project.metadata.captions
            : null;
        const generatedStyle =
          typeof project.captionStyle === "string" && project.captionStyle.trim()
            ? project.captionStyle.trim()
            : generatedCaptionsMeta && typeof generatedCaptionsMeta === "object"
              ? (generatedCaptionsMeta.style || generatedCaptionsMeta.template || "").trim()
              : "";
        state.captionStyle = generatedStyle || "Classic Clean";
        if (typeof project.runtimeSeconds === "number") {
          state.runtimeSeconds = project.runtimeSeconds;
        } else {
          state.runtimeSeconds = null;
        }
        state.durationSeconds =
          typeof project.durationSeconds === "number"
            ? project.durationSeconds
            : state.durationSeconds;
        const scenes = project.scenes || [];
        state.scenes = scenes.map((scene, index) => ({
          id: scene.id ?? nanoid(),
          text: scene.text || "",
          ttsVoice: scene.ttsVoice ?? null,
          media: scene.media ?? null,
          keywords: scene.keywords || [],
          imagePrompt: scene.imagePrompt ?? null,
          visual: scene.visual || null,
          script: scene.script || scene.text || "",
          order: scene.order ?? index,
        })).map((scene) => {
          const audioEstimate =
            typeof scene.audioDuration === "number"
              ? scene.audioDuration
              : estimateSpeechDuration(scene.script || scene.text, scene.ttsVoice || state.voiceModel);
          return {
            ...scene,
            audioDuration: Math.round(audioEstimate * 100) / 100,
            duration:
              typeof scene.duration === "number"
                ? scene.duration
                : Math.max(3, Math.round(audioEstimate)),
          };
        });
        state.selectedSceneId = state.scenes[0]?.id ?? null;
        state.isDirty = true;
        state.render = {
          ...state.render,
          status: "idle",
          jobId: null,
          videoUrl: null,
          error: null,
          autoTrigger: false,
          progress: 0,
        };
        state.mediaSuggest = {
          status: "idle",
          error: null,
        };
        state.sceneEnrich = {
          status: "idle",
          error: null,
          source: null,
        };
        state.costEstimate = {
          status: "stale",
          error: null,
          data: null,
          tokenBalance: state.tokenBalance,
          updatedAt: null,
        };
      })
      .addCase(generateProjectFromPrompt.rejected, (state, action) => {
        state.status = "failed";
        state.error =
          action.payload?.error ||
          action.error?.message ||
          "Failed to generate project";
        state.render.autoTrigger = false;
      })
      .addCase(triggerRender.pending, (state) => {
        state.render.status = "queued";
        state.render.error = null;
        state.render.jobId = null;
        state.render.autoTrigger = false;
        state.render.progress = 0;
        state.render.videoUrl = null;
      })
      .addCase(triggerRender.fulfilled, (state, action) => {
        const job = action.payload || {};
        state.render.status = job.status || "queued";
        state.render.jobId = job.id || null;
        state.render.videoUrl = job.videoUrl || state.render.videoUrl;
        state.render.error = job.error || null;
        state.render.autoTrigger = false;
        state.render.progress = job.progress ?? state.render.progress;
        state.isDirty = false;
      })
      .addCase(triggerRender.rejected, (state, action) => {
        state.render.status = "failed";
        state.render.error =
          action.payload?.error || action.error?.message || "Failed to queue render";
        state.render.autoTrigger = false;
        state.isDirty = true;
      })
      .addCase(fetchRenderStatus.fulfilled, (state, action) => {
        const job = action.payload || {};
        const status = job.status || state.render.status;
        state.render.status = status;
        const isFinalCancelled = status === "cancelled";
        const isFinalPaused = status === "paused";
        if (job.id && !isFinalCancelled && !isFinalPaused) {
          state.render.jobId = job.id;
        }
        if (isFinalCancelled || isFinalPaused) {
          state.render.jobId = null;
          state.render.videoUrl = null;
        } else if (job.videoUrl) {
          state.render.videoUrl = job.videoUrl;
        }
        state.render.error = job.error || null;
        state.render.autoTrigger = false;
        state.render.progress =
          typeof job.progress === "number" ? job.progress : state.render.progress;
        if (job.status === "completed" && !state.isDirty) {
          state.isDirty = false;
        }
        if ((isFinalCancelled || isFinalPaused) && status) {
          state.isDirty = true;
        }
      })
      .addCase(fetchRenderStatus.rejected, (state, action) => {
        state.render.error =
          action.payload?.error || action.error?.message || "Failed to fetch render status";
        state.render.status = state.render.status === "rendering" ? "rendering" : state.render.status;
      })
      .addCase(cancelRenderJob.pending, (state) => {
        state.render.error = null;
        if (state.render.jobId) {
          state.render.status = "cancelling";
        }
      })
      .addCase(cancelRenderJob.fulfilled, (state, action) => {
        const job = action.payload || {};
        const finalStatus = job.status || "cancelled";
        state.render.status = finalStatus;
        state.render.error = job.error || null;
        state.render.progress = typeof job.progress === "number" ? job.progress : state.render.progress;
        state.render.videoUrl = job.videoUrl || (finalStatus === "cancelled" ? null : state.render.videoUrl);
        state.render.jobId = finalStatus === "cancelled" ? null : (job.id || state.render.jobId);
        state.render.autoTrigger = false;
        state.isDirty = true;
      })
      .addCase(cancelRenderJob.rejected, (state, action) => {
        state.render.error =
          action.payload?.error || action.error?.message || "Failed to cancel render";
      })
      .addCase(pauseRenderJob.pending, (state) => {
        state.render.error = null;
        if (state.render.jobId) {
          state.render.status = "pausing";
        }
      })
      .addCase(pauseRenderJob.fulfilled, (state, action) => {
        const job = action.payload || {};
        const finalStatus = job.status || "paused";
        state.render.status = finalStatus;
        state.render.error = job.error || null;
        state.render.progress = typeof job.progress === "number" ? job.progress : state.render.progress;
        state.render.videoUrl = job.videoUrl || (finalStatus === "paused" ? null : state.render.videoUrl);
        state.render.jobId = finalStatus === "paused" ? null : (job.id || state.render.jobId);
        state.render.autoTrigger = false;
        state.isDirty = true;
      })
      .addCase(pauseRenderJob.rejected, (state, action) => {
        state.render.error =
          action.payload?.error || action.error?.message || "Failed to pause render";
      })
      .addCase(estimateProjectCost.pending, (state) => {
        state.costEstimate.status = "loading";
        state.costEstimate.error = null;
      })
      .addCase(estimateProjectCost.fulfilled, (state, action) => {
        const payload = action.payload || {};
        state.costEstimate.data = payload.estimate || null;
        state.costEstimate.tokenBalance =
          typeof payload.tokenBalance === "number"
            ? payload.tokenBalance
            : state.costEstimate.tokenBalance;
        state.costEstimate.status = payload.estimate ? "succeeded" : "idle";
        state.costEstimate.error = null;
        state.costEstimate.updatedAt = payload.estimate ? Date.now() : null;
        if (typeof payload.tokenBalance === "number") {
          state.tokenBalance = payload.tokenBalance;
        }
      })
      .addCase(estimateProjectCost.rejected, (state, action) => {
        state.costEstimate.status = "failed";
        state.costEstimate.error =
          action.payload?.error || action.error?.message || "Failed to estimate render cost";
      })
      .addCase(enrichSceneMetadata.pending, (state) => {
        state.sceneEnrich.status = "loading";
        state.sceneEnrich.error = null;
        state.sceneEnrich.source = null;
      })
      .addCase(enrichSceneMetadata.fulfilled, (state, action) => {
        state.sceneEnrich.status = "succeeded";
        const payload = action.payload || {};
        state.sceneEnrich.source = payload.source || null;
        const updates = Array.isArray(payload.scenes) ? payload.scenes : [];
        updates.forEach((item) => {
          if (!item || typeof item !== "object") return;
          const scene = state.scenes.find((s) => s.id === item.id);
          if (!scene) return;
          if (Array.isArray(item.keywords) && item.keywords.length) {
            const merged = Array.from(
              new Set([...(scene.keywords || []), ...item.keywords.filter(Boolean)])
            );
            scene.keywords = merged.slice(0, 6);
          }
          if (item.imagePrompt) {
            scene.imagePrompt = item.imagePrompt;
          }
        });
      })
      .addCase(enrichSceneMetadata.rejected, (state, action) => {
        state.sceneEnrich.status = "failed";
        state.sceneEnrich.error =
          action.payload?.error || action.error?.message || "Failed to enrich scenes";
        state.sceneEnrich.source = null;
      })
      .addCase(autofillSceneMedia.pending, (state) => {
        state.mediaSuggest.status = "loading";
        state.mediaSuggest.error = null;
      })
        .addCase(autofillSceneMedia.fulfilled, (state, action) => {
          state.mediaSuggest.status = "succeeded";
          const updates = action.payload || [];
          let changed = false;
          updates.forEach(({ sceneId, media, keywords }) => {
            const scene = state.scenes.find((s) => s.id === sceneId);
            if (!scene) return;
            if (keywords && keywords.length) {
              const combined = Array.from(
                new Set([...(scene.keywords || []), ...keywords.filter(Boolean)])
              );
              scene.keywords = combined.slice(0, 6);
            }
            if (media && media.url) {
              scene.media = media;
              changed = true;
            }
          });
          if (changed) {
            state.isDirty = true;
          }
        })
        .addCase(autofillSceneMedia.rejected, (state, action) => {
          state.mediaSuggest.status = "failed";
          state.mediaSuggest.error =
            action.payload?.error || action.error?.message || "Failed to suggest media";
        });
  },
});

export const {
  initProject,
  setCaptionStyle,
  addScene,
  removeScene,
  updateSceneText,
  setSceneMedia,
  selectScene,
  reorderScenes,
  setFormat,
  setVoiceModel,
  setDurationSeconds,
  resetProject,
} = projectSlice.actions;

export default projectSlice.reducer;
