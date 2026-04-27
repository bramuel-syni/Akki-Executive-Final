/**
 * ValidatedByIndependentModelBadge
 *
 * Surfaces the existing Synisense-shielded validation pass as an editorial
 * chip — the user feedback addendum (§4.2 + §5) was explicit: this
 * differentiation must come through in the journey, not be buried.
 *
 * Today: every claim AKKI surfaces routes through the Synisense shielding
 * and counter-check pass. We render the chip wherever those outputs are
 * displayed — briefings, document summaries, signals, simulations.
 *
 * Hover/click reveals an editorial methodology tooltip explaining what
 * "validated by an independent model" means at AKKI.
 *
 * The component is intentionally small (~64×20px) so it can sit beside a
 * headline without competing.
 */
import React, { useState } from "react";
import { ShieldCheck } from "lucide-react";

export default function ValidatedBadge({ size = "default", className = "" }) {
  const [open, setOpen] = useState(false);
  const isCompact = size === "compact";
  return (
    <span className={`relative inline-flex ${className}`}>
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        className={`inline-flex items-center gap-1 border border-emerald-200 bg-emerald-50 text-emerald-800 rounded-sm tracking-wider uppercase font-medium ${
          isCompact ? "px-1.5 py-0.5 text-[9.5px]" : "px-2 py-0.5 text-[10px]"
        }`}
        data-testid="validated-badge"
        aria-label="Validated by an independent model"
      >
        <ShieldCheck className={isCompact ? "w-2.5 h-2.5" : "w-3 h-3"} strokeWidth={2} />
        Validated by an independent model
      </button>
      {open && (
        <span
          className="absolute z-30 left-0 top-full mt-1 w-[300px] bg-white border border-[var(--rule)] rounded-md shadow-md p-3 text-[12px] text-[var(--deep)] leading-relaxed normal-case tracking-normal"
          data-testid="validated-badge-popover"
          role="tooltip"
        >
          <p className="akki-serif italic text-[12.5px] text-[var(--ink)] mb-1">
            What this means
          </p>
          <p>
            Before this output reached you, a second model — independent of the
            one that drafted it — counterchecked the claims, verified the
            sources, and flagged anything it couldn't ground. What survived
            that pass is what you're reading.
          </p>
          <p className="text-[var(--muted)] italic mt-1.5 text-[11px]">
            The validation pass runs on every briefing, summary, signal and
            simulation. You can audit the trail in the trust centre.
          </p>
        </span>
      )}
    </span>
  );
}
