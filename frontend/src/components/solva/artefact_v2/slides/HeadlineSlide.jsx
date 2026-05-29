/**
 * Solva v2 — Headline slide (Slice 2a, 2026-05-29).
 * Element 2 of 15. "If you read nothing else, read this" + exactly-3
 * numbered key findings. Schema enforces exactly-3; if upstream emits
 * !=3, we log a console warning and render what's present.
 */
import React from "react";
import SlideShell from "../SlideShell";


export default function HeadlineSlide({
  headline,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
  readyAt,
}) {
  if (!headline) return null;
  const findings = headline.key_findings || [];
  if (findings.length !== 3) {
    // Log-only — schema enforces but we don't crash a real session.
    // eslint-disable-next-line no-console
    console.warn(
      `[Solva v2] HeadlineSlide expected exactly 3 key_findings, got ${findings.length}`,
    );
  }

  return (
    <SlideShell
      kind="headline"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      readyAt={readyAt}
      sectionTag="Headline"
    >
      <div className="flex flex-col">
        <p
          className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3"
          data-testid="solva-v2-headline-intro"
        >
          {headline.intro_copy || "If you read nothing else, read this."}
        </p>

        <ol className="space-y-7 mt-4" data-testid="solva-v2-headline-findings">
          {findings.map((kf, idx) => (
            <li
              key={kf.number ?? idx + 1}
              className="grid grid-cols-[56px_1fr] gap-x-4"
              data-solva-v2-headline-finding={String(kf.number ?? idx + 1)}
            >
              <span className="akki-serif text-[36px] leading-none text-[var(--ned-purple)]">
                {String(kf.number ?? idx + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="text-[16px] leading-[1.45] text-[var(--ink)] mb-2">
                  {kf.paragraph_text}
                </p>
                {(kf.source_citations || []).length > 0 && (
                  <p className="text-[10.5px] font-mono uppercase tracking-[0.14em] text-[var(--muted)]">
                    {kf.source_citations.length} citation
                    {kf.source_citations.length === 1 ? "" : "s"} ·{" "}
                    {kf.source_citations
                      .map((c) => c.source_layer || c.source_kind)
                      .join(" · ")}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </SlideShell>
  );
}
