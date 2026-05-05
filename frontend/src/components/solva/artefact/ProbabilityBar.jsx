/**
 * Probability bar visual — brief §5.2 + §7.4. Animated fill over 600ms
 * ease-out on first paint; CI extension visible behind the point
 * estimate. Respects prefers-reduced-motion (no transition under it).
 *
 * Props:
 *   pct      — point estimate (0-100)
 *   low      — confidence interval lower bound (0-100)
 *   high     — confidence interval upper bound (0-100)
 *   label    — short scenario heading (Georgia 11pt bold)
 *   desc     — longer scenario description (Georgia 10.5pt italic)
 *   tier     — tier marker (corpus / comparable / etc.) for ARIA only
 */
import React, { useEffect, useState } from "react";
import { TOKEN, FONT } from "../flow/tokens";
import usePrefersReducedMotion from "../flow/usePrefersReducedMotion";

export default function ProbabilityBar({
  label,
  desc,
  pct = 50,
  low = null,
  high = null,
  tier = null,
  testId,
}) {
  const reduced = usePrefersReducedMotion();
  const safePct = Math.max(0, Math.min(100, Math.round(pct)));
  const safeLow = low == null ? safePct : Math.max(0, Math.min(100, Math.round(low)));
  const safeHigh = high == null ? safePct : Math.max(0, Math.min(100, Math.round(high)));

  // Animation: start width at 0, animate to safePct on mount.
  const [drawn, setDrawn] = useState(reduced ? safePct : 0);
  useEffect(() => {
    if (reduced) {
      setDrawn(safePct);
      return undefined;
    }
    const t = requestAnimationFrame(() => setDrawn(safePct));
    return () => cancelAnimationFrame(t);
  }, [safePct, reduced]);

  const ariaLabel =
    `${label}: ${safePct}% probability, confidence interval ${safeLow} to ${safeHigh}.` +
    (tier ? ` Tier ${tier}.` : "");

  return (
    <div
      data-testid={testId}
      role="img"
      aria-label={ariaLabel}
      style={{ margin: "18px 0" }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4, gap: 12 }}>
        <span
          style={{
            fontFamily: FONT.GEORGIA,
            fontSize: 18,
            color: TOKEN.INK,
            fontWeight: 700,
            flex: 1,
          }}
        >
          {label}
        </span>
        <span
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 14,
            color: TOKEN.DEEP,
            whiteSpace: "nowrap",
          }}
        >
          {safePct}% ({safeLow}–{safeHigh}%)
        </span>
      </div>
      {desc && (
        <div
          style={{
            fontFamily: FONT.GEORGIA,
            fontSize: 14,
            color: TOKEN.DEEP,
            fontStyle: "italic",
            marginBottom: 8,
            lineHeight: 1.5,
          }}
        >
          {desc}
        </div>
      )}
      <div
        style={{
          position: "relative",
          height: 14,
          background: TOKEN.RULE,
          borderRadius: 1,
          overflow: "hidden",
        }}
      >
        {/* CI extension layer (behind the point estimate) */}
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            left: `${safeLow}%`,
            width: `${Math.max(0, safeHigh - safeLow)}%`,
            background: "rgba(42, 27, 29, 0.35)",
            transition: reduced ? "none" : "width 600ms ease-out, left 600ms ease-out",
          }}
        />
        {/* Point estimate fill */}
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            left: 0,
            width: `${drawn}%`,
            background: TOKEN.INK,
            transition: reduced ? "none" : "width 600ms ease-out",
          }}
        />
      </div>
    </div>
  );
}
