/**
 * Single-column shell shared by every Solva v3 flow / artefact screen.
 * Centred, max-width 760px, full-screen background, ample whitespace.
 * Brief §7.3 + §3.3.
 */
import React from "react";
import { TOKEN } from "./tokens";

export default function SolvaShell({
  children,
  background = TOKEN.PAPER,
  topPadding = 80,
  maxWidth = 760,
  testId,
}) {
  return (
    <div
      data-testid={testId}
      style={{
        minHeight: "100vh",
        background,
        paddingTop: topPadding,
        paddingBottom: 80,
        paddingLeft: 16,
        paddingRight: 16,
      }}
    >
      <div style={{ maxWidth, margin: "0 auto" }}>
        {children}
      </div>
    </div>
  );
}
