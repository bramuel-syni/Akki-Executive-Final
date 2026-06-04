/**
 * Phase L.a (2026-05-27) — Streaming-progress hook (fetch-based SSE).
 *
 * Reads from any backend endpoint that emits the Phase L SSE event
 * taxonomy:
 *   - `script`   → { surface, phases: [{label, icon}, ...], total }
 *   - `phase`    → { index, label, icon, total, elapsed_ms }
 *   - `complete` → { index, total, elapsed_ms, result: <legacy-json> }
 *   - `error`    → { code, error }
 *
 * **Why fetch instead of EventSource:**
 *   - EventSource is GET-only; the Solva frame-audit endpoint is POST.
 *   - EventSource doesn't accept custom headers (we need bearer auth).
 *   - fetch + ReadableStream covers both POST and GET, carries bearer,
 *     and the SSE wire format is identical to parse.
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
 * **Cancellation:** when the consuming component unmounts OR explicitly
 * calls `cancel()`, the AbortController aborts the fetch. The backend
 * detects the disconnect via `request.is_disconnected()`.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

const INITIAL_STATE = {
  surface: null,
  phases: [],
  activeIndex: -1,
  completedIndexes: new Set(),
  result: null,
  error: null,
  status: "idle",
};

function _parseSseBlocks(buffer) {
  // Returns { events: [{event, data}], remainder }
  const events = [];
  let buf = buffer;
  let idx;
  while ((idx = buf.indexOf("\n\n")) !== -1) {
    const block = buf.slice(0, idx);
    buf = buf.slice(idx + 2);
    if (!block.trim() || block.trimStart().startsWith(":")) {
      // comment / heartbeat — skip
      continue;
    }
    let eventName = "message";
    let dataLine = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLine += line.slice(5).trim();
    }
    events.push({ event: eventName, data: dataLine });
  }
  return { events, remainder: buf };
}

export default function useStreamingProgress() {
  const [state, setState] = useState(INITIAL_STATE);
  const abortRef = useRef(null);

  const _abort = useCallback(() => {
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch { /* noop */ }
      abortRef.current = null;
    }
  }, []);

  const cancel = useCallback(() => {
    _abort();
    setState((s) => ({ ...s, status: s.status === "complete" ? "complete" : "cancelled" }));
  }, [_abort]);

  const reset = useCallback(() => {
    _abort();
    setState(INITIAL_STATE);
  }, [_abort]);

  /**
   * Open a fetch-SSE stream against `url`.
   *
   * @param {string} url   - target endpoint (caller must include `?stream=1` etc.)
   * @param {object} opts  - { method?, body?, headers? }
   *   method  default "GET"
   *   body    JSON-serialised if present (sets Content-Type: application/json)
   *   headers extra request headers (Authorization is auto-added from localStorage)
   */
  const stream = useCallback(async (url, opts = {}) => {
    const { method = "GET", body = null, headers = {} } = opts;
    _abort();
    setState({ ...INITIAL_STATE, status: "connecting" });

    const tok = (typeof window !== "undefined")
      ? window.localStorage.getItem("akki_access_token")
      : null;
    // Track A Phase 5 (2026-06-04, W3 Tightening 1) — the CSRF
    // middleware on every `/stream` endpoint rejects POSTs that lack
    // an `X-CSRF-Token` header with 403. The non-stream paths get
    // their CSRF header from the `api` axios interceptor; this hook
    // fetches the token explicitly because we use raw `fetch()` for
    // ReadableStream support (axios can't expose it). Repro evidence:
    // /tmp/phase5_w3_repro_v2.py Case D — POST /enhance/minutes/stream
    // returned 403 {"code":"csrf_token_missing"} before this fix.
    let csrfToken = null;
    if (method !== "GET" && method !== "HEAD") {
      try {
        const csrfRes = await api.get("/csrf");
        csrfToken = csrfRes?.data?.csrf_token || null;
      } catch { /* CSRF fetch best-effort; the request will surface the 403 if missing */ }
    }

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    // Phase L.b.3 (2026-05-27): FormData bodies pass through verbatim
    // so multipart uploads (e.g. Work Studio Enhance) can stream too.
    // The browser sets the multipart boundary itself when Content-Type
    // is omitted — we therefore skip the JSON Content-Type header for
    // FormData bodies.
    const isFormData = typeof FormData !== "undefined" && body instanceof FormData;
    const requestBody = body == null
      ? null
      : (isFormData ? body : JSON.stringify(body));
    const contentTypeHeader = (body != null && !isFormData)
      ? { "Content-Type": "application/json" }
      : {};

    let res;
    try {
      // eslint-disable-next-line no-restricted-syntax -- SSE stream; axios can't expose ReadableStream
      res = await fetch(url, {
        method,
        headers: {
          Accept: "text/event-stream",
          ...contentTypeHeader,
          ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
          ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
          ...headers,
        },
        body: requestBody,
        signal: ctrl.signal,
        credentials: "include",
      });
    } catch (e) {
      if (e.name === "AbortError") return;
      setState((s) => ({ ...s, status: "error",
        error: { code: "fetch_failed", message: String(e?.message || e) } }));
      return;
    }

    if (!res.ok || !res.body) {
      setState((s) => ({ ...s, status: "error",
        error: { code: `http_${res.status}`, message: `HTTP ${res.status}` } }));
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    try {
      // First-chunk transition to streaming
      setState((s) => ({ ...s, status: "streaming" }));

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const { events, remainder } = _parseSseBlocks(buf);
        buf = remainder;
        for (const ev of events) {
          let payload = {};
          try { payload = ev.data ? JSON.parse(ev.data) : {}; } catch { payload = {}; }

          if (ev.event === "script") {
            setState((s) => ({
              ...s,
              status: "streaming",
              surface: payload.surface || s.surface,
              phases: Array.isArray(payload.phases) ? payload.phases : [],
            }));
          } else if (ev.event === "phase") {
            setState((s) => {
              const completed = new Set(s.completedIndexes);
              for (let i = 0; i < payload.index; i++) completed.add(i);
              return {
                ...s,
                status: "streaming",
                activeIndex: typeof payload.index === "number" ? payload.index : s.activeIndex,
                completedIndexes: completed,
              };
            });
          } else if (ev.event === "complete") {
            setState((s) => {
              const completed = new Set(s.completedIndexes);
              const finalIdx = typeof payload.index === "number" ? payload.index : s.activeIndex;
              for (let i = 0; i <= finalIdx; i++) completed.add(i);
              return {
                ...s,
                status: "complete",
                result: payload.result ?? null,
                completedIndexes: completed,
                activeIndex: finalIdx,
              };
            });
          } else if (ev.event === "error") {
            setState((s) => ({
              ...s,
              status: "error",
              error: {
                code: payload.code || "server_error",
                message: payload.error || "Stream failed",
              },
            }));
          }
          // `message` / unknown event types are ignored — Phase L taxonomy is fixed.
        }
      }
    } catch (e) {
      if (e.name === "AbortError") return;
      setState((s) => {
        if (s.status === "complete") return s;
        return { ...s, status: "error",
          error: { code: "stream_read_failed", message: String(e?.message || e) } };
      });
    } finally {
      abortRef.current = null;
    }
  }, [_abort]);

  // Cleanup on unmount
  useEffect(() => {
    return () => { _abort(); };
  }, [_abort]);

  return { state, stream, cancel, reset };
}
