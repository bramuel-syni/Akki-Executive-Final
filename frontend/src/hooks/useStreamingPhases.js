/**
 * useStreamingPhases — Patch 12 v3 rewrite.
 *
 * Consumes one of the Patch 9 SSE wrapper endpoints, paces the visible
 * content through `clauseStream` (variable cadence), and surfaces the
 * standard motion state.
 *
 *   const {
 *     start, stop, retry,
 *     phase, status,
 *     visibleContent,  // user-facing string — paced, clause-grouped
 *     result,          // full JSON returned by the inner handler
 *     error,
 *     latencyMs,
 *   } = useStreamingPhases({ endpoint, body });
 *
 * Differences vs v2 (Patch 9):
 *   - No skeleton frame state — caller renders the empty state
 *   - Clause-aware pacing replaces the raw text accumulation
 *   - `visibleContent` advances at a "thinking pace", not at network pace
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { createClauseBuffer, createClausePacer } from "@/lib/clauseStream";

const DEFAULT_STALL_MS = 10_000;


export default function useStreamingPhases({
  endpoint,
  method = "POST",
  headers = {},
  body = null,
  stallMs = DEFAULT_STALL_MS,
  autoStart = false,
} = {}) {
  const [phase, setPhase] = useState("reading_context");
  const [status, setStatus] = useState("idle");
  const [visibleContent, setVisibleContent] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [latencyMs, setLatencyMs] = useState(null);

  const abortRef = useRef(null);
  const stallRef = useRef(null);
  const bufRef = useRef(null);
  const pacerRef = useRef(null);
  const t0Ref = useRef(0);

  const clearStallTimer = () => {
    if (stallRef.current) { clearTimeout(stallRef.current); stallRef.current = null; }
  };
  const armStallTimer = useCallback(() => {
    clearStallTimer();
    stallRef.current = setTimeout(() => {
      setStatus((s) => (s === "complete" || s === "error" ? s : "stalled"));
    }, stallMs);
  }, [stallMs]);

  const teardown = useCallback(() => {
    if (abortRef.current) { abortRef.current.abort(); abortRef.current = null; }
    if (pacerRef.current) { pacerRef.current.cancel(); pacerRef.current = null; }
    if (bufRef.current) { bufRef.current.cancel(); bufRef.current = null; }
    clearStallTimer();
  }, []);

  const stop = useCallback(() => {
    teardown();
    setStatus((s) => (s === "error" ? s : "complete"));
  }, [teardown]);

  const start = useCallback(async () => {
    if (!endpoint) return;
    teardown();
    setStatus("streaming");
    setVisibleContent("");
    setResult(null);
    setError(null);
    setPhase("reading_context");
    setLatencyMs(null);
    t0Ref.current = performance.now();

    // Pace clauses onto the screen.
    const pacer = createClausePacer({
      onClause: ({ text }) => setVisibleContent((s) => s + text),
    });
    pacerRef.current = pacer;
    const cbuf = createClauseBuffer({
      onFlush: (clause) => pacer.enqueue(clause),
    });
    bufRef.current = cbuf;

    const ctrl = new AbortController();
    abortRef.current = ctrl;
    armStallTimer();

    try {
      // Patch 24B — raw fetch() is required here because we need
      // ReadableStream support for SSE-style token streaming, which
      // axios doesn't expose cleanly. Manually inject the bearer
      // token (same pattern as pages/Chat.jsx) so this matches what
      // the axios `api` interceptor would do automatically.
      const tok = typeof window !== "undefined"
        ? window.localStorage.getItem("akki_access_token")
        : null;
      // eslint-disable-next-line no-restricted-syntax -- streaming SSE; axios cannot
      const res = await fetch(endpoint, {
        method,
        headers: {
          "Content-Type": "application/json",
          ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
          ...headers,
        },
        body: body == null ? null : JSON.stringify(body),
        signal: ctrl.signal,
        credentials: "include",
      });
      if (!res.ok || !res.body) {
        setStatus("error");
        setError(`HTTP ${res.status}`);
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const block = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          let eventType = "message";
          let dataLine = "";
          for (const line of block.split("\n")) {
            if (line.startsWith("event:")) eventType = line.slice(6).trim();
            else if (line.startsWith("data:")) dataLine += line.slice(5).trim();
          }
          armStallTimer();
          setStatus((s) => (s === "stalled" ? "streaming" : s));
          if (eventType === "phase") {
            try {
              const p = JSON.parse(dataLine || "{}");
              if (p?.phase) setPhase(p.phase);
            } catch { /* keep current */ }
          } else if (eventType === "token") {
            try {
              const p = JSON.parse(dataLine || "{}");
              if (typeof p?.text === "string") cbuf.push(p.text);
            } catch {
              cbuf.push(dataLine);
            }
          } else if (eventType === "error") {
            let payload = null;
            try { payload = JSON.parse(dataLine || "{}"); } catch { /* noop */ }
            setError(payload?.detail || dataLine || "Stream error");
            setStatus("error");
          } else if (eventType === "done") {
            // wait for any queued clauses
          } else {
            // Default `message` event carries the final JSON body.
            try {
              const p = JSON.parse(dataLine);
              setResult(p);
            } catch { /* noop */ }
          }
        }
      }
      // Drain.
      cbuf.flush();
      setLatencyMs(performance.now() - t0Ref.current);
      setStatus((s) => (s === "error" ? s : "complete"));
    } catch (e) {
      if (e.name === "AbortError") return;
      setError(e.message || String(e));
      setStatus("error");
    } finally {
      clearStallTimer();
      abortRef.current = null;
    }
  }, [endpoint, method, headers, body, armStallTimer, teardown]);

  const retry = useCallback(() => { start(); }, [start]);

  useEffect(() => {
    if (autoStart) { start(); }
    return () => { teardown(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart]);

  return { start, stop, retry, phase, status, visibleContent, result, error, latencyMs };
}
