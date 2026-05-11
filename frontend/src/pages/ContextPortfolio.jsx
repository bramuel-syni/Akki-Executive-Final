import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Landmark, Briefcase, Plus, CheckCircle2, Layers, ArrowRight,
  Sparkles, FileText, ScrollText, Flame,
} from "lucide-react";

const TYPE_LABEL = {
  ned_personal: "NED · Personal",
  ned_sponsored: "NED · Sponsored",
  executive_personal: "Executive · Personal",
  executive_enterprise: "Executive · Enterprise",
};

function roleIcon(c) {
  if (c.type?.startsWith("ned")) return Landmark;
  return Briefcase;
}

function ContextCard({ c, active, metrics, state, onOpen }) {
  const Icon = roleIcon(c);
  const sponsored =
    c.provisioning === "sponsored" ||
    c.type === "ned_sponsored" ||
    c.type === "executive_enterprise";
  // HOME sprint — derive a couple of state badges.
  const cycle = state?.cycle;
  const cycleLabel = cycle && cycle.status !== "no_cycle"
    ? `Cycle · ${cycle.act_label}`
    : null;
  const goalsAtRisk = state?.goals_at_risk_count || 0;
  const pendingFollowups = state?.pending_followups_count || 0;
  const unreadSignals = state?.unread_signals_count || 0;

  return (
    <button
      type="button"
      onClick={onOpen}
      className={`relative text-left bg-white border rounded-lg p-6 transition-all hover:shadow-sm akki-fade-up group ${
        active
          ? "border-[var(--accent)]"
          : "border-[var(--rule)] hover:border-[var(--ink)]/30"
      }`}
      data-testid={`portfolio-card-${c.id}`}
    >
      <div
        className={`absolute left-0 top-0 bottom-0 w-[3px] rounded-l-lg transition-opacity ${
          active ? "bg-[var(--accent)] opacity-100" : "bg-[var(--accent)]/0 group-hover:opacity-60"
        }`}
      />

      {/* Top row — type icon + sponsored chip + active check */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-[var(--cream-deep)] rounded-md flex items-center justify-center">
            <Icon className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">
              {TYPE_LABEL[c.type] || c.type}
            </p>
            {c.my_sub_role === "admin" && (
              <p className="text-[10px] uppercase tracking-wider text-[var(--accent)] font-medium mt-0.5">
                Admin
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {sponsored && (
            <span className="text-[9px] uppercase tracking-[0.2em] text-[var(--accent)] bg-[var(--accent-soft)] px-1.5 py-0.5 rounded">
              Sponsored
            </span>
          )}
          {active && <CheckCircle2 className="w-4 h-4 text-[var(--accent)]" />}
        </div>
      </div>

      {/* Name */}
      <h3 className="akki-serif text-[22px] leading-snug text-[var(--ink)] mb-2 font-normal">
        {c.name}
      </h3>
      <p className="text-[12.5px] text-[var(--muted)] mb-5">
        {c.industry ? `${c.industry}` : "—"}
        {c.jurisdiction ? ` · ${c.jurisdiction}` : ""}
        {c.sector ? ` · ${c.sector}` : ""}
      </p>

      {/* Metrics row */}
      <div className="grid grid-cols-3 gap-3 pt-4 border-t border-[var(--rule)]">
        <Metric icon={Sparkles} label="Signals" value={metrics?.signals ?? "—"} />
        <Metric icon={ScrollText} label="Briefings" value={metrics?.briefings ?? "—"} />
        <Metric icon={FileText} label="Docs" value={metrics?.documents ?? "—"} />
      </div>

      {/* HOME sprint — state badges row (cycle / goals at risk / followups / signals). */}
      {(cycleLabel || goalsAtRisk > 0 || pendingFollowups > 0 || unreadSignals > 0) && (
        <div className="flex flex-wrap gap-2 mt-3" data-testid={`portfolio-state-${c.id}`}>
          {cycleLabel && (
            <span
              className="text-[10px] uppercase tracking-[0.14em] text-[var(--graphite)] border border-[var(--graphite-light)] px-2 py-0.5 rounded-sm"
              data-testid="portfolio-badge-cycle"
            >
              {cycleLabel}
            </span>
          )}
          {goalsAtRisk > 0 && (
            <span
              className="text-[10px] uppercase tracking-[0.14em] text-[var(--oxblood)] bg-[rgba(122,46,46,0.06)] px-2 py-0.5 rounded-sm"
              data-testid="portfolio-badge-risk"
            >
              {goalsAtRisk} goal{goalsAtRisk === 1 ? "" : "s"} at risk
            </span>
          )}
          {pendingFollowups > 0 && (
            <span
              className="text-[10px] uppercase tracking-[0.14em] text-[var(--oxblood)] bg-[rgba(122,46,46,0.06)] px-2 py-0.5 rounded-sm"
              data-testid="portfolio-badge-followups"
            >
              {pendingFollowups} follow-up{pendingFollowups === 1 ? "" : "s"}
            </span>
          )}
          {unreadSignals > 0 && (
            <span
              className="text-[10px] uppercase tracking-[0.14em] text-[var(--graphite)] border border-[var(--graphite-light)] px-2 py-0.5 rounded-sm"
              data-testid="portfolio-badge-signals"
            >
              {unreadSignals} signal{unreadSignals === 1 ? "" : "s"}
            </span>
          )}
        </div>
      )}

      {/* Gesture */}
      <div className="flex items-center justify-between mt-4 pt-3 border-t border-[var(--rule)]/50">
        <span className="text-[11px] text-[var(--muted)]">
          {active ? "Current company" : "Switch to this company"}
        </span>
        <span className="akki-gesture text-[13px]">
          Open <ArrowRight className="w-3.5 h-3.5" />
        </span>
      </div>
    </button>
  );
}

function Metric({ icon: Icon, label, value }) {
  return (
    <div>
      <div className="flex items-center gap-1 mb-0.5">
        <Icon className="w-3 h-3 text-[var(--muted)]" strokeWidth={1.8} />
        <span className="text-[10px] uppercase tracking-wider text-[var(--muted)]">{label}</span>
      </div>
      <p className="text-[15px] font-medium text-[var(--ink)]">{value}</p>
    </div>
  );
}

export default function ContextPortfolio() {
  const { contexts, activeContextId, switchContext, account } = useAuth();
  const navigate = useNavigate();
  const [metricsMap, setMetricsMap] = useState({});
  const [stateMap, setStateMap] = useState({});
  const [loading, setLoading] = useState(true);

  // HOME sprint — fetch portfolio state once per mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(`/me/portfolio`);
        if (cancelled) return;
        const next = {};
        (data?.items || []).forEach((row) => { next[row.context_id] = row.state; });
        setStateMap(next);
      } catch {
        if (!cancelled) setStateMap({});
      }
    })();
    return () => { cancelled = true; };
  }, [contexts.length]); // refresh when membership set changes

  // Fetch signals/briefings/documents counts per context in parallel.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!contexts.length) { setLoading(false); return; }
      setLoading(true);
      const results = await Promise.all(
        contexts.map(async (c) => {
          try {
            const [s, b, d] = await Promise.all([
              api.get(`/contexts/${c.id}/signals`).catch(() => ({ data: [] })),
              api.get(`/contexts/${c.id}/briefings`).catch(() => ({ data: [] })),
              api.get(`/contexts/${c.id}/documents`).catch(() => ({ data: [] })),
            ]);
            const sigs = s.data || [];
            // "Boards to watch" heuristic: count fresh (<14d) high-confidence
            // risks + gaps — the signals a NED actually cares about right now.
            const FRESH_MS = 14 * 86400 * 1000;
            const cutoff = Date.now() - FRESH_MS;
            const watchCount = sigs.filter((sig) =>
              (sig.type === "risk" || sig.type === "gap") &&
              sig.confidence === "high" &&
              new Date(sig.created_at).getTime() >= cutoff
            ).length;
            return [c.id, {
              signals: sigs.length,
              briefings: (b.data || []).length,
              documents: (d.data || []).length,
              watchCount,
            }];
          } catch {
            return [c.id, { signals: 0, briefings: 0, documents: 0 }];
          }
        })
      );
      if (cancelled) return;
      setMetricsMap(Object.fromEntries(results));
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, [contexts]);

  const grouped = useMemo(() => {
    const ned = contexts.filter((c) => c.type?.startsWith("ned"));
    const exec = contexts.filter((c) => c.type?.startsWith("executive"));
    return { ned, exec };
  }, [contexts]);

  const totalSignals = Object.values(metricsMap).reduce((sum, m) => sum + (m?.signals || 0), 0);
  const totalBriefings = Object.values(metricsMap).reduce((sum, m) => sum + (m?.briefings || 0), 0);
  const totalDocs = Object.values(metricsMap).reduce((sum, m) => sum + (m?.documents || 0), 0);

  // Derive "boards to watch" — contexts with the most fresh high-conf risks/gaps.
  const boardsToWatch = useMemo(() => {
    return contexts
      .map((c) => ({ ctx: c, watchCount: metricsMap[c.id]?.watchCount || 0 }))
      .filter((x) => x.watchCount > 0)
      .sort((a, b) => b.watchCount - a.watchCount)
      .slice(0, 2);
  }, [contexts, metricsMap]);

  const openContext = (cid) => {
    switchContext(cid);
    navigate("/app");
  };

  const firstName = (account?.name || "there").split(" ")[0];

  return (
    <AppShell>
      <div className="h-[calc(100vh-4rem)] akki-w-medium px-8 overflow-hidden flex flex-col">
        {/* Header */}
        <div className="shrink-0 pt-10 pb-6 akki-fade-up">
          <p className="akki-overline mb-2 flex items-center gap-2">
            <Layers className="w-3 h-3 text-[var(--accent)]" /> Portfolio
          </p>
          <div className="flex items-end justify-between gap-6 flex-wrap">
            <div>
              <h1 className="akki-greeting">Your boards & operating companies, {firstName}.</h1>
              <p className="akki-meta mt-2 max-w-2xl">
                Every company is isolated. Data, signals, members and briefings stay within each board. Open one to work in it.
              </p>
            </div>
            <Button
              onClick={() => navigate("/app/contexts/new")}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-10 px-4 font-medium shrink-0"
              data-testid="portfolio-add-context-btn"
            >
              <Plus className="w-4 h-4 mr-1.5" /> Add company
            </Button>
          </div>

          {/* Portfolio summary strip */}
          <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
            <SummaryTile label="Companies" value={contexts.length} />
            <SummaryTile label="Signals" value={loading ? "…" : totalSignals} />
            <SummaryTile label="Briefings" value={loading ? "…" : totalBriefings} />
            <SummaryTile label="Documents" value={loading ? "…" : totalDocs} />
          </div>
        </div>

        {/* Scrolling body */}
        <div className="flex-1 min-h-0 overflow-y-auto pr-2 -mr-2 pb-8 space-y-10" data-testid="portfolio-scroll">
          {/* Boards to watch this week — opinionated triage banner */}
          {!loading && boardsToWatch.length > 0 && (
            <section
              className="bg-[var(--accent-soft)]/70 border border-[var(--accent)]/25 rounded-md p-5 akki-fade-up"
              data-testid="boards-to-watch"
            >
              <div className="flex items-center gap-2 mb-3">
                <Flame className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
                <p className="akki-overline">Boards to watch this week</p>
                <span className="text-[11px] text-[var(--muted)] ml-auto">
                  Fresh high-confidence risks & gaps · last 14 days
                </span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {boardsToWatch.map(({ ctx, watchCount }) => (
                  <button
                    key={ctx.id}
                    onClick={() => openContext(ctx.id)}
                    className="text-left bg-white border border-[var(--rule)] rounded-md p-4 hover:border-[var(--accent)]/60 transition-colors group"
                    data-testid={`watch-card-${ctx.id}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="akki-serif text-[18px] text-[var(--ink)] leading-snug mb-1">{ctx.name}</p>
                        <p className="text-[12px] text-[var(--muted)]">
                          {ctx.industry ? `${ctx.industry} · ` : ""}{watchCount} fresh signal{watchCount > 1 ? "s" : ""} for your attention
                        </p>
                      </div>
                      <div className="w-10 h-10 bg-[var(--accent)] text-white rounded-sm flex items-center justify-center shrink-0">
                        <span className="akki-serif text-[18px]">{watchCount}</span>
                      </div>
                    </div>
                    <p className="text-[12px] text-[var(--accent)] mt-3 flex items-center gap-1 opacity-80 group-hover:opacity-100">
                      Open this board <ArrowRight className="w-3 h-3" />
                    </p>
                  </button>
                ))}
              </div>
            </section>
          )}

          {grouped.ned.length > 0 && (
            <section data-testid="portfolio-section-ned">
              <div className="flex items-center gap-2 mb-4">
                <Landmark className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
                <p className="akki-overline">NED boards · {grouped.ned.length}</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                {grouped.ned.map((c) => (
                  <ContextCard
                    key={c.id}
                    c={c}
                    active={c.id === activeContextId}
                    metrics={metricsMap[c.id]} state={stateMap[c.id]}
                    onOpen={() => openContext(c.id)}
                  />
                ))}
              </div>
            </section>
          )}

          {grouped.exec.length > 0 && (
            <section data-testid="portfolio-section-executive">
              <div className="flex items-center gap-2 mb-4">
                <Briefcase className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
                <p className="akki-overline">Executive companies · {grouped.exec.length}</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                {grouped.exec.map((c) => (
                  <ContextCard
                    key={c.id}
                    c={c}
                    active={c.id === activeContextId}
                    metrics={metricsMap[c.id]} state={stateMap[c.id]}
                    onOpen={() => openContext(c.id)}
                  />
                ))}
              </div>
            </section>
          )}

          {contexts.length === 0 && (
            <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-12 text-center">
              <Layers className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
              <p className="akki-lead mb-2">Your portfolio is empty.</p>
              <p className="text-[13px] text-[var(--muted)] mb-5 max-w-md mx-auto">
                Add your first NED board or executive company to start surfacing signals.
              </p>
              <Button
                onClick={() => navigate("/app/contexts/new")}
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-10 px-5 font-medium"
                data-testid="portfolio-empty-add-btn"
              >
                <Plus className="w-4 h-4 mr-1.5" /> Add your first company
              </Button>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}

function SummaryTile({ label, value }) {
  return (
    <div className="bg-white border border-[var(--rule)] rounded-md px-4 py-3">
      <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] mb-1">{label}</p>
      <p className="akki-serif text-[24px] font-normal text-[var(--ink)] leading-none">{value}</p>
    </div>
  );
}
