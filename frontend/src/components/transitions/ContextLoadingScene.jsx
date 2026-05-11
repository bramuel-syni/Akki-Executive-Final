/**
 * Phase K — ContextLoadingScene. The 10+ second analytical wait that
 * appears during Solva Layer 0 ingest, Akki Commentary generation,
 * Cycle Manager compilation, and Work Studio Enhance.
 *
 * Spec contract: each line reflects a real completed phase boundary.
 * When the caller supplies `phaseIndex` (driven by backend progress
 * polling), the hook honours that; otherwise it falls back to a
 * 1500ms timer for offline/test scenarios.
 */
import React from "react";
import useStreamingScene from "./useStreamingScene";

export default function ContextLoadingScene({
  title = "Putting this together.",
  lines,
  phaseIndex,         // optional — driven by real backend status
  onComplete,
  testId = "context-loading-scene",
}) {
  const finalLines = lines || [
    "Reading your inputs.",
    "Checking the grounding contract.",
    "Composing.",
    "Validating.",
    "Almost there.",
  ];
  const { stepIndex } = useStreamingScene({
    lines: finalLines,
    intervalMs: 1500,
    phaseIndex,
    onComplete,
  });
  return (
    <div
      data-testid={testId}
      role="status"
      aria-live="polite"
      style={{
        textAlign: "center",
        paddingTop: 60,
        color: "var(--ink)",
      }}
    >
      <div
        style={{
          fontFamily: "Georgia, 'Times New Roman', serif",
          fontSize: 26, fontWeight: 700, color: "var(--ink)",
          marginBottom: 32,
        }}
      >
        {title}
      </div>
      {finalLines.map((line, i) => (
        <div
          key={line}
          aria-hidden={i > stepIndex}
          style={{
            fontFamily: "Calibri, 'Helvetica Neue', Arial, sans-serif",
            fontSize: 14, color: "var(--slate)",
            opacity: i <= stepIndex ? 1 : 0.18,
            marginBottom: 8,
            transition: "opacity 200ms ease-out",
          }}
        >
          {i < stepIndex ? "✓  " : i === stepIndex ? "·  " : "   "}{line}
        </div>
      ))}
    </div>
  );
}
