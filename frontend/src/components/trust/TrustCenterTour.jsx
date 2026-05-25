/**
 * TrustCenterTour — J3 (2026-05-25, ratified spec §3 Stage 5).
 *
 * Three-stop introduction overlay that appears on the user's FIRST
 * visit to Trust Center after they've uploaded at least one document
 * (the Stage 4 `first_doc_uploaded` gate).
 *
 * Stops (spec §3 Stage 5 — verbatim copy below):
 *   1. Master Audit panel — the canonical record of every Shield touch.
 *   2. Sensitivity Band header — what each band means and how it routes.
 *   3. de_id_summary info popover — the chunk-(d) methodology surface.
 *
 * Contract invariants:
 *   - DOM-unconditional scaffolding (closeout §5.1 + §5.7) — the tour
 *     ROOT renders whenever the parent decides the tour applies; only
 *     the inner step content varies with `currentStep` state.
 *   - Verbatim G28 empty-state copy is the responsibility of the
 *     TrustCenter page (not this tour). The tour copy is its own
 *     spec'd contract: each stop's heading + body string is treated
 *     as a literal.
 *   - On dismiss → `POST /api/users/me/onboarding-status/trust-center-tour/dismiss`
 *     which sets `first_session.trust_center_introduced = true`. The
 *     tour will not re-appear on subsequent visits.
 */
import React, { useState, useCallback, useEffect } from "react";
import { X as XIcon, ArrowRight, ArrowLeft, ShieldCheck } from "lucide-react";
import api from "../../lib/api";

// Spec §3 Stage 5 — verbatim tour-stop copy. Each entry is treated
// as a literal by tests (see test_j3_stage_5_trust_center_tour).
const TOUR_STOPS = [
  {
    id: "master-audit",
    overline: "STOP 1 OF 3",
    title: "Your Master Audit lives here.",
    body: "Every time Shield touched your data — uploads, chats, briefings — there's a row for it below. Tamper-evident, signed, and yours to export.",
  },
  {
    id: "sensitivity-band",
    overline: "STOP 2 OF 3",
    title: "Each session carries a sensitivity band.",
    body: "Bands flag how sensitive the data Shield processed was. They determine where it could go — which models, which audit retention, which export controls.",
  },
  {
    id: "de-id-summary",
    overline: "STOP 3 OF 3",
    title: "Click the info icon on any counter.",
    body: "Session totals and per-turn counts answer different questions. The Info button next to 'Identifiers shielded' explains what each one is counting.",
  },
];

export default function TrustCenterTour({ show, onDismiss }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [dismissing, setDismissing] = useState(false);

  // Reset to step 0 whenever the tour becomes visible.
  useEffect(() => {
    if (show) setStepIndex(0);
  }, [show]);

  const handleDismiss = useCallback(async () => {
    if (dismissing) return;
    setDismissing(true);
    try {
      await api.post("/users/me/onboarding-status/trust-center-tour/dismiss");
    } catch {
      // Best-effort — if the POST fails, still let the user out of the
      // overlay locally. The next visit will re-show the tour, which
      // is acceptable noise.
    } finally {
      if (onDismiss) onDismiss();
    }
  }, [dismissing, onDismiss]);

  const handleNext = useCallback(() => {
    if (stepIndex < TOUR_STOPS.length - 1) {
      setStepIndex((s) => s + 1);
    } else {
      handleDismiss();
    }
  }, [stepIndex, handleDismiss]);

  const handlePrev = useCallback(() => {
    if (stepIndex > 0) setStepIndex((s) => s - 1);
  }, [stepIndex]);

  // DOM-unconditional scaffolding: the root ALWAYS emits when the
  // parent renders <TrustCenterTour show={...} />. The `show` flag
  // controls visibility via CSS, NOT presence in the DOM. This lets
  // tests assert `[data-testid="trust-center-tour"]` exists
  // regardless of timing.
  const stop = TOUR_STOPS[stepIndex];
  return (
    <div
      data-testid="trust-center-tour"
      data-tour-visible={show ? "true" : "false"}
      className={
        "fixed inset-0 z-[80] " +
        (show
          ? "pointer-events-auto bg-black/40 backdrop-blur-[1.5px]"
          : "pointer-events-none invisible opacity-0")
      }
      onClick={(e) => {
        // Click on the backdrop dismisses — but only if clicking
        // OUTSIDE the card itself.
        if (e.target === e.currentTarget) handleDismiss();
      }}
    >
      <div className="absolute right-6 top-20 w-[360px] max-w-[90vw] bg-[var(--cream)] border border-[var(--cream-deep)] rounded-lg shadow-2xl">
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <div className="flex items-center gap-2 text-[var(--ink)]">
            <ShieldCheck className="w-4 h-4" strokeWidth={1.7} />
            <span className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
              Trust Center tour
            </span>
          </div>
          <button
            type="button"
            data-testid="trust-center-tour-close"
            aria-label="Close Trust Center tour"
            onClick={handleDismiss}
            className="text-[var(--muted)] hover:text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--deep)] rounded-sm transition-colors"
          >
            <XIcon className="w-4 h-4" strokeWidth={1.7} />
          </button>
        </div>

        <div className="px-4 pb-4 pt-2">
          <div
            data-testid={`trust-center-tour-stop-${stop.id}`}
            className="space-y-2"
          >
            <div className="text-[10.5px] uppercase tracking-wide text-[var(--muted)]">
              {stop.overline}
            </div>
            <h3 className="text-[16px] text-[var(--ink)] leading-snug font-serif">
              {stop.title}
            </h3>
            <p className="text-[13px] text-[var(--ink)]/85 leading-relaxed">
              {stop.body}
            </p>
          </div>

          <div className="mt-5 flex items-center justify-between">
            <button
              type="button"
              data-testid="trust-center-tour-prev"
              onClick={handlePrev}
              disabled={stepIndex === 0}
              className={
                "inline-flex items-center gap-1 text-[12px] " +
                (stepIndex === 0
                  ? "text-[var(--muted)]/50 cursor-not-allowed"
                  : "text-[var(--muted)] hover:text-[var(--ink)]")
              }
            >
              <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.7} />
              Back
            </button>

            <div className="flex items-center gap-1.5">
              {TOUR_STOPS.map((_, i) => (
                <span
                  key={i}
                  className={
                    "block w-1.5 h-1.5 rounded-full transition-colors " +
                    (i === stepIndex
                      ? "bg-[var(--deep)]"
                      : "bg-[var(--muted)]/30")
                  }
                  aria-hidden="true"
                />
              ))}
            </div>

            <button
              type="button"
              data-testid="trust-center-tour-next"
              onClick={handleNext}
              className="inline-flex items-center gap-1 text-[12px] text-[var(--deep)] hover:text-[var(--ink)] transition-colors"
            >
              {stepIndex < TOUR_STOPS.length - 1 ? "Next" : "Got it"}
              <ArrowRight className="w-3.5 h-3.5" strokeWidth={1.7} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Exported for behavior tests — anti-source-string-assertion guard
// (closeout §5.8). The test imports this constant and asserts the
// verbatim shape, NOT a substring match against rendered output.
export { TOUR_STOPS };
