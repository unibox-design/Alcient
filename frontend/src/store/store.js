// src/store/store.js
import { configureStore } from "@reduxjs/toolkit";
import projectReducer from "./projectSlice";

const store = configureStore({
  reducer: {
    project: projectReducer,
  },
});

export { store };
