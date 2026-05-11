/**
 * Phase K — WorkspaceEntryScene. First-time-in-session reveal for the
 * four operational workspaces: Solva / Cycle Manager / Work Studio /
 * Monitor. 3–5 second total. Drives lines from `useStreamingScene`.
 *
 * Pattern (per spec): context line → architecture reveals progressively
 * → operational state.
 */
import React from "react";
import useStreamingScene from "./useStreamingScene";

export default function WorkspaceEntryScene({
  workspace,        // one of: 'solva' | 'cycle' | 'work_studio' | 'monitor'
  lines,            // optional override; otherwise use defaults below
  onComplete,
  testId,
}) {
  const finalLines = lines || DEFAULT_LINES[workspace] || DEFAULT_LINES.solva;
  const { stepIndex } = useStreamingScene({
    lines: finalLines,
    intervalMs: 1100,
    onComplete,
  });
  return (
    <div
      data-testid={testId || `workspace-entry-${workspace}`}
      role="status"
      aria-live="polite"
      style={{
        textAlign: "center",
        padding: "72px 32px 96px",
        minHeight: 320,
        color: "var(--ink)",
      }}
    >
      <p
        style={{
          fontFamily: "Georgia, 'Times New Roman', serif",
          fontSize: 26, fontWeight: 700, marginBottom: 36,
        }}
      >
        {finalLines[0]}
      </p>
      {finalLines.slice(1).map((line, i) => (
        <p
          key={line}
          aria-hidden={i + 1 > stepIndex}
          style={{
            fontFamily: "Calibri, 'Helvetica Neue', Arial, sans-serif",
            fontSize: 15, color: "var(--muted)",
            opacity: (i + 1) <= stepIndex ? 1 : 0.16,
            marginBottom: 10,
            transition: "opacity 200ms ease-out",
          }}
        >
          {line}
        </p>
      ))}
    </div>
  );
}

const DEFAULT_LINES = {
  solva: [
    "Solva is opening.",
    "Loading your framing options.",
    "Preparing the four modes.",
    "Ready when you are.",
  ],
  cycle: [
    "Cycle Manager.",
    "Reading the agenda.",
    "Threading the follow-ups.",
    "Ready.",
  ],
  work_studio: [
    "Work Studio.",
    "Loading your boardpacks, briefs and reports.",
    "Determinism contract armed.",
    "Ready.",
  ],
  monitor: [
    "Monitor.",
    "Reading your role's signal whitelist.",
    "Surfacing what is worth attention.",
    "Ready.",
  ],
};
