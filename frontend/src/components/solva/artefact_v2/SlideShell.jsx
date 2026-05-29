/**
 * Solva v2 — SlideShell (Slice 3b, 2026-05-29).
 *
 * Wraps every slide with the per-slide header (slide number + section
 * tag) and footer ("Solva Session Output · Confidential · {ctx} ·
 * {n} / {total}").
 *
 * Locked DOM contract — e1_tester selectors:
 *   • Root:   data-solva-v2-slide="true"
 *             data-solva-v2-slide-kind="{cover|headline|...|in_closing}"
 *             data-solva-v2-slide-number="{n}"
 *             data-solva-v2-slide-state="{loading|ready|placeholder}"   (NEW Slice 3b)
 *   • Footer: data-solva-v2-slide-footer="true"
 *
 * Per-slide state contract (Slice 3b):
 *   • "loading"     — Skeleton with subtle ned-purple pulse. Renders
 *                     the slide chrome (header + footer + section tag)
 *                     but replaces the body with a 3-line shimmer.
 *   • "ready"       — Slide body renders normally.
 *   • "placeholder" — Empty-arc observational placeholder (e.g. the
 *                     "No tension was surfaced" copy from Slice 2b).
 *                     No pulse — placeholder is the final state, not a
 *                     waiting state.
 *
 * Wave 4.2.followup.2 compliance: ALL skeleton tints come from
 * `bg-ned-purple/N` Tailwind short-name utilities, never
 * `bg-[var(--ned-purple)]/N` (which silently fails on hex CSS vars).
 */
import React from "react";


function SlideSkeleton() {
  // 3-line ned-purple shimmer. Pulse animation comes from Tailwind's
  // built-in `animate-pulse` which targets opacity, not background-color.
  return (
    <div
      className="solva-v2-slide-skeleton flex flex-col gap-4 w-full"
      data-testid="solva-v2-slide-skeleton"
    >
      <div className="h-3.5 rounded-sm bg-ned-purple/15 animate-pulse w-3/5" />
      <div className="h-2.5 rounded-sm bg-ned-purple/10 animate-pulse w-4/5" />
      <div className="h-2.5 rounded-sm bg-ned-purple/10 animate-pulse w-2/3" />
      <div className="mt-3 h-2.5 rounded-sm bg-ned-purple/10 animate-pulse w-3/4" />
      <div className="h-2.5 rounded-sm bg-ned-purple/10 animate-pulse w-1/2" />
    </div>
  );
}


export default function SlideShell({
  kind,
  number,
  total,
  contextName,
  sectionTag,
  slideState = "ready",   // Slice 3b: 'loading' | 'ready' | 'placeholder'
  readyAt,                // Slice 7 (2026-05-29): ISO timestamp captured
                          // when the slide first transitioned to 'ready'.
                          // Surfaces verbatim on the slide root so probes
                          // can audit when each slide became authoritative.
  children,
}) {
  const showSkeleton = slideState === "loading";

  return (
    <section
      data-solva-v2-slide="true"
      data-solva-v2-slide-kind={kind}
      data-solva-v2-slide-number={String(number)}
      data-solva-v2-slide-state={slideState}
      data-solva-v2-slide-ready-at={readyAt || ""}
      className="solva-v2-slide solva-v2-slide-frame relative w-full bg-white border border-[var(--rule)] rounded-sm px-10 py-12 mb-6 print:mb-0 print:break-after-page print:rounded-none print:border-0 overflow-hidden"
      style={{ minHeight: "660px" }}
    >
      {/* Header strip — slide number + section tag */}
      <header className="flex items-baseline justify-between mb-8 gap-4">
        <span
          className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] truncate"
          data-solva-v2-slide-section-tag="true"
        >
          {sectionTag || kind.replace(/_/g, " ")}
        </span>
        <span className="font-mono text-[10.5px] tracking-[0.18em] text-[var(--muted)] flex-shrink-0">
          {String(number).padStart(2, "0")}&nbsp;/&nbsp;{String(total).padStart(2, "0")}
        </span>
      </header>

      {/* Slide body — skeleton or content */}
      <div className="solva-v2-slide-body w-full">
        {showSkeleton ? <SlideSkeleton /> : children}
      </div>

      {/* Footer — locked template */}
      <footer
        data-solva-v2-slide-footer="true"
        className="absolute bottom-4 left-10 right-10 flex items-baseline justify-between gap-4 border-t border-[var(--rule)] pt-3 font-mono text-[10.5px] tracking-[0.14em] text-[var(--muted)]"
      >
        <span className="truncate pr-4">
          Solva Session Output&nbsp;·&nbsp;Confidential&nbsp;·&nbsp;{contextName}
        </span>
        <span className="flex-shrink-0">
          {String(number).padStart(2, "0")}&nbsp;/&nbsp;{String(total).padStart(2, "0")}
        </span>
      </footer>
    </section>
  );
}
