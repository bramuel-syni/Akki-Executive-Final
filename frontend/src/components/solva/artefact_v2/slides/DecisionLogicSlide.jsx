/**
 * Solva v2 — Decision logic slide (Slice 2b, 2026-05-29).
 * Element 10 of 15. If/then conditional branches derived from top
 * scenarios + top sensitivity inputs. Always observational, never
 * imperative — integrity validator enforces upstream.
 */
import React from "react";
import SlideShell from "../SlideShell";


export default function DecisionLogicSlide({
  branches,
  slideNumber,
  totalSlides,
  contextName,
}) {
  const items = branches || [];
  return (
    <SlideShell
      kind="decision_logic"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      sectionTag="Decision Logic"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Conditional branches
        </p>
        <h2 className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-6 max-w-[680px]">
          How the read changes as evidence resolves
        </h2>

        {items.length === 0 ? (
          <p className="text-[13px] italic text-[var(--muted)]">
            No conditional branches were derived from this session.
          </p>
        ) : (
          <ol
            className="space-y-5"
            data-testid="solva-v2-decision-list"
          >
            {items.map((b, idx) => (
              <li
                key={idx}
                className="grid grid-cols-[40px_1fr] gap-x-4 py-3 border-b border-[var(--rule)] last:border-b-0"
                data-solva-v2-decision-index={idx}
                data-testid={`solva-v2-decision-branch-${idx}`}
              >
                <span className="akki-serif text-[24px] leading-none text-[var(--ned-purple)]">
                  {String(idx + 1).padStart(2, "0")}
                </span>
                <div>
                  <div className="mb-1.5">
                    <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--ned-purple)] mr-1.5">
                      If ·
                    </span>
                    <span className="text-[13.5px] text-[var(--ink)] leading-snug">
                      {b.condition}
                    </span>
                  </div>
                  <div className="mb-2">
                    <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--ned-purple)] mr-1.5">
                      Then ·
                    </span>
                    <span className="text-[13.5px] text-[var(--ink)] leading-snug">
                      {b.conclusion}
                    </span>
                  </div>
                  <p className="text-[12px] text-[var(--muted)] leading-relaxed">
                    <span className="font-mono uppercase tracking-[0.14em] mr-1.5">
                      Rationale ·
                    </span>
                    {b.rationale}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </SlideShell>
  );
}
