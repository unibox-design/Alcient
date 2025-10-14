import React from "react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { store } from "./store/store";
import App from "./App";
import "./index.css";

if (typeof window !== "undefined" && window.localStorage) {
  try {
    window.localStorage.removeItem("alcient.projectState.v1");
  } catch (err) {
    console.warn("Failed to clear cached project state:", err);
  }
}

createRoot(document.getElementById("root")).render(
  <Provider store={store}>
    <App />
  </Provider>
);
