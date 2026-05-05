/**
 * Phase J.4 placeholder. Real implementation lands in sub-step J.4.
 */
import React from "react";
import { TOKEN, FONT } from "./tokens";

export default function Step4CycleSnapshot({ onComplete }) {
  return (
    <div style={{ textAlign: "center", padding: 80 }}>
      <h2 style={{ fontFamily: FONT.GEORGIA, color: TOKEN.INK, fontSize: 24 }}>
        Step 4 — Cycle Manager snapshot
      </h2>
      <p style={{ fontFamily: FONT.CALIBRI, color: TOKEN.MUTED, fontSize: 13, marginTop: 16 }}>
        Coming next: J.4 read-only snapshot per role + org type.
      </p>
      <button
        type="button"
        onClick={onComplete}
        style={{ marginTop: 32, padding: "12px 28px", background: TOKEN.ACCENT_DARK, color: TOKEN.LIGHT, fontFamily: FONT.CALIBRI, fontSize: 14, border: "none", borderRadius: 2, cursor: "pointer" }}
      >
        (placeholder) Continue
      </button>
    </div>
  );
}
