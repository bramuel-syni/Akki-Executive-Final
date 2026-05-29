/**
 * Solva v2 — Pathway slide (Slice 2a, 2026-05-29).
 * Element 9 of 15. Sequenced recommendations with timeline_tag +
 * follows_from_cluster_id provenance chip.
 *
 * Refuse-to-decide is enforced upstream by the integrity validator —
 * by the time pathway items reach this component, their detail_paragraph
 * has been rewritten into conditional/observational form.
 */
import React from "react";
import SlideShell from "../SlideShell";


// Wave 4.2.followup.2 — Tailwind-config short names.
const TIMELINE_TONE = {
  "DAYS 0-30":                "bg-ned-purple/15 text-[var(--ned-purple)] border-ned-purple/30",
  "DAYS 0-14":                "bg-ned-purple/20 text-[var(--ned-purple)] border-ned-purple/30",
  "DAYS 15-30":               "bg-ned-purple/15 text-[var(--ned-purple)] border-ned-purple/30",
  "DAYS 30-60":               "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/25",
  "DAYS 60-90":               "bg-ned-purple/10 text-[var(--ned-purple)] border-ned-purple/20",
  "BOARD-LEVEL · IN PARALLEL": "bg-amber-50 text-[var(--oxblood)] border-[rgba(122,46,46,0.25)]",
  "ONGOING":                   "bg-brand-rule/30 text-[var(--muted)] border-[var(--rule)]",
};


export default function PathwaySlide({
  pathway,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
  readyAt,
}) {
  const items = pathway || [];
  return (
    <SlideShell
      kind="pathway"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      readyAt={readyAt}
      sectionTag="Pathway"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Conditional Pathway
        </p>
        <h2 className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-6 max-w-[680px]">
          What the weighted picture supports as next moves
        </h2>

        {items.length === 0 ? (
          <p className="text-[13px] italic text-[var(--muted)]">
            No pathway items were derived from this session.
          </p>
        ) : (
          <ol className="space-y-6" data-testid="solva-v2-pathway-list">
            {items.map((p, idx) => (
              <li
                key={p.number || idx + 1}
                className="grid grid-cols-[56px_1fr] gap-x-5"
                data-solva-v2-pathway-number={String(p.number || idx + 1)}
              >
                <span className="akki-serif text-[28px] leading-none text-[var(--ned-purple)]">
                  {String(p.number || idx + 1).padStart(2, "0")}
                </span>
                <div>
                  <div className="flex items-baseline flex-wrap gap-2 mb-2">
                    <span
                      className={`inline-block px-1.5 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider border ${
                        TIMELINE_TONE[p.timeline_tag] || TIMELINE_TONE["DAYS 0-30"]
                      }`}
                      data-testid={`solva-v2-pathway-timeline-${p.number}`}
                    >
                      {p.timeline_tag}
                    </span>
                    {(p.follows_from_cluster_label || p.follows_from_cluster_id) && (
                      <span
                        className="inline-block px-1.5 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider bg-ned-purple/5 text-[var(--ned-purple)] border border-ned-purple/15"
                        data-testid={`solva-v2-pathway-cluster-${p.number}`}
                      >
                        follows from · {p.follows_from_cluster_label || p.follows_from_cluster_id}
                      </span>
                    )}
                  </div>
                  <h3 className="text-[15.5px] leading-snug text-[var(--ink)] font-medium mb-1.5">
                    {p.action_heading}
                  </h3>
                  <p className="text-[13px] text-[var(--deep)] leading-relaxed">
                    {p.detail_paragraph}
                  </p>
                  {p.adversarial_counter && (
                    <div
                      className="mt-3 border-l-2 border-ned-purple/40 bg-ned-purple/5 px-4 py-3"
                      data-testid={`solva-v2-pathway-adversarial-${p.number || idx + 1}`}
                      data-solva-v2-adversarial-counter="pathway"
                    >
                      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--ned-purple)] mb-1.5">
                        Strongest case against this conclusion
                      </p>
                      <p className="text-[12.5px] text-[var(--deep)] leading-relaxed mb-2">
                        {p.adversarial_counter.steel_man_position}
                      </p>
                      <p className="text-[12px] text-[var(--muted)] leading-relaxed italic">
                        <span className="font-mono not-italic text-[10px] uppercase tracking-[0.14em] mr-1.5">
                          Why it matters ·
                        </span>
                        {p.adversarial_counter.why_it_matters}
                      </p>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </SlideShell>
  );
}
