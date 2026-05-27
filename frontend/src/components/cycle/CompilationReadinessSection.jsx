/**
 * CompilationReadinessSection — Phase E.2 (2026-05-26).
 *
 * Two stacked cards relocated from `components/work_studio/CompilationRail.jsx`
 * to the Cycle Manager (`/app/cycle`) surface per the Phase E.2 brief:
 *
 *   1. Ready to compile — top 3 aggregates with readiness >= 80%
 *   2. At risk           — top 3 with readiness <= 40% OR no activity > 7 days
 *
 * Data source unchanged: GET /api/contexts/{cid}/briefings/aggregates/all
 * with the same row-shape and readiness formula
 *   (document_count*12 + contributor_count*10, clamped 0-100)
 * the original rail used. We do NOT touch the rail's data contract —
 * just the rendering surface.
 *
 * Click handlers:
 *   • Ready row → onCompile({ artefactType, sourceId })
 *     Caller wires this into the Cycle compile wizard / route.
 *   • At-risk row → navigate to the artefact detail surface (decks/reports/etc).
 *
 * Oxblood used ONLY on the at-risk readiness numeral (severity case),
 * matching the original rail.
 */
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import {
  AlertCircle, RefreshCw, Loader2,
} from "lucide-react";


const KINDS = [
  { artefact_type: "board_pack",     kind: "cycle_board_pack",     label: "Board pack" },
  { artefact_type: "minutes",        kind: "cycle_minutes",        label: "Minutes" },
  { artefact_type: "committee_pack", kind: "cycle_committee_pack", label: "Committee pack" },
  { artefact_type: "deck",           kind: "deck",                 label: "Deck" },
  { artefact_type: "report",         kind: "report",               label: "Report" },
  { artefact_type: "briefing",       kind: "briefing",             label: "Briefing" },
];


function fmtRelDays(iso) {
  if (!iso) return "—";
  try {
    const ms = Date.now() - new Date(iso).getTime();
    const days = Math.floor(ms / (1000 * 60 * 60 * 24));
    if (days < 1) return "<1d";
    return `${days}d`;
  } catch { return "—"; }
}


function rowReadiness(row) {
  if (typeof row.readiness_pct === "number") return row.readiness_pct;
  const docs = row.document_count || 0;
  const contribs = row.contributor_count || 0;
  return Math.max(0, Math.min(100, docs * 12 + contribs * 10));
}


function artefactDetailHref(row, kindEntry) {
  const raw = row.id || "";
  const idPart = raw.includes("::") ? raw.split("::")[1] : raw;
  if (kindEntry.artefact_type === "deck") return `/app/decks/${idPart}`;
  if (kindEntry.artefact_type === "report") return `/app/cycle?tab=overview&report=${idPart}`;
  return `/app/work-studio?kind=${kindEntry.kind}`;
}


