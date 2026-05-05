/**
 * Synthesis preparation interstitial. Brief §4.2.
 *
 * Single column. Centred message: "Putting this together."
 * Below it, three lines of subtle status text that update as each
 * reasoning model conceptually completes.
 *
 * No real progress data — the orchestrator runs synchronously on the
 * server. We rotate the lines on a 1.5s cadence (or instantly under
 * prefers-reduced-motion).
 */
import React, { useEffect, useState } from "react";
import { TOKEN, FONT } from "./tokens";
import usePrefersReducedMotion from "./usePrefersReducedMotion";

const LINES = [
  "Looking across what you've shared.",
  "Checking against your evidence.",
  "Composing the synthesis.",
];

export default function PreparingInterstitial({ testId = "solva-preparing" }) {
  const reduced = usePrefersReducedMotion();
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (reduced) {
      setStep(LINES.length - 1);
      return undefined;
    }
    const id = setInterval(() => {
      setStep((s) => Math.min(s + 1, LINES.length - 1));
    }, 1500);
    return () => clearInterval(id);
  }, [reduced]);

  return (
    <div
      data-testid={testId}
      role="status"
      aria-live="polite"
      style={{
        textAlign: "center",
        paddingTop: 60,
      }}
    >
      <div
        style={{
          fontFamily: FONT.GEORGIA,
          fontSize: 26,
          color: TOKEN.INK,
          marginBottom: 32,
        }}
      >
        Putting this together.
      </div>

      {LINES.map((line, i) => (
        <div
          key={line}
          aria-hidden={i > step}
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 14,
            color: TOKEN.DEEP,
            opacity: i <= step ? 1 : 0.18,
            marginBottom: 8,
            transition: reduced ? "none" : "opacity 200ms ease-out",
          }}
        >
          {line}
        </div>
      ))}
    </div>
  );
}
