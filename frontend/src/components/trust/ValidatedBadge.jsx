/**
 * ValidatedBadge
 *
 * Surfaces AKKI's independent-model validation pass. The badge is
 * STRICTLY honest: we render it only when a real second-LLM
 * countercheck has actually run and produced a verdict. Static / "trust
 * marker" rendering was retired in Phase 8 to avoid the cosmetic-only
 * failure mode the iter68 audit flagged on Decks, Reports and Solve
 * syntheses.
 *
 *   - validation = null / undefined  → renders nothing.
 *   - validation = { verdict: "validated" | "qualified" | "flagged",
 *                    confidence?, notes?[], validator_model? }
 *     → renders the chip + tooltip.
 *
 * Surfaces that want a generic trust marker should use the cream
 * "Shielded" chip in the top bar instead — that one is honest because
 * the regex shielding pass actually does run on every LLM call.
 */
import React, { useState } from "react";
import { ShieldCheck, AlertTriangle, ShieldAlert } from "lucide-react";

const VERDICT_STYLES = {
  validated: {
    label: "Validated by an independent model",
    icon: ShieldCheck,
    classes: "border-emerald-200 bg-emerald-50 text-emerald-800",
  },
  qualified: {
    label: "Qualified — read with care",
    icon: AlertTriangle,
    classes: "border-amber-200 bg-amber-50 text-amber-800",
  },
  flagged: {
    label: "Flagged by an independent model",
    icon: ShieldAlert,
    classes: "border-red-200 bg-red-50 text-red-800",
  },
};

export default function ValidatedBadge({ size = "default", className = "", validation = null }) {
  const [open, setOpen] = useState(false);
  const verdict = validation?.verdict;
  const style = VERDICT_STYLES[verdict] || null;

  // Honest render: no real validation result, no badge. This is the
  // intentional fix for the cosmetic-only badge problem on Decks /
  // Reports / Solve syntheses where the second-LLM call does not run.
  if (!style) return null;

  const isCompact = size === "compact";
  const Icon = style.icon;
  const label = `${style.label}${validation?.confidence ? ` · ${validation.confidence}%` : ""}`;

  return (
    <span className={`relative inline-flex ${className}`}>
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        className={`inline-flex items-center gap-1 border rounded-sm tracking-wider uppercase font-medium ${style.classes} ${
          isCompact ? "px-1.5 py-0.5 text-[9.5px]" : "px-2 py-0.5 text-[10px]"
        }`}
        data-testid={`validated-badge-${verdict}`}
        aria-label={label}
      >
        <Icon className={isCompact ? "w-2.5 h-2.5" : "w-3 h-3"} strokeWidth={2} />
        {label}
      </button>
      {open && (
        <span
          className="absolute z-30 left-0 top-full mt-1 w-[320px] bg-white border border-[var(--rule)] rounded-md shadow-md p-3 text-[12px] text-[var(--deep)] leading-relaxed normal-case tracking-normal"
          data-testid="validated-badge-popover"
          role="tooltip"
        >
          <p className="akki-serif italic text-[12.5px] text-[var(--ink)] mb-1">
            What the second model said
          </p>
          <p>
            {verdict === "validated" && "A second model — independent of the drafter — read this and didn't find anything to qualify."}
            {verdict === "qualified" && "A second model read this and asked you to read with care:"}
            {verdict === "flagged" && "A second model flagged claims it couldn't ground:"}
          </p>
          {Array.isArray(validation?.notes) && validation.notes.length > 0 && (
            <ul className="mt-2 space-y-1 list-disc pl-4 text-[11.5px]">
              {validation.notes.map((n, i) => (
                <li key={i} className="leading-snug">{n}</li>
              ))}
            </ul>
          )}
          <p className="text-[var(--muted)] italic mt-2 text-[11px]">
            Drafter: Claude Sonnet 4.5. Validator: {validation?.validator_model || "Gemini 2.5 Flash"}.
          </p>
        </span>
      )}
    </span>
  );
}
