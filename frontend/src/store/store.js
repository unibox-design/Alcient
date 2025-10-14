// src/store/store.js
import { configureStore } from "@reduxjs/toolkit";
import projectReducer from "./projectSlice";

const STORAGE_KEY = "alcient.projectState.v1";

const loadPreloadedState = () => {
  if (typeof window === "undefined" || !window.localStorage) return undefined;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return undefined;
    return { project: parsed };
  } catch (err) {
    console.warn("Failed to load saved project state:", err);
    return undefined;
  }
};

const store = configureStore({
  reducer: {
    project: projectReducer,
  },
  preloadedState: loadPreloadedState(),
});

if (typeof window !== "undefined" && window.localStorage) {
  store.subscribe(() => {
    try {
      const state = store.getState();
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state.project));
    } catch (err) {
      console.warn("Failed to persist project state:", err);
    }
  });
}

export { store };
