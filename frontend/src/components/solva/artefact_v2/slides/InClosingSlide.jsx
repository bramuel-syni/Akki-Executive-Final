/**
 * Solva v2 — In closing slide (Slice 2b, 2026-05-29).
 * Element 13 of 15. The reframing paragraph, the key-findings recap,
 * and the final observational statement. This is the deck's last
 * content slide before the footer-only "fin" marker.
 */
import React from "react";
import SlideShell from "../SlideShell";


export default function InClosingSlide({
  inClosing,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
}) {
  if (!inClosing) return null;
  const recap = inClosing.key_findings_recap || [];
  return (
    <SlideShell
      kind="in_closing"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      sectionTag="In Closing"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          In closing
        </p>
        <h2 className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-6 max-w-[680px]">
          The opening framing — re-read against the evidence
        </h2>

        {/* Reframing paragraph */}
        <div data-testid="solva-v2-closing-reframing" className="mb-6">
          <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--ned-purple)] mb-1.5">
            Reframing
          </p>
          <p className="text-[14px] text-[var(--ink)] leading-relaxed max-w-[700px]">
            {inClosing.reframing_paragraph}
          </p>
        </div>

        {/* Key findings recap */}
        {recap.length > 0 && (
          <div data-testid="solva-v2-closing-recap" className="mb-6">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-2">
              Key findings · recap
            </p>
            <ul className="space-y-2 max-w-[700px]">
              {recap.map((line, idx) => (
                <li
                  key={idx}
                  className="grid grid-cols-[32px_1fr] gap-x-3 text-[13px] text-[var(--deep)] leading-relaxed"
                  data-testid={`solva-v2-closing-recap-${idx + 1}`}
                >
                  <span className="font-mono text-[var(--ned-purple)] tabular-nums">
                    {String(idx + 1).padStart(2, "0")}
                  </span>
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Final statement */}
        <div
          className="border-t border-[var(--rule)] pt-5 max-w-[700px]"
          data-testid="solva-v2-closing-final"
        >
          <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--ned-purple)] mb-1.5">
            Final
          </p>
          <p className="akki-serif text-[18px] leading-snug text-[var(--ink)]">
            {inClosing.final_statement}
          </p>
        </div>
      </div>
    </SlideShell>
  );
}
