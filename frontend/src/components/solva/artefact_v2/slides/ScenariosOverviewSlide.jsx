/**
 * Solva v2 — Scenarios overview slide (Slice 2b, 2026-05-29).
 * Element 5 of 15. Lists weighted scenarios with weight %, confidence %,
 * tier marker, and calibration reasoning. The dedicated confidence
 * TABLE is the next slide (PerScenarioConfidenceTable).
 */
import React from "react";
import SlideShell from "../SlideShell";


export default function ScenariosOverviewSlide({
  scenarios,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
  readyAt,
}) {
  const items = scenarios || [];
  return (
    <SlideShell
      kind="scenarios_overview"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      readyAt={readyAt}
      sectionTag="Scenarios"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Weighted scenarios
        </p>
        <h2 className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-6 max-w-[680px]">
          How the evidence distributes across possible reads
        </h2>

        {items.length === 0 ? (
          <p className="text-[13px] italic text-[var(--muted)]">
            No scenarios were weighted in this session.
          </p>
        ) : (
          <ul className="space-y-5" data-testid="solva-v2-scenarios-list">
            {items.map((s, idx) => (
              <li
                key={idx}
                className="grid grid-cols-[64px_1fr_auto] gap-x-4 py-3 border-b border-[var(--rule)] last:border-b-0"
                data-solva-v2-scenario-index={idx}
              >
                {/* Weight column — large numeric */}
                <div className="flex flex-col items-start">
                  <span
                    className="akki-serif text-[28px] leading-none text-[var(--ned-purple)]"
                    data-testid={`solva-v2-scenario-weight-${idx}`}
                  >
                    {s.weight_pct}%
                  </span>
                  <span className="font-mono text-[9.5px] uppercase tracking-[0.14em] text-[var(--muted)] mt-1">
                    weight
                  </span>
                </div>

                {/* Label + description + calibration */}
                <div>
                  <h3 className="text-[15.5px] leading-snug text-[var(--ink)] font-medium mb-1">
                    {s.label}
                  </h3>
                  {s.description && (
                    <p className="text-[13px] text-[var(--deep)] leading-relaxed mb-2">
                      {s.description}
                    </p>
                  )}
                  <p
                    className="text-[11.5px] text-[var(--muted)] leading-snug"
                    data-testid={`solva-v2-scenario-calibration-${idx}`}
                  >
                    <span className="font-mono uppercase tracking-[0.14em]">
                      Calibration ·
                    </span>{" "}
                    {s.confidence_calibration_reasoning}
                  </p>
                </div>

                {/* Confidence column + tier chip */}
                <div className="flex flex-col items-end gap-1.5 min-w-[80px]">
                  <span
                    className="font-mono text-[13.5px] text-[var(--ink)] tabular-nums"
                    data-testid={`solva-v2-scenario-confidence-${idx}`}
                  >
                    {s.confidence_pct}%
                  </span>
                  <span className="font-mono text-[9.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
                    confidence
                  </span>
                  {s.tier && (
                    <span className="inline-block px-1.5 py-0.5 rounded-sm text-[9px] uppercase tracking-wider bg-ned-purple/10 text-[var(--ned-purple)] border border-ned-purple/20 whitespace-nowrap mt-1">
                      {s.tier.replace(/_/g, " ")}
                    </span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </SlideShell>
  );
}
