/**
 * Solva v2 — Bias Inventory slide (Slice 4, 2026-05-29) — Trust pillar 2.
 *
 * Surfaces named biases that may be operating in the founder's
 * framing, evidence-grounded. Different from tensions — tensions are
 * framing-vs-evidence contradictions; biases are systematic patterns
 * of reasoning that may be coloring the user's interpretation.
 *
 * Visual: list of bias cards. Each card:
 *   • bias_display_name (human-readable, brand-purple)
 *   • likelihood pill — brand-purple at varying opacity:
 *       high   → bg-ned-purple/30
 *       medium → bg-ned-purple/20
 *       low    → bg-ned-purple/10
 *     (Wave 4.2.followup.2 — opacity steps inside the allowlist.)
 *   • evidence_grounded_reasoning paragraph
 *   • suggested_mitigation (italic, when present)
 *   • source citation count footer
 *
 * Hidden bias_name (machine-readable) on the card root via
 * `data-solva-v2-bias-name` so tests can probe by canonical id.
 */
import React from "react";
import SlideShell from "../SlideShell";


const LIKELIHOOD_TONE = {
  high:   "bg-ned-purple/30 text-[var(--ned-purple)] border-ned-purple/40",
  medium: "bg-ned-purple/20 text-[var(--ned-purple)] border-ned-purple/30",
  low:    "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/20",
};


export default function BiasInventorySlide({
  biasInventory,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
  readyAt,
}) {
  if (!biasInventory) return null;
  const items = biasInventory.biases || [];
  return (
    <SlideShell
      kind="bias_inventory"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      readyAt={readyAt}
      sectionTag="Bias Inventory"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Trust pillar — bias inventory
        </p>
        <h2
          className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-3 max-w-[680px]"
          data-testid="solva-v2-bias-inventory-title"
        >
          Named biases · evidence-grounded
        </h2>
        <p className="text-[13px] text-[var(--deep)] leading-relaxed mb-6 max-w-[680px]">
          {biasInventory.intro_copy}
        </p>

        <ul
          className="space-y-5"
          data-testid="solva-v2-bias-inventory-list"
        >
          {items.map((b, idx) => (
            <li
              key={idx}
              className="grid grid-cols-[44px_1fr] gap-x-4 py-3 border-b border-[var(--rule)] last:border-b-0"
              data-solva-v2-bias-index={idx}
              data-solva-v2-bias-name={b.bias_name}
              data-testid={`solva-v2-bias-${b.bias_name}`}
            >
              <span className="akki-serif text-[22px] leading-none text-[var(--ned-purple)]">
                {String(idx + 1).padStart(2, "0")}
              </span>
              <div>
                <div className="flex items-baseline justify-between gap-3 mb-2">
                  <h3
                    className="text-[15.5px] leading-snug text-[var(--ink)] font-medium"
                    data-testid={`solva-v2-bias-display-${b.bias_name}`}
                  >
                    {b.bias_display_name}
                  </h3>
                  <span
                    className={`inline-block px-2 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider border whitespace-nowrap flex-shrink-0 ${
                      LIKELIHOOD_TONE[b.likelihood] || LIKELIHOOD_TONE.low
                    }`}
                    data-testid={`solva-v2-bias-likelihood-${b.bias_name}`}
                    data-solva-v2-bias-likelihood={b.likelihood}
                  >
                    {b.likelihood}
                  </span>
                </div>
                <p
                  className="text-[13px] text-[var(--deep)] leading-relaxed mb-2"
                  data-testid={`solva-v2-bias-reasoning-${b.bias_name}`}
                >
                  {b.evidence_grounded_reasoning}
                </p>
                {b.suggested_mitigation && (
                  <p
                    className="text-[12.5px] leading-relaxed text-[var(--deep)] italic"
                    data-testid={`solva-v2-bias-mitigation-${b.bias_name}`}
                  >
                    <span className="font-mono not-italic text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] mr-1.5">
                      Mitigation ·
                    </span>
                    {b.suggested_mitigation}
                  </p>
                )}
                {(b.source_input_ids || []).length > 0 && (
                  <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mt-2">
                    {b.source_input_ids.length} source citation
                    {b.source_input_ids.length === 1 ? "" : "s"}
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
