/**
 * StreamingShell — Patch 4B.
 *
 * Document-typesetting motion for high-impact streaming surfaces:
 * Solva (all 4 modes), Cycle session compilation, Work Studio Enhance,
 * and workspace/role transitions.
 *
 * Architecture:
 *   1. Skeleton frame renders first — heading + dividers + section labels
 *   2. Content fills in under each section as tokens arrive
 *   3. Phase label (small editorial line above stream) cycles through
 *      real backend phases:
 *        Reading context → Shielding input → Reasoning →
 *        Drafting → Refining → Complete
 *   4. Cursor at the streaming edge
 *   5. Provider+model+latency footer line
 *   6. Stop generating always reachable
 *   7. Graceful failure: >10s stall → "Reconnecting… retry now"
 *      inline, preserves partial output
 *
 * Chat surface uses a quieter variant — only the cursor.
 *
 * No emoji, no spinners at page level, no bouncy effects.
 */
import React, { useEffect, useMemo, useState } from "react";
import { Loader2, Square, RefreshCw } from "lucide-react";


export const PHASE_LABELS = {
  reading_context:   "Reading context",
  shielding_input:   "Shielding input",
  reasoning:         "Reasoning",
  drafting:          "Drafting",
  refining:          "Refining",
  complete:          "Complete",
};

export const PHASE_ORDER = [
  "reading_context",
  "shielding_input",
  "reasoning",
  "drafting",
  "refining",
  "complete",
];


function PhaseLabel({ phase }) {
  const label = PHASE_LABELS[phase] || PHASE_LABELS.reasoning;
  return (
    <p
      className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mb-2"
      data-testid="streaming-phase-label"
    >
      {label}
    </p>
  );
}


function StreamingFooter({ provider, model, latencyMs, onStop, onRetry, status }) {
  return (
    <div className="flex items-center justify-between gap-3 mt-3 pt-2 border-t border-[var(--rule)]" data-testid="streaming-footer">
      <p className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)]">
        {provider || "akki"} · {model || "—"}
        {typeof latencyMs === "number" && ` · ${Math.round(latencyMs)}ms`}
      </p>
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


/**
 * Skeleton — a heading + 3 section labels with parchment-fade dividers.
 * Renders first while we wait for tokens.
 */
function Skeleton({ sections = ["Section 1", "Section 2", "Section 3"] }) {
  return (
    <div className="space-y-5 animate-akki-fade" data-testid="streaming-skeleton">
      <div className="space-y-2">
        <div className="h-5 w-2/3 bg-[var(--parchment)] rounded-sm" />
        <div className="h-3 w-1/3 bg-[var(--parchment)] rounded-sm" />
      </div>
      {sections.map((label, i) => (
        <div key={i} className="space-y-2">
          <p className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)]">
            {label}
          </p>
          <div className="h-3 w-full bg-[var(--parchment)] rounded-sm" />
          <div className="h-3 w-5/6 bg-[var(--parchment)] rounded-sm" />
          <div className="h-3 w-4/6 bg-[var(--parchment)] rounded-sm" />
        </div>
      ))}
    </div>
  );
}


/**
 * Subtle blinking cursor at the streaming edge.
 */
function StreamCursor() {
  return (
    <span
      className="inline-block w-[2px] h-[1.1em] align-[-2px] ml-[1px] bg-[var(--ink)] animate-akki-cursor"
      data-testid="streaming-cursor"
      aria-hidden="true"
    />
  );
}


export default function StreamingShell({
  phase = "reasoning",
  status = "streaming",        // streaming | stalled | complete
  provider,
  model,
  latencyMs,
  onStop,
  onRetry,
  sections,                    // for skeleton
  partial,                     // streamed content node — when null, renders skeleton
  variant = "document",        // "document" (default) | "quiet" (chat)
}) {
  // Detect stall: if status === "streaming" and we don't get a phase update
  // for >10s, the parent should switch us to "stalled".
  const showCursor = status !== "complete";

  if (variant === "quiet") {
    return (
      <div data-testid="streaming-shell-quiet" className="flex items-center gap-2">
        {partial}
        {showCursor && <StreamCursor />}
      </div>
    );
  }

  const showSkeleton = !partial && status !== "complete";

  return (
    <div className="space-y-3" data-testid="streaming-shell">
      <PhaseLabel phase={phase} />
      {showSkeleton ? (
        <Skeleton sections={sections} />
      ) : (
        <div className="akki-serif text-[15px] leading-[1.7] text-[var(--ink)]" data-testid="streaming-content">
          {partial}
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
