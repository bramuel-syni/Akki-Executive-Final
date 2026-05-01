/**
 * ProPill — small inline badge used next to Pro-gated CTAs.
 *
 * Sits to the right of the primary CTA label (e.g. "Run Risk Lens ⟶ (Pro)")
 * or as a standalone nav-adjacent marker. Oxblood text on cream-deep
 * background, 11px tracking, no border. Screen-reader text reads "Pro
 * plan required".
 */
import React from "react";

export default function ProPill({ className = "", children = "Pro" }) {
  return (
    <span
      className={`inline-flex items-center akki-overline text-[10px] tracking-[0.18em] text-[var(--accent)] bg-[var(--cream-deep)] px-1.5 py-[2px] rounded-sm ${className}`}
      data-testid="pro-pill"
    >
      <span aria-hidden="true">{children}</span>
      <span className="sr-only"> plan required</span>
    </span>
  );
}
