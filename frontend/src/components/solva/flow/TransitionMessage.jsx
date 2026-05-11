/**
 * TransitionMessage — Wave 1.8 (UAT pack 2026-05-10).
 *
 * A brief peer-voiced line that fades in for ~1.5 s between layer
 * transitions. Solva is a wizard, not a chat — we don't have a
 * conversation pane to render system messages into. Per the spec,
 * we use a small italic line, muted, centred, that doesn't block
 * input.
 *
 * Copy is keyed by (submodule, fromLayer, toLayer). The lookup
 * defaults to a generic line if a specific one isn't found, so
 * adding new submodules later doesn't require updating this file.
 */
import React, { useEffect, useState } from "react";

const COPY_KEYS = (submodule, fromLayer, toLayer) => [
  `${submodule}|${fromLayer}|${toLayer}`,
  `*|${fromLayer}|${toLayer}`,
];

const COPY = {
  // FRAMING → SURFACE (Q1)
  "*|FRAMING|Q1": "OK — we have your framing. Now let's surface the candidates.",
  "seek_clarity|FRAMING|Q1": "OK — we have what you've shared. Let's pull on the threads.",
  "develop_strategy|FRAMING|Q1": "Got it. Let's surface the options worth weighing.",
  "simulate_hypothesis|FRAMING|Q1": "OK — hypothesis on the table. Let's surface what supports and undermines it.",
  "get_perspective|FRAMING|Q1": "OK. Let's surface the angles worth hearing.",

  // Q3 → DEPTH_Q1
  "*|Q3|DEPTH_Q1": "OK — we have what we need on the surface. Now let's get into where these candidates hold up and where they don't.",
  "develop_strategy|Q3|DEPTH_Q1": "OK — three options on the table. Now let's pressure-test them.",

  // DEPTH_Q3 → PREPARING
  "*|DEPTH_Q3|PREPARING": "We have what we need. Now let's see how these hold up.",
  "simulate_hypothesis|DEPTH_Q3|PREPARING": "We have enough to stress-test. Pulling it together now.",

  // ARTEFACT → REFLECT_1
  "*|ARTEFACT|REFLECT_1": "Now let's step back. Three quick reflections.",
  "ARTEFACT_REFUSAL|*|REFLECT_1": "Now let's reflect on what we noticed.",
};

function copyFor(submodule, from, to) {
  for (const k of COPY_KEYS(submodule, from, to)) {
    if (COPY[k]) return COPY[k];
  }
  return null;
}

export default function TransitionMessage({ submodule, fromLayer, toLayer, durationMs = 1500 }) {
  const message = copyFor(submodule, fromLayer, toLayer);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (!message) return undefined;
    const t = setTimeout(() => setVisible(false), durationMs);
    return () => clearTimeout(t);
  }, [message, durationMs]);

  if (!message || !visible) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="solva-transition-msg"
      style={{
        position: "fixed",
        left: 0, right: 0, bottom: 28,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
        zIndex: 50,
      }}
    >
      <p
        style={{
          fontFamily: "Georgia, serif",
          fontStyle: "italic",
          fontSize: 13.5,
          color: "var(--graphite)",
          background: "rgba(250, 246, 238, 0.92)",
          border: "1px solid rgba(0,0,0,0.06)",
          borderRadius: 999,
          padding: "7px 18px",
          margin: 0,
          textAlign: "center",
          maxWidth: "min(640px, 92vw)",
          animation: "akki-fade-in 0.25s ease both",
        }}
      >
        {message}
      </p>
      <style>{`@keyframes akki-fade-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }`}</style>
    </div>
  );
}
