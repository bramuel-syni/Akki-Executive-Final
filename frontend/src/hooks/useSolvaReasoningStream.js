/**
 * Solva v2 — Slice 3b (2026-05-29) reasoning-stream consumer hook.
 *
 * Layered on top of the same fetch+ReadableStream SSE primitive as
 * `useStreamingProgress` (Phase L), but with its own event taxonomy:
 *
 *     event: solva.reasoning.script    → header (total_events, schema_version)
 *     event: solva.reasoning           → per-event SolvaStreamEvent payload
 *     event: complete                   → session closure
 *
 * The hook returns:
 *   • events           — array of all received SolvaStreamEvent objects (arrival order)
 *   • currentLayer     — locked layer_id of the most recent event ('L0'..'L4' | null)
 *   • currentLayerName — canonical layer_name ('frame_audit' | 'surface' | 'depth' | 'synthesis' | 'reflection')
 *   • currentStep      — latest step_description string
 *   • slideReadyMap    — { cover: true, headline: false, ... } for the 13 locked kinds
 *   • totalEvents      — locked count from the script header (so the ticker can show progress)
 *   • isComplete       — true once event:complete OR session.complete arrives
 *   • status           — 'idle' | 'connecting' | 'streaming' | 'complete' | 'error' | 'cancelled'
 *   • error            — { code, message } | null
 *   • replayMode       — true when the SSE endpoint replays a completed session
 *
 * The hook honors a `?replay=0` URL override: when set, the SSE call
 * is skipped and `slideReadyMap` initialises with all 13 kinds true so
 * the artefact lands fully-rendered without an animation.
 *
 * Wave 4.2.followup.2 compliance — all skeleton tints come from
 * `bg-ned-purple/N` short-name utilities; no opacity-modifier-on-hex
 * traps.
 */
import { useCallback, useEffect, useRef, useState } from "react";


const LOCKED_SLIDE_KINDS = [
  "cover",
  "headline",
  "tensions_overview",
  "per_tension",
  "scenarios_overview",
  "per_scenario_table",
  "sensitivity",
  "reflection",
  "bias_inventory",
  "pathway",
  "decision_logic",
  "risk_mitigation",
  "methodological_honesty",
  "in_closing",
];


function _emptySlideMap(initial = false) {
  return LOCKED_SLIDE_KINDS.reduce(
    (acc, k) => Object.assign(acc, { [k]: initial }),
    {},
  );
}


/**
 * Parse a raw SSE buffer into discrete events. Returns
 * `{ events: [{event, data}], remainder }`. Same shape as the Phase L
 * primitive in `useStreamingProgress.js`. Reproduced here so this hook
 * stays self-contained — extending the Phase L hook would couple this
 * surface to that one's taxonomy.
 */
function _parseSseBlocks(buffer) {
  const out = [];
  const parts = buffer.split(/\r?\n\r?\n/);
  const remainder = parts.pop();
  for (const block of parts) {
    if (!block.trim()) continue;
    let eventName = "message";
    let dataLines = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith(":")) continue;            // SSE comment
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).replace(/^\s/, ""));
      }
    }
    out.push({ event: eventName, data: dataLines.join("\n") });
  }
  return { events: out, remainder };
}


/**
 * Resolve the `?replay=...` URL override to one of three discrete
 * modes. The orchestrator surfaces this verbatim on the artefact root
 * as `data-solva-v2-replay-mode` so tests can probe deterministically.
 *
 *   "instant"  → ?replay=0/false/off/no — bypass animation, slides
 *                 render fully right away
 *   "replay"   → no URL param OR ?replay=1/true/on/yes — animated
 *                 rapid-replay of the 5-layer pass (default UX)
 *   "live"     → reserved for future in-flight session broadcast
 *                 (Slice 3.followup.1, parked). Not currently emitted
 *                 by the helper but reserved on the attribute enum.
 */
function _resolveReplayMode() {
  if (typeof window === "undefined" || !window.location) return "replay";
  try {
    const sp = new URLSearchParams(window.location.search);
    if (!sp.has("replay")) return "replay";
    const raw = String(sp.get("replay") || "").trim().toLowerCase();
    if (["0", "false", "off", "no"].includes(raw)) return "instant";
    if (["1", "true", "on", "yes"].includes(raw)) return "replay";
  } catch {
    // noop
  }
  return "replay";
}


function _isReplayBypass() {
  return _resolveReplayMode() === "instant";
}


const INITIAL_STATE = {
  events: [],
  currentLayer: null,
  currentLayerName: null,
  currentStep: "",
  slideReadyMap: _emptySlideMap(false),
  totalEvents: 0,
  isComplete: false,
  status: "idle",
  error: null,
  replayMode: "replay",   // Slice 3b correction (2026-05-29): resolved
                           // by `_resolveReplayMode()` on mount; one of
                           // "replay" | "instant" | "live". Surfaced
                           // verbatim on the artefact root.
};


