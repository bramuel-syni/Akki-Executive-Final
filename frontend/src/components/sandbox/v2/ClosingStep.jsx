/**
 * Phase J.4 placeholder. Real implementation lands in sub-step J.4.
 */
import React from "react";
import { TOKEN, FONT } from "./tokens";

export default function ClosingStep({ flow }) {
  return (
    <div style={{ textAlign: "center", padding: 80 }}>
      <h2 style={{ fontFamily: FONT.GEORGIA, color: TOKEN.INK, fontSize: 28, fontWeight: 700 }}>
        This is Akki.
      </h2>
      <p style={{ fontFamily: FONT.GEORGIA, color: TOKEN.DEEP, fontSize: 16, marginTop: 16, fontStyle: "italic" }}>
        Hello {flow?.welcome?.name || "there"} — J.4 ships the closing copy + 3-CTA conversion block.
      </p>
    </div>
  );
}
