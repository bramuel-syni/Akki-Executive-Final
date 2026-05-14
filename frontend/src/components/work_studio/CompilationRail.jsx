/**
 * CompilationRail — Patch 2B.2.
 *
 * Sticky right rail on Work Studio. Hidden on viewports < 1100px.
 *
 * Layout (top → bottom):
 *   1. Primary CTA: full-width `Compile a Report` button → opens wizard
 *   2. Ready to compile — top 3 with readiness ≥ 80%
 *   3. At risk      — top 3 with readiness ≤ 40% OR no activity > 7 days
 *   4. Document Journal — Chunk 6.5-REVISED (2026-05-13, Task D)
 *      top 5 most-recent documents in the context with a "View more"
 *      CTA routing to `/app/workspace`.
 *
 * Source: aggregates across all 6 kinds, with deterministic readiness.
 * The same readiness placeholder is used as in the wizard
 * (document_count*12 + contributor_count*10, clamped 0-100) until a
 * real readiness signal lands.
 *
 * Click handlers:
 *   • Primary CTA → onOpenWizard()
 *   • Ready row    → onOpenWizard({ artefactType, sourceId })  (pre-selects on Step 2)
 *   • At-risk row  → navigates to the artefact detail surface
 *   • Document row → navigates to /app/documents/<id>
 *   • View more →  → navigates to /app/workspace
 *
 * Constant-height constraint (Chunk 6.5-REVISED): each deck body
 * carries an explicit `min-height` + `max-height` + overflow:hidden,
 * so the rail's vertical layout doesn't jump as data populates. The
 * Document Journal deck's "View more" button stays visible regardless
 * of how many docs are returned (the overflow rolls behind it).
 *
 * Oxblood is used ONLY on the At-risk readiness numeral (severity case).
 */
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Sparkles, RefreshCw, AlertCircle, Loader2, BookOpenCheck, ArrowRight,
} from "lucide-react";


// Match the wizard's artefact type ↔ aggregate kind mapping.
const KINDS = [
  { artefact_type: "board_pack",     kind: "cycle_board_pack",     label: "Board pack" },
  { artefact_type: "minutes",        kind: "cycle_minutes",        label: "Minutes" },
  { artefact_type: "committee_pack", kind: "cycle_committee_pack", label: "Committee pack" },
  { artefact_type: "deck",           kind: "deck",                 label: "Deck" },
  { artefact_type: "report",         kind: "report",               label: "Report" },
  { artefact_type: "briefing",       kind: "briefing",             label: "Briefing" },
];


// Per-deck body height. 3-row sections (Ready / At-risk) cap at ~120px;
// the 5-row Document Journal deck caps at ~180px. Both render at fixed
// height regardless of how many items load, so the rail doesn't jump.
const DECK_BODY_HEIGHT_3ROW = 120;
const DECK_BODY_HEIGHT_5ROW = 180;
const RECENT_DOCS_LIMIT = 5;


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
  // Decks → /app/decks/<id>, Reports → /app/cycle?tab=overview&report=<id>.
  // Anything else routes back to the work studio tab.
  const raw = row.id || "";
  const idPart = raw.includes("::") ? raw.split("::")[1] : raw;
  if (kindEntry.artefact_type === "deck") return `/app/decks/${idPart}`;
  if (kindEntry.artefact_type === "report") return `/app/cycle?tab=overview&report=${idPart}`;
  return `/app/work-studio?kind=${kindEntry.kind}`;
}


