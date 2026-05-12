/**
 * StreamingShell — Patch 12 v3 rewrite.
 *
 * Philosophy: authenticity over theatre. The earlier v1 (Patch 4B) used a
 * pre-rendered skeleton frame; v2 (Patch 9) wired phase events. v3
 * removes the skeleton, drives every motion off real backend signals,
 * adopts variable cadence + crossfading phase labels.
 *
 * Inputs:
 *   - phase    "reading_context" | … | "complete"
 *   - status   "idle" | "streaming" | "stalled" | "complete" | "error"
 *   - content  the current renderable string (consumer-paced via
 *              useStreamingPhases + createClausePacer)
 *   - provider / model / latencyMs  → settle-state footer line
 *   - onStop, onRetry
 *
 * No skeleton. The page is empty until the model speaks; then content
 * appears top-down at a clause-aware cadence. On `complete` we play a
 * single 240ms vertical-lift settle. Headings ARE rendered at once by
 * the caller (clauseStream emits them whole) — the shell just paints.
 *
 * Chat surface uses the `quiet` variant (cursor only).
 */
import React, { useEffect, useRef, useState } from "react";
import { Square, RefreshCw } from "lucide-react";


export const PHASE_LABELS = {
  reading_context: "Reading context",
  shielding_input: "Shielding input",
  reasoning:       "Reasoning",
  drafting:        "Drafting",
  refining:        "Refining",
  complete:        "Complete",
};

export const PHASE_ORDER = [
  "reading_context",
  "shielding_input",
  "reasoning",
  "drafting",
  "refining",
  "complete",
];


/**
 * PhaseCaption — graphite caption above the streaming surface.
 *
 * Crossfades between the previous and current phase over 250ms.
 * If two phases arrive within 200ms, we snap to the new label
 * (no crossfade — pretending to crossfade nothing is dishonest).
 *
 * Reasoning has a subtle horizontal pulse on the label itself
 * (4% opacity dip + rebound, 1.5s cycle). No separate spinner.
 *
 * On `complete`: caption fades fully after 1.2s (work is done — get
 * out of the way).
 */
function PhaseCaption({ phase, status }) {
  const [prev, setPrev] = useState(phase);
  const [snap, setSnap] = useState(false);
  const lastChangeRef = useRef(Date.now());
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    if (phase === prev) return undefined;
    const dt = Date.now() - lastChangeRef.current;
    setSnap(dt < 200);
    setPrev(phase);
    lastChangeRef.current = Date.now();
    return undefined;
  }, [phase, prev]);

  useEffect(() => {
    if (status !== "complete") { setHidden(false); return undefined; }
    const t = setTimeout(() => setHidden(true), 1200);
    return () => clearTimeout(t);
  }, [status]);

  if (hidden) return null;

  const label = PHASE_LABELS[phase] || PHASE_LABELS.reasoning;
  const isReasoning = phase === "reasoning" && status !== "complete";
  const cls = [
    "text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)]",
    snap ? "" : "akki-phase-crossfade",
    isReasoning ? "akki-phase-pulse" : "",
  ].filter(Boolean).join(" ");

  return (
    <p className={cls} data-testid="streaming-phase-label" data-phase={phase}>
      {label}
    </p>
  );
}


function StreamCursor() {
  return (
    <span
      className="inline-block w-[2px] h-[1.1em] align-[-2px] ml-[1px] bg-[var(--ink)] animate-akki-cursor"
      aria-hidden="true"
      data-testid="streaming-cursor"
    />
  );
}


function StreamingFooter({ provider, model, latencyMs, onStop, onRetry, status }) {
  // Footer fades in only at completion (the latency value is honest
  // once we have it). During streaming we hide it — no provisional
  // latency theatre.
  const visible = status === "complete";
  if (!visible && status !== "stalled" && status !== "streaming") return null;
  return (
    <div
      className={[
        "flex items-center justify-between gap-3 mt-3 pt-2 border-t border-[var(--rule)]",
        visible ? "akki-footer-fade-in" : "",
      ].join(" ")}
      data-testid="streaming-footer"
    >
      {visible ? (
        <p className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)]">
          {provider || "akki"} · {model || "—"}
          {typeof latencyMs === "number" && ` · ${Math.round(latencyMs)}ms`}
        </p>
      ) : (
        <span />
      )}
      <div className="flex items-center gap-2">
        {status === "stalled" && onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="text-[11.5px] inline-flex items-center gap-1 px-2 py-1 border border-[var(--rule)] rounded-sm text-[color:var(--oxblood)] hover:bg-[var(--parchment)]"
            data-testid="streaming-retry"
          >
            <RefreshCw className="w-3 h-3" strokeWidth={1.7} /> Reconnecting · retry now
          </button>
        )}
        {status !== "complete" && onStop && (
          <button
            type="button"
            onClick={onStop}
            className="text-[11.5px] inline-flex items-center gap-1 px-2 py-1 border border-[var(--rule)] rounded-sm hover:bg-[var(--parchment)]"
            data-testid="streaming-stop"
          >
            <Square className="w-3 h-3" strokeWidth={1.7} /> Stop generating
          </button>
        )}
      </div>
    </div>
  );
}


export default function StreamingShell({
  phase = "reading_context",
  status = "streaming",
  provider,
  model,
  latencyMs,
  onStop,
  onRetry,
  content,                 // string OR React node — already paced by useStreamingPhases
  variant = "document",    // "document" | "quiet"
}) {
  const contentRef = useRef(null);
  const settledRef = useRef(false);
  const showCursor = status !== "complete" && status !== "error";

  // Completion settle — fire exactly once on real `complete`.
  useEffect(() => {
    if (status !== "complete" || settledRef.current) return undefined;
    const node = contentRef.current;
    if (!node) return undefined;
    settledRef.current = true;
    node.classList.add("akki-completion-settle");
    const t = setTimeout(() => node.classList.remove("akki-completion-settle"), 280);
    return () => clearTimeout(t);
  }, [status]);

  if (variant === "quiet") {
    return (
      <div data-testid="streaming-shell-quiet" className="inline-flex items-center gap-1">
        {content}
        {showCursor && <StreamCursor />}
      </div>
    );
  }

  // Empty state until content actually arrives. NO skeleton, NO scaffolding.
  const isEmpty = !content || (typeof content === "string" && content.length === 0);
  return (
    <div className="space-y-3" data-testid="streaming-shell">
      <PhaseCaption phase={phase} status={status} />
      {!isEmpty && (
        <div
          ref={contentRef}
          className="akki-serif text-[15px] leading-[1.7] text-[var(--ink)]"
          data-testid="streaming-content"
        >
          {typeof content === "string" ? (
            <span style={{ whiteSpace: "pre-wrap" }}>{content}</span>
          ) : content}
          {showCursor && <StreamCursor />}
        </div>
      )}
      <StreamingFooter
        provider={provider}
        model={model}
        latencyMs={latencyMs}
        onStop={onStop}
        onRetry={onRetry}
        status={status}
      />
    </div>
  );
}
