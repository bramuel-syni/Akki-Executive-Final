import React, { useEffect, useState, useRef } from "react";
import { getSandboxSession } from "../api";

/**
 * Phase J — Streaming Transitions: Context Loading pattern.
 *
 * K1 update (2026-05-12) — the surfacing lines now reflect REAL
 * backend phase boundaries instead of a fixed 1.7s timer. The polling
 * loop reads `session.progress.phase` and translates each phase into
 * the visible line. If the backend hasn't checkpointed yet (very early
 * polls), we still surface line 0 so the screen never looks blank.
 *
 * Polls every 800ms during generation; hard ceiling at 18s = 22 polls,
 * after which we proceed with whatever state exists (the backend's
 * default fallback always lands a `ready` state eventually).
 */
const PHASE_TO_INDEX = {
  received: 0,
  composing_org: 1,
  drafting_solva: 2,
  surfacing_pulse: 3,
  preparing_work_studio: 4,
  finalising: 4,
  ready: 4,
};

const LINES = [
  "Reading your inputs.",
  "Composing a fictional organisation that fits.",
  "Drafting your Solva opening question.",
  "Surfacing the Pulse signals.",
  "Preparing the rest.",
];

export default function SandboxLoading({ sessionId, onReady }) {
  const [phaseIndex, setPhaseIndex] = useState(0);
  const polledRef = useRef(false);

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
        const phase = s?.progress?.phase || "received";
        const idx = PHASE_TO_INDEX[phase] ?? 0;
        // Lines advance monotonically — never go backwards if a poll
        // races with a phase write.
        setPhaseIndex((cur) => Math.max(cur, idx));
        if (s.status === "ready") {
          // Minimum hold so the calm tone reads even on a fast finish.
          if (attempts <= 2) await new Promise((r) => setTimeout(r, 1200));
          if (!cancelled) onReady(s);
          return;
        }
      } catch (_) { /* swallow — keep polling */ }
      if (attempts >= 22) {
        try {
          const s = await getSandboxSession(sessionId);
          if (!cancelled) onReady(s);
        } catch (_) { /* fully abandon */ }
        return;
      }
      setTimeout(tick, 800);
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
              (i <= phaseIndex ? "sb-loading-line--visible " : "") +
              (i < phaseIndex ? "sb-loading-line--done" : "")
            }
            data-testid={`sandbox-loading-line-${i}`}
          >
            {i < phaseIndex ? "✓  " : i === phaseIndex ? "·  " : "   "}
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
