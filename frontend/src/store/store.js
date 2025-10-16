// src/store/store.js
import { configureStore } from "@reduxjs/toolkit";
import projectReducer from "./projectSlice";
import billingReducer from "./billingSlice";

const store = configureStore({
  reducer: {
    project: projectReducer,
    billing: billingReducer,
  },
});

export { store };
