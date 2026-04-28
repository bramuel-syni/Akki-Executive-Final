/**
 * /admin — index of all admin/superadmin surfaces. The "control room"
 * landing page that pulls a quick at-a-glance signal from each surface so
 * the operator knows where to look first.
 */
import React, { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Activity, Sparkles, BarChart3, Target, ArrowRight, ShieldCheck } from "lucide-react";

export default function AdminIndex() {
  const { account, loading } = useAuth();
  const [signals, setSignals] = useState({
    health: null, llm: null, deck: null, sandbox: null, signalKpi: null,
  });

  useEffect(() => {
    if (!account?.is_superadmin) return;
    (async () => {
      const safe = (p) => p.then((r) => r.data).catch(() => null);
      const [health, llm, deck, sandbox, signalKpi] = await Promise.all([
        safe(api.get("/admin/health")),
        safe(api.get("/admin/llm/spend?days=7")),
        safe(api.get("/admin/llm/decks/quality?days=30")),
        safe(api.get("/admin/sandbox/kpi")),
        safe(api.get("/admin/signals/kpi")),
      ]);
      setSignals({ health, llm, deck, sandbox, signalKpi });
    })();
  }, [account]);

  if (loading) return null;
  if (!account?.is_superadmin) return <Navigate to="/app" replace />;

  const tiles = [
    {
      to: "/admin/health",
      icon: ShieldCheck,
      title: "Service health",
      desc: "MongoDB · LLM key · Stripe · Resend · Cron.",
      pill: signals.health
        ? { tone: signals.health.overall === "pass" ? "ok" :
                  signals.health.overall === "warn" ? "warn" : "bad",
            text: signals.health.overall.toUpperCase() }
        : null,
      testid: "admin-tile-health",
    },
    {
      to: "/admin/llm-spend",
      icon: Sparkles,
      title: "LLM spend",
      desc: "Deep-tier (Opus) calls, cost, top accounts.",
      pill: signals.llm
        ? { tone: signals.llm.totals.calls > 5000 ? "warn" : "ok",
            text: `$${signals.llm.totals.est_cost_usd.toFixed(2)} · 7d` }
        : null,
      testid: "admin-tile-llm",
    },
    {
      to: "/admin/llm-spend?panel=decks",
      icon: BarChart3,
      title: "Deck quality",
      desc: "Outline approval rate, quality score, satisfaction.",
      pill: signals.deck
        ? {
            tone: (signals.deck.avg_quality_score || 0) >= 70 ? "ok" :
                  (signals.deck.avg_quality_score || 0) >= 55 ? "warn" : "bad",
            text: signals.deck.decks_generated
              ? `q ${signals.deck.avg_quality_score ?? "—"} · ${signals.deck.decks_generated} decks`
              : "no decks yet",
          }
        : null,
      testid: "admin-tile-deck-quality",
    },
    {
      to: "/admin/sandbox-kpi",
      icon: Target,
      title: "Sandbox · objectives",
      desc: "Captured · delivered · partial · missed.",
      pill: signals.sandbox
        ? { tone: "ok",
            text: `${signals.sandbox.delivered ?? 0}/${signals.sandbox.captured ?? 0}` }
        : null,
      testid: "admin-tile-sandbox",
    },
    {
      to: "/admin/signal-kpi",
      icon: Activity,
      title: "Signals · Act-on KPI",
      desc: "Acted vs ignored, by sector and weekday.",
      pill: signals.signalKpi
        ? { tone: "ok",
            text: `${signals.signalKpi.totals?.acted ?? 0} acts` }
        : null,
      testid: "admin-tile-signals",
    },
  ];

  return (
    <div className="min-h-screen bg-[var(--cream)] py-12 px-6" data-testid="admin-index">
      <div className="max-w-4xl mx-auto">
        <header className="mb-10">
          <p className="akki-overline mb-2">Control room · superadmin</p>
          <h1 className="akki-greeting mb-2">The operator's home.</h1>
          <p className="akki-meta max-w-xl">
            Five surfaces. Each runs its own checks; together they show whether
            AKKI is behaving — or burning budget.
          </p>
        </header>
        <div className="grid sm:grid-cols-2 gap-5" data-testid="admin-tiles">
          {tiles.map((t) => (
            <Link
              key={t.to}
              to={t.to}
              className="group bg-white border border-[var(--rule)] rounded-sm p-5 hover:border-[var(--accent)] transition-colors flex flex-col"
              data-testid={t.testid}
            >
              <div className="flex items-start justify-between mb-3">
                <t.icon className="w-5 h-5 text-[var(--accent)]" strokeWidth={1.7} />
                {t.pill && (
                  <span
                    className={`text-[10px] uppercase tracking-[0.14em] px-2 py-0.5 rounded-sm ${
                      t.pill.tone === "ok" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" :
                      t.pill.tone === "warn" ? "bg-amber-50 text-amber-700 border border-amber-200" :
                      "bg-rose-50 text-rose-700 border border-rose-200"
                    }`}
                  >
                    {t.pill.text}
                  </span>
                )}
              </div>
              <h3 className="akki-serif text-[18px] text-[var(--ink)] mb-1">{t.title}</h3>
              <p className="text-[12.5px] text-[var(--muted)] leading-snug flex-1">{t.desc}</p>
              <p className="mt-3 text-[11px] uppercase tracking-[0.16em] text-[var(--accent)] flex items-center gap-1 group-hover:gap-2 transition-all">
                Open <ArrowRight className="w-3 h-3" />
              </p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
