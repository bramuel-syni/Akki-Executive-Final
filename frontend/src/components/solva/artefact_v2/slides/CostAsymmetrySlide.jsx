/**
 * Solva v2 — Cost asymmetry slide (Slice 6, 2026-05-29) — Trust pillar 5.
 *
 * Makes the asymmetric-bet logic explicit: for each scenario the
 * pathway commits to, what does it cost if right vs. wrong?
 *
 * Visual: a stack of two-column scenario blocks. Each block:
 *   • pathway_label as the row header
 *   • cost_kind chip (locked taxonomy) + cost_magnitude chip
 *   • If correct / If wrong columns side by side
 *   • Source citation count footer
 *
 * Each scenario card carries `data-solva-v2-cost-scenario-index` and
 * `data-solva-v2-cost-kind` for tests to address by canonical id.
 */
import React from "react";
import SlideShell from "../SlideShell";


// Wave 4.2.followup.2 — Tailwind-config short-name opacity steps.
// All values inside the allowlist {5,10,15,20,25,30,40,50,60,70,...}.
const COST_KIND_TONE = {
  capital_burn:        "bg-ned-purple/20 text-[var(--ned-purple)] border-ned-purple/30",
  opportunity_cost:    "bg-ned-purple/15 text-[var(--ned-purple)] border-ned-purple/25",
  reputational_risk:   "bg-ned-purple/15 text-[var(--ned-purple)] border-ned-purple/25",
  optionality_loss:    "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/20",
  time_cost:           "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/20",
  stakeholder_trust:   "bg-ned-purple/15 text-[var(--ned-purple)] border-ned-purple/30",
};


const COST_KIND_LABEL = {
  capital_burn:        "Capital burn",
  opportunity_cost:    "Opportunity cost",
  reputational_risk:   "Reputational risk",
  optionality_loss:    "Optionality loss",
  time_cost:           "Time cost",
  stakeholder_trust:   "Stakeholder trust",
};


const COST_MAGNITUDE_TONE = {
  low:    "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/20",
  medium: "bg-ned-purple/20 text-[var(--ned-purple)] border-ned-purple/30",
  high:   "bg-ned-purple/30 text-[var(--ned-purple)] border-ned-purple/40",
};


export default function CostAsymmetrySlide({
  costAsymmetry,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
  readyAt,
}) {
  if (!costAsymmetry) return null;
  const scenarios = costAsymmetry.scenarios || [];
  return (
    <SlideShell
      kind="cost_asymmetry"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      readyAt={readyAt}
      sectionTag="Cost asymmetry"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Trust pillar — asymmetric bets
        </p>
        <h2
          className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-3 max-w-[680px]"
          data-testid="solva-v2-cost-asymmetry-title"
        >
          What does each pathway cost if it&rsquo;s right — and if it&rsquo;s wrong?
        </h2>
        <p className="text-[13px] text-[var(--deep)] leading-relaxed mb-6 max-w-[680px]">
          {costAsymmetry.intro_copy}
        </p>

        <div
          className="space-y-5"
          data-testid="solva-v2-cost-asymmetry-list"
        >
          {scenarios.map((sc, idx) => (
            <div
              key={idx}
              className="border-t border-[var(--rule)] pt-4"
              data-solva-v2-cost-scenario-index={idx}
              data-solva-v2-cost-kind={sc.cost_kind}
              data-solva-v2-cost-magnitude={sc.cost_magnitude}
              data-testid={`solva-v2-cost-scenario-${sc.cost_kind}`}
            >
              <div className="flex items-baseline justify-between gap-3 mb-3">
                <h3
                  className="text-[15.5px] text-[var(--ink)] font-medium"
                  data-testid={`solva-v2-cost-pathway-${idx}`}
                >
                  {sc.pathway_label}
                </h3>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-block px-2 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider border whitespace-nowrap ${
                      COST_KIND_TONE[sc.cost_kind] || COST_KIND_TONE.capital_burn
                    }`}
                    data-testid={`solva-v2-cost-kind-chip-${sc.cost_kind}`}
                  >
                    {COST_KIND_LABEL[sc.cost_kind] || sc.cost_kind}
                  </span>
                  <span
                    className={`inline-block px-2 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider border whitespace-nowrap ${
                      COST_MAGNITUDE_TONE[sc.cost_magnitude] || COST_MAGNITUDE_TONE.medium
                    }`}
                    data-testid={`solva-v2-cost-magnitude-chip-${idx}`}
                  >
                    {sc.cost_magnitude}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-x-6">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--ned-purple)] mb-1.5">
                    If correct →
                  </p>
                  <p
                    className="text-[12.5px] text-[var(--deep)] leading-relaxed"
                    data-testid={`solva-v2-cost-if-correct-${sc.cost_kind}`}
                  >
                    {sc.if_correct_outcome}
                  </p>
                </div>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">
                    If wrong →
                  </p>
                  <p
                    className="text-[12.5px] text-[var(--deep)] leading-relaxed"
                    data-testid={`solva-v2-cost-if-wrong-${sc.cost_kind}`}
                  >
                    {sc.if_wrong_cost}
                  </p>
                </div>
              </div>
              {(sc.source_input_ids || []).length > 0 && (
                <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mt-3">
                  {sc.source_input_ids.length} source citation
                  {sc.source_input_ids.length === 1 ? "" : "s"}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </SlideShell>
  );
}
