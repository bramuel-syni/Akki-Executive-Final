import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Phase 13.4 — `@axe-core/react` dev-time accessibility reporting.
// Logs WCAG 2.2 AA violations to the browser console with file/line
// context as users navigate. Zero impact on the production bundle —
// the import is gated and tree-shakes out at `yarn build`.
if (process.env.NODE_ENV !== "production") {
  import("@axe-core/react")
    .then(({ default: axe }) => axe(React, ReactDOM, 1000))
    .catch(() => { /* axe optional — silent fail in dev if not installed */ });
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
