/**
 * HighlightsStats — the editorial stats panel for Signals.
 *
 * Per user feedback: the previous decorative donut didn't pull its weight.
 * This redesign carries actual informational mass — risk vs opportunity vs
 * gap percentage breakdown, 14-day volume trend, and the 'what is a signal'
 * frame so the page communicates clearly instead of decorating space.
 */
import React, { useMemo } from "react";
import { AlertTriangle, TrendingUp, CircleSlash } from "lucide-react";

const OXBLOOD = "#8B2E2B";
const OXBLOOD_SOFT = "#C58A88";
const INK = "#1F2937";
const MUTED = "#64748B";
const RULE = "#E1E6ED";

function Sparkline({ points }) {
  const w = 220;
  const h = 44;
  const pad = 4;
  const max = Math.max(1, ...points);
  const step = points.length > 1 ? (w - pad * 2) / (points.length - 1) : 0;
  const pts = points.map((v, i) => {
    const x = pad + i * step;
    const y = h - pad - (v / max) * (h - pad * 2);
    return [x, y];
  });
  const path = pts.length ? pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ") : "";
  const area = path ? `${path} L ${w - pad} ${h - pad} L ${pad} ${h - pad} Z` : "";
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} data-testid="highlights-sparkline">
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={OXBLOOD} stopOpacity="0.22" />
          <stop offset="100%" stopColor={OXBLOOD} stopOpacity="0" />
        </linearGradient>
      </defs>
      {area && <path d={area} fill="url(#spark-fill)" />}
      {path && (
        <path d={path} fill="none" stroke={OXBLOOD} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      )}
      {pts.map(([x, y], i) => {
        const last = i === pts.length - 1;
        return (
          <circle
            key={i}
            cx={x} cy={y} r={last ? 3 : 1.5}
            fill={last ? OXBLOOD : OXBLOOD_SOFT}
            stroke={last ? "#F7F3EA" : "none"}
            strokeWidth={last ? 1.5 : 0}
          />
        );
      })}
    </svg>
  );
}

function MiniBar({ pct, color }) {
  return (
    <div className="h-1.5 w-full bg-[var(--rule)] rounded-full overflow-hidden">
      <div
        className="h-full transition-all"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  );
}

export default function HighlightsStats({ signals = [] }) {
  const stats = useMemo(() => {
    const by = { risk: 0, opportunity: 0, gap: 0 };
    const conf = { high: 0, medium: 0, low: 0 };
    for (const s of signals) {
      if (by[s.type] !== undefined) by[s.type] += 1;
      if (conf[s.confidence] !== undefined) conf[s.confidence] += 1;
    }
    const total = signals.length;

    // 14-day rolling window
    const now = new Date();
    const days = Array.from({ length: 14 }, (_, i) => {
      const d = new Date(now);
      d.setDate(d.getDate() - (13 - i));
      d.setHours(0, 0, 0, 0);
      return d;
    });
    const counts = days.map(() => 0);
    for (const s of signals) {
      const t = s.created_at ? new Date(s.created_at) : null;
      if (!t) continue;
      t.setHours(0, 0, 0, 0);
      const idx = days.findIndex((d) => d.getTime() === t.getTime());
      if (idx >= 0) counts[idx] += 1;
    }
    const sparkTotal = counts.reduce((a, b) => a + b, 0);

    // Compare last 7 days vs prior 7 days for the trend arrow
    const last7  = counts.slice(7).reduce((a, b) => a + b, 0);
    const prior7 = counts.slice(0, 7).reduce((a, b) => a + b, 0);

    return { by, conf, total, counts, sparkTotal, last7, prior7 };
  }, [signals]);

  if (stats.total === 0) return null;

  const pct = (n) => stats.total === 0 ? 0 : Math.round((n / stats.total) * 100);
  const trendDir = stats.last7 === stats.prior7 ? "flat" : stats.last7 > stats.prior7 ? "up" : "down";
  const trendCopy =
    trendDir === "up" ? `↑ ${stats.last7} vs ${stats.prior7} prior week` :
    trendDir === "down" ? `↓ ${stats.last7} vs ${stats.prior7} prior week` :
    `→ ${stats.last7} vs ${stats.prior7} prior week`;

  const breakdown = [
    { key: "risk",        icon: AlertTriangle, label: "Risks",         n: stats.by.risk,        color: "#b91c1c", desc: "to react to" },
    { key: "opportunity", icon: TrendingUp,    label: "Opportunities", n: stats.by.opportunity, color: "#047857", desc: "to act on" },
    { key: "gap",         icon: CircleSlash,   label: "Gaps",          n: stats.by.gap,         color: "#b45309", desc: "to close" },
  ];

  return (
    <div
      className="bg-white border border-[var(--rule)] rounded-lg p-6 mb-6 akki-fade-up grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-8"
      data-testid="highlights-stats"
    >
      {/* LEFT — what's a signal + breakdown bars */}
      <div>
        <p className="akki-overline mb-2">A signal is</p>
        <p className="akki-serif text-[15.5px] text-[var(--ink)] leading-snug mb-4 max-w-md">
          Something the executive needs to react to — a risk, an opportunity, or a gap that needs to be closed.
        </p>

        <div className="space-y-2.5">
          {breakdown.map((b) => {
            const Icon = b.icon;
            const p = pct(b.n);
            return (
              <div key={b.key} data-testid={`highlights-breakdown-${b.key}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Icon className="w-3 h-3 shrink-0" style={{ color: b.color }} strokeWidth={2} />
                  <span className="text-[12px] text-[var(--ink)]">
                    {b.label} <span className="text-[var(--muted)] italic">{b.desc}</span>
                  </span>
                  <span className="ml-auto akki-serif text-[14px] tabular-nums text-[var(--ink)]">
                    {b.n} <span className="text-[11px] text-[var(--muted)]">· {p}%</span>
                  </span>
                </div>
                <MiniBar pct={p} color={b.color} />
              </div>
            );
          })}
        </div>
      </div>

      {/* RIGHT — volume + confidence */}
      <div className="lg:border-l lg:border-[var(--rule)] lg:pl-8">
        <p className="akki-overline mb-1">14-day volume</p>
        <Sparkline points={stats.counts} />
        <p className="text-[11.5px] text-[var(--muted)] mt-1 mb-4">
          <span className="akki-serif text-[14px] text-[var(--ink)] tabular-nums">{stats.sparkTotal}</span>
          <span className="ml-1.5">new signals · {trendCopy}</span>
        </p>

        <div className="border-t border-[var(--rule)] pt-3">
          <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] mb-2">
            Confidence
          </p>
          <div className="flex items-center gap-3 text-[12px] flex-wrap">
            <span className="inline-flex items-baseline gap-1">
              <strong className="akki-serif text-[14px]" style={{ color: OXBLOOD }}>{stats.conf.high}</strong>
              <span className="text-[var(--muted)]">high</span>
            </span>
            <span className="text-[var(--muted)]/60">·</span>
            <span className="inline-flex items-baseline gap-1">
              <strong className="akki-serif text-[14px]">{stats.conf.medium}</strong>
              <span className="text-[var(--muted)]">medium</span>
            </span>
            <span className="text-[var(--muted)]/60">·</span>
            <span className="inline-flex items-baseline gap-1">
              <strong className="akki-serif text-[14px] text-[var(--muted)]">{stats.conf.low}</strong>
              <span className="text-[var(--muted)]">low</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
