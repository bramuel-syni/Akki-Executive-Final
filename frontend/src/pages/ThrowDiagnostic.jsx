/**
 * Phase P2.1-4 (2026-02) — Diagnostic test-throw leaf.
 *
 * Double-gated: only mounts in non-production AND when `?ack=1` is in
 * the URL. This guard prevents accidental customer exposure even if
 * `REACT_APP_ENV` is misconfigured.
 *
 * Used by the ErrorBoundary verification trace (see /tmp/p2_1_trace_b3_error_boundary.py).
 * Hitting `/__throw?ack=1` mounts this component, which throws on
 * render. The boundary catches the throw and renders the
 * documented voice-clean fallback UI.
 *
 * Keep this route in place after verification — future tester passes
 * use it to re-confirm boundary behaviour.
 */
import React from "react";

function _BoomLeaf() {
  // Throw during render so the boundary's getDerivedStateFromError +
  // componentDidCatch both fire.
  throw new Error("P2.1-4 diagnostic — error boundary verification (intentional throw).");
}

export default function ThrowDiagnostic() {
  const isProd = (process.env.REACT_APP_ENV || "").toLowerCase() === "production";
  const ack =
    typeof window !== "undefined" &&
    new URLSearchParams(window.location.search).get("ack") === "1";

  if (isProd || !ack) {
    return (
      <div
        className="min-h-[50vh] flex items-center justify-center p-8 text-center text-sm text-[var(--muted)]"
        data-testid="throw-diagnostic-gated"
      >
        Diagnostic route. Append <code className="font-mono">?ack=1</code> to enable in non-production environments.
      </div>
    );
  }
  return <_BoomLeaf />;
}
