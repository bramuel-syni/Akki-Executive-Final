/**
 * Solva v2 — Risk + mitigation slide (Slice 2b, 2026-05-29).
 * Element 11 of 15. Renders the risk / mitigation pairs derived from
 * high-severity tensions. Each pair sits in a 2-column row.
 */
import React from "react";
import SlideShell from "../SlideShell";


export default function RiskMitigationSlide({
  pairs,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
}) {
  const items = pairs || [];
  return (
    <SlideShell
      kind="risk_mitigation"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      sectionTag="Risk · Mitigation"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Risk register
        </p>
        <h2 className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-6 max-w-[680px]">
          What could go wrong, and the mitigations available today
        </h2>

        {items.length === 0 ? (
          <p className="text-[13px] italic text-[var(--muted)]">
            No high-severity risks were flagged in this session.
          </p>
        ) : (
          <ul
            className="space-y-4"
            data-testid="solva-v2-risk-list"
          >
            {items.map((pair, idx) => (
              <li
                key={idx}
                className="grid grid-cols-[40px_1fr_1fr] gap-x-4 py-3 border-b border-[var(--rule)] last:border-b-0"
                data-solva-v2-risk-index={idx}
                data-testid={`solva-v2-risk-pair-${idx}`}
              >
                <span className="akki-serif text-[20px] leading-none text-[var(--ned-purple)]">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <div>
                  <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--ned-purple)] mb-1.5">
                    Risk
                  </p>
                  <p
                    className="text-[13px] text-[var(--ink)] leading-relaxed"
                    data-testid={`solva-v2-risk-${idx}`}
                  >
                    {pair.risk}
                  </p>
                </div>
                <div>
                  <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--ned-purple)] mb-1.5">
                    Mitigation
                  </p>
                  <p
                    className="text-[13px] text-[var(--deep)] leading-relaxed"
                    data-testid={`solva-v2-mitigation-${idx}`}
                  >
                    {pair.mitigation}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </SlideShell>
  );
}
