/**
 * Sandbox v2 progress chrome — brief §8.2.
 *
 * Text-only "Step N of 4" indicator on the left and "Exit Sandbox"
 * link on the right. Renders on every step except WELCOME and
 * CLOSING.
 */
import React from "react";
import { TOKEN, FONT } from "./tokens";
import { stepIndexForState } from "@/lib/sandboxV2Flow";

export default function ProgressChrome({ state, onExit }) {
  const idx = stepIndexForState(state);
  if (!idx) return null;
  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 5,
        background: "transparent",
        padding: "18px 24px 6px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        maxWidth: 960,
        margin: "0 auto",
      }}
    >
      <div
        role="status"
        aria-live="polite"
        data-testid="sandbox-v2-progress"
        style={{
          fontFamily: FONT.CALIBRI,
          fontSize: 12,
          textTransform: "uppercase",
          letterSpacing: 1.4,
          color: TOKEN.MUTED,
        }}
      >
        Step {idx} of 4
      </div>
      <button
        type="button"
        onClick={onExit}
        data-testid="sandbox-v2-exit"
        style={{
          fontFamily: FONT.CALIBRI,
          fontSize: 12,
          color: TOKEN.MUTED,
          background: "transparent",
          border: "none",
          textDecoration: "underline",
          textUnderlineOffset: 4,
          cursor: "pointer",
          padding: 0,
        }}
      >
        Exit Sandbox
      </button>
    </header>
  );
}
