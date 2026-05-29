/**
 * Solva v2 — Pre-mortem slide (Slice 5, 2026-05-29) — Trust pillar 4.
 *
 * Imagined-regret framing: "Imagine 12 months from now you regret this
 * pathway. What was the most likely failure mode?" Each failure mode
 * is named, evidence-grounded, observational. The slide complements
 * the adversarial counter-cases shipped on the pathway + decision_logic
 * slides — together they form the seasoned-partner adversarial debate.
 *
 * Visual: list of failure-mode cards. Each card:
 *   • failure_kind chip (brand-purple, locked taxonomy)
 *   • failure_narrative paragraph
 *   • triggering_signals as `→` bulletted list
 *   • counter_action callout (italic, observational opener)
 *   • source citation count footer
 *
 * Hidden machine-readable failure_kind on the card root via
 * `data-solva-v2-failure-kind` so tests probe by canonical id.
 */
import React from "react";
import SlideShell from "../SlideShell";


// Wave 4.2.followup.2 — Tailwind-config short-name opacity steps.
// All values inside the allowlist {5,10,15,20,25,30,40,50,60,70,...}.
const FAILURE_KIND_TONE = {
  data_signal_misread:       "bg-ned-purple/20 text-[var(--ned-purple)] border-ned-purple/30",
  execution_velocity:        "bg-ned-purple/15 text-[var(--ned-purple)] border-ned-purple/30",
  market_shift:              "bg-ned-purple/15 text-[var(--ned-purple)] border-ned-purple/25",
  stakeholder_misalignment:  "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/25",
  capability_gap:            "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/20",
  external_shock:            "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/20",
};


const FAILURE_KIND_LABEL = {
  data_signal_misread:       "Data signal misread",
  execution_velocity:        "Execution velocity",
  market_shift:              "Market shift",
  stakeholder_misalignment:  "Stakeholder misalignment",
  capability_gap:            "Capability gap",
  external_shock:            "External shock",
};


export default function PreMortemSlide({
  preMortem,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
}) {
  if (!preMortem) return null;
  const items = preMortem.failure_modes || [];
  return (
    <SlideShell
      kind="pre_mortem"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      sectionTag="Pre-mortem"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Trust pillar — imagined regret
        </p>
        <h2
          className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-3 max-w-[680px]"
          data-testid="solva-v2-pre-mortem-title"
        >
          What was the most likely failure mode?
        </h2>
        <p className="text-[13px] text-[var(--deep)] leading-relaxed mb-6 max-w-[680px]">
          {preMortem.intro_copy}
        </p>

        <ul
          className="space-y-6"
          data-testid="solva-v2-pre-mortem-list"
        >
          {items.map((fm, idx) => (
            <li
              key={idx}
              className="grid grid-cols-[44px_1fr] gap-x-4 py-3 border-b border-[var(--rule)] last:border-b-0"
              data-solva-v2-failure-index={idx}
              data-solva-v2-failure-kind={fm.failure_kind}
              data-testid={`solva-v2-failure-${fm.failure_kind}`}
            >
              <span className="akki-serif text-[22px] leading-none text-[var(--ned-purple)]">
                {String(idx + 1).padStart(2, "0")}
              </span>
              <div>
                <div className="flex items-baseline justify-between gap-3 mb-2">
                  <span
                    className={`inline-block px-2 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider border whitespace-nowrap ${
                      FAILURE_KIND_TONE[fm.failure_kind] || FAILURE_KIND_TONE.data_signal_misread
                    }`}
                    data-testid={`solva-v2-failure-kind-${fm.failure_kind}`}
                  >
                    {FAILURE_KIND_LABEL[fm.failure_kind] || fm.failure_kind}
                  </span>
                </div>
                <p
                  className="text-[13px] text-[var(--deep)] leading-relaxed mb-3"
                  data-testid={`solva-v2-failure-narrative-${fm.failure_kind}`}
                >
                  {fm.failure_narrative}
                </p>
                {(fm.triggering_signals || []).length > 0 && (
                  <ul
                    className="space-y-1 mb-3 text-[12.5px] text-[var(--deep)] leading-relaxed"
                    data-testid={`solva-v2-failure-signals-${fm.failure_kind}`}
                  >
                    {fm.triggering_signals.map((sig, sidx) => (
                      <li
                        key={sidx}
                        className="grid grid-cols-[20px_1fr] gap-x-1"
                      >
                        <span className="font-mono text-[var(--ned-purple)]">→</span>
                        <span>{sig}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {fm.counter_action && (
                  <p
                    className="text-[12.5px] leading-relaxed text-[var(--deep)] italic mb-2"
                    data-testid={`solva-v2-failure-counter-${fm.failure_kind}`}
                  >
                    <span className="font-mono not-italic text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] mr-1.5">
                      Counter ·
                    </span>
                    {fm.counter_action}
                  </p>
                )}
                {(fm.source_input_ids || []).length > 0 && (
                  <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mt-2">
                    {fm.source_input_ids.length} source citation
                    {fm.source_input_ids.length === 1 ? "" : "s"}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </SlideShell>
  );
}
