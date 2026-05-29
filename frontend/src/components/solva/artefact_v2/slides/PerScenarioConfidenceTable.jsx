/**
 * Solva v2 — Per-scenario confidence TABLE slide (Slice 2b, 2026-05-29).
 * Element 6 of 15. The same data as scenarios_overview, rendered as a
 * 4-column table for at-a-glance confidence comparison.
 *
 * Columns: # · Scenario · Weight · Confidence · Tier
 */
import React from "react";
import SlideShell from "../SlideShell";


export default function PerScenarioConfidenceTable({
  table,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
  readyAt,
}) {
  const rows = (table && table.rows) || [];
  return (
    <SlideShell
      kind="per_scenario_table"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      readyAt={readyAt}
      sectionTag="Confidence Table"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Per-scenario confidence
        </p>
        <h2 className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-6 max-w-[680px]">
          Confidence by scenario, side by side
        </h2>

        {rows.length === 0 ? (
          <p className="text-[13px] italic text-[var(--muted)]">
            No scenario rows available.
          </p>
        ) : (
          <div className="w-full overflow-x-auto -mx-1 px-1">
            <table
              className="w-full border-collapse text-[13px]"
              style={{ tableLayout: "fixed" }}
              data-testid="solva-v2-confidence-table"
            >
            <thead>
              <tr className="border-b border-[var(--rule)]">
                <th className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] text-left py-2 pr-3 w-8">
                  #
                </th>
                <th className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] text-left py-2 pr-3">
                  Scenario
                </th>
                <th className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] text-right py-2 pr-3 w-20">
                  Weight
                </th>
                <th className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] text-right py-2 pr-3 w-24">
                  Confidence
                </th>
                <th className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] text-left py-2 w-28">
                  Tier
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, idx) => (
                <tr
                  key={idx}
                  className="border-b border-[var(--rule)] last:border-b-0 align-top"
                  data-solva-v2-table-row={idx}
                  data-testid={`solva-v2-confidence-table-row-${idx}`}
                >
                  <td className="py-3 pr-3 font-mono text-[var(--muted)] tabular-nums">
                    {String(idx + 1).padStart(2, "0")}
                  </td>
                  <td className="py-3 pr-3 text-[var(--ink)] leading-snug break-words">
                    <div className="font-medium break-words">{r.label}</div>
                    {r.description && (
                      <div className="text-[11.5px] text-[var(--muted)] mt-0.5 break-words">
                        {r.description}
                      </div>
                    )}
                  </td>
                  <td className="py-3 pr-3 text-right text-[var(--ned-purple)] font-mono tabular-nums">
                    {r.weight_pct}%
                  </td>
                  <td className="py-3 pr-3 text-right text-[var(--ink)] font-mono tabular-nums">
                    {r.confidence_pct}%
                  </td>
                  <td className="py-3">
                    {r.tier ? (
                      <span className="inline-block px-1.5 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider bg-ned-purple/10 text-[var(--ned-purple)] border border-ned-purple/20 whitespace-nowrap">
                        {r.tier.replace(/_/g, " ")}
                      </span>
                    ) : (
                      <span className="text-[var(--muted)] text-[11px]">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>
    </SlideShell>
  );
}
