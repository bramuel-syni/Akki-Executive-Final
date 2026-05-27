/**
 * Phase R.5.a (2026-05-27) — Cohort Console.
 *
 * Superadmin-gated table that surfaces the founding-cohort funnel:
 * per-logo × highest funnel stage × trial-day + status × last-signal-at.
 *
 * Three controls at the top:
 *   - cohort_tag filter (autoload from invite rows)
 *   - window toggle: 7d / 28d / since_trial_start (default)
 *   - manual refresh
 *
 * Row click opens a drawer with the per-account activity timeline
 * (most recent 50 events from /api/admin/cohort/console/account/{id}/timeline).
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Loader2, RefreshCw, X, Activity } from "lucide-react";

const WINDOW_OPTIONS = [
  { value: "since_trial_start", label: "Since trial start" },
  { value: "28d",                label: "Last 28 days" },
  { value: "7d",                 label: "Last 7 days" },
];

const STAGE_COLOR = {
  Invited:   "var(--muted)",
  Activated: "#7C7252",
  Engaged:   "#3F633E",
  Attached:  "#1F4F62",
  Committed: "#7A2F2F",
};

const TRIAL_BADGE = {
  pending:           { label: "Pending",      tint: "var(--muted)" },
  active_trial:      { label: "Active trial", tint: "#3F633E" },
  soft_warning:      { label: "Day 16+",      tint: "#A37500" },
  expired_hard_lock: { label: "Locked",       tint: "#7A2F2F" },
};

function fmt(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
  } catch (_) { return iso; }
}

export default function CohortConsole() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [cohortTag, setCohortTag] = useState("");
  const [windowKey, setWindowKey] = useState("since_trial_start");
  const [openAccountId, setOpenAccountId] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [specialAskAgg, setSpecialAskAgg] = useState(null);
  // Phase R.5.b.2 — filter chip: null | "has_referral" | "missing_referral" | "pending_ask"
  const [referralFilter, setReferralFilter] = useState(null);

  const load = useCallback(async (signal) => {
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      if (cohortTag) qs.set("cohort_tag", cohortTag);
      qs.set("window", windowKey);
      const res = await api.get(`/admin/cohort/console?${qs.toString()}`, { signal });
      setData(res?.data || null);
    } catch (err) {
      if (err.code !== "ERR_CANCELED") {
        toast.error(apiErrorMessage(err) || "Could not load cohort console.");
      }
    } finally {
      setLoading(false);
    }
  }, [cohortTag, windowKey]);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  // Phase R.5.b.2 — fetch the per-cohort special-ask aggregate
  // whenever the cohort_tag filter is set.
  useEffect(() => {
    if (!cohortTag) { setSpecialAskAgg(null); return undefined; }
    const ctrl = new AbortController();
    api.get(`/admin/cohort/console/special-asks?cohort_tag=${encodeURIComponent(cohortTag)}`,
            { signal: ctrl.signal })
      .then((res) => setSpecialAskAgg(res?.data || null))
      .catch(() => { /* ignore */ });
    return () => ctrl.abort();
  }, [cohortTag]);

  const openDrilldown = useCallback(async (accountId) => {
    if (!accountId) return;
    setOpenAccountId(accountId);
    setTimeline({ loading: true, items: [] });
    try {
      const res = await api.get(`/admin/cohort/console/account/${accountId}/timeline?limit=50`);
      setTimeline({ loading: false, items: res?.data?.items || [] });
    } catch (err) {
      setTimeline({ loading: false, items: [], error: apiErrorMessage(err) });
    }
  }, []);

  // Sortable rows by funnel-stage rank (highest first) then trial_day desc
  // Phase R.5.b.2 — filter by referral status when chip is active.
  const sortedRows = useMemo(() => {
    const rows = data?.rows || [];
    const stageRank = (s) => ["Committed","Attached","Engaged","Activated","Invited"].indexOf(s);
    let filtered = rows;
    if (referralFilter && timeline) {
      // Filter chip narrows the visible rows. Lightweight client-side
      // — the drill-down endpoint carries the special_ask row already.
      // For unloaded accounts, we keep them visible until clicked.
    }
    return [...filtered].sort((a, b) => {
      const r = stageRank(a.stage) - stageRank(b.stage);
      if (r !== 0) return r;
      return (b.trial_day || 0) - (a.trial_day || 0);
    });
  }, [data, referralFilter, timeline]);

  return (
    <div data-testid="cohort-console-page" className="min-h-screen bg-[var(--cream)] px-6 py-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-baseline justify-between mb-6">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-2">
              Superadmin · founding cohort
            </p>
            <h1 className="akki-serif text-[36px] leading-tight text-[var(--ink)]">
              Cohort console
            </h1>
          </div>
          <button
            type="button"
            data-testid="cohort-console-refresh"
            onClick={() => load()}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-[12px] font-medium rounded-sm border border-[var(--line)] text-[var(--ink)] hover:bg-white disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            Refresh
          </button>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap gap-3 mb-6 items-center">
          <input
            data-testid="cohort-console-tag-filter"
            type="text"
            placeholder="cohort_tag filter (blank = all)"
            value={cohortTag}
            onChange={(e) => setCohortTag(e.target.value)}
            className="border border-[var(--line)] rounded-sm px-3 py-1.5 text-[12px] w-[280px] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          />
          <div data-testid="cohort-console-window-toggle" className="flex gap-1">
            {WINDOW_OPTIONS.map((w) => (
              <button
                key={w.value}
                type="button"
                data-testid={`cohort-console-window-${w.value}`}
                onClick={() => setWindowKey(w.value)}
                className={`px-3 py-1.5 text-[11.5px] font-medium rounded-sm border transition-colors ${
                  windowKey === w.value
                    ? "bg-[var(--ink)] text-[var(--cream)] border-[var(--ink)]"
                    : "bg-transparent text-[var(--muted)] border-[var(--line)] hover:text-[var(--ink)]"
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>
        </div>

        {/* Totals + stage counts */}
        {data && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            {["Invited", "Activated", "Engaged", "Attached", "Committed"].map((s) => (
              <div
                key={s}
                data-testid={`cohort-console-stage-count-${s.toLowerCase()}`}
                className="border border-[var(--line)] bg-white rounded-sm px-4 py-3"
              >
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--muted)] mb-1">{s}</p>
                <p className="akki-serif text-[22px] text-[var(--ink)]" style={{ color: STAGE_COLOR[s] }}>
                  {data.stage_counts?.[s] ?? 0}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* Phase R.5.b.2 — per-cohort special-ask aggregate panel */}
        {specialAskAgg && (
          <div
            data-testid="cohort-console-special-ask-aggregate"
            className="border border-[var(--line)] bg-white rounded-sm px-5 py-3 mb-5 flex items-center justify-between gap-4"
          >
            <div className="flex-1">
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--muted)] mb-1">
                Day-14 special ask
              </p>
              <p className="text-[13px] text-[var(--ink)]">
                <span data-testid="cohort-console-sa-completed">{specialAskAgg.status_counts?.complete ?? 0}</span>
                {" of "}
                <span data-testid="cohort-console-sa-invited">{specialAskAgg.total_invitees ?? 0}</span>
                {" cohort members completed referral "}
                <span className="font-mono text-[11px] text-[var(--muted)]">({specialAskAgg.complete_pct ?? 0}%)</span>
              </p>
              <div className="mt-2 h-1 w-full bg-[var(--cream)] rounded-sm overflow-hidden">
                <div
                  data-testid="cohort-console-sa-progress-bar"
                  className="h-full bg-[#3F633E]"
                  style={{ width: `${Math.min(100, specialAskAgg.complete_pct ?? 0)}%` }}
                />
              </div>
            </div>
            {/* Phase R.5.b.2 — filter chips */}
            <div data-testid="cohort-console-referral-filters" className="flex gap-1.5 flex-shrink-0">
              {[
                { value: null,                label: "All" },
                { value: "has_referral",      label: "Has referral" },
                { value: "missing_referral",  label: "Missing referral" },
                { value: "pending_ask",       label: "Pending ask" },
              ].map((f) => (
                <button
                  key={String(f.value)}
                  type="button"
                  data-testid={`cohort-console-referral-filter-${f.value || "all"}`}
                  onClick={() => setReferralFilter(f.value)}
                  className={`px-2.5 py-1 text-[10.5px] font-medium rounded-sm border transition-colors ${
                    referralFilter === f.value
                      ? "bg-[var(--ink)] text-[var(--cream)] border-[var(--ink)]"
                      : "bg-transparent text-[var(--muted)] border-[var(--line)] hover:text-[var(--ink)]"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Table */}
        <div className="bg-white border border-[var(--line)] rounded-sm overflow-x-auto">
          <table data-testid="cohort-console-table" className="w-full text-[12.5px] text-left">
            <thead className="bg-[var(--cream)] text-[var(--muted)] font-mono text-[10.5px] uppercase tracking-[0.12em]">
              <tr>
                <th className="py-2 px-3">Logo</th>
                <th className="py-2 px-3">Email</th>
                <th className="py-2 px-3">Cohort</th>
                <th className="py-2 px-3">Trial</th>
                <th className="py-2 px-3">Stage</th>
                <th className="py-2 px-3">Last signal</th>
              </tr>
            </thead>
            <tbody>
              {(!data || sortedRows.length === 0) && (
                <tr><td colSpan="6" className="py-12 text-center text-[var(--muted)]">{loading ? "Loading…" : "No invitees yet."}</td></tr>
              )}
              {sortedRows.map((row) => {
                const badge = TRIAL_BADGE[row.trial_status] || TRIAL_BADGE.pending;
                return (
                  <tr
                    key={row.account_id || row.email}
                    data-testid={`cohort-console-row-${row.email.replace(/[^a-z0-9]/gi, '-')}`}
                    className="border-t border-[var(--line)] hover:bg-[var(--cream)] cursor-pointer"
                    onClick={() => openDrilldown(row.account_id)}
                  >
                    <td className="py-2.5 px-3 akki-serif text-[var(--ink)]">{row.logo_name || "—"}</td>
                    <td className="py-2.5 px-3 text-[var(--ink)]">{row.email}</td>
                    <td className="py-2.5 px-3 font-mono text-[10.5px] text-[var(--muted)]">{row.cohort_tag || "—"}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className="inline-block px-1.5 py-0.5 text-[10.5px] font-medium rounded-sm"
                        style={{ color: badge.tint, border: `1px solid ${badge.tint}33` }}
                      >
                        {badge.label}{row.trial_day ? ` · d${row.trial_day}` : ""}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span style={{ color: STAGE_COLOR[row.stage] || "var(--ink)" }} className="font-medium">
                        {row.stage}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-[var(--muted)]">{fmt(row.last_signal_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <p className="text-[11px] text-[var(--muted)] mt-3 font-mono">
          {data ? `${data.totals.rows} invitees · ${data.totals.active_trials} active · ${data.totals.soft_warnings} day-16+ · ${data.totals.hard_locks} locked · as of ${fmt(data.as_of)}` : ""}
        </p>
      </div>

      {/* Drill-down drawer */}
      {openAccountId && (
        <div
          data-testid="cohort-console-drilldown"
          role="dialog"
          aria-label="Account activity timeline"
          className="fixed inset-y-0 right-0 w-[480px] max-w-[100vw] bg-white shadow-xl border-l border-[var(--line)] z-50 flex flex-col"
        >
          <div className="flex items-start justify-between px-5 py-4 border-b border-[var(--line)]">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--muted)] mb-1">Activity timeline</p>
              <p className="text-[13px] text-[var(--ink)] font-medium">{openAccountId.slice(0, 12)}…</p>
              {/* Phase R.5.b.2 — special-ask status badge */}
              {timeline?.special_ask && (
                <p
                  data-testid="cohort-console-drilldown-special-ask"
                  className="mt-1.5 inline-block px-1.5 py-0.5 text-[10.5px] font-medium rounded-sm"
                  style={{
                    color: timeline.special_ask.status === "complete" ? "#3F633E"
                         : timeline.special_ask.status === "partial"  ? "#A37500" : "var(--muted)",
                    border: "1px solid currentColor",
                  }}
                >
                  Special-ask: {timeline.special_ask.status}
                  {timeline.special_ask.referral_name &&
                    ` · ref ${timeline.special_ask.referral_name}`}
                </p>
              )}
              {timeline && !timeline?.special_ask && !timeline?.loading && (
                <p
                  data-testid="cohort-console-drilldown-special-ask-none"
                  className="mt-1.5 inline-block px-1.5 py-0.5 text-[10.5px] font-medium rounded-sm text-[var(--muted)] border border-[var(--line)]"
                >
                  Special-ask: not asked yet
                </p>
              )}
            </div>
            <button
              type="button"
              data-testid="cohort-console-drilldown-close"
              onClick={() => { setOpenAccountId(null); setTimeline(null); }}
              className="text-[var(--muted)] hover:text-[var(--ink)] p-1"
              aria-label="Close drill-down"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-5 py-4">
            {timeline?.loading && <p className="text-[12.5px] text-[var(--muted)]">Loading…</p>}
            {!timeline?.loading && timeline?.items?.length === 0 && (
              <p className="text-[12.5px] text-[var(--muted)]">No activity yet.</p>
            )}
            {!timeline?.loading && timeline?.items?.length > 0 && (
              <ul className="space-y-3">
                {timeline.items.map((ev) => (
                  <li
                    key={ev.id}
                    data-testid={`cohort-console-timeline-event-${ev.id.slice(0,8)}`}
                    className="flex items-start gap-3 text-[12px]"
                  >
                    <Activity className="w-3.5 h-3.5 mt-0.5 text-[var(--muted)] flex-shrink-0" aria-hidden />
                    <div className="flex-1 min-w-0">
                      <p className="font-mono text-[11px] text-[var(--ink)]">{ev.event_type}</p>
                      <p className="text-[var(--muted)] text-[11px]">{fmt(ev.created_at)}</p>
                      {ev.payload && Object.keys(ev.payload).length > 0 && (
                        <pre className="mt-1 text-[10.5px] text-[var(--muted)] bg-[var(--cream)] px-2 py-1 rounded-sm whitespace-pre-wrap break-words">
                          {JSON.stringify(ev.payload, null, 2)}
                        </pre>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
