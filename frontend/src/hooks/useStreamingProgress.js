/**
 * Phase L.a (2026-05-27) — Streaming-progress hook.
 *
 * Opens an EventSource against a long-op endpoint with `?stream=1` and
 * normalises the inbound events into a shape `StreamingLogScene` can
 * render. Bridges the backend SSE pipe (services/streaming/progress.py)
 * to the React tree.
 *
 * Inbound SSE events:
 *   - `script`   → { surface, phases: [{label, icon}, ...], total }
 *   - `phase`    → { index, label, icon, total, elapsed_ms }
 *   - `complete` → { index, total, elapsed_ms, result: <legacy-json> }
 *   - `error`    → { code, error }
 *
 * Outbound hook state:
 *   {
 *     surface: string | null,
 *     phases:  Array<{label, icon}>,
 *     activeIndex: number,           // -1 before any phase, 0..N-1 during
 *     completedIndexes: Set<number>, // phases with checkmark
 *     result: any | null,            // populated when 'complete' fires
 *     error: { code, message } | null,
 *     status: 'idle' | 'connecting' | 'streaming' | 'complete' | 'error' | 'cancelled',
 *   }
 *
 * **Auth carry:** EventSource doesn't accept custom headers, so we
 * rely on the existing httponly cookie path (browser sends it
 * automatically on same-origin SSE GET). The `withCredentials: true`
 * EventSource option is required for cross-origin — but akki-executive
 * preview is same-origin so this is a no-op there. Production setups
 * with a separate API host need to set `withCredentials: true`.
 *
 * **Cancellation:** when the consuming component unmounts OR explicitly
 * calls `cancel()`, the EventSource closes cleanly. The backend detects
 * the disconnect via `request.is_disconnected()` and short-circuits.
 *
 * **Reduced motion:** the hook itself doesn't animate — that's
 * `StreamingLogScene`'s job. We just emit state; the component reads
 * `prefers-reduced-motion` and collapses transitions accordingly.
 */
import { useCallback, useEffect, useRef, useState } from "react";

const INITIAL_STATE = {
  surface: null,
  phases: [],
  activeIndex: -1,
  completedIndexes: new Set(),
  result: null,
  error: null,
  status: "idle",
};

export default function useStreamingProgress() {
  const [state, setState] = useState(INITIAL_STATE);
  const esRef = useRef(/** @type {EventSource | null} */ (null));

  const _close = useCallback(() => {
    if (esRef.current) {
      try { esRef.current.close(); } catch { /* noop */ }
      esRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    _close();
    setState((s) => ({ ...s, status: s.status === "complete" ? "complete" : "cancelled" }));
  }, [_close]);

  const reset = useCallback(() => {
    _close();
    setState(INITIAL_STATE);
  }, [_close]);

  /**
   * Open an EventSource against `url`. Caller is expected to ensure
   * the URL has `?stream=1` (or whatever flag the endpoint requires).
   * `withCredentials` defaults to true so cookies carry on cross-origin.
   */
  const stream = useCallback((url, { withCredentials = true } = {}) => {
    _close();
    setState({ ...INITIAL_STATE, status: "connecting" });

    let es;
    try {
      es = new EventSource(url, { withCredentials });
    } catch (e) {
      setState((s) => ({ ...s, status: "error",
        error: { code: "eventsource_init_failed", message: String(e) } }));
      return;
    }
    esRef.current = es;

    es.addEventListener("script", (ev) => {
      try {
        const data = JSON.parse(ev.data);
        setState((s) => ({
          ...s,
          status: "streaming",
          surface: data.surface || s.surface,
          phases: Array.isArray(data.phases) ? data.phases : [],
        }));
      } catch { /* ignore malformed */ }
    });

    es.addEventListener("phase", (ev) => {
      try {
        const data = JSON.parse(ev.data);
        setState((s) => {
          // Mark all previous indexes as completed (idempotent set
          // construction so React notices the change)
          const completed = new Set(s.completedIndexes);
          for (let i = 0; i < data.index; i++) completed.add(i);
          return {
            ...s,
            status: "streaming",
            activeIndex: data.index,
            completedIndexes: completed,
          };
        });
      } catch { /* ignore malformed */ }
    });

    es.addEventListener("complete", (ev) => {
      try {
        const data = JSON.parse(ev.data);
        setState((s) => {
          // Mark the active phase + all prior as completed
          const completed = new Set(s.completedIndexes);
          const finalIdx = typeof data.index === "number" ? data.index : s.activeIndex;
          for (let i = 0; i <= finalIdx; i++) completed.add(i);
          return {
            ...s,
            status: "complete",
            result: data.result ?? null,
            completedIndexes: completed,
            activeIndex: finalIdx,
          };
        });
      } catch { /* ignore */ }
      _close();
    });

    es.addEventListener("error", (ev) => {
      // EventSource fires `error` both for backend `event: error` AND
      // for transport errors (connection closed). Distinguish by
      // checking the ready state.
      if (es.readyState === EventSource.CLOSED) {
        setState((s) => {
          // If we already received `complete`, this is just the natural
          // close — don't overwrite status.
          if (s.status === "complete") return s;
          // Transport-layer disconnect mid-stream.
          return { ...s, status: s.status === "streaming" ? "cancelled" : "error",
            error: s.error || { code: "transport_closed", message: "Stream connection lost" } };
        });
        _close();
        return;
      }
      // Server-side `event: error` payload.
      try {
        const data = ev.data ? JSON.parse(ev.data) : {};
        setState((s) => ({
          ...s,
          status: "error",
          error: { code: data.code || "server_error", message: data.error || "Stream failed" },
        }));
      } catch {
        setState((s) => ({ ...s, status: "error",
          error: { code: "server_error", message: "Stream failed" } }));
      }
    });
  }, [_close]);

  // Cleanup on unmount
  useEffect(() => {
    return () => { _close(); };
  }, [_close]);

  return { state, stream, cancel, reset };
}
