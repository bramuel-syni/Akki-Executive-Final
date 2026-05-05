/**
 * Phase J.3 placeholder. Real implementation lands in sub-step J.3.
 */
import React from "react";
import { TOKEN, FONT } from "./tokens";

export default function Step3StudioWrapper({ onComplete }) {
  return (
    <div style={{ textAlign: "center", padding: 80 }}>
      <h2 style={{ fontFamily: FONT.GEORGIA, color: TOKEN.INK, fontSize: 24 }}>
        Step 3 — Work Studio
      </h2>
      <p style={{ fontFamily: FONT.CALIBRI, color: TOKEN.MUTED, fontSize: 13, marginTop: 16 }}>
        Coming next: J.3 split-view source / draft + provenance moment.
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
