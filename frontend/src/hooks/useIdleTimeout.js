/**
 * Phase J (2026-05-27) — Idle auto-logoff hook.
 *
 * Listens for human activity (mousemove / keydown / touchstart / click /
 * scroll) at the window level with passive listeners. After 30 minutes
 * of zero activity, the user is logged out automatically.
 *
 * Multi-tab coordination: activity in any tab updates a shared
 * `localStorage` key (`akki_last_activity_ts`). Every tab reads from
 * the same key on each tick so a typing user in tab A doesn't get
 * timed out in background tab B.
 *
 * Visibility guard: when a tab is hidden, we DO NOT update the activity
 * timestamp on `visibilitychange` (would cheat the timeout by simply
 * revealing the tab). Hidden tabs still poll the shared timestamp.
 *
 * UX:
 *   - At T - WARN_AT_MS (2min default): caller's onWarn() fires; the
 *     consumer renders a non-intrusive banner.
 *   - Any subsequent activity dismisses the warning + resets the timer.
 *   - At T = 0: caller's onLogout() fires (usually call /auth/logout
 *     + redirect to /sign-in?reason=idle).
 *
 * Config knobs (env-driven via REACT_APP_IDLE_TIMEOUT_MINUTES, default 30).
 */
import { useEffect, useRef, useState, useCallback } from "react";

const STORAGE_KEY = "akki_last_activity_ts";
const THROTTLE_MS = 5000;   // max 1 reset per 5s
const TICK_MS     = 5000;   // poll cadence
const WARN_OFFSET_MS = 2 * 60 * 1000; // banner 2 min before logout

const ACTIVITY_EVENTS = [
  "mousemove", "keydown", "touchstart", "click", "scroll",
];

function readEnvMinutes() {
  const raw = process.env.REACT_APP_IDLE_TIMEOUT_MINUTES;
  const n = parseInt(raw, 10);
  if (!isNaN(n) && n > 0 && n < 24 * 60) return n;
  return 30;
}

export default function useIdleTimeout({ onLogout, onWarn, onClearWarn, enabled = true } = {}) {
  const timeoutMs = readEnvMinutes() * 60 * 1000;
  const lastResetRef = useRef(0);
  const warnFiredRef = useRef(false);
  const firedRef = useRef(false);
  const [secondsRemaining, setSecondsRemaining] = useState(null);

  // Touch the shared timestamp. Throttled to once per 5s so heavy
  // mousemove activity doesn't hammer localStorage.
  const touchActivity = useCallback(() => {
    if (firedRef.current) return;
    const nowMs = Date.now();
    if (nowMs - lastResetRef.current < THROTTLE_MS) return;
    lastResetRef.current = nowMs;
    try { window.localStorage.setItem(STORAGE_KEY, String(nowMs)); } catch { /* noop */ }
    if (warnFiredRef.current) {
      warnFiredRef.current = false;
      if (typeof onClearWarn === "function") onClearWarn();
    }
  }, [onClearWarn]);

  // Attach activity listeners
  useEffect(() => {
    if (!enabled) return undefined;
    // Seed the timestamp on mount so the first idle window starts now.
    try { window.localStorage.setItem(STORAGE_KEY, String(Date.now())); } catch { /* noop */ }
    const opts = { passive: true, capture: true };
    ACTIVITY_EVENTS.forEach((ev) => window.addEventListener(ev, touchActivity, opts));
    return () => {
      ACTIVITY_EVENTS.forEach((ev) => window.removeEventListener(ev, touchActivity, opts));
    };
  }, [enabled, touchActivity]);

  // Poll the shared timestamp + fire warn/logout when thresholds hit
  useEffect(() => {
    if (!enabled) return undefined;
    const tick = () => {
      if (firedRef.current) return;
      let last;
      try { last = parseInt(window.localStorage.getItem(STORAGE_KEY) || "0", 10); }
      catch { last = Date.now(); }
      if (!last) { last = Date.now(); }
      const elapsed = Date.now() - last;
      const remaining = timeoutMs - elapsed;
      setSecondsRemaining(Math.max(0, Math.round(remaining / 1000)));
      if (remaining <= 0) {
        firedRef.current = true;
        if (typeof onLogout === "function") onLogout();
        return;
      }
      if (remaining <= WARN_OFFSET_MS && !warnFiredRef.current) {
        warnFiredRef.current = true;
        if (typeof onWarn === "function") onWarn(Math.round(remaining / 1000));
      }
    };
    tick();  // immediate read so consumers don't wait 5s for the first state
    const id = setInterval(tick, TICK_MS);
    return () => clearInterval(id);
  }, [enabled, timeoutMs, onLogout, onWarn]);

  return { secondsRemaining, timeoutMs };
}
