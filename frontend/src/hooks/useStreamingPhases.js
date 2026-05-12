/**
 * useStreamingPhases — Patch 9 client hook.
 *
 * Connects to one of the new SSE wrapper endpoints and surfaces:
 *   • phase        — current phase key (PHASE_LABELS in StreamingShell maps to user-facing text)
 *   • status       — "idle" | "streaming" | "stalled" | "complete" | "error"
 *   • partial      — accumulated `data:` payloads (final result lands in `result`)
 *   • result       — the final JSON body emitted by the inner handler
 *   • error        — error text when an `event: error` is received
 *
 * Stall detection: if no `phase` event is received for `stallMs` (default 10s),
 * status flips to "stalled" until the next event arrives (then back to
 * "streaming"). This drives the "Reconnecting · retry now" affordance in
 * StreamingShell.
 *
 * Usage:
 *   const { start, stop, phase, status, partial, result, error } =
 *     useStreamingPhases({
 *       endpoint: `${BACKEND_URL}/api/contexts/${cid}/cycle/draft-compilation/stream`,
 *       method: "POST",
 *       body: { cycle_id: cid },
 *     });
 *
 * Then render:
 *   <StreamingShell phase={phase} status={status} partial={partial} onStop={stop} ... />
 */
import { useCallback, useEffect, useRef, useState } from "react";

const DEFAULT_STALL_MS = 10_000;


export default function useStreamingPhases({ endpoint, method = "POST", headers = {}, body = null, stallMs = DEFAULT_STALL_MS, autoStart = false } = {}) {
  const [phase, setPhase] = useState("reading_context");
  const [status, setStatus] = useState("idle");
  const [partial, setPartial] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);
  const stallTimerRef = useRef(null);

  const clearStallTimer = () => {
    if (stallTimerRef.current) {
      clearTimeout(stallTimerRef.current);
      stallTimerRef.current = null;
    }
  };

  const armStallTimer = useCallback(() => {
    clearStallTimer();
    stallTimerRef.current = setTimeout(() => {
      setStatus((s) => (s === "complete" || s === "error" ? s : "stalled"));
    }, stallMs);
  }, [stallMs]);

  const stop = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    clearStallTimer();
    setStatus((s) => (s === "complete" || s === "error" ? s : "complete"));
  }, []);

  const start = useCallback(async () => {
    if (!endpoint) return;
    setStatus("streaming");
    setPartial("");
    setResult(null);
    setError(null);
    setPhase("reading_context");
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    armStallTimer();
    try {
      const res = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json", ...headers },
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
      let dataBag = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        // Split SSE blocks on blank lines.
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
          // Re-arm the stall timer on every event received.
          armStallTimer();
          setStatus((s) => (s === "stalled" ? "streaming" : s));
          if (eventType === "phase") {
            try {
              const p = JSON.parse(dataLine || "{}");
              if (p?.phase) setPhase(p.phase);
            } catch { /* keep current phase */ }
          } else if (eventType === "error") {
            let payload = null;
            try { payload = JSON.parse(dataLine || "{}"); } catch { /* noop */ }
            setError(payload?.detail || dataLine || "Stream error");
            setStatus("error");
          } else if (eventType === "done") {
            setStatus("complete");
          } else {
            // Default `message` event (no explicit `event:` line)
            // carries the final data body. We accumulate so streaming
            // tokens can be supported later.
            dataBag += dataLine;
            try {
              const p = JSON.parse(dataLine);
              setResult(p);
            } catch {
              setPartial((s) => s + dataLine);
            }
          }
        }
      }
      // Drain any final buffered block.
      if (buf.trim()) {
        try {
          const p = JSON.parse(buf.trim().replace(/^data:\s*/, ""));
          setResult(p);
        } catch { /* noop */ }
      }
      setStatus((s) => (s === "error" ? s : "complete"));
    } catch (e) {
      if (e.name === "AbortError") return;
      setError(e.message || String(e));
      setStatus("error");
    } finally {
      clearStallTimer();
      abortRef.current = null;
    }
  }, [endpoint, method, headers, body, armStallTimer]);

  useEffect(() => {
    if (autoStart) { start(); }
    return () => { stop(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart]);

  return { start, stop, phase, status, partial, result, error };
}