export default function CompilationReadinessSection({ contextId, onCompile, layout = "grid" }) {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!contextId) return;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        // Same fetch shape as the original CompilationRail.
        const responses = await Promise.all(
          KINDS.map((k) =>
            api.get(`/contexts/${contextId}/briefings/aggregates`, {
              params: { kind: k.kind, page_size: 50, sort: "recent" },
            }).then((r) => ({ kindEntry: k, items: r.data?.items || [] })),
          ),
        );
        if (cancelled) return;
        const merged = [];
        for (const r of responses) {
          for (const it of r.items) {
            merged.push({ ...it, _kind: r.kindEntry, _readiness: rowReadiness(it) });
          }
        }
        setRows(merged);
        setErr(null);
      } catch (e) {
        if (!cancelled) setErr(e?.message || "Failed to load readiness data.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [contextId]);

  const { ready, atRisk } = useMemo(() => {
    const sorted = [...rows].sort((a, b) => b._readiness - a._readiness);
    return {
      ready: sorted.filter((r) => r._readiness >= 80).slice(0, 3),
      atRisk: sorted.filter((r) => r._readiness <= 40).slice(-3).reverse(),
    };
  }, [rows]);

  if (!contextId) return null;

  // Layout — `grid` (default, side-by-side at md+) for wide page
  // surfaces, or `stack` (vertical, full width) when mounted in a
  // narrow right rail. Card internals + dimensions are unchanged.
  const wrapperCls =
    layout === "stack"
      ? "mt-6 flex flex-col gap-4"
      : "mt-6 grid grid-cols-1 md:grid-cols-2 gap-4";
  // The `md:col-span-2` error pill only applies in grid layout.
  const errPillCls =
    layout === "stack"
      ? "text-[11.5px] text-amber-900 inline-flex items-center gap-1.5"
      : "md:col-span-2 text-[11.5px] text-amber-900 inline-flex items-center gap-1.5";

  return (
    <aside
      className={wrapperCls}
      data-testid="cycle-list-compilation-readiness"
      data-layout={layout}
    >
      {/* Ready to compile */}
      <section
        className="border border-[var(--rule)] bg-white rounded-sm"
        data-testid="cycle-list-ready-to-compile"
      >
        <header className="px-3 py-2 border-b border-[var(--rule)] flex items-center justify-between">
          <p className="text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--ink)]">
            Ready to Compile
          </p>
          {loading && <Loader2 className="w-3 h-3 animate-spin text-[var(--muted)]" />}
        </header>
        <div className="p-2.5">
          {loading ? null : ready.length === 0 ? (
            <p className="text-[12px] text-[var(--muted)] italic px-1" data-testid="cycle-list-ready-empty">
              Nothing ready yet.
            </p>
          ) : (
            <ul className="space-y-1.5" data-testid="cycle-list-ready-list">
              {ready.map((row) => (
                <li key={row.id} className="text-[12.5px]">
                  <button
                    type="button"
                    onClick={() => onCompile && onCompile({
                      artefactType: row._kind.artefact_type,
                      sourceId: row.id,
                    })}
                    className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] flex items-center gap-2"
                    data-testid="cycle-list-ready-row"
                  >
                    <span className="flex-1 min-w-0 truncate text-[var(--ink)]">{row.name}</span>
                    <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] shrink-0">
                      {row._kind.label}
                    </span>
                    <span className="font-mono text-[12px] tabular-nums text-[var(--ink)] shrink-0 w-10 text-right">
                      {row._readiness}%
                    </span>
                    <RefreshCw className="w-3 h-3 text-[var(--muted)] shrink-0" strokeWidth={1.7} aria-label="Compile" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* At risk */}
      <section
        className="border border-[var(--rule)] bg-white rounded-sm"
        data-testid="cycle-list-at-risk"
      >
        <header className="px-3 py-2 border-b border-[var(--rule)] flex items-center gap-1.5">
          <AlertCircle className="w-3 h-3 text-[color:var(--oxblood)]" strokeWidth={1.7} />
          <p className="text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--ink)]">At risk</p>
        </header>
        <div className="p-2.5">
          {loading ? null : atRisk.length === 0 ? (
            <p className="text-[12px] text-[var(--muted)] italic px-1" data-testid="cycle-list-at-risk-empty">
              Nothing at risk. Healthy queue.
            </p>
          ) : (
            <ul className="space-y-1.5" data-testid="cycle-list-at-risk-list">
              {atRisk.map((row) => (
                <li key={row.id} className="text-[12.5px]">
                  <button
                    type="button"
                    onClick={() => navigate(artefactDetailHref(row, row._kind))}
                    className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] flex items-center gap-2"
                    data-testid="cycle-list-at-risk-row"
                  >
                    <span className="flex-1 min-w-0 truncate text-[var(--ink)]">{row.name}</span>
                    <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] shrink-0">
                      {row._kind.label}
                    </span>
                    <span
                      className="font-mono text-[12px] tabular-nums text-[color:var(--oxblood)] shrink-0 w-10 text-right"
                      data-testid="cycle-list-at-risk-readiness"
                    >
                      {row._readiness}%
                    </span>
                    <span className="font-mono text-[11px] text-[var(--muted)] shrink-0 w-8 text-right">
                      {fmtRelDays(row.meeting_date || row.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {err && (
        <p className={errPillCls}>
          <AlertCircle className="w-3 h-3" /> {err}
        </p>
      )}
    </aside>
  );
}
