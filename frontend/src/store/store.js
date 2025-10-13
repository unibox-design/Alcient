// src/store/store.js
import { configureStore } from "@reduxjs/toolkit";
import projectReducer from "./projectSlice";

export const store = configureStore({
  reducer: {
    project: projectReducer,
  },
});
