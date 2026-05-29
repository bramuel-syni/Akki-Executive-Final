/**
 * Solva v2 — Per-tension deep-dive slide (Slice 2b, 2026-05-29).
 * Element 4 of 15. One slide per `tensions[]` entry — renders the
 * tension head + evidence verbatim quote + implication + any
 * additional citations carried by `per_tension_deep_dive[]`.
 *
 * Wave 4.2.followup.2 — short-name brand utilities only.
 */
import React from "react";
import SlideShell from "../SlideShell";


const SEVERITY_TONE = {
  high:   "bg-ned-purple/15 text-[var(--ned-purple)] border-ned-purple/30",
  medium: "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/20",
  low:    "bg-brand-rule/30 text-[var(--muted)] border-[var(--rule)]",
};


export default function PerTensionSlide({
  tension,
  deepDive,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
  readyAt,
}) {
  if (!tension) return null;
  const extraParagraphs = (deepDive && deepDive.extended_detail_paragraphs) || [];
  const extraCitations = (deepDive && deepDive.additional_citations) || [];

  return (
    <SlideShell
      kind="per_tension"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      readyAt={readyAt}
      sectionTag={`Tension ${tension.number}`}
    >
      <div
        className="flex flex-col"
        data-solva-v2-per-tension-number={tension.number}
        data-testid={`solva-v2-per-tension-${tension.number}`}
      >
        <div className="flex items-baseline gap-4 mb-3">
          <span className="akki-serif text-[44px] leading-none text-[var(--ned-purple)]">
            {tension.number}
          </span>
          <span
            className={`inline-block px-1.5 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider border ${
              SEVERITY_TONE[tension.severity] || SEVERITY_TONE.medium
            }`}
          >
            {tension.severity || "medium"}
          </span>
        </div>

        <h2
          className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-2 max-w-[680px]"
          data-testid={`solva-v2-per-tension-title-${tension.number}`}
        >
          {tension.title}
        </h2>
        {tension.subtitle && (
          <p className="text-[13.5px] text-[var(--deep)] mb-4 max-w-[680px]">
            {tension.subtitle}
          </p>
        )}

        <div className="grid grid-cols-1 gap-5 mt-2">
          {/* Prevailing framing block */}
          <div>
            <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">
              Prevailing framing
            </p>
            <p className="text-[13.5px] text-[var(--ink)] leading-relaxed">
              {tension.prevailing_framing}
            </p>
          </div>

          {/* Evidence block — verbatim user quote */}
          {tension.evidence_block && (
            <div data-testid={`solva-v2-per-tension-evidence-${tension.number}`}>
              <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">
                Evidence · {tension.evidence_block.source_layer || "user input"}
              </p>
              <blockquote className="border-l-2 border-ned-purple/40 pl-4 text-[13.5px] italic text-[var(--deep)] leading-relaxed">
                “{tension.evidence_block.user_quote}”
              </blockquote>
            </div>
          )}

          {/* Implication */}
          <div>
            <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">
              Implication
            </p>
            <p className="text-[13.5px] text-[var(--ink)] leading-relaxed">
              {tension.implication}
            </p>
          </div>

          {/* Extended detail paragraphs (from per_tension_deep_dive) */}
          {extraParagraphs.length > 0 && (
            <div data-testid={`solva-v2-per-tension-detail-${tension.number}`}>
              <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">
                Detail
              </p>
              {extraParagraphs.map((p, i) => (
                <p
                  key={i}
                  className="text-[13px] text-[var(--deep)] leading-relaxed mb-2 last:mb-0"
                >
                  {p}
                </p>
              ))}
            </div>
          )}

          {/* Citation count footer */}
          {extraCitations.length > 0 && (
            <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] pt-2">
              {extraCitations.length} additional citation
              {extraCitations.length === 1 ? "" : "s"}
            </p>
          )}
        </div>
      </div>
    </SlideShell>
  );
}
