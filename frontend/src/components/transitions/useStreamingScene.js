/**
 * Phase K (2026-05-12) — Central streaming-scene hook.
 *
 * Single source of truth for the three strategic in-app streaming
 * transition spots:
 *   1. WorkspaceEntry  — first-time entry to Solva/Cycle/WorkStudio/Monitor.
 *      3–5 second reveal, 3–4 lines.
 *   2. ContextLoading  — 10+ second analytical waits (Solva Layer 0 ingest,
 *      Akki Commentary, Cycle compilation, Work Studio Enhance).
 *      5–7 lines, optionally driven by a real-phase signal.
 *   3. Solva Layer Transitions — already implemented in
 *      `components/solva/flow/TransitionMessage.jsx`; kept as-is to
 *      avoid disturbing the audit-row lineage that depends on its
 *      timing.
 *
 * Hook contract:
 *   const { stepIndex, completed } = useStreamingScene({
 *     lines: string[],
 *     intervalMs: 1500,          // ignored when reduced motion or phaseIndex provided
 *     phaseIndex: number | undefined,  // when provided, step is max(stepIndex, phaseIndex)
 *     onComplete: () => void,
 *   })
 *
 * Calm-fast defaults: 200ms cross-fade between lines. `prefers-reduced-motion`
 * collapses the scene to its final state (all lines visible, no animation).
 */
import { useEffect, useState, useRef } from "react";
import usePrefersReducedMotion from "@/components/solva/flow/usePrefersReducedMotion";

export default function useStreamingScene({
  lines,
  intervalMs = 1500,
  phaseIndex,
  onComplete,
}) {
  const reduced = usePrefersReducedMotion();
  const [stepIndex, setStepIndex] = useState(0);
  const completedRef = useRef(false);

  // Phase-driven progression takes precedence over the timer when
  // provided. Step only moves forward — never backward — so phase
  // jitter doesn't replay earlier lines.
  useEffect(() => {
    if (typeof phaseIndex === "number") {
      setStepIndex((s) => Math.max(s, Math.min(phaseIndex, (lines?.length || 1) - 1)));
    }
  }, [phaseIndex, lines]);

  // Timer-driven progression — used when no phaseIndex is supplied.
  useEffect(() => {
    if (!lines || lines.length === 0) return undefined;
    if (reduced) {
      setStepIndex(lines.length - 1);
      if (!completedRef.current && onComplete) { completedRef.current = true; onComplete(); }
      return undefined;
    }
    if (typeof phaseIndex === "number") return undefined; // phase-driven; skip timer
    const tid = setInterval(() => {
      setStepIndex((s) => {
        const next = Math.min(s + 1, lines.length - 1);
        if (next === lines.length - 1 && !completedRef.current && onComplete) {
          completedRef.current = true;
          // Allow current paint to settle before firing the completion.
          setTimeout(onComplete, intervalMs);
        }
        return next;
      });
    }, intervalMs);
    return () => clearInterval(tid);
  }, [lines, intervalMs, reduced, phaseIndex, onComplete]);

  return {
    stepIndex,
    completed: lines ? stepIndex >= lines.length - 1 : false,
    reduced,
  };
}
