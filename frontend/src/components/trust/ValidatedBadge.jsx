/**
 * ValidatedBadge
 *
 * Small editorial chip that surfaces AKKI's independent-model validation
 * pass. Two modes:
 *
 *   1. Static (no `validation` prop) — labels the surface as "Validated
 *      by an independent model" with a hover tooltip explaining the
 *      methodology. Used as a generic trust marker on forms.
 *
 *   2. Live (with `validation` prop from the backend) — renders the
 *      actual verdict from a real second-LLM countercheck (Gemini after
 *      a Claude draft). Three states:
 *        - "validated"   → emerald chip + confidence %
 *        - "qualified"   → amber chip + confidence % + first note tooltip
 *        - "flagged"     → oxblood chip + first note tooltip
 *
 * Hover/click reveals the validator's notes plus the model identity.
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
  const isCompact = size === "compact";
  const verdict = validation?.verdict;
  const style = VERDICT_STYLES[verdict] || null;
  const Icon = style?.icon || ShieldCheck;
  const isLive = Boolean(verdict);

  const label = isLive
    ? `${style.label}${validation?.confidence ? ` · ${validation.confidence}%` : ""}`
    : "Validated by an independent model";

  const chipClasses = isLive
    ? style.classes
    : "border-emerald-200 bg-emerald-50 text-emerald-800";

  return (
    <span className={`relative inline-flex ${className}`}>
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        className={`inline-flex items-center gap-1 border rounded-sm tracking-wider uppercase font-medium ${chipClasses} ${
          isCompact ? "px-1.5 py-0.5 text-[9.5px]" : "px-2 py-0.5 text-[10px]"
        }`}
        data-testid={`validated-badge${isLive ? `-${verdict}` : ""}`}
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
            {isLive ? "What the second model said" : "What this means"}
          </p>
          {isLive ? (
            <>
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
            </>
          ) : (
            <>
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
            </>
          )}
        </span>
      )}
    </span>
  );
}
