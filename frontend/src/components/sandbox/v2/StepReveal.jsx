/**
 * Phase J.2 placeholder. Real implementation lands in sub-step J.2.
 */
import React from "react";
import { TOKEN, FONT } from "./tokens";

export default function StepReveal({ stepIndex = 1, onAdvance, advanceLabel = "Continue →" }) {
  return (
    <div style={{ textAlign: "center", padding: 80 }}>
      <h2 style={{ fontFamily: FONT.GEORGIA, color: TOKEN.INK, fontSize: 28, fontWeight: 700 }}>
        Step {stepIndex} reveal
      </h2>
      <p style={{ fontFamily: FONT.GEORGIA, color: TOKEN.DEEP, fontStyle: "italic", fontSize: 16, marginTop: 16 }}>
        Brief-spec copy lands in J.2 / J.3 / J.4.
      </p>
      <button
        type="button"
        onClick={onAdvance}
        style={{ marginTop: 32, padding: "12px 28px", background: TOKEN.ACCENT_DARK, color: TOKEN.LIGHT, fontFamily: FONT.CALIBRI, fontSize: 14, border: "none", borderRadius: 2, cursor: "pointer" }}
      >
        {advanceLabel}
      </button>
    </div>
  );
}
