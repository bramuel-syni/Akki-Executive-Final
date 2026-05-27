/**
 * Phase L.b.2 (2026-05-27) — Synthesis preparation interstitial.
 *
 * The Solva session lands here after DEPTH_Q3 while the orchestrator
 * runs the synthesis pass server-side. This component renders the
 * locked Claude-reference `<StreamingLogScene>` walking the
 * `solva-synthesis` 6-phase script via `usePhasedTimer`.
 *
 * No real progress data — the orchestrator runs synchronously on the
 * server. The timer cadence is calibrated against observed synthesis
 * latency (~8-12s) so the user sees natural phase advancement.
 *
 * When the parent dispatches `preparingDone`, the component unmounts;
 * `usePhasedTimer` cleans up on unmount via its `useEffect` return.
 *
 * `prefers-reduced-motion` users: `StreamingLogScene` already honours
 * reduced motion via the CSS keyframe + 200ms fade-in tokens.
 */
import React, { useEffect } from "react";
import StreamingLogScene from "@/components/transitions/StreamingLogScene";
import usePhasedTimer from "@/hooks/usePhasedTimer";
import { FONT, TOKEN } from "./tokens";

export default function PreparingInterstitial({ testId = "solva-preparing" }) {
  const { state, start } = usePhasedTimer();

  useEffect(() => {
    start("solva-synthesis", { stepMs: 1500 });
  }, [start]);

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
        state={state}
        emptyHint="Preparing..."
      />
    </div>
  );
}
