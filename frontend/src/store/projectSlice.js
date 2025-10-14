// src/store/projectSlice.js
import { createAsyncThunk, createSlice, nanoid } from "@reduxjs/toolkit";
import { estimateSpeechDuration } from "../lib/speech";
import { triggerRender as triggerRenderApi, fetchRenderStatus as fetchRenderStatusApi } from "../lib/renderApi";

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
};

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
      const payload = {
        id: project.id,
        title: project.title,
        format: project.format,
        voiceModel: project.voiceModel,
        narration: project.narration,
        durationSeconds: project.durationSeconds,
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
      };
      if (!payload.scenes.length) {
        throw new Error("Add at least one scene before rendering");
      }
      const job = await triggerRenderApi(payload);
      return job;
    } catch (err) {
      return rejectWithValue({ error: err.message || "Render failed" });
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
      console.warn("fetchRenderStatus:error", { jobId, projectId, message: err.message, error: err });
      return rejectWithValue({ error: err.message || "Unable to fetch render status" });
    }
  }
);

/**
 * Scene model:
 * {
 *   id: string,
 *   text: string,
 *   duration: number, // seconds
 *   ttsVoice: string|null,
 *   media: { id, url, thumbnail, width, height, duration, source, attribution } | null,
 *   order: number,
 *   keywords: string[]
 * }
 */

const initialState = {
  id: null,
  title: "",
  format: "landscape",
  voiceModel: "Lady Holiday",
  durationSeconds: 60,
  runtimeSeconds: null,
  prompt: "",
  narration: "",
  keywords: [],
  scenes: [],
  selectedSceneId: null,
  status: "idle",
  error: null,
  isDirty: false,
  render: {
    status: "idle",
    jobId: null,
    videoUrl: null,
    error: null,
    autoTrigger: false,
    progress: 0,
  },
};

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
        autoTrigger: true,
        videoUrl: null,
      };
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
    },
    setVoiceModel(state, action) {
      state.voiceModel = action.payload || state.voiceModel;
    },
    setDurationSeconds(state, action) {
      const raw = action.payload;
      if (raw == null) return;
      const numeric = typeof raw === "number" ? raw : parseInt(raw, 10);
      if (!Number.isNaN(numeric) && numeric > 0) {
        state.durationSeconds = numeric;
      }
    },
    resetProject(state) {
      Object.assign(state, initialState);
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
          autoTrigger: true,
          progress: 0,
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
        state.render.status = job.status || state.render.status;
        state.render.jobId = job.id || state.render.jobId;
        state.render.videoUrl = job.videoUrl || state.render.videoUrl;
        state.render.error = job.error || null;
        state.render.autoTrigger = false;
        state.render.progress =
          typeof job.progress === "number" ? job.progress : state.render.progress;
        if (job.status === "completed" && !state.isDirty) {
          state.isDirty = false;
        }
      })
      .addCase(fetchRenderStatus.rejected, (state, action) => {
        state.render.error =
          action.payload?.error || action.error?.message || "Failed to fetch render status";
        state.render.status = state.render.status === "rendering" ? "rendering" : state.render.status;
      });
  },
});

export const {
  initProject,
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
