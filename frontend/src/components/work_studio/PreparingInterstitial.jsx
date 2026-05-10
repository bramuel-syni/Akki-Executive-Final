/**
 * Phase C.3 — Preparing interstitial for the Refine flow.
 *
 * Voice and rhythm match the Solva flow's `PreparingInterstitial` (single
 * column, one Georgia headline, three sub-lines that reveal on a 1.5s
 * cadence). Re-implemented here so the Solva file stays untouched per
 * the C.3 brief's hard rule.
 */
import React, { useEffect, useState } from "react";
import usePrefersReducedMotion from "@/components/solva/flow/usePrefersReducedMotion";
import { TOKEN, FONT } from "@/components/solva/flow/tokens";

const LINES = [
  "Reading the parent revision.",
  "Composing the change against the citation contract.",
  "Validating with an independent family.",
];

export default function WorkStudioPreparing({ testId = "work-studio-preparing" }) {
  const reduced = usePrefersReducedMotion();
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (reduced) { setStep(LINES.length - 1); return undefined; }
    const id = setInterval(() => setStep((s) => Math.min(s + 1, LINES.length - 1)), 1500);
    return () => clearInterval(id);
  }, [reduced]);
  return (
    <div
      data-testid={testId}
      role="status"
      aria-live="polite"
      style={{ textAlign: "center", paddingTop: 60, paddingBottom: 48 }}
    >
      <div style={{ fontFamily: FONT.GEORGIA, fontSize: 24, color: TOKEN.INK, marginBottom: 28 }}>
        Refining.
      </div>
      {LINES.map((line, i) => (
        <div
          key={line}
          aria-hidden={i > step}
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 13.5,
            color: TOKEN.DEEP,
            opacity: i <= step ? 1 : 0.18,
            marginBottom: 6,
            transition: reduced ? "none" : "opacity 200ms ease-out",
          }}
        >
          {line}
        </div>
      ))}
    </div>
  );
}
