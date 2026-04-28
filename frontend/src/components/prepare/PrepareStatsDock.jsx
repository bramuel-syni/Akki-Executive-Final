/**
 * PrepareStatsDock — the "uplift" stat strip the user asked us to bring
 * back to the top of /app/prepare. Three editorial cards, each with a
 * progress bar, that communicate the executive's preparation posture
 * for the active context at a glance:
 *
 *   1. Brief coverage  — % of saved briefs in the last 30 days vs target (8/mo)
 *   2. Signal pulse    — recent signal count vs the rolling 14-day baseline
 *   3. Briefing rhythm — % of briefings opened/read out of those generated
 *
 * Everything is read-only and inferred from existing collections — no
 * new endpoint. The progress bars use a calm two-stop oxblood/cream
 * fill, no gradients, no animation jitter.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { ScrollText, Activity, BookOpen } from "lucide-react";

function ProgressBar({ pct, tone = "accent" }) {
  const clamped = Math.max(0, Math.min(100, pct || 0));
  const fill =
    tone === "amber" ? "bg-amber-500" :
    tone === "green" ? "bg-emerald-600" :
    "bg-[var(--accent)]";
  return (
    <div className="h-1.5 bg-[var(--cream-deep)] rounded-full overflow-hidden">
      <div
        className={`h-full ${fill} transition-[width] duration-700`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

export default function PrepareStatsDock({ contextId }) {
  const [data, setData] = useState({ briefs: [], signals: [], briefings: [] });
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    if (!contextId) return;
    try {
      const [bf, sg, br] = await Promise.all([
        api.get(`/contexts/${contextId}/briefs?limit=200`).catch(() => ({ data: { items: [] } })),
        api.get(`/contexts/${contextId}/signals`).catch(() => ({ data: [] })),
        api.get(`/contexts/${contextId}/briefings`).catch(() => ({ data: { briefings: [] } })),
      ]);
      setData({
        briefs: bf.data?.items || [],
        signals: Array.isArray(sg.data) ? sg.data : (sg.data?.signals || []),
        briefings: Array.isArray(br.data) ? br.data : (br.data?.briefings || []),
      });
    } catch { /* swallow — render with zeros */ }
    finally { setLoaded(true); }
  }, [contextId]);
  useEffect(() => { load(); }, [load]);

  const cards = useMemo(() => {
    const now = Date.now();
    const ms30 = 30 * 24 * 3600 * 1000;
    const ms14 = 14 * 24 * 3600 * 1000;
    const ms7 = 7 * 24 * 3600 * 1000;

    // Brief coverage — saved briefs in last 30 days vs target of 8.
    const briefs30 = data.briefs.filter(
      (b) => b.created_at && now - new Date(b.created_at).getTime() <= ms30
    ).length;
    const briefTarget = 8;
    const briefPct = Math.round((briefs30 / briefTarget) * 100);

    // Signal pulse — last 7 days vs rolling 14-day baseline.
    const signalsLast7 = data.signals.filter((s) => {
      const t = s.created_at || s.updated_at;
      return t && now - new Date(t).getTime() <= ms7;
    }).length;
    const signalsLast14 = data.signals.filter((s) => {
      const t = s.created_at || s.updated_at;
      return t && now - new Date(t).getTime() <= ms14;
    }).length;
    const signalBaseline = Math.max(1, signalsLast14 / 2); // weekly baseline
    const pulsePct = Math.round((signalsLast7 / signalBaseline) * 100);

    // Briefing rhythm — % read out of generated.
    const briefingsTotal = data.briefings.length;
    const briefingsRead = data.briefings.filter((b) => b.read_at || b.read).length;
    const rhythmPct = briefingsTotal === 0 ? 0 : Math.round((briefingsRead * 100) / briefingsTotal);

    return [
      {
        key: "brief-coverage",
        kicker: "Brief coverage",
        icon: BookOpen,
        hero: briefs30,
        heroSuffix: `of ${briefTarget}`,
        sub: "saved in the last 30 days",
        pct: briefPct,
        tone: briefPct >= 80 ? "green" : briefPct >= 40 ? "accent" : "amber",
      },
      {
        key: "signal-pulse",
        kicker: "Signal pulse",
        icon: Activity,
        hero: signalsLast7,
        heroSuffix: "this week",
        sub: signalsLast14
          ? `vs ${(signalsLast14 / 2).toFixed(1)} avg the prior fortnight`
          : "no baseline yet — generate a few to populate",
        pct: pulsePct,
        tone: pulsePct >= 100 ? "green" : "accent",
      },
      {
        key: "briefing-rhythm",
        kicker: "Briefing rhythm",
        icon: ScrollText,
        hero: briefingsRead,
        heroSuffix: `of ${briefingsTotal}`,
        sub: briefingsTotal === 0
          ? "no briefings generated yet"
          : "briefings opened",
        pct: rhythmPct,
        tone: rhythmPct >= 70 ? "green" : rhythmPct >= 40 ? "accent" : "amber",
      },
    ];
  }, [data]);

  return (
    <section
      className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-3"
      data-testid="prepare-stats-dock"
    >
      {cards.map((c) => {
        const Icon = c.icon;
        return (
          <div
            key={c.key}
            className="bg-white border border-[var(--rule)] rounded-md p-4"
            data-testid={`prepare-stat-${c.key}`}
          >
            <div className="flex items-start justify-between mb-3">
              <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono">
                {c.kicker}
              </p>
              <Icon className="w-3.5 h-3.5 text-[var(--muted)]" strokeWidth={1.6} />
            </div>
            <p className="akki-serif text-[26px] leading-none text-[var(--ink)] tabular-nums mb-1">
              {loaded ? c.hero : "—"}
              {c.heroSuffix && (
                <span className="text-[13px] text-[var(--muted)] ml-1.5 italic">
                  {c.heroSuffix}
                </span>
              )}
            </p>
            <p className="text-[11.5px] text-[var(--muted)] mb-3">{c.sub}</p>
            <ProgressBar pct={c.pct} tone={c.tone} />
          </div>
        );
      })}
    </section>
  );
}
