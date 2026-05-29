/**
 * Solva v2 — Slice 3b (2026-05-29) live reasoning ticker.
 *
 * Sticky panel that surfaces Solva's current layer + step description
 * as the SSE stream progresses. On `session.complete`, the ticker
 * collapses to a compact pill that stays visible for ~8 seconds, then
 * fades to a small "Session log" icon-button (Slice 3b ships the
 * icon-button stub; the full event-history side-panel opens in Slice 7).
 *
 * Visual language matches the streaming-loader treatment used on the
 * 7 long-op surfaces from Phase L: monospace lower-cap label, serif
 * body, brand-purple accent dot, narrow horizontal stack.
 *
 * Wave 4.2.followup.2 — all tints come from Tailwind short-name brand
 * utilities (`bg-ned-purple/N`, `border-ned-purple/N`); no
 * opacity-modifier-on-hex-CSS-var traps.
 */
import React, { useEffect, useState } from "react";
import { Loader2, CheckCircle2, History } from "lucide-react";


const LAYER_DISPLAY_NAMES = {
  L0: "Frame Audit",
  L1: "Surface",
  L2: "Depth",
  L3: "Synthesis",
  L4: "Reflection",
};


export default function SolvaReasoningTicker({
  currentLayer,
  currentLayerName,
  currentStep,
  isComplete,
  totalEvents,
  receivedEvents,
}) {
  // Two-stage post-completion lifecycle:
  //   • complete → 8s pill visible
  //   • after 8s → icon-button stub (clicks no-op for Slice 3b)
  const [postCompleteStage, setPostCompleteStage] = useState("ticker");

  useEffect(() => {
    if (!isComplete) {
      setPostCompleteStage("ticker");
      return undefined;
    }
    setPostCompleteStage("pill");
    const t = setTimeout(() => setPostCompleteStage("icon"), 8_000);
    return () => clearTimeout(t);
  }, [isComplete]);

  // Final-state icon-button stub
  if (postCompleteStage === "icon") {
    return (
      <button
        type="button"
        data-testid="solva-v2-ticker-log-icon"
        data-solva-v2-ticker-stage="icon"
        className="fixed top-4 right-4 z-40 flex items-center gap-1.5 rounded-full border border-ned-purple/30 bg-[var(--parchment)] px-2.5 py-1.5 text-[var(--ned-purple)] hover:bg-ned-purple/10 transition-colors shadow-sm"
        aria-label="Open Solva session log"
      >
        <History className="w-3.5 h-3.5" />
        <span className="font-mono text-[10.5px] uppercase tracking-[0.14em]">
          Session log
        </span>
      </button>
    );
  }

  // Compact pill — first 8s after session.complete
  if (postCompleteStage === "pill") {
    return (
      <div
        data-testid="solva-v2-ticker-pill"
        data-solva-v2-ticker-stage="pill"
        className="fixed top-4 right-4 z-40 flex items-center gap-2 rounded-full border border-ned-purple/30 bg-[var(--parchment)] px-3.5 py-2 shadow-sm"
      >
        <CheckCircle2 className="w-3.5 h-3.5 text-[var(--ned-purple)]" />
        <span
          className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--ink)]"
          data-testid="solva-v2-ticker-pill-text"
        >
          Session complete · 5 layers · 13 slides
        </span>
      </div>
    );
  }

  // Live / replay ticker
  const layerLabel = currentLayer ? LAYER_DISPLAY_NAMES[currentLayer] : null;
  const progressLine = totalEvents
    ? `${receivedEvents} / ${totalEvents}`
    : null;

  return (
    <aside
      data-testid="solva-v2-ticker"
      data-solva-v2-ticker-stage="active"
      data-solva-v2-ticker-layer={currentLayer || ""}
      className="solva-v2-ticker fixed top-4 right-4 z-40 w-[320px] rounded-md border border-ned-purple/30 bg-[var(--parchment)] px-3.5 py-3 shadow-sm"
    >
      <div className="flex items-baseline justify-between mb-2 gap-3">
        <div className="flex items-center gap-1.5">
          <Loader2 className="w-3 h-3 animate-spin text-[var(--ned-purple)]" />
          <span
            className="font-mono text-[9.5px] uppercase tracking-[0.18em] text-[var(--muted)]"
            data-testid="solva-v2-ticker-layer-label"
          >
            {currentLayer ? (
              <>
                {currentLayer}&nbsp;·&nbsp;{layerLabel}
              </>
            ) : (
              <>Solva — connecting</>
            )}
          </span>
        </div>
        {progressLine && (
          <span
            className="font-mono text-[9.5px] tabular-nums text-[var(--muted)]"
            data-testid="solva-v2-ticker-progress"
          >
            {progressLine}
          </span>
        )}
      </div>
      <p
        className="text-[12px] leading-snug text-[var(--ink)] min-h-[2.6em]"
        data-testid="solva-v2-ticker-step"
      >
        {currentStep || "Awaiting first reasoning event…"}
      </p>
    </aside>
  );
}
