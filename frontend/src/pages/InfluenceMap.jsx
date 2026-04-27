/**
 * Influence Map — who's reading, sharing, mentioning what.
 *
 * Editorial matrix view (not a force-directed graph) — people on the
 * left axis, documents across the top. Each cell carries a glyph
 * weighted by engagement intensity. Side panels surface the top
 * influencers and the most-engaged documents. Window picker lets the
 * user widen the lens (7d / 30d / 90d / 1y).
 *
 *   Read = ·
 *   Share = ◐
 *   Comment = ●
 *   Mention = ★
 *
 * Ed-cell intensity scales from cream → oxblood as score climbs.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  Activity, Loader2, BookOpen, User, Share2, MessageSquare, AtSign,
} from "lucide-react";

const WINDOWS = [
  { value: 7, label: "Last 7 days" },
  { value: 30, label: "Last 30 days" },
  { value: 90, label: "Last 90 days" },
  { value: 365, label: "Last year" },
];

const KIND_GLYPH = { read: "·", share: "◐", comment: "●", mention: "★" };

export default function InfluenceMap() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!cid) return;
    setLoading(true);
    try {
      const { data: d } = await api.get(
        `/contexts/${cid}/influence-map`,
        { params: { days } },
      );
      setData(d);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [cid, days]);
  useEffect(() => { load(); }, [load]);

  // Build a person × doc matrix of edge maps for fast lookup.
  const matrix = useMemo(() => {
    if (!data) return null;
    const m = new Map();
    for (const e of data.edges || []) {
      const key = `${e.source}::${e.target}`;
      const cell = m.get(key) || { kinds: {}, total: 0, last_at: null };
      cell.kinds[e.kind] = (cell.kinds[e.kind] || 0) + e.weight;
      cell.total += e.weight;
      if (!cell.last_at || (e.last_at && e.last_at > cell.last_at)) {
        cell.last_at = e.last_at;
      }
      m.set(key, cell);
    }
    return m;
  }, [data]);

  if (!cid) {
    return <AppShell><div className="p-12 text-center text-sm text-[var(--muted)]">No company selected.</div></AppShell>;
  }

  const empty = !loading && data && (data.people.length === 0 || data.top_docs.length === 0);

  return (
    <AppShell>
      <div className="max-w-[1400px] mx-auto px-8 py-8" data-testid="influence-map-page">
        <header className="mb-6 akki-fade-up">
          <p className="akki-overline mb-2 flex items-center gap-1.5">
            <Activity className="w-3 h-3 text-[var(--accent)]" /> Influence map · {activeContext?.name}
          </p>
          <h1 className="akki-greeting mb-2">Who's actually reading.</h1>
          <p className="akki-meta max-w-2xl">
            The pattern of attention across your board's papers. AKKI surfaces who
            engages with what — reads, shares, comments, mentions — so you can see
            stakeholder dynamics rather than guess at them.
          </p>
        </header>

        {/* Window picker + totals */}
        <div className="bg-white border border-[var(--rule)] rounded-lg p-4 mb-5 flex items-center gap-3 flex-wrap" data-testid="influence-controls">
          <div className="flex items-center gap-1">
            <span className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono mr-2">Window</span>
            {WINDOWS.map((w) => (
              <button
                key={w.value}
                onClick={() => setDays(w.value)}
                className={`text-[11.5px] px-2.5 py-1 rounded-sm border transition-colors ${
                  days === w.value
                    ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                    : "bg-[var(--cream)] border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"
                }`}
                data-testid={`influence-window-${w.value}`}
              >
                {w.label}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-3 text-[11px]">
            <Legend icon={User}        label={`${data?.totals?.people || 0} people`} />
            <Legend icon={BookOpen}    label={`${data?.totals?.documents_engaged || 0} docs`} />
            <Legend icon={Share2}      label={`${data?.totals?.shares || 0} shares`} />
            <Legend icon={MessageSquare} label={`${data?.totals?.comments || 0} comments`} />
            <Legend icon={AtSign}      label={`${data?.totals?.mentions || 0} mentions`} />
          </div>
        </div>

        {loading ? (
          <div className="text-center py-16" data-testid="influence-loading">
            <Loader2 className="w-7 h-7 animate-spin text-[var(--accent)] mx-auto mb-3" />
            <p className="text-[12.5px] text-[var(--muted)] italic">Reading the engagement signal…</p>
          </div>
        ) : empty ? (
          <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-12 text-center" data-testid="influence-empty">
            <Activity className="w-9 h-9 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.2} />
            <p className="akki-serif text-[16px] text-[var(--ink)] mb-2">
              No engagement on file in this window yet.
            </p>
            <p className="text-[12.5px] text-[var(--muted)] leading-relaxed max-w-md mx-auto">
              Share a document or briefing with a colleague, or have someone open one,
              and the map will populate. Comments and @-mentions also count.
            </p>
          </div>
        ) : data && (
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-5" data-testid="influence-content">
            <Matrix data={data} matrix={matrix} />
            <div className="space-y-5">
              <TopPanel
                kicker="Top influencers"
                rows={data.people.slice(0, 8)}
                renderRight={(r) => (
                  <span className="font-mono text-[10px] text-[var(--muted)]">
                    {r.breakdown.share || 0}◐ · {r.breakdown.comment || 0}● · {r.breakdown.mention || 0}★
                  </span>
                )}
                testid="influence-top-people"
              />
              <TopPanel
                kicker="Most-engaged documents"
                rows={data.top_docs.slice(0, 8)}
                renderRight={(r) => (
                  <span className="font-mono text-[10px] text-[var(--muted)]">
                    {r.readers} reader{r.readers === 1 ? "" : "s"}
                  </span>
                )}
                testid="influence-top-docs"
              />
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function Legend({ icon: Icon, label }) {
  return (
    <span className="inline-flex items-center gap-1 text-[var(--muted)]">
      <Icon className="w-3 h-3" strokeWidth={1.6} />
      <span className="tabular-nums">{label}</span>
    </span>
  );
}

function Matrix({ data, matrix }) {
  // Cap to keep the matrix readable. Tail gets folded into a "+ N more" hint.
  const people = data.people.slice(0, 14);
  const docs   = data.top_docs.slice(0, 12);
  const peopleHidden = data.people.length - people.length;
  const docsHidden   = data.top_docs.length - docs.length;
  // Score → cell intensity (0..4)
  const cellTone = (score) => {
    if (!score) return "bg-transparent";
    if (score >= 8)  return "bg-[var(--accent)]/90 text-white";
    if (score >= 5)  return "bg-[var(--accent)]/70 text-white";
    if (score >= 3)  return "bg-[var(--accent)]/40 text-[var(--ink)]";
    if (score >= 1)  return "bg-[var(--accent)]/15 text-[var(--ink)]";
    return "bg-transparent";
  };

  return (
    <div className="bg-white border border-[var(--rule)] rounded-lg overflow-hidden" data-testid="influence-matrix">
      <div className="overflow-x-auto">
        <table className="w-full text-[11px] border-collapse">
          <thead>
            <tr className="border-b border-[var(--rule)]">
              <th className="text-left p-2 font-normal text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] sticky left-0 bg-white z-10 min-w-[160px]">
                People \ Documents
              </th>
              {docs.map((d) => (
                <th
                  key={d.id}
                  className="text-left p-1.5 font-normal text-[10px] text-[var(--ink)] align-bottom min-w-[26px]"
                  title={d.label}
                >
                  <div className="rotate-[-50deg] origin-bottom-left whitespace-nowrap pl-2"
                       style={{ height: 90, transformOrigin: "0 100%" }}>
                    {d.label.length > 28 ? d.label.slice(0, 28) + "…" : d.label}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {people.map((p) => (
              <tr key={p.id} className="border-b border-[var(--rule)] last:border-b-0">
                <td className="p-2 sticky left-0 bg-white z-10 border-r border-[var(--rule)]">
                  <div className="flex items-center gap-2">
                    <span className="text-[12.5px] text-[var(--ink)] truncate max-w-[140px]" title={p.label}>
                      {p.label}
                    </span>
                  </div>
                  <span className="font-mono text-[9px] text-[var(--muted)]">
                    score {p.score} · {p.breakdown.read || 0} reads
                  </span>
                </td>
                {docs.map((d) => {
                  const cell = matrix.get(`${p.id}::${d.id}`);
                  const total = cell?.total || 0;
                  const kinds = cell?.kinds || {};
                  return (
                    <td
                      key={d.id}
                      className={`p-1 text-center align-middle border-r border-[var(--rule)]/40 transition-colors ${cellTone(total)}`}
                      data-testid={`influence-cell-${p.id}-${d.id}`}
                      title={total ? Object.entries(kinds).map(([k, n]) => `${n} ${k}${n === 1 ? "" : "s"}`).join(" · ") : ""}
                    >
                      {total ? (
                        <span className="font-mono text-[12px] leading-none">
                          {kinds.mention ? KIND_GLYPH.mention :
                           kinds.comment ? KIND_GLYPH.comment :
                           kinds.share   ? KIND_GLYPH.share   :
                                           KIND_GLYPH.read}
                        </span>
                      ) : null}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(peopleHidden > 0 || docsHidden > 0) && (
        <div className="px-3 py-2 text-[10.5px] text-[var(--muted)] border-t border-[var(--rule)] bg-[var(--cream)]" data-testid="influence-overflow-note">
          Showing top {people.length} of {data.people.length} people × top {docs.length} of {data.top_docs.length} documents.
        </div>
      )}
      <div className="px-3 py-2 text-[10.5px] text-[var(--muted)] border-t border-[var(--rule)] bg-white flex items-center gap-3 flex-wrap" data-testid="influence-glyph-key">
        <span className="font-mono">·</span> read
        <span className="font-mono ml-2">◐</span> share
        <span className="font-mono ml-2">●</span> comment
        <span className="font-mono ml-2">★</span> mention
        <span className="ml-3 italic">Cell intensity scales with combined weight.</span>
      </div>
    </div>
  );
}

function TopPanel({ kicker, rows, renderRight, testid }) {
  return (
    <div className="bg-white border border-[var(--rule)] rounded-lg p-4" data-testid={testid}>
      <p className="akki-overline mb-3">{kicker}</p>
      {rows.length === 0 ? (
        <p className="text-[12px] text-[var(--muted)] italic">None yet in this window.</p>
      ) : (
        <ol className="space-y-2">
          {rows.map((r, i) => (
            <li key={r.id} className="flex items-baseline gap-2">
              <span className="font-mono text-[10px] text-[var(--muted)] tabular-nums shrink-0">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="text-[12.5px] text-[var(--ink)] flex-1 truncate" title={r.label}>
                {r.label}
              </span>
              {renderRight(r)}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