export default function CompilationRail({ contextId, onOpenWizard, refreshKey = 0 }) {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  // Chunk 6.5-REVISED (Task D) — Document Journal side deck state.
  const [recentDocs, setRecentDocs] = useState([]);
  const [recentDocsLoading, setRecentDocsLoading] = useState(true);

  useEffect(() => {
    if (!contextId) return undefined;
    let dead = false;
    setLoading(true);
    setErr(null);
    Promise.all(KINDS.map((k) =>
      api
        .get(`/contexts/${contextId}/briefings/aggregates`, {
          params: { kind: k.kind, page_size: 50, sort: "recent" },
        })
        .then(({ data }) => (data?.items || []).map((it) => ({ ...it, _kind: k })))
        .catch(() => []),
    ))
      .then((all) => {
        if (dead) return;
        setRows(all.flat());
      })
      .catch(() => { if (!dead) setErr("Could not load rail."); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [contextId, refreshKey]);

  // Document Journal deck — fetched independently so a Document Journal
  // outage doesn't blank the Compile-report sections.
  useEffect(() => {
    if (!contextId) return undefined;
    let dead = false;
    setRecentDocsLoading(true);
    api
      .get(`/contexts/${contextId}/document-journal/recent`, { params: { limit: RECENT_DOCS_LIMIT } })
      .then(({ data }) => { if (!dead) setRecentDocs(data?.items || []); })
      .catch(() => { if (!dead) setRecentDocs([]); })
      .finally(() => { if (!dead) setRecentDocsLoading(false); });
    return () => { dead = true; };
  }, [contextId, refreshKey]);

  const { ready, atRisk } = useMemo(() => {
    const sevenDaysMs = 7 * 24 * 60 * 60 * 1000;
    const now = Date.now();
    const decorated = rows.map((r) => {
      const readiness = rowReadiness(r);
      let lastTs = 0;
      try { lastTs = new Date(r.meeting_date || r.created_at || 0).getTime() || 0; } catch { /* noop */ }
      const stale = lastTs > 0 && (now - lastTs) > sevenDaysMs;
      return { ...r, _readiness: readiness, _stale: stale, _lastTs: lastTs };
    });
    const r = decorated
      .filter((r2) => r2._readiness >= 80)
      .sort((a, b) => b._readiness - a._readiness)
      .slice(0, 3);
    const a = decorated
      .filter((r2) => r2._readiness <= 40 || r2._stale)
      .sort((x, y) => (x._readiness - y._readiness) || (x._lastTs - y._lastTs))
      .slice(0, 3);
    return { ready: r, atRisk: a };
  }, [rows]);

  return (
    <aside
      className="hidden xl:block w-[340px] shrink-0"
      data-testid="compilation-rail"
    >
      <div
        className="sticky top-24 space-y-5"
        data-testid="compilation-rail-sticky"
      >
        {/* Primary CTA */}
        <Button
          type="button"
          onClick={() => onOpenWizard && onOpenWizard()}
          className="w-full bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
          data-testid="compilation-rail-cta"
        >
          <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Compile a Report
        </Button>

        {/* Ready to compile */}
        <section
          className="border border-[var(--rule)] bg-white rounded-sm"
          data-testid="compilation-rail-ready"
        >
          <header className="px-3 py-2 border-b border-[var(--rule)] flex items-center justify-between">
            <p className="akki-overline text-[10.5px] tracking-[0.16em] text-[var(--ink)]">
              Ready to compile
            </p>
            {loading && <Loader2 className="w-3 h-3 animate-spin text-[var(--muted)]" />}
          </header>
          <div
            className="p-2.5 overflow-hidden"
            style={{ minHeight: DECK_BODY_HEIGHT_3ROW, maxHeight: DECK_BODY_HEIGHT_3ROW }}
          >
            {loading ? null : ready.length === 0 ? (
              <p className="text-[12px] text-[var(--muted)] italic px-1" data-testid="compilation-rail-ready-empty">
                Nothing ready yet.
              </p>
            ) : (
              <ul className="space-y-1.5" data-testid="compilation-rail-ready-list">
                {ready.map((row) => (
                  <li key={row.id} className="text-[12.5px]">
                    <button
                      type="button"
                      onClick={() => onOpenWizard && onOpenWizard({
                        artefactType: row._kind.artefact_type,
                        sourceId: row.id,
                      })}
                      className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] flex items-center gap-2"
                      data-testid="compilation-rail-ready-row"
                    >
                      <span className="flex-1 min-w-0 truncate text-[var(--ink)]">{row.name}</span>
                      <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] shrink-0">
                        {row._kind.label}
                      </span>
                      <span className="font-mono text-[12px] tabular-nums text-[var(--ink)] shrink-0 w-10 text-right">
                        {row._readiness}%
                      </span>
                      <RefreshCw
                        className="w-3 h-3 text-[var(--muted)] shrink-0"
                        strokeWidth={1.7}
                        aria-label="Compile"
                      />
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
          data-testid="compilation-rail-atrisk"
        >
          <header className="px-3 py-2 border-b border-[var(--rule)] flex items-center gap-1.5">
            <AlertCircle className="w-3 h-3 text-[color:var(--oxblood)]" strokeWidth={1.7} />
            <p className="akki-overline text-[10.5px] tracking-[0.16em] text-[var(--ink)]">At risk</p>
          </header>
          <div
            className="p-2.5 overflow-hidden"
            style={{ minHeight: DECK_BODY_HEIGHT_3ROW, maxHeight: DECK_BODY_HEIGHT_3ROW }}
          >
            {loading ? null : atRisk.length === 0 ? (
              <p className="text-[12px] text-[var(--muted)] italic px-1" data-testid="compilation-rail-atrisk-empty">
                Nothing at risk. Healthy queue.
              </p>
            ) : (
              <ul className="space-y-1.5" data-testid="compilation-rail-atrisk-list">
                {atRisk.map((row) => (
                  <li key={row.id} className="text-[12.5px]">
                    <button
                      type="button"
                      onClick={() => navigate(artefactDetailHref(row, row._kind))}
                      className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] flex items-center gap-2"
                      data-testid="compilation-rail-atrisk-row"
                    >
                      <span className="flex-1 min-w-0 truncate text-[var(--ink)]">{row.name}</span>
                      <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] shrink-0">
                        {row._kind.label}
                      </span>
                      {/* oxblood numeral — severity case (spec-locked) */}
                      <span
                        className="font-mono text-[12px] tabular-nums text-[color:var(--oxblood)] shrink-0 w-10 text-right"
                        data-testid="compilation-rail-atrisk-readiness"
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

        {/* Chunk 6.5-REVISED (2026-05-13, Task D) — Document Journal deck. */}
        <section
          className="border border-[var(--rule)] bg-white rounded-sm"
          data-testid="compilation-rail-document-journal"
        >
          <header className="px-3 py-2 border-b border-[var(--rule)] flex items-center gap-1.5">
            <BookOpenCheck className="w-3 h-3 text-[var(--deep)]" strokeWidth={1.7} />
            <p className="akki-overline text-[10.5px] tracking-[0.16em] text-[var(--ink)]">Document journal</p>
            {recentDocsLoading && <Loader2 className="w-3 h-3 animate-spin text-[var(--muted)] ml-auto" />}
          </header>
          <div
            className="p-2.5 overflow-hidden"
            style={{ minHeight: DECK_BODY_HEIGHT_5ROW, maxHeight: DECK_BODY_HEIGHT_5ROW }}
          >
            {recentDocsLoading ? null : recentDocs.length === 0 ? (
              <p className="text-[12px] text-[var(--muted)] italic px-1" data-testid="compilation-rail-document-journal-empty">
                No documents yet.
              </p>
            ) : (
              <ul className="space-y-1.5" data-testid="compilation-rail-document-journal-list">
                {recentDocs.map((d) => (
                  <li key={d.id} className="text-[12.5px]">
                    <button
                      type="button"
                      onClick={() => navigate(`/app/documents/${d.id}`)}
                      className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] flex items-center gap-2"
                      data-testid={`compilation-rail-document-journal-row-${d.id}`}
                    >
                      <span className="flex-1 min-w-0 truncate text-[var(--ink)]">{d.title}</span>
                      {d.doc_kind && (
                        <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] shrink-0">
                          {d.doc_kind}
                        </span>
                      )}
                      <span className="font-mono text-[11px] text-[var(--muted)] shrink-0 w-8 text-right">
                        {fmtRelDays(d.created_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <footer className="px-3 py-2 border-t border-[var(--rule)] bg-[var(--cream-deep)]/40">
            <button
              type="button"
              onClick={() => navigate("/app/workspace")}
              className="text-[11.5px] text-[var(--deep)] hover:text-[var(--ink)] inline-flex items-center gap-1 transition-colors"
              data-testid="compilation-rail-document-journal-view-more"
            >
              View more <ArrowRight className="w-3 h-3" strokeWidth={1.7} />
            </button>
          </footer>
        </section>

        {err && (
          <p className="text-[11.5px] text-amber-900 inline-flex items-center gap-1.5">
            <AlertCircle className="w-3 h-3" /> {err}
          </p>
        )}
      </div>
    </aside>
  );
}
