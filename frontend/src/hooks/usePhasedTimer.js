/**
 * Phase L.b.2 (2026-05-27) — usePhasedTimer.
 *
 * Timer-driven phase walker that mirrors the state shape of
 * `useStreamingProgress` so the SAME `<StreamingLogScene>` component
 * renders identically whether the driver is a real SSE pipe (L.a) or
 * a local timer (L.b.2).
 *
 * Why timer-driven instead of SSE for the L.b surfaces:
 *  - WS Enhance: backend wrap declares `Body(...)`; the existing POST
 *    is multipart (file upload). Can't be JSON-streamed without a
 *    backend signature change.
 *  - Task Manager Compile + Decks Generation: inner handlers are
 *    job-queue-based (202 + job_id), so the SSE wrap's `complete`
 *    event carries the job_id, not the final artefact — frontend
 *    still polls. Phase events would emit before the work starts.
 *  - Calendar Sync: inner handler signature uses `me=Depends(...)`,
 *    not `ctx=Depends(...)` — wrap call mismatch.
 *  - Solva Synthesis: legacy URL is `/api/solva/v2/sessions/{sid}/turn`
 *    (no context_id); streaming endpoint requires context_id.
 *
 * When the L.b backend pipes are reconciled (a future L.b.3 dispatch),
 * consumers swap to `useStreamingProgress` by replacing this hook —
 * the `state` shape is identical.
 *
 * State shape (matches useStreamingProgress.state):
 *   {
 *     surface:          string | null,
 *     phases:           Array<{label, icon}>,
 *     activeIndex:      number  (-1 idle, 0..N-1 streaming),
 *     completedIndexes: Set<number>,
 *     result:           any | null,
 *     error:            { code, message } | null,
 *     status:           'idle' | 'streaming' | 'complete' | 'error' | 'cancelled',
 *   }
 *
 * `start(surface, opts?)` begins walking the surface's PHASE_SCRIPTS.
 * Each phase advances on a fixed interval (default 1400ms). On the
 * final phase, `status` stays `streaming` (with the final phase
 * `active`) until the consumer calls `complete(payload)` to indicate
 * the actual data POST landed — at which point all phases flip to
 * completed and `status` becomes `complete`.
 *
 * `error(code, message)` switches to error state.
 * `cancel()` stops the timer and switches to cancelled.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { LB_PHASE_SCRIPTS } from "@/data/phaseScripts";

const INITIAL_STATE = {
  surface: null,
  phases: [],
  activeIndex: -1,
  completedIndexes: new Set(),
  result: null,
  error: null,
  status: "idle",
};

export default function usePhasedTimer() {
  const [state, setState] = useState(INITIAL_STATE);
  const intervalRef = useRef(null);

  const _clearInterval = useCallback(() => {
    if (intervalRef.current) {
      try { clearInterval(intervalRef.current); } catch { /* noop */ }
      intervalRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    _clearInterval();
    setState(INITIAL_STATE);
  }, [_clearInterval]);

  const start = useCallback((surface, opts = {}) => {
    const { stepMs = 1400 } = opts;
    const phases = LB_PHASE_SCRIPTS[surface];
    if (!phases || !phases.length) {
      setState({
        ...INITIAL_STATE,
        status: "error",
        error: { code: "unknown_surface", message: `Unknown surface: ${surface}` },
      });
      return;
    }
    _clearInterval();
    setState({
      ...INITIAL_STATE,
      surface,
      phases,
      activeIndex: 0,
      status: "streaming",
    });
    // Walk through phases on the timer, stopping at the last phase
    // (so the consumer's complete() call triggers the final flip).
    intervalRef.current = setInterval(() => {
      setState((s) => {
        if (s.status !== "streaming") return s;
        const next = s.activeIndex + 1;
        if (next >= s.phases.length) {
          // Stay on the final phase as `active` until complete() lands.
          _clearInterval();
          return s;
        }
        const completed = new Set(s.completedIndexes);
        completed.add(s.activeIndex);
        return { ...s, activeIndex: next, completedIndexes: completed };
      });
    }, stepMs);
  }, [_clearInterval]);

  const complete = useCallback((payload = null) => {
    _clearInterval();
    setState((s) => {
      if (s.status === "error" || s.status === "cancelled") return s;
      const completed = new Set(s.completedIndexes);
      const finalIdx = s.phases.length - 1;
      for (let i = 0; i <= finalIdx; i++) completed.add(i);
      return {
        ...s,
        status: "complete",
        result: payload,
        completedIndexes: completed,
        activeIndex: finalIdx,
      };
    });
  }, [_clearInterval]);

  const error = useCallback((code, message) => {
    _clearInterval();
    setState((s) => ({
      ...s,
      status: "error",
      error: { code: code || "unknown_error", message: message || "Something went wrong." },
    }));
  }, [_clearInterval]);

  const cancel = useCallback(() => {
    _clearInterval();
    setState((s) => ({ ...s, status: s.status === "complete" ? "complete" : "cancelled" }));
  }, [_clearInterval]);

  useEffect(() => () => { _clearInterval(); }, [_clearInterval]);

  return { state, start, complete, error, cancel, reset };
}
