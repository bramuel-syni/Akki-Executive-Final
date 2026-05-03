/**
 * PulsePlaceholder — honest holding page for Phase 14's Akki Pulse.
 *
 * Phase 13.3 added a primary nav slot for Pulse ahead of its build, so
 * users discover it during 13.x and don't get a 404. Editorial FT voice;
 * no "coming soon" ribbon, no banned marketing words. Just the actual
 * promise and a deep link to where per-board signals live today.
 */
import React from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { ArrowRight, Activity } from "lucide-react";

export default function PulsePlaceholder() {
  return (
    <AppShell>
      <div className="max-w-[860px] mx-auto px-8 py-20" data-testid="pulse-placeholder">
        <p className="akki-overline mb-3 text-[var(--accent)] flex items-center gap-2">
          <Activity className="w-3 h-3" /> Akki Pulse
        </p>
        <h1 className="akki-serif text-[40px] sm:text-[52px] leading-[1.08] tracking-[-0.018em] text-[var(--ink)] mb-6 font-normal">
          Akki Pulse arrives in the next phase.
        </h1>
        <p className="akki-serif text-[17px] leading-[1.7] text-[var(--deep)] max-w-[58ch] mb-3">
          When it does, you'll see cross-board patterns surfacing as they happen — capital pressure,
          succession risk, regulatory drift, cyber — each with source attribution back to the
          originating board. NEDs sitting on three or more boards see Pulse first; the patterns are
          anonymised across boards by default and only ever name a specific seat to that seat's
          chair.
        </p>
        <p className="akki-serif text-[17px] leading-[1.7] text-[var(--deep)] max-w-[58ch] mb-10">
          Per-board signals live under{" "}
          <Link to="/app/cycle?tab=signals" className="underline underline-offset-4 decoration-[var(--accent)] hover:text-[var(--ink)]">
            Cycle Manager → Signals
          </Link>
          {" "}for now. Same underlying engine; Pulse adds the cross-board lens.
        </p>
        <Link to="/app/cycle?tab=signals" className="inline-flex items-center gap-2 text-[14px] text-[var(--accent)] hover:text-[var(--ink)] font-medium">
          See per-board signals → <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </AppShell>
  );
}
