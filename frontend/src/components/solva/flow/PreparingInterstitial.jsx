/**
 * Phase L.b.3 (2026-05-27) — Synthesis preparation interstitial.
 *
 * The Solva session lands here after DEPTH_Q3 while the orchestrator
 * runs the synthesis pass server-side. This component renders the
 * locked Claude-reference `<StreamingLogScene>` driven by real
 * backend SSE events flowing from the synthesis turn POST.
 *
 * The parent (`SolvaSession.jsx`) owns the `useStreamingProgress`
 * driver — it fires the synthesis turn through the streaming
 * endpoint and passes the resulting `state` down via the `state`
 * prop. When `state.status === "complete"` the parent dispatches
 * `preparingDone(...)` based on the server session record.
 *
 * Backwards compatibility: when `state` is undefined the component
 * falls back to an empty placeholder so it doesn't crash if any
 * future call site forgets to pass the prop.
 *
 * `prefers-reduced-motion` users: `StreamingLogScene` already honours
 * reduced motion via the CSS keyframe + 200ms fade-in tokens.
 */
import React from "react";
import StreamingLogScene from "@/components/transitions/StreamingLogScene";
import { FONT, TOKEN } from "./tokens";

const EMPTY_STATE = {
  surface: "solva-synthesis",
  phases: [],
  activeIndex: -1,
  completedIndexes: new Set(),
  result: null,
  error: null,
  status: "connecting",
};

export default function PreparingInterstitial({ testId = "solva-preparing", state }) {
  const effectiveState = state || EMPTY_STATE;

  return (
    <div
      data-testid={testId}
      style={{
        textAlign: "left",
        maxWidth: 640,
        margin: "0 auto",
        paddingTop: 60,
        paddingInline: 24,
      }}
    >
      <div
        style={{
          fontFamily: FONT.GEORGIA,
          fontSize: 26,
          color: TOKEN.INK,
          marginBottom: 28,
          textAlign: "center",
        }}
      >
        Putting this together.
      </div>

      <StreamingLogScene
        surfaceId="streaming-log-solva-synthesis"
        state={effectiveState}
        emptyHint="Preparing..."
      />
    </div>
  );
}
