/**
 * Solva v2 — Methodological honesty slide (Slice 2b, 2026-05-29).
 * Element 12 of 15. What the report IS, what it IS NOT, the
 * provisional-nature paragraph, the input confidence aggregate, and
 * the not-sole-basis disclaimer.
 */
import React from "react";
import SlideShell from "../SlideShell";


export default function MethodologicalHonestySlide({
  honesty,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
  readyAt,
}) {
  if (!honesty) return null;
  return (
    <SlideShell
      kind="methodological_honesty"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      readyAt={readyAt}
      sectionTag="Methodological Honesty"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Method disclosure
        </p>
        <h2 className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-6 max-w-[680px]">
          What this report is — and what it is not
        </h2>

        <div className="space-y-5">
          {/* What it IS */}
          <div data-testid="solva-v2-honesty-is">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--ned-purple)] mb-1.5">
              What this report IS
            </p>
            <p className="text-[13.5px] text-[var(--ink)] leading-relaxed">
              {honesty.what_report_is}
            </p>
          </div>

          {/* What it IS NOT */}
          <div data-testid="solva-v2-honesty-is-not">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--ned-purple)] mb-1.5">
              What this report IS NOT
            </p>
            <p className="text-[13.5px] text-[var(--ink)] leading-relaxed">
              {honesty.what_report_is_not}
            </p>
          </div>

          {/* Provisional nature paragraph */}
          <div data-testid="solva-v2-honesty-provisional">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">
              Provisional
            </p>
            <p className="text-[13px] text-[var(--deep)] leading-relaxed">
              {honesty.provisional_nature_paragraph}
            </p>
          </div>

          {/* Input confidence + not-sole-basis */}
          <div
            className="grid grid-cols-[120px_1fr] gap-x-5 pt-3 border-t border-[var(--rule)]"
            data-testid="solva-v2-honesty-confidence"
          >
            <div>
              <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">
                Input confidence
              </p>
              <p
                className="akki-serif text-[32px] leading-none text-[var(--ned-purple)] tabular-nums"
                data-testid="solva-v2-honesty-confidence-pct"
              >
                {honesty.input_confidence_pct}%
              </p>
            </div>
            <div>
              <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">
                Not the sole basis
              </p>
              <p className="text-[13px] text-[var(--deep)] leading-relaxed">
                {honesty.not_sole_basis_paragraph}
              </p>
            </div>
          </div>
        </div>
      </div>
    </SlideShell>
  );
}
