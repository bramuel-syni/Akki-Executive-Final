/**
 * Solva v2 — Section divider (Slice 2b correction, 2026-05-29).
 *
 * CORRECTION FROM PRIOR CLOSE-OUT: section dividers are NOT slides —
 * they are visual separators between narrative arcs. They MUST NOT
 * carry `data-solva-v2-slide="true"` or `data-solva-v2-slide-kind=*`
 * because that pollutes the locked 13-kind inventory.
 *
 * New contract for dividers:
 *   • `data-solva-v2-section-divider="true"` (locator for tests)
 *   • `data-solva-v2-section-divider-number={n}` (page number in deck)
 *   • `data-solva-v2-section-divider-footer="true"` (matching footer)
 *   • NO `data-solva-v2-slide-*` attributes anywhere
 *
 * Hairline color = `rgb(184, 182, 175)` (matches sign-in divider via
 * the `--rule` token).
 */
import React from "react";


export default function SectionDivider({
  number,
  total,
  contextName,
  sectionLabel,
  sectionSubtitle,
}) {
  return (
    <section
      data-solva-v2-section-divider="true"
      data-solva-v2-section-divider-number={String(number)}
      className="solva-v2-section-divider solva-v2-slide-frame relative w-full bg-[var(--parchment)] border border-[var(--rule)] rounded-sm px-10 py-12 mb-6 print:mb-0 print:break-after-page print:rounded-none print:border-0"
      style={{ minHeight: "660px" }}
    >
      <header className="flex items-baseline justify-between mb-8">
        <span className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)]">
          Section
        </span>
        <span className="font-mono text-[10.5px] tracking-[0.18em] text-[var(--muted)]">
          {String(number).padStart(2, "0")}&nbsp;/&nbsp;{String(total).padStart(2, "0")}
        </span>
      </header>

      {/* Centered hairline + label */}
      <div className="flex flex-col items-start justify-center" style={{ minHeight: "440px" }}>
        <div
          className="w-24 h-px bg-[var(--rule)] mb-8"
          data-testid="solva-v2-section-divider-hairline"
        />
        <h2 className="akki-serif text-[44px] leading-tight text-[var(--ink)] mb-4 break-words">
          {sectionLabel}
        </h2>
        {sectionSubtitle && (
          <p className="text-[15px] text-[var(--deep)] max-w-[600px] leading-snug break-words">
            {sectionSubtitle}
          </p>
        )}
      </div>

      <footer
        data-solva-v2-section-divider-footer="true"
        className="absolute bottom-4 left-10 right-10 flex items-baseline justify-between border-t border-[var(--rule)] pt-3 font-mono text-[10.5px] tracking-[0.14em] text-[var(--muted)]"
      >
        <span className="truncate pr-4">
          Solve Session Output&nbsp;·&nbsp;Confidential&nbsp;·&nbsp;{contextName}
        </span>
        <span className="flex-shrink-0">
          {String(number).padStart(2, "0")}&nbsp;/&nbsp;{String(total).padStart(2, "0")}
        </span>
      </footer>
    </section>
  );
}
