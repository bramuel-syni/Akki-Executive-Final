/**
 * Phase P5.14.1 — Analyze stage tracker.
 *
 * Real-wire stage state machine for the Analyze surface. The hook
 * does NOT use setTimeout or fake progress bars — every transition
 * is driven by a `start()` / `success()` / `error()` call placed
 * around an actual fetch lifecycle event. Stages render in their
 * declared order; only the currently-running stage shows the
 * spinner; completed stages show ✓ and a real duration in ms.
 *
 * Contract used by `WorkStudioAnalyze.jsx`:
 *
 *   const stages = useAnalyzeStages();
 *   ...
 *   stages.start("simulate");
 *   try {
 *     const r = await api.post(`/workbook/analyses/${aid}/simulate`, body);
 *     stages.success("simulate");
 *   } catch (e) {
 *     stages.error("simulate", e?.response?.data?.detail || e.message);
 *     throw e;
 *   }
 *
 * Stage ids are the literal labels mapped in STAGE_DEFS below.
 */
import { useCallback, useRef, useState } from "react";

export const STAGE_DEFS = [
  { id: "parse",     label: "Parsing workbook…",      done: "Parsed" },
  { id: "signals",   label: "Extracting signals…",    done: "Signals extracted" },
  { id: "simulate",  label: "Running Monte Carlo…",   done: "Simulation complete" },
  { id: "forecast",  label: "Projecting forecast…",   done: "Forecast complete" },
  { id: "anomalies", label: "Detecting anomalies…",   done: "Anomalies surfaced" },
  { id: "report",    label: "Composing report…",      done: "Report ready" },
];

const _initialState = () =>
  STAGE_DEFS.reduce((acc, s) => {
    acc[s.id] = { status: "idle", startMs: null, durationMs: null, error: null };
    return acc;
  }, {});

export default function useAnalyzeStages() {
  const [state, setState] = useState(_initialState());
  // Track per-stage start times outside React state so we don't
  // race a `start` → `success` pair when the API call is faster
  // than the next render.
  const startRef = useRef({});

  const reset = useCallback(() => {
    startRef.current = {};
    setState(_initialState());
  }, []);

  const start = useCallback((id) => {
    if (!STAGE_DEFS.find((s) => s.id === id)) return;
    startRef.current[id] = performance.now();
    setState((prev) => ({
      ...prev,
      [id]: { ...prev[id], status: "running", startMs: startRef.current[id], error: null },
    }));
  }, []);

  const success = useCallback((id) => {
    if (!STAGE_DEFS.find((s) => s.id === id)) return;
    const startedAt = startRef.current[id] ?? performance.now();
    const dur = Math.max(0, Math.round(performance.now() - startedAt));
    setState((prev) => ({
      ...prev,
      [id]: { ...prev[id], status: "success", durationMs: dur, error: null },
    }));
  }, []);

  const error = useCallback((id, err) => {
    if (!STAGE_DEFS.find((s) => s.id === id)) return;
    const startedAt = startRef.current[id] ?? performance.now();
    const dur = Math.max(0, Math.round(performance.now() - startedAt));
    const msg = typeof err === "string" ? err : (err?.message || String(err));
    setState((prev) => ({
      ...prev,
      [id]: { ...prev[id], status: "error", durationMs: dur, error: msg },
    }));
  }, []);

  return { stages: state, defs: STAGE_DEFS, start, success, error, reset };
}