export default function useSolvaReasoningStream(sessionId, opts = {}) {
  const { enabled = true, apiBase = "" } = opts;
  const [state, setState] = useState(INITIAL_STATE);
  const abortRef = useRef(null);

  const _abort = useCallback(() => {
    if (abortRef.current) {
      try { abortRef.current.abort(); } catch { /* noop */ }
      abortRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!enabled || !sessionId) return undefined;

    // ?replay=0 fast-path — bypass the animation, mark every slide ready.
    if (_isReplayBypass()) {
      setState({
        ...INITIAL_STATE,
        slideReadyMap: _emptySlideMap(true),
        status: "complete",
        isComplete: true,
        currentStep: "Session complete — replay bypassed (?replay=0)",
        replayMode: "instant",
      });
      return undefined;
    }

    let dead = false;
    // Resolve the replay mode synchronously so the orchestrator's
    // `data-solva-v2-replay-mode` attribute reflects the URL override
    // from the very first render, not after the SSE script header lands.
    const resolvedMode = _resolveReplayMode();
    setState({ ...INITIAL_STATE, status: "connecting", replayMode: resolvedMode });

    const tok = (typeof window !== "undefined")
      ? window.localStorage.getItem("akki_access_token")
      : null;

    const baseURL =
      apiBase ||
      (typeof process !== "undefined" && process.env && process.env.REACT_APP_BACKEND_URL) ||
      "";
    const url = `${baseURL}/api/solva/sessions/${sessionId}/v2/stream`;

    const ctrl = new AbortController();
    abortRef.current = ctrl;

    (async () => {
      let res;
      try {
        // eslint-disable-next-line no-restricted-syntax -- SSE: axios cannot expose ReadableStream
        res = await fetch(url, {
          method: "GET",
          headers: {
            Accept: "text/event-stream",
            ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
          },
          signal: ctrl.signal,
          credentials: "include",
        });
      } catch (e) {
        if (e.name === "AbortError" || dead) return;
        setState((s) => ({
          ...s,
          status: "error",
          error: { code: "fetch_failed", message: String(e?.message || e) },
        }));
        return;
      }
      if (!res.ok || !res.body) {
        if (dead) return;
        setState((s) => ({
          ...s,
          status: "error",
          error: { code: `http_${res.status}`, message: `HTTP ${res.status}` },
        }));
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      setState((s) => ({ ...s, status: "streaming" }));

      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          if (dead) return;
          buf += decoder.decode(value, { stream: true });
          const { events, remainder } = _parseSseBlocks(buf);
          buf = remainder;
          for (const ev of events) {
            let payload = {};
            try { payload = ev.data ? JSON.parse(ev.data) : {}; } catch { payload = {}; }

            if (ev.event === "solva.reasoning.script") {
              setState((s) => ({
                ...s,
                totalEvents: typeof payload.total_events === "number" ? payload.total_events : s.totalEvents,
                // Note: do NOT override replayMode here. The mode is
                // resolved from the URL on mount and stays stable; the
                // SSE script header just confirms the server is
                // streaming, it doesn't redefine the user's intent.
              }));
            } else if (ev.event === "solva.reasoning") {
              setState((s) => {
                const nextEvents = s.events.concat([payload]);
                const nextSlideMap = (
                  payload.step_kind === "slide.ready" && payload.slide_kind
                ) ? Object.assign({}, s.slideReadyMap, { [payload.slide_kind]: true })
                  : s.slideReadyMap;
                return {
                  ...s,
                  events: nextEvents,
                  currentLayer: payload.layer_id || s.currentLayer,
                  currentLayerName: payload.layer_name || s.currentLayerName,
                  currentStep: payload.step_description || s.currentStep,
                  slideReadyMap: nextSlideMap,
                  isComplete: payload.step_kind === "session.complete" ? true : s.isComplete,
                  status: payload.step_kind === "session.complete" ? "complete" : "streaming",
                };
              });
            } else if (ev.event === "complete") {
              // Slice 3b correction (2026-05-29): DO NOT force all
              // slides ready on the SSE wire-close event. Each slide
              // must flip to ready strictly via its own slide.ready
              // event so the visual progression stays coherent with
              // the ticker's layer-by-layer narration. The synthesizer
              // emits all 13 slide.ready events BEFORE session.complete
              // arrives, so the map is naturally fully populated by
              // the time event:complete fires.
              setState((s) => ({
                ...s,
                status: "complete",
                isComplete: true,
              }));
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
          }
        }
      } catch (e) {
        if (e.name === "AbortError" || dead) return;
        setState((s) => {
          if (s.status === "complete") return s;
          return {
            ...s,
            status: "error",
            error: { code: "stream_read_failed", message: String(e?.message || e) },
          };
        });
      } finally {
        abortRef.current = null;
      }
    })();

    return () => {
      dead = true;
      _abort();
    };
  }, [sessionId, enabled, apiBase, _abort]);

  return state;
}


// Exposed for unit testing.
export const __TESTING__ = {
  LOCKED_SLIDE_KINDS,
  _parseSseBlocks,
  _isReplayBypass,
  _emptySlideMap,
};
