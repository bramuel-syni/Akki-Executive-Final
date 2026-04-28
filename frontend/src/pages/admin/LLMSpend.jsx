/**
 * LLMSpend — `/admin/llm-spend`.
 *
 * Superadmin telemetry for deep-tier (Claude Opus) usage. Surfaces
 * rolling-30-day call counts, estimated cost, per-surface mix, and the
 * top-spending accounts. Companion to /admin/health and /admin/sandbox-kpi.
 *
 * Source data: `llm_deep_usage` collection. Read-only.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { RefreshCw, Loader2, Sparkles, BarChart3, Users, Calendar } from "lucide-react";

const SURFACE_LABEL = {
  brief:    "Deep Brief",
  blog:     "ExCo360 blog",
  deck:     "Deck generation",
  chat:     "Chat (Opus)",
  validate: "Validation",
  minutes:  "Minutes narrative",
};

function fmtUSD(n) {
  if (n === undefined || n === null) return "—";
  return `$${Number(n).toFixed(2)}`;
}

export default function LLMSpend() {
  const { account, loading: authLoading } = useAuth();
  const [data, setData] = useState(null);
  const [deckQuality, setDeckQuality] = useState(null);
  const [loading, setLoading] = useState(true);
  const [windowDays, setWindowDays] = useState("30");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [{ data }, { data: dq }] = await Promise.all([
        api.get(`/admin/llm/spend?days=${windowDays}`),
        api.get(`/admin/llm/decks/quality?days=${windowDays}`).catch(() => ({ data: null })),
      ]);
      setData(data);
      setDeckQuality(dq);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [windowDays]);
  useEffect(() => { load(); }, [load]);

  if (authLoading) return null;
  if (!account?.is_superadmin) return <Navigate to="/app" replace />;

  const t = data?.totals;
  const maxDayCalls = Math.max(1, ...(data?.by_day || []).map((d) => d.calls));

  return (
    <div className="min-h-screen bg-[var(--cream)] py-10 px-6" data-testid="llm-spend-dashboard">
      <div className="max-w-5xl mx-auto">
        <header className="mb-8 flex items-end justify-between gap-6 flex-wrap">
          <div>
            <p className="akki-overline mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Deep-tier usage · superadmin
            </p>
            <h1 className="akki-greeting mb-2">Where the Opus budget went.</h1>
            <p className="akki-meta max-w-2xl">
              Rolling view of every deep-tier (Claude Opus) call, by surface
              and account. Estimated cost uses ${data?.unit_cost_usd ?? "0.045"}{" "}
              per generation — adjust via <code className="text-[11.5px] bg-[var(--cream-deep)]/40 px-1.5 py-0.5 rounded-sm">AKKI_DEEP_UNIT_COST_USD</code>.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Select value={windowDays} onValueChange={setWindowDays}>
              <SelectTrigger
                className="h-9 w-[140px] bg-white border-[var(--rule)]"
                data-testid="llm-spend-window-select"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">Today</SelectItem>
                <SelectItem value="7">Last 7 days</SelectItem>
                <SelectItem value="30">Last 30 days</SelectItem>
                <SelectItem value="90">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              onClick={load}
              disabled={loading}
              className="h-9 border-[var(--rule)]"
              data-testid="llm-spend-refresh"
            >
              {loading ? (
                <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
              ) : (
                <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
              )}
              Refresh
            </Button>
          </div>
        </header>

        {/* Summary tiles */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8" data-testid="llm-spend-tiles">
          <Tile
            label="Calls"
            value={t ? t.calls.toLocaleString() : "—"}
            subline={t ? `${t.surfaces_used} surfaces` : ""}
          />
          <Tile
            label="Estimated cost"
            value={fmtUSD(t?.est_cost_usd)}
            subline={data?.unit_cost_usd ? `@ ${fmtUSD(data.unit_cost_usd)}/call` : ""}
            accent
          />
          <Tile
            label="Active accounts"
            value={t ? t.active_accounts.toLocaleString() : "—"}
            subline="touched ≥1 deep call"
          />
          <Tile
            label="Window"
            value={`${data?.window_days || windowDays} days`}
            subline={data?.today_utc ? `as of ${data.today_utc} UTC` : ""}
          />
        </section>

        {/* By surface */}
        <section className="bg-white border border-[var(--rule)] rounded-sm mb-8" data-testid="llm-spend-by-surface">
          <header className="px-5 py-3.5 border-b border-[var(--rule)] flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.7} />
            <h2 className="akki-serif text-[17px] text-[var(--ink)]">By surface</h2>
          </header>
          {loading && !data ? (
            <p className="px-5 py-10 text-center text-[12.5px] italic text-[var(--muted)]">Loading…</p>
          ) : (data?.by_surface || []).length === 0 ? (
            <p className="px-5 py-10 text-center text-[12.5px] italic text-[var(--muted)]">No deep-tier calls in this window.</p>
          ) : (
            <ul className="divide-y divide-[var(--rule)]">
              {data.by_surface.map((s) => {
                const maxCalls = Math.max(1, ...data.by_surface.map((x) => x.calls));
                const pctOfMax = Math.round((s.calls / maxCalls) * 100);
                const pctOfTotal = t?.calls ? Math.round((s.calls / t.calls) * 100) : 0;
                return (
                  <li
                    key={s.surface}
                    className="px-5 py-4 grid grid-cols-12 gap-4 items-center"
                    data-testid={`llm-spend-surface-${s.surface}`}
                  >
                    <div className="col-span-3">
                      <p className="akki-serif text-[15px] text-[var(--ink)]">
                        {SURFACE_LABEL[s.surface] || s.surface}
                      </p>
                      <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
                        {s.accounts} {s.accounts === 1 ? "user" : "users"} · cap {s.default_limit}/day
                      </p>
                    </div>
                    <div className="col-span-6">
                      <div className="h-2 bg-[var(--cream-deep)]/50 rounded-sm overflow-hidden">
                        <div
                          className="h-full bg-[var(--accent)] transition-all"
                          style={{ width: `${pctOfMax}%` }}
                        />
                      </div>
                      <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mt-1.5 tabular-nums">
                        {pctOfTotal}% of window
                      </p>
                    </div>
                    <div className="col-span-3 text-right">
                      <p className="akki-serif text-[18px] text-[var(--ink)] tabular-nums">
                        {s.calls.toLocaleString()}
                      </p>
                      <p className="text-[11px] text-[var(--accent)] tabular-nums">
                        {fmtUSD(s.est_cost_usd)}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        {/* By day sparkline */}
        {(data?.by_day || []).length > 0 && (
          <section className="bg-white border border-[var(--rule)] rounded-sm mb-8" data-testid="llm-spend-by-day">
            <header className="px-5 py-3.5 border-b border-[var(--rule)] flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.7} />
              <h2 className="akki-serif text-[17px] text-[var(--ink)]">By day</h2>
            </header>
            <div className="px-5 py-5 flex items-end gap-1.5 h-[140px]">
              {data.by_day.map((d) => {
                const h = Math.max(2, Math.round((d.calls / maxDayCalls) * 110));
                return (
                  <div
                    key={d.day}
                    className="flex-1 flex flex-col items-center justify-end group"
                    title={`${d.day} · ${d.calls} calls · ${fmtUSD(d.est_cost_usd)}`}
                  >
                    <div
                      className="w-full bg-[var(--accent)]/70 group-hover:bg-[var(--accent)] transition-colors rounded-t-sm"
                      style={{ height: `${h}px` }}
                    />
                  </div>
                );
              })}
            </div>
            <div className="px-5 pb-3 flex justify-between text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] tabular-nums">
              <span>{data.by_day[0]?.day}</span>
              <span>{data.by_day[data.by_day.length - 1]?.day}</span>
            </div>
          </section>
        )}

        {/* Deck quality panel — behaviour monitoring */}
        {deckQuality && deckQuality.outlines_drafted > 0 && (
          <section
            className="bg-white border border-[var(--rule)] rounded-sm mb-8"
            data-testid="llm-spend-deck-quality"
          >
            <header className="px-5 py-3.5 border-b border-[var(--rule)] flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.7} />
                <h2 className="akki-serif text-[17px] text-[var(--ink)]">Deck quality · behaviour</h2>
              </div>
              <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
                Are we burning Opus on weak prompts?
              </p>
            </header>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-0 divide-x divide-[var(--rule)]">
              <DeckMetric
                label="Avg quality"
                value={deckQuality.avg_quality_score != null ? `${deckQuality.avg_quality_score}/100` : "—"}
                accent={(deckQuality.avg_quality_score || 0) >= 70}
                hint={`${deckQuality.decks_generated} decks scored`}
              />
              <DeckMetric
                label="Outline → deck"
                value={deckQuality.outline_to_deck_ratio != null ? `${deckQuality.outline_to_deck_ratio}×` : "—"}
                hint={`${deckQuality.outlines_drafted} outlines, ${deckQuality.decks_generated} generated`}
              />
              <DeckMetric
                label="Satisfaction"
                value={deckQuality.satisfaction_pct != null ? `${deckQuality.satisfaction_pct}%` : "—"}
                hint={`${deckQuality.thumbs_up} 👍 · ${deckQuality.thumbs_down} 👎`}
              />
              <DeckMetric
                label="Insufficient ctx"
                value={`${deckQuality.insufficient_context_count}`}
                warn={deckQuality.insufficient_context_count > 2}
                hint={`partial ${deckQuality.partial_context_count} · regen rec ${deckQuality.quality_recommends_regen_count}`}
              />
            </div>
          </section>
        )}

        {/* Top accounts */}
        <section className="bg-white border border-[var(--rule)] rounded-sm" data-testid="llm-spend-by-account">
          <header className="px-5 py-3.5 border-b border-[var(--rule)] flex items-center gap-2">
            <Users className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.7} />
            <h2 className="akki-serif text-[17px] text-[var(--ink)]">Top accounts</h2>
          </header>
          {(data?.by_account_top || []).length === 0 ? (
            <p className="px-5 py-10 text-center text-[12.5px] italic text-[var(--muted)]">No accounts in window.</p>
          ) : (
            <table className="w-full text-[13.5px]">
              <thead>
                <tr className="text-left text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] border-b border-[var(--rule)]">
                  <th className="px-5 py-2.5 font-medium">Account</th>
                  <th className="px-5 py-2.5 font-medium">Top surface</th>
                  <th className="px-5 py-2.5 font-medium text-right">Calls</th>
                  <th className="px-5 py-2.5 font-medium text-right">Est. cost</th>
                </tr>
              </thead>
              <tbody>
                {data.by_account_top.map((a) => (
                  <tr
                    key={a.account_id}
                    className="border-b border-[var(--rule)]/60 last:border-0 hover:bg-[var(--cream-deep)]/20"
                    data-testid={`llm-spend-account-${a.account_id}`}
                  >
                    <td className="px-5 py-3">
                      <p className="text-[var(--ink)]">{a.name || a.email}</p>
                      <p className="text-[11px] text-[var(--muted)] font-mono">{a.email}</p>
                    </td>
                    <td className="px-5 py-3 text-[var(--deep)]">
                      {SURFACE_LABEL[a.top_surface] || a.top_surface || "—"}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-[var(--ink)]">
                      {a.calls.toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-[var(--accent)]">
                      {fmtUSD(a.est_cost_usd)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  );
}

function Tile({ label, value, subline, accent = false }) {
  return (
    <div
      className={`bg-white border rounded-sm px-5 py-4 ${accent ? "border-[var(--accent)]/30" : "border-[var(--rule)]"}`}
      data-testid={`llm-spend-tile-${label.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono">
        {label}
      </p>
      <p className={`akki-serif text-[26px] mt-1 ${accent ? "text-[var(--accent)]" : "text-[var(--ink)]"}`}>
        {value}
      </p>
      {subline && (
        <p className="text-[11px] text-[var(--muted)] mt-1">{subline}</p>
      )}
    </div>
  );
}

function DeckMetric({ label, value, hint, accent = false, warn = false }) {
  return (
    <div className="px-5 py-4" data-testid={`llm-spend-deck-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)]">{label}</p>
      <p className={`akki-serif text-[22px] mt-1 tabular-nums ${
        warn ? "text-amber-700" : accent ? "text-[var(--accent)]" : "text-[var(--ink)]"
      }`}>
        {value}
      </p>
      {hint && <p className="text-[11px] text-[var(--muted)] mt-0.5">{hint}</p>}
    </div>
  );
}
