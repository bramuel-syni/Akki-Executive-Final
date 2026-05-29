/**
 * Solva v2 — SlideShell (Slice 2b correction, 2026-05-29).
 *
 * Wraps every slide with the per-slide header (slide number + section
 * tag) and footer ("Solva Session Output · Confidential · {ctx} ·
 * {n} / {total}"). Auto-numbered from the orchestrator's slides[]
 * iteration.
 *
 * Locked DOM contract — e1_tester selectors:
 *   • Root:   data-solva-v2-slide="true"
 *             data-solva-v2-slide-kind="{cover|headline|tensions_overview|
 *               per_tension|scenarios_overview|per_scenario_table|
 *               sensitivity|reflection|pathway|decision_logic|
 *               risk_mitigation|methodological_honesty|in_closing}"
 *             data-solva-v2-slide-number="{n}"
 *   • Footer: data-solva-v2-slide-footer="true"
 *
 * Width safety: `w-full` + `max-w-[860px]` is set on the parent
 * article. The shell itself uses `w-full` so it collapses to its
 * parent width at narrow viewports. `overflow-hidden` on the body
 * container prevents any inner element (long titles, table content)
 * from pushing the slide wider than its frame.
 *
 * Print CSS — every slide is a print-page (`break-after: page`).
 * Founder browser-prints to PDF for offline sharing without any
 * server-side render dependency.
 *
 * Wave 4.2.followup.2 compliance — all colors come from configured
 * Tailwind tokens / CSS variables; no opacity-modifier-on-hex-CSS-var.
 */
import React from "react";


export default function SlideShell({
  kind,
  number,
  total,
  contextName,
  sectionTag,
  children,
}) {
  return (
    <section
      data-solva-v2-slide="true"
      data-solva-v2-slide-kind={kind}
      data-solva-v2-slide-number={String(number)}
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

      {/* Slide body */}
      <div className="solva-v2-slide-body w-full">{children}</div>

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
