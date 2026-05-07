/**
 * SignalKPI — `/admin/signal-kpi`.
 *
 * Superadmin Act-on heatmap: which recommendation labels get picked, by
 * bucket. Companion to /admin/sandbox-kpi. Helps us read which next-steps
 * actually feel actionable to executives vs. which sit unloved in the
 * dropdown.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  RefreshCw, Loader2, Activity, Users, Sparkles, Clock, Zap,
} from "lucide-react";

const BUCKET_TONE = {
  risk:        { label: "Risk",        cls: "text-red-700 bg-red-50 border-red-200" },
  opportunity: { label: "Opportunity", cls: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  gap:         { label: "Gap",         cls: "text-amber-700 bg-amber-50 border-amber-200" },
  neutral:     { label: "Neutral",     cls: "text-slate-700 bg-slate-50 border-slate-200" },
};

export default function SignalKPI() {
  const { account, loading: authLoading } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/admin/signals/action-heatmap");
      setData(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (authLoading) return null;
  if (!account?.is_superadmin) return <Navigate to="/app" replace />;

  const t = data?.totals;
  const maxPicks = Math.max(
    1,
    ...(data?.by_bucket || []).flatMap((b) =>
      (b.recommendations || []).map((r) => r.picks)),
  );

  return (
    <div className="min-h-screen bg-[var(--cream)]" data-testid="signal-kpi-page">
      <header className="px-8 py-6 border-b border-[var(--rule)] flex items-center justify-between">
        <div>
          <p className="akki-overline mb-1 flex items-center gap-2">
            <Activity className="w-3 h-3 text-[var(--accent)]" /> Act-on heatmap
          </p>
          <h1 className="akki-serif text-[26px] text-[var(--ink)] leading-tight">
            Which next-steps do executives actually pick?
          </h1>
        </div>
        <Button
          variant="outline"
          onClick={load}
          disabled={loading}
          className="border-[var(--rule)]"
          data-testid="signal-kpi-refresh"
        >
          {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
          Refresh
        </Button>
      </header>

      <main className="px-8 py-8 akki-w-medium space-y-8">
        {/* Top metrics */}
        <section className="grid grid-cols-2 md:grid-cols-3 gap-4" data-testid="signal-kpi-totals">
          <Stat label="Total acted" value={t?.acted ?? "—"} icon={Zap} />
          <Stat label="Total shared" value={t?.shared ?? "—"} icon={Users} />
          <Stat label="Unique share recipients" value={t?.share_recipients ?? "—"} icon={Sparkles} />
        </section>

        {/* Heatmap by bucket */}
        <section data-testid="signal-kpi-by-bucket">
          <p className="akki-overline mb-3 flex items-center gap-2">
            <Activity className="w-3 h-3 text-[var(--accent)]" /> By signal bucket
          </p>
          {(data?.by_bucket || []).length === 0 ? (
            <p className="bg-white border border-[var(--rule)] rounded-md px-5 py-8 text-center text-[13px] text-[var(--muted)] italic">
              No actions logged yet. Once executives pick recommendations from the Signals dropdown, the heatmap fills in.
            </p>
          ) : (
            <div className="space-y-4">
              {data.by_bucket.map((b) => {
                const tone = BUCKET_TONE[b.bucket] || BUCKET_TONE.neutral;
                return (
                  <div
                    key={b.bucket}
                    className="bg-white border border-[var(--rule)] rounded-md p-5"
                    data-testid={`signal-kpi-bucket-${b.bucket}`}
                  >
                    <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                      <span className={`text-[10.5px] uppercase tracking-[0.2em] px-2 py-1 rounded-sm border ${tone.cls}`}>
                        {tone.label}
                      </span>
                      <p className="text-[12px] text-[var(--muted)]">
                        <strong className="text-[var(--ink)]">{b.acted}</strong> acted
                        <span className="mx-2 text-[var(--muted)]/40">·</span>
                        <strong className="text-[var(--ink)]">{b.shared}</strong> shared
                      </p>
                    </div>
                    <div className="space-y-2">
                      {(b.recommendations || []).map((r, idx) => {
                        const widthPct = Math.round((r.picks / maxPicks) * 100);
                        return (
                          <div
                            key={r.label + idx}
                            className="flex items-center gap-3"
                            data-testid={`signal-kpi-rec-${b.bucket}-${idx}`}
                          >
                            <p className="akki-serif text-[14px] text-[var(--ink)] flex-1 min-w-0 truncate" title={r.label}>
                              {r.label}
                            </p>
                            <div className="w-[200px] h-2 rounded-sm bg-[var(--cream-deep)] overflow-hidden shrink-0">
                              <div
                                className="h-full bg-[var(--accent)]"
                                style={{ width: `${widthPct}%` }}
                              />
                            </div>
                            <span className="akki-serif text-[15px] text-[var(--ink)] w-8 text-right shrink-0">
                              {r.picks}
                            </span>
                          </div>
                        );
                      })}
                      {(b.recommendations || []).length === 0 && (
                        <p className="text-[12px] text-[var(--muted)] italic">
                          No 'acted' actions in this bucket — only shares.
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Recent timeline */}
        {(data?.recent_actions || []).length > 0 && (
          <section data-testid="signal-kpi-recent">
            <p className="akki-overline mb-3 flex items-center gap-2">
              <Clock className="w-3 h-3 text-[var(--accent)]" /> Recent actions
            </p>
            <div className="bg-white border border-[var(--rule)] rounded-md overflow-hidden">
              {data.recent_actions.map((r) => {
                const tone = BUCKET_TONE[r.bucket] || BUCKET_TONE.neutral;
                return (
                  <div
                    key={r.id}
                    className="border-b border-[var(--rule)] last:border-b-0 px-5 py-3 flex items-start gap-3"
                    data-testid={`signal-kpi-action-${r.id}`}
                  >
                    <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-sm border shrink-0 ${tone.cls}`}>
                      {tone.label}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] text-[var(--ink)] truncate akki-serif">
                        {r.signal_headline || r.signal_id}
                      </p>
                      <p className="text-[11.5px] text-[var(--muted)] mt-0.5">
                        {r.action_type === "acted"
                          ? <><Zap className="w-3 h-3 inline mr-1" /> {r.recommendation_label || "Custom action"}</>
                          : <><Users className="w-3 h-3 inline mr-1" /> Shared with {r.recipients_count} recipient{r.recipients_count === 1 ? "" : "s"}</>
                        }
                      </p>
                    </div>
                    <p className="text-[10.5px] text-[var(--muted)] shrink-0 whitespace-nowrap">
                      {r.created_at ? new Date(r.created_at).toLocaleDateString() : ""}
                    </p>
                  </div>
                );
              })}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

function Stat({ label, value, icon: Icon }) {
  return (
    <div className="bg-white border border-[var(--rule)] rounded-md p-4">
      <p className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] mb-2 inline-flex items-center gap-1.5">
        {Icon && <Icon className="w-3 h-3 text-[var(--accent)]" />}
        {label}
      </p>
      <p className="akki-serif text-[28px] leading-none text-[var(--ink)]">{value}</p>
    </div>
  );
}
