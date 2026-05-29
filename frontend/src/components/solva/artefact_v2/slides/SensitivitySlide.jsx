/**
 * Solva v2 — Sensitivity slide (Slice 2b, 2026-05-29).
 * Element 7 of 15. Ranked sensitivity inputs (HIGHEST / HIGH / MEDIUM /
 * LOW) with the cluster-weight-shift mechanic each could trigger.
 */
import React from "react";
import SlideShell from "../SlideShell";


const RANK_TONE = {
  HIGHEST: "bg-ned-purple/20 text-[var(--ned-purple)] border-ned-purple/40",
  HIGH:    "bg-ned-purple/15 text-[var(--ned-purple)] border-ned-purple/30",
  MEDIUM:  "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/20",
  LOW:     "bg-brand-rule/30 text-[var(--muted)] border-[var(--rule)]",
};


export default function SensitivitySlide({
  sensitivity,
  slideNumber,
  totalSlides,
  contextName,
}) {
  const items = sensitivity || [];
  return (
    <SlideShell
      kind="sensitivity"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      sectionTag="Sensitivity"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          What could change the read
        </p>
        <h2 className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-6 max-w-[680px]">
          Inputs that materially move the weighted picture
        </h2>

        {items.length === 0 ? (
          <p className="text-[13px] italic text-[var(--muted)]">
            No sensitivity inputs were ranked in this session.
          </p>
        ) : (
          <ul className="space-y-5" data-testid="solva-v2-sensitivity-list">
            {items.map((s, idx) => (
              <li
                key={idx}
                className="grid grid-cols-[96px_1fr] gap-x-5 py-3 border-b border-[var(--rule)] last:border-b-0"
                data-solva-v2-sensitivity-index={idx}
              >
                <div>
                  <span
                    className={`inline-block px-2 py-0.5 rounded-sm text-[10px] uppercase tracking-wider border ${
                      RANK_TONE[s.rank] || RANK_TONE.MEDIUM
                    }`}
                    data-testid={`solva-v2-sensitivity-rank-${idx}`}
                  >
                    {s.rank}
                  </span>
                </div>
                <div>
                  <h3 className="text-[15px] leading-snug text-[var(--ink)] font-medium mb-1.5">
                    {s.input_description}
                  </h3>
                  <p className="text-[13px] text-[var(--deep)] leading-relaxed mb-2">
                    {s.impact_explanation}
                  </p>
                  <p
                    className="text-[12px] leading-snug text-[var(--ned-purple)] italic"
                    data-testid={`solva-v2-sensitivity-shift-${idx}`}
                  >
                    Mechanic · {s.cluster_weight_shift_mechanic}
                  </p>
                  {(s.source_citations || []).length > 0 && (
                    <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mt-2">
                      {s.source_citations.length} citation
                      {s.source_citations.length === 1 ? "" : "s"}
                    </p>
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
