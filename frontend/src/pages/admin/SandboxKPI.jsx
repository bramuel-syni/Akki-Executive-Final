/**
 * SandboxKPI — `/admin/sandbox-kpi`.
 *
 * Superadmin-only conversion dashboard for the Q5 objective loop.
 * Surfaces (a) overall delivery rates, (b) per-sector breakdown, and
 * (c) the most recent objectives + answers + free-text notes — exactly
 * the loop the user feedback doc described:
 *   "we use this to measure later whether AKKI delivered on it."
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
import {
  RefreshCw, Loader2, BarChart3, Sparkles, TrendingUp, AlertTriangle, Clock,
} from "lucide-react";

const ANSWER_TONE = {
  yes:     { label: "Delivered",   tone: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  partial: { label: "Partial",     tone: "text-amber-700 bg-amber-50 border-amber-200" },
  no:      { label: "Missed",      tone: "text-red-700 bg-red-50 border-red-200" },
  skipped: { label: "Skipped",     tone: "text-[var(--muted)] bg-[var(--cream)] border-[var(--rule)]" },
  pending: { label: "Pending",     tone: "text-slate-700 bg-slate-50 border-slate-200" },
};

const SECTOR_LABEL = {
  financial_services: "Financial services",
  saas: "SaaS / Tech",
  logistics: "Logistics",
  healthcare: "Healthcare",
  manufacturing: "Manufacturing",
  retail: "Retail",
  real_estate: "Real estate",
  other: "Other",
  unknown: "Unknown",
};

export default function SandboxKPI() {
  const { account, loading: authLoading } = useAuth();
  const [kpi, setKpi] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ sector: "all", answer: "all" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [k, i] = await Promise.all([
        api.get("/admin/sandbox/kpi"),
        api.get("/admin/sandbox/objectives", {
          params: {
            limit: 100,
            sector: filter.sector === "all" ? undefined : filter.sector,
            answer: filter.answer === "all" ? undefined : filter.answer,
          },
        }),
      ]);
      setKpi(k.data);
      setItems(i.data?.items || []);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  if (authLoading) return null;
  if (!account?.is_superadmin) return <Navigate to="/app" replace />;

  const t = kpi?.totals;

  return (
    <div className="min-h-screen bg-[var(--cream)]" data-testid="sandbox-kpi-page">
      <header className="px-8 py-6 border-b border-[var(--rule)] flex items-center justify-between">
        <div>
          <p className="akki-overline mb-1 flex items-center gap-2">
            <BarChart3 className="w-3 h-3 text-[var(--accent)]" /> Conversion KPI
          </p>
          <h1 className="akki-serif text-[26px] text-[var(--ink)] leading-tight">
            Sandbox objectives — what we promised, what we delivered.
          </h1>
        </div>
        <Button
          variant="outline"
          onClick={load}
          disabled={loading}
          className="border-[var(--rule)]"
          data-testid="sandbox-kpi-refresh"
        >
          {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
          Refresh
        </Button>
      </header>

      <main className="px-8 py-8 akki-w-medium space-y-8">
        {/* Top metrics — 4 numbers, editorial strip */}
        <section
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
          data-testid="sandbox-kpi-totals"
        >
          <Stat label="Captured objectives"  value={t?.with_objective ?? "—"} />
          <Stat label="Answers received"     value={t?.answered ?? "—"} sub={t ? `${t.answer_rate_pct}% answer rate` : null} />
          <Stat label="Delivered"            value={t?.yes ?? "—"} sub={t ? `${t.delivery_rate_pct}% delivery rate` : null} accent="emerald" />
          <Stat label="Missed or partial"    value={t ? (t.partial + t.no) : "—"} sub={t ? `${t.partial} partial · ${t.no} missed` : null} accent="red" />
        </section>

        {/* Per-sector */}
        <section data-testid="sandbox-kpi-by-sector">
          <p className="akki-overline mb-3 flex items-center gap-2">
            <TrendingUp className="w-3 h-3 text-[var(--accent)]" /> By sector
          </p>
          <div className="bg-white border border-[var(--rule)] rounded-md overflow-hidden">
            {(kpi?.by_sector || []).length === 0 ? (
              <p className="px-5 py-8 text-center text-[13px] text-[var(--muted)] italic">
                No objectives captured yet. Try the sandbox flow then come back.
              </p>
            ) : (
              <table className="w-full text-[13px]">
                <thead className="bg-[var(--cream-deep)]/50 text-[10.5px] uppercase tracking-wider text-[var(--muted)]">
                  <tr>
                    <th className="text-left px-5 py-2 font-normal">Sector</th>
                    <th className="text-right px-3 py-2 font-normal">Captured</th>
                    <th className="text-right px-3 py-2 font-normal">Delivered</th>
                    <th className="text-right px-3 py-2 font-normal">Partial</th>
                    <th className="text-right px-3 py-2 font-normal">Missed</th>
                    <th className="text-right px-3 py-2 font-normal">Skipped</th>
                    <th className="text-right px-5 py-2 font-normal">Delivery rate</th>
                  </tr>
                </thead>
                <tbody>
                  {kpi.by_sector.map((s) => (
                    <tr key={s.sector} className="border-t border-[var(--rule)]" data-testid={`sandbox-kpi-sector-${s.sector}`}>
                      <td className="px-5 py-3 text-[var(--ink)] akki-serif text-[14px]">
                        {SECTOR_LABEL[s.sector] || s.sector}
                      </td>
                      <td className="px-3 py-3 text-right">{s.with_objective}</td>
                      <td className="px-3 py-3 text-right text-emerald-700">{s.yes}</td>
                      <td className="px-3 py-3 text-right text-amber-700">{s.partial}</td>
                      <td className="px-3 py-3 text-right text-red-700">{s.no}</td>
                      <td className="px-3 py-3 text-right text-[var(--muted)]">{s.skipped}</td>
                      <td className="px-5 py-3 text-right">
                        <span className={`akki-serif text-[15px] ${s.delivery_rate_pct >= 60 ? "text-emerald-700" : s.delivery_rate_pct >= 30 ? "text-amber-700" : "text-red-700"}`}>
                          {s.delivery_rate_pct}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Most-recent objectives */}
        <section data-testid="sandbox-kpi-objectives">
          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
            <p className="akki-overline flex items-center gap-2">
              <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Captured objectives
            </p>
            <div className="flex items-center gap-2">
              <Select value={filter.sector} onValueChange={(v) => setFilter((f) => ({ ...f, sector: v }))}>
                <SelectTrigger className="h-9 w-[180px] bg-white border-[var(--rule)] text-[12.5px] text-[var(--ink)]" data-testid="sandbox-kpi-sector-filter">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All sectors</SelectItem>
                  {Object.entries(SECTOR_LABEL).map(([k, v]) => (
                    <SelectItem key={k} value={k}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={filter.answer} onValueChange={(v) => setFilter((f) => ({ ...f, answer: v }))}>
                <SelectTrigger className="h-9 w-[150px] bg-white border-[var(--rule)] text-[12.5px] text-[var(--ink)]" data-testid="sandbox-kpi-answer-filter">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All answers</SelectItem>
                  <SelectItem value="yes">Delivered</SelectItem>
                  <SelectItem value="partial">Partial</SelectItem>
                  <SelectItem value="no">Missed</SelectItem>
                  <SelectItem value="skipped">Skipped</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="bg-white border border-[var(--rule)] rounded-md overflow-hidden">
            {items.length === 0 ? (
              <p className="px-5 py-8 text-center text-[13px] text-[var(--muted)] italic">
                Nothing matches that filter.
              </p>
            ) : (
              items.map((it) => {
                const tone = ANSWER_TONE[it.answer] || ANSWER_TONE.pending;
                return (
                  <div
                    key={it.context_id}
                    className="border-b border-[var(--rule)] last:border-b-0 px-5 py-4"
                    data-testid={`sandbox-kpi-row-${it.context_id}`}
                  >
                    <div className="flex items-center justify-between gap-4 mb-1.5 flex-wrap">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="akki-serif text-[15px] text-[var(--ink)] truncate">
                          {it.company_name || it.context_id}
                        </span>
                        <span className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] font-mono">
                          {SECTOR_LABEL[it.sector] || it.sector}
                        </span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`text-[10.5px] uppercase tracking-wider px-2 py-0.5 rounded-sm border ${tone.tone}`}>
                          {tone.label}
                        </span>
                        {it.generated_at && (
                          <span className="text-[10.5px] text-[var(--muted)] inline-flex items-center gap-1">
                            <Clock className="w-3 h-3" /> {new Date(it.generated_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="akki-serif italic text-[13px] text-[var(--deep)] leading-relaxed border-l-2 border-[var(--rule)] pl-3">
                      “{it.objective}”
                    </p>
                    {it.note && (
                      <p className="text-[12px] text-[var(--muted)] mt-2 leading-relaxed">
                        <span className="text-[10px] uppercase tracking-wider mr-1.5">User note:</span>
                        {it.note}
                      </p>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </section>

        {(t?.with_objective ?? 0) === 0 && (
          <p className="text-[12px] text-[var(--muted)] italic flex items-center gap-2">
            <AlertTriangle className="w-3 h-3" /> Sandbox objectives only start populating once users complete the Q5 step.
            The 24-hour follow-up answers (yes/partial/no) won't appear until users have spent ≥24h with their context.
          </p>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, sub, accent }) {
  const accentClass =
    accent === "emerald" ? "text-emerald-700" :
    accent === "red"     ? "text-red-700" :
    "text-[var(--ink)]";
  return (
    <div className="bg-white border border-[var(--rule)] rounded-md p-4">
      <p className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] mb-2">{label}</p>
      <p className={`akki-serif text-[28px] leading-none ${accentClass}`}>{value}</p>
      {sub && <p className="text-[11px] text-[var(--muted)] mt-1.5 italic">{sub}</p>}
    </div>
  );
}
