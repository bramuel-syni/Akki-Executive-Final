import React, { useEffect, useState, useRef } from "react";
import { getSandboxSession } from "../api";

const LINES = [
  "Reading your inputs.",
  "Composing a fictional organisation that fits.",
  "Drafting your Solva opening question.",
  "Surfacing the Pulse signals.",
  "Preparing the rest.",
];

/**
 * SandboxLoading — Streaming Transitions: Context Loading pattern.
 * Progressive surfacing 1-2s apart. Polls the session every 1.5s.
 * Hard ceiling at 18s — if generation hasn't finished, we still
 * proceed (the backend's `default` fallback will have served by then).
 */
export default function SandboxLoading({ sessionId, onReady }) {
  const [visibleLines, setVisibleLines] = useState(0);
  const [completedLines, setCompletedLines] = useState(0);
  const polledRef = useRef(false);

  // Progressive surfacing — reveal a new line every 1.7s up to 5.
  useEffect(() => {
    if (visibleLines >= LINES.length) return;
    const t = setTimeout(() => setVisibleLines((v) => v + 1), 1700);
    return () => clearTimeout(t);
  }, [visibleLines]);

  // Mark earlier lines as done as we progress.
  useEffect(() => {
    if (visibleLines > 0 && completedLines < visibleLines - 1) {
      const t = setTimeout(() => setCompletedLines((c) => c + 1), 800);
      return () => clearTimeout(t);
    }
  }, [visibleLines, completedLines]);

  // Poll the session.
  useEffect(() => {
    if (!sessionId || polledRef.current) return;
    polledRef.current = true;
    let cancelled = false;
    let attempts = 0;
    const tick = async () => {
      if (cancelled) return;
      attempts += 1;
      try {
        const s = await getSandboxSession(sessionId);
        if (s.status === "ready") {
          // Ensure the user sees the loading screen for at least 3s
          // even if generation completed faster, so the calm tone holds.
          if (attempts <= 2) {
            await new Promise((r) => setTimeout(r, 1500));
          }
          if (!cancelled) onReady(s);
          return;
        }
      } catch (_) { /* swallow — keep polling */ }
      // Hard ceiling at 18s = 12 polls.
      if (attempts >= 12) {
        // Best-effort — read whatever state exists; the backend's
        // default fallback always lands a `ready` state eventually.
        try {
          const s = await getSandboxSession(sessionId);
          if (!cancelled) onReady(s);
        } catch (_) { /* fully abandon */ }
        return;
      }
      setTimeout(tick, 1500);
    };
    tick();
    return () => { cancelled = true; };
  }, [sessionId, onReady]);

  return (
    <div className="sb-shell" data-testid="sandbox-loading">
      <span className="sb-label">Composing your session…</span>
      <h2>Akki is composing.</h2>
      <span className="sb-rule" />
      <div style={{ marginTop: 24 }}>
        {LINES.map((line, i) => (
          <div
            key={i}
            className={
              "sb-loading-line " +
              (i < visibleLines ? "sb-loading-line--visible " : "") +
              (i < completedLines ? "sb-loading-line--done" : "")
            }
            data-testid={`sandbox-loading-line-${i}`}
          >
            {i < completedLines ? "✓  " : i < visibleLines ? "·  " : "   "}
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
