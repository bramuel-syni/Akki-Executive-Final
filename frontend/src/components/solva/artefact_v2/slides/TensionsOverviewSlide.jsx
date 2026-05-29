/**
 * Solva v2 — Tensions overview slide (Slice 2a, 2026-05-29).
 * Element 3 of 15. Numbered 01/02/03 list of tensions with title +
 * 1-line description. Per-tension deep-dive slides come in Slice 2b.
 */
import React from "react";
import SlideShell from "../SlideShell";


// Wave 4.2.followup.2 — Tailwind-config short name, no opacity-on-hex-var.
const SEVERITY_TONE = {
  high:   "bg-ned-purple/15 text-[var(--ned-purple)] border-ned-purple/30",
  medium: "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/20",
  low:    "bg-brand-rule/30 text-[var(--muted)] border-[var(--rule)]",
};


export default function TensionsOverviewSlide({
  tensions,
  slideNumber,
  totalSlides,
  contextName,
}) {
  const items = tensions || [];
  return (
    <SlideShell
      kind="tensions_overview"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      sectionTag="Tensions"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Tensions surfaced
        </p>
        <h2 className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-6 max-w-[680px]">
          Three contradictions worth pressure-testing
        </h2>

        {items.length === 0 ? (
          <p className="text-[13px] italic text-[var(--muted)]">
            No tensions were surfaced in this session.
          </p>
        ) : (
          <ul className="space-y-5" data-testid="solva-v2-tensions-list">
            {items.map((t, idx) => (
              <li
                key={t.number || idx}
                className="grid grid-cols-[64px_1fr] gap-x-5 py-3 border-b border-[var(--rule)] last:border-b-0"
                data-solva-v2-tension-number={t.number || `${idx + 1}`.padStart(2, "0")}
              >
                <span className="akki-serif text-[28px] leading-none text-[var(--ned-purple)]">
                  {t.number}
                </span>
                <div>
                  <div className="flex items-baseline justify-between gap-3 mb-1.5">
                    <h3 className="text-[15.5px] leading-snug text-[var(--ink)] font-medium">
                      {t.title}
                    </h3>
                    <span
                      className={`inline-block px-1.5 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider border whitespace-nowrap ${
                        SEVERITY_TONE[t.severity] || SEVERITY_TONE.medium
                      }`}
                      data-testid={`solva-v2-tension-severity-${t.number}`}
                    >
                      {t.severity || "medium"}
                    </span>
                  </div>
                  <p className="text-[13px] text-[var(--deep)] leading-relaxed mb-1">
                    {t.prevailing_framing}
                  </p>
                  <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
                    Contradiction · {(t.contradiction_source || "").replace(/_/g, " ")}
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
