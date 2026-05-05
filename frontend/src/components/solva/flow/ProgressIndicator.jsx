/**
 * Quiet progress text — "Question 2 of 3" in muted Calibri. Brief §4.2.
 * No bar; the text IS the progress.
 */
import React from "react";
import { TOKEN, FONT } from "./tokens";
import { questionProgress, isReflectionState } from "@/lib/solvaFlow";

export default function ProgressIndicator({ state }) {
  let label = null;
  const qp = questionProgress(state);
  if (qp) {
    label = `Question ${qp.n} of ${qp.of}` + (qp.depth ? "" : "");
  } else if (isReflectionState(state)) {
    const map = { REFLECT_1: 1, REFLECT_2: 2, REFLECT_3: 3 };
    label = `Reflection ${map[state]} of 3`;
  } else if (state === "FRAMING") {
    label = "Framing";
  } else if (state === "PREPARING") {
    label = "Putting this together";
  } else if (state === "ARTEFACT" || state === "ARTEFACT_REFUSAL") {
    label = "Artefact";
  }
  if (!label) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        fontFamily: FONT.CALIBRI,
        fontSize: 12,
        textTransform: "uppercase",
        letterSpacing: 1.4,
        color: TOKEN.MUTED,
        textAlign: "center",
        marginBottom: 32,
      }}
    >
      {label}
    </div>
  );
}
