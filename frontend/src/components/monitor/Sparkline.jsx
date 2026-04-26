import React from "react";

/**
 * Sparkline — pure-SVG 12-week trend line for a Strategic Goal score.
 *
 * No chart library needed. Renders a 60×20 svg with a smooth polyline,
 * colour-keyed by the most recent score (red <40, amber 40-69, green ≥70).
 * If only one or zero datapoints exist, renders an "—" placeholder.
 */
export default function Sparkline({ history = [], width = 60, height = 20 }) {
  const points = (history || []).filter((p) => typeof p.score === "number");
  if (points.length < 2) {
    return (
      <span
        className="inline-block text-[10px] text-[var(--muted)]/70 italic"
        style={{ width, height, lineHeight: `${height}px` }}
        title="Not enough history yet — score one more time to see the trend."
      >
        —
      </span>
    );
  }

  const values = points.map((p) => p.score);
  const min = 0;
  const max = 100;
  const dx = width / (points.length - 1);
  const path = values
    .map((v, i) => {
      const x = i * dx;
      const y = height - ((v - min) / (max - min)) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const last = values[values.length - 1];
  const stroke = last >= 70 ? "#047857" : last >= 40 ? "#b45309" : "#b91c1c";
  const dot = { x: (points.length - 1) * dx, y: height - ((last - min) / (max - min)) * height };

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="inline-block align-middle"
      aria-label={`12-week score trend, latest ${last}`}
      data-testid="goal-sparkline"
    >
      <path d={path} fill="none" stroke={stroke} strokeWidth={1.4} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={dot.x} cy={dot.y} r={1.6} fill={stroke} />
    </svg>
  );
}
