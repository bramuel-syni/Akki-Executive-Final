/**
 * Phase L.a (2026-05-27) — StreamingLogScene.
 *
 * Claude-reference visual treatment for long-op progress streaming.
 * Visual spec locked at `/app/memory/sprints/PHASE_L_VISUAL_REFERENCE.md`:
 *   - multi-line progressive reveal (NOT single-line fade)
 *   - sans-serif, muted greys
 *   - completed phases keep their line + checkmark
 *   - active phase: subtle pulse indicator
 *   - upcoming phases: NOT shown
 *   - subtle semantic icons per phase (book-open, shield-check, etc.)
 *   - 200ms fade-in for new lines
 *   - reduced-motion: collapses to final state
 *
 * Reads from `useStreamingProgress` state. Per-surface testid via the
 * `surfaceId` prop (e.g. `streaming-log-work-studio-compile`).
 */
import React from "react";
import {
  BookOpen, ShieldCheck, Map, PenTool, CheckSquare,
  List, FileText, Sparkles, Loader2, AlertCircle,
  Scale, Calendar, Download, Presentation,
} from "lucide-react";

// Phase L.a icon map — matches the `icon` key in `PHASE_SCRIPTS` (backend).
// Phase L.b.2 (2026-05-27): added scale/calendar/download/presentation
// for the 5 L.b surfaces (solva-synthesis, work-studio-enhance,
// task-manager-compile, events-calendar-sync, decks-generation).
// Future surfaces extending the script add their icon here.
const ICON_MAP = {
  "book-open":     BookOpen,
  "shield-check":  ShieldCheck,
  "map":           Map,
  "pen-tool":      PenTool,
  "check-square":  CheckSquare,
  "list":          List,
  "file-text":     FileText,
  "sparkles":      Sparkles,
  "scale":         Scale,
  "calendar":      Calendar,
  "download":      Download,
  "presentation":  Presentation,
};

function PhaseLine({ phase, index, status, surfaceId }) {
  // status: 'completed' | 'active' | 'pending' (we don't render pending)
  const Icon = ICON_MAP[phase.icon] || BookOpen;
  const isCompleted = status === "completed";
  const isActive    = status === "active";

  return (
    <div
      data-testid={`${surfaceId}-line-${index}${isActive ? "-active" : ""}${isCompleted ? "-done" : ""}`}
      className={`streaming-log-line flex items-start gap-3 py-2 ${
        isCompleted ? "opacity-70" : "opacity-100"
      }`}
      style={{
        // 200ms fade-in for new lines per the locked spec.
        animation: "akki-streaming-log-fade 200ms ease-out",
      }}
    >
      <div className="flex-shrink-0 mt-0.5">
        {isCompleted ? (
          <CheckSquare
            className="w-4 h-4 text-[var(--accent)]"
            strokeWidth={1.7}
            aria-label="done"
          />
        ) : isActive ? (
          // Active phase: same icon as planned, slight pulse via class
          <Icon
            className="w-4 h-4 text-[var(--ink)] akki-streaming-log-pulse"
            strokeWidth={1.7}
            aria-label="in progress"
          />
        ) : (
          <Icon
            className="w-4 h-4 text-[var(--muted)]"
            strokeWidth={1.7}
            aria-hidden="true"
          />
        )}
      </div>
      <div
        className={`text-[14px] leading-relaxed ${
          isCompleted
            ? "text-[var(--muted)]"
            : "text-[var(--ink)]"
        }`}
      >
        {phase.label}
      </div>
    </div>
  );
}

export default function StreamingLogScene({
  surfaceId,                    // e.g. "streaming-log-work-studio-compile"
  state,                        // from useStreamingProgress: {phases, activeIndex, completedIndexes, status, error}
  emptyHint = "Preparing...",
  className = "",
}) {
  const { phases, activeIndex, completedIndexes, status, error } = state;

  // Render lines up to + including the active index. NO upcoming phases
  // per the locked Claude-reference spec ("phases that haven't started
  // yet are not shown").
  const visibleIndexes = [];
  for (let i = 0; i <= activeIndex; i++) {
    visibleIndexes.push(i);
  }

  // If we have nothing to show yet (status='connecting' or 'idle'),
  // surface a single placeholder line so the surface doesn't render
  // empty.
  const isEmpty = phases.length === 0 || activeIndex < 0;

  return (
    <div
      data-testid={surfaceId}
      role="status"
      aria-live="polite"
      aria-busy={status === "streaming" || status === "connecting"}
      className={`streaming-log-scene ${className}`}
    >
      {isEmpty && status !== "error" && (
        <div
          data-testid={`${surfaceId}-empty`}
          className="flex items-center gap-3 py-2 text-[14px] text-[var(--muted)]"
        >
          <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.7} aria-hidden="true" />
          <span>{emptyHint}</span>
        </div>
      )}

      {!isEmpty && visibleIndexes.map((i) => {
        const phase = phases[i];
        if (!phase) return null;
        const isActive = i === activeIndex && status === "streaming";
        const isCompleted = completedIndexes.has(i) || (status === "complete" && i <= activeIndex);
        return (
          <PhaseLine
            key={i}
            phase={phase}
            index={i}
            status={isCompleted ? "completed" : isActive ? "active" : "completed"}
            surfaceId={surfaceId}
          />
        );
      })}

      {status === "error" && error && (
        <div
          data-testid={`${surfaceId}-error`}
          className="flex items-start gap-3 py-2 text-[14px] text-[var(--accent)]"
        >
          <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" strokeWidth={1.7} />
          <span>{error.message || "Something went wrong while preparing this."}</span>
        </div>
      )}
    </div>
  );
}
