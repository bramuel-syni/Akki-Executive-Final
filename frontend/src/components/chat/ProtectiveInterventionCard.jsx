/**
 * ProtectiveInterventionCard — renders a per-message intervention
 * (hypothesis-test framing / Solva handoff offer). For Mode B
 * annotation rendering see AnnotatedReply.
 *
 * Phase C (2026-05-13).
 */
import React from "react";
import { Sparkles, ArrowRight } from "lucide-react";

export default function ProtectiveInterventionCard({
  event,
  onSolvaContinue,
}) {
  if (!event || !event.intervention_type || event.intervention_type === "none")
    return null;

  if (event.intervention_type === "hypothesis_test") {
    return (
      <div
        data-testid="protective-card-hypothesis-test"
        className="mb-3 rounded-md border border-amber-200 bg-amber-50/60 px-3 py-2 text-sm text-amber-900"
      >
        <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
          <Sparkles className="h-3.5 w-3.5" />
          Akki recommends framing this first
        </div>
        <p>{event.intervention_text}</p>
      </div>
    );
  }
  if (event.intervention_type === "solva_handoff_offered") {
    return (
      <div
        data-testid="protective-card-solva-handoff"
        className="mt-3 rounded-md border border-indigo-200 bg-indigo-50/60 px-3 py-3 text-sm text-indigo-900"
      >
        <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-indigo-700">
          <Sparkles className="h-3.5 w-3.5" />
          This carries consequence
        </div>
        <p>{event.intervention_text}</p>
        <button
          type="button"
          onClick={onSolvaContinue}
          data-testid="protective-card-solva-button"
          className="mt-2 inline-flex items-center gap-1 rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
        >
          Continue in Solva <ArrowRight className="h-3 w-3" />
        </button>
      </div>
    );
  }
  return null;
}
