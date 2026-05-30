/**
 * Phase P2 B.3 (2026-02) — Frontend ErrorBoundary.
 *
 * Wraps every top-level route. Catches React render errors below this
 * boundary and shows a friendly fallback rather than a blank white
 * screen. When Sentry is wired (D.1), errors are reported via
 * `captureException`. Voice-clean: no marketing puffery.
 *
 * Why class component? React's `componentDidCatch` only works on class
 * components — there's no hook equivalent today.
 */
import React from "react";
import * as Sentry from "@sentry/react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // Report to Sentry when initialised (D.1). When the SDK is in
    // no-op mode (no DSN), `captureException` is a safe call.
    try {
      Sentry.captureException(error, { extra: { componentStack: info?.componentStack } });
    } catch (_e) { /* swallow — never throw from componentDidCatch */ }
    // Also log to the browser console so the user can paste it
    // into a feedback widget submission.
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary caught:", error, info);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    const msg = (this.state.error && this.state.error.message) || "Something went wrong.";
    return (
      <div
        className="min-h-[60vh] flex flex-col items-center justify-center px-6 py-12 text-center"
        data-testid="error-boundary-fallback"
      >
        <h2
          className="akki-serif text-[28px] text-[var(--ink)] mb-3"
          data-testid="error-boundary-heading"
        >
          This page hit an error.
        </h2>
        <p
          className="text-[14px] text-[var(--deep)] max-w-md mb-6 leading-relaxed"
          data-testid="error-boundary-body"
        >
          The page below failed to render. Reload to recover. If it
          happens again, share the message below with the team.
        </p>
        <pre
          className="text-[11px] font-mono bg-[var(--cream-deep)] text-[var(--ink)] rounded-sm px-3 py-2 mb-6 max-w-2xl overflow-x-auto"
          data-testid="error-boundary-message"
        >
          {msg}
        </pre>
        <button
          onClick={this.handleReload}
          className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white px-5 py-2 rounded-full text-[13px] font-medium transition-colors"
          data-testid="error-boundary-reload-btn"
        >
          Reload page
        </button>
      </div>
    );
  }
}
