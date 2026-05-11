/**
 * SOLVA sprint (2026-05-12) — PerSectionSynisenseBadge.
 *
 * Mirror of the CHAT per-message badge, scoped to a single Solva
 * reasoning surface (framing / grounding / hypothesis / synthesis /
 * reflection). Renders inline at the top of each artefact section.
 *
 * Visual: mono 10px, oxblood text on oxblood-6% bg, 2px radius, 1px 6px
 * padding. Compact single-line: `N IDENTIFIERS REDACTED · L1 X · L2 Y · L3 Z`.
 * Hover surfaces the same numbers in a tooltip for accessibility.
 */
import React, { useEffect, useRef, useState } from "react";

export default function PerSectionSynisenseBadge({ surface, runs, testId }) {
  const [open, setOpen] = useState(false);
  const reducedRef = useRef(false);
  useEffect(() => {
    reducedRef.current =
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);
  if (!runs) {
    return (
      <span
        className="inline-flex items-center font-mono text-[10px] uppercase tracking-[0.14em] px-[6px] py-[1px] rounded-sm bg-[rgba(122,46,46,0.04)] text-[var(--graphite)]"
        data-testid={testId || `solva-section-synisense-${surface}`}
      >
        —
      </span>
    );
  }
  const n = runs?.identifiers_count ?? 0;
  const lb = runs?.layers || { regex: 0, presidio: 0, llm: 0 };
  const label =
    n === 0
      ? "—"
      : n === 1
      ? `1 IDENTIFIER · L1 ${lb.regex || 0} · L2 ${lb.presidio || 0} · L3 ${lb.llm || 0}`
      : `${n} IDENTIFIERS · L1 ${lb.regex || 0} · L2 ${lb.presidio || 0} · L3 ${lb.llm || 0}`;
  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span
        tabIndex={0}
        className="font-mono text-[10px] uppercase tracking-[0.14em] px-[6px] py-[1px] rounded-sm bg-[rgba(122,46,46,0.06)] text-[var(--oxblood)] cursor-default"
        data-testid={testId || `solva-section-synisense-${surface}`}
        aria-describedby={open ? `${testId}-tt` : undefined}
      >
        {label}
      </span>
      {open && n > 0 && (
        <span
          id={`${testId}-tt`}
          role="tooltip"
          className="absolute left-0 top-full mt-1 z-30 whitespace-nowrap font-mono text-[10px] tracking-wide px-2 py-1 rounded-sm bg-[var(--ink)] text-[var(--parchment)]"
          style={{ transition: reducedRef.current ? "none" : "opacity 150ms ease" }}
        >
          Layer 1 regex · {lb.regex || 0} · Layer 2 Presidio · {lb.presidio || 0} · Layer 3 fallback · {lb.llm || 0}
        </span>
      )}
    </span>
  );
}
