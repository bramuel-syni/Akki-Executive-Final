/**
 * HighlightsStats — compact visual strip for the Highlights surface.
 *
 * Two pure-SVG visualisations, drawn in the Cream/Oxblood palette:
 *   1. Confidence donut — shows the share of High / Medium / Low signals
 *   2. Volume sparkline — signals created per day over the last 14 days
 *
 * Zero external chart library; stays editorial, stays fast, prints cleanly.
 */
import React, { useMemo } from "react";

const OXBLOOD = "#8B2E2B";
const OXBLOOD_SOFT = "#C58A88";
const INK = "#1F2937";
const MUTED = "#64748B";
const RULE = "#E1E6ED";

function Donut({ buckets, total }) {
  // buckets: [{ key, label, value, color }]
  const size = 108;
  const stroke = 14;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;

  if (total === 0) {
    return (
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={RULE} strokeWidth={stroke} />
      </svg>
    );
  }

  let offset = 0;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} data-testid="highlights-donut">
      <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={RULE} strokeWidth={stroke} />
        {buckets.map((b) => {
          if (b.value === 0) return null;
          const len = (b.value / total) * c;
          const el = (
            <circle
              key={b.key}
              cx={size / 2}
              cy={size / 2}
              r={r}
              fill="none"
              stroke={b.color}
              strokeWidth={stroke}
              strokeDasharray={`${len} ${c - len}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
            >
              <animate attributeName="stroke-dasharray" from={`0 ${c}`} to={`${len} ${c - len}`} dur="0.7s" fill="freeze" />
            </circle>
          );
          offset += len;
          return el;
        })}
      </g>
      <text
        x={size / 2} y={size / 2 - 2}
        textAnchor="middle" fontFamily="Georgia, serif"
        fontSize="22" fill={INK}
      >
        {total}
      </text>
      <text
        x={size / 2} y={size / 2 + 14}
        textAnchor="middle" fontFamily="Inter, sans-serif"
        fontSize="8.5" fill={MUTED} letterSpacing="1.5"
      >
        SIGNALS
      </text>
    </svg>
  );
}

function Sparkline({ points }) {
  // points: array of 14 integers (newest last)
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
        <path d={path} fill="none" stroke={OXBLOOD} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <animate attributeName="stroke-dasharray" from="0 1000" to="1000 0" dur="1s" fill="freeze" />
        </path>
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

export default function HighlightsStats({ signals = [] }) {
  const { buckets, total, sparkPoints, sparkTotal } = useMemo(() => {
    const by = { high: 0, medium: 0, low: 0 };
    for (const s of signals) {
      const k = s.confidence || "medium";
      if (by[k] !== undefined) by[k] += 1;
    }
    const bucketDef = [
      { key: "high",   label: "High",   value: by.high,   color: OXBLOOD },
      { key: "medium", label: "Medium", value: by.medium, color: OXBLOOD_SOFT },
      { key: "low",    label: "Low",    value: by.low,    color: RULE },
    ];

    // 14-day rolling window, newest last
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

    return {
      buckets: bucketDef,
      total: signals.length,
      sparkPoints: counts,
      sparkTotal: counts.reduce((a, b) => a + b, 0),
    };
  }, [signals]);

  if (total === 0) return null;

  return (
    <div
      className="bg-white border border-[var(--rule)] rounded-lg p-5 mb-6 flex items-center gap-8 akki-fade-up"
      data-testid="highlights-stats"
    >
      <div className="shrink-0">
        <Donut buckets={buckets} total={total} />
      </div>

      <div className="flex-1 min-w-0 grid grid-cols-3 gap-x-5 gap-y-1">
        {buckets.map((b) => (
          <div key={b.key} className="flex items-center gap-2 min-w-0">
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: b.color === RULE ? "#CBD5E1" : b.color }}
            />
            <span className="text-[11px] uppercase tracking-[0.12em] text-[var(--muted)] truncate">
              {b.label}
            </span>
            <span className="akki-serif text-[14px] text-[var(--ink)] ml-auto tabular-nums">
              {b.value}
            </span>
          </div>
        ))}
        <p className="col-span-3 text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] mt-2">
          Confidence distribution · what the reader should weight most
        </p>
      </div>

      <div className="border-l border-[var(--rule)] pl-8 shrink-0">
        <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] mb-1">
          Last 14 days
        </p>
        <Sparkline points={sparkPoints} />
        <p className="text-[11px] text-[var(--muted)] mt-1">
          <span className="akki-serif text-[13px] text-[var(--ink)]">{sparkTotal}</span>
          <span className="ml-1.5">new signals in the window</span>
        </p>
      </div>
    </div>
  );
}
