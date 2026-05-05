/**
 * Sandbox v2 background shell — brief §8.1 visual register progression.
 *
 *   Welcome     -> PAPER
 *   Step 1      -> CREAM
 *   Step 2      -> CREAM_DEEP   (deferred to D.2; tokens reserved here)
 *   Step 3      -> LIGHT (#FFFFFF)
 *   Step 4      -> PAPER
 *   Closing     -> PAPER
 *
 * The cross-fade between states is handled by SandboxV2Page; this
 * component only paints the background and centres content.
 */
import React from "react";
import { TOKEN } from "./tokens";

export default function StepShell({ state, children, maxWidth = 720 }) {
  const bg = backgroundForState(state);
  return (
    <div
      style={{
        minHeight: "100vh",
        background: bg,
        paddingTop: 32,
        paddingBottom: 80,
        paddingLeft: 16,
        paddingRight: 16,
        transition: "background-color 400ms ease-out",
      }}
    >
      <div style={{ maxWidth, margin: "24px auto 0" }}>
        {children}
      </div>
    </div>
  );
}

export function backgroundForState(state) {
  switch (state) {
    case "WELCOME":         return TOKEN.PAPER;
    case "STEP_1_SOLVA":
    case "STEP_1_REVEAL":   return TOKEN.CREAM;
    case "STEP_2_PULSE":
    case "STEP_2_REVEAL":   return TOKEN.CREAM_DEEP;
    case "STEP_3_STUDIO":
    case "STEP_3_REVEAL":   return TOKEN.LIGHT;
    case "STEP_4_CYCLE":
    case "STEP_4_REVEAL":   return TOKEN.PAPER;
    case "CLOSING":         return TOKEN.PAPER;
    default:                return TOKEN.PAPER;
  }
}
