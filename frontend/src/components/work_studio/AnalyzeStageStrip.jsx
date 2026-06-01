/**
 * Phase P5.14.1 — Analyze stage strip.
 *
 * Renders the ordered list of analysis stages with real status
 * driven by `useAnalyzeStages`. No timer-based progress bars.
 * The currently running stage shows a small spinner glyph; done
 * stages show ✓ and a duration in ms; errored stages show ✗ + the
 * real backend error message.
 *
 * Visible only after the first stage transitions out of "idle"
 * so the empty pristine state doesn't show 6 grey idle dots.
 */
import React from "react";

export default function AnalyzeStageStrip({ stages, defs }) {
  // Hide the strip until at least one stage has begun.
  const anyActive = defs.some((d) => stages[d.id].status !== "idle");
  if (!anyActive) return null;

  return (
    <ol
      data-testid="analyze-stage-strip"
      className="mt-4 flex flex-wrap gap-3 text-xs border border-[var(--rule)] rounded-md px-4 py-3 bg-[color:var(--bg-soft,transparent)]"
    >
      {defs.map((def) => {
        const s = stages[def.id];
        const isRunning = s.status === "running";
        const isDone = s.status === "success";
        const isError = s.status === "error";
        const isIdle = s.status === "idle";
        return (
          <li
            key={def.id}
            data-testid={`analyze-stage-${def.id}`}
            data-status={s.status}
            className={`flex items-center gap-2 px-2 py-1 rounded ${
              isError
                ? "bg-[color:#fee2e2] text-[color:#991b1b]"
                : isRunning
                  ? "text-[var(--ink)] font-medium"
                  : isDone
                    ? "text-[var(--muted)]"
                    : "text-[color:#9ca3af]"
            }`}
          >
            <span className="inline-block w-3.5 text-center" data-testid={`analyze-stage-${def.id}-glyph`}>
              {isRunning && (
                <span
                  className="inline-block w-3 h-3 rounded-full border-2 border-current border-r-transparent animate-spin align-middle"
                  aria-hidden="true"
                />
              )}
              {isDone && <span>✓</span>}
              {isError && <span>✗</span>}
              {isIdle && <span aria-hidden="true">·</span>}
            </span>
            <span data-testid={`analyze-stage-${def.id}-label`}>
              {isDone ? def.done : isError ? def.label.replace(/…$/, " failed") : def.label}
            </span>
            {isDone && s.durationMs != null && (
              <span
                data-testid={`analyze-stage-${def.id}-duration`}
                className="opacity-60"
              >
                {s.durationMs}ms
              </span>
            )}
            {isError && s.error && (
              <span
                data-testid={`analyze-stage-${def.id}-error`}
                className="font-mono text-[10px]"
              >
                — {String(s.error).slice(0, 140)}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
