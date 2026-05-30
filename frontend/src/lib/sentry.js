/**
 * Phase P2 D.1 (2026-02) — Sentry frontend wiring.
 *
 * Initialises @sentry/react when REACT_APP_SENTRY_DSN is set. No-op
 * otherwise. PII scrubbing is forced ON via `sendDefaultPii: false`
 * and a `beforeSend` hook that drops obvious PII fields out of the
 * event body before it leaves the browser.
 *
 * Returns `"live"` when initialised, `"noop"` otherwise — used by
 * the boot console line so operators can confirm the mode.
 */
import * as Sentry from "@sentry/react";

const PII_KEYS = [
  "email", "password", "first_name", "last_name", "full_name",
  "authorization", "cookie", "set-cookie",
];

function _scrub(value) {
  if (Array.isArray(value)) return value.map(_scrub);
  if (value && typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      const lk = k.toLowerCase();
      out[k] = PII_KEYS.some((p) => lk.includes(p)) ? "[scrubbed]" : _scrub(v);
    }
    return out;
  }
  return value;
}

export function initSentry() {
  const dsn = (process.env.REACT_APP_SENTRY_DSN || "").trim();
  if (!dsn) {
    // eslint-disable-next-line no-console
    console.info("[sentry] noop (REACT_APP_SENTRY_DSN unset)");
    return "noop";
  }
  try {
    Sentry.init({
      dsn,
      environment: (process.env.REACT_APP_SENTRY_ENVIRONMENT || "development").trim(),
      release: (process.env.REACT_APP_SENTRY_RELEASE || undefined),
      tracesSampleRate: Number(process.env.REACT_APP_SENTRY_TRACES_SAMPLE_RATE || "0") || 0,
      replaysSessionSampleRate: 0,
      replaysOnErrorSampleRate: 0,
      sendDefaultPii: false,
      beforeSend(event) {
        try { return _scrub(event); } catch (_e) { return null; }
      },
    });
    // eslint-disable-next-line no-console
    console.info("[sentry] live env=" + (process.env.REACT_APP_SENTRY_ENVIRONMENT || "development"));
    return "live";
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn("[sentry] init failed — continuing in noop mode", e);
    return "noop";
  }
}
