/**
 * Phase J — reusable reveal step (Sandbox v2 brief §8.3).
 *
 * Animation (full):
 *   t=0   : title fades in over 800ms
 *   t=800 : 400ms hold (no body yet)
 *   t=1200: body fades in over 600ms
 *   t=1800: continue / conversion CTAs revealed (200ms ease)
 *
 * Under `prefers-reduced-motion: reduce` everything snaps to its
 * final state immediately.
 *
 * Typography (locked):
 *   - title  : Georgia 28px, bold
 *   - body   : Georgia 18px, italic
 *
 * The title + body strings come from props so editorial can swap copy
 * without rebuilding. When the parent doesn't supply them, we fall
 * back to brand-aligned defaults derived from `stepIndex` and the
 * Solva refusal flag (so the reveal still renders something coherent
 * during state-machine debugging).
 *
 * A11y: the reveal uses an aria-live="polite" status region so screen
 * readers are notified when each text block appears. The progressive
 * disclosure is purely visual; the role="status" wrapper carries the
 * full reveal text from frame zero so AT users hear it once, intact.
 */
import React, { useEffect, useState } from "react";
import { TOKEN, FONT } from "./tokens";
import usePrefersReducedMotion from "@/components/solva/flow/usePrefersReducedMotion";

const TITLE_FADE_MS = 800;
const HOLD_MS = 400;
const BODY_FADE_MS = 600;
const CTA_FADE_MS = 200;

/** Default reveal copy keyed by step + refusal. Locked editorial
 *  scaffolding — overridable via props for the Phase 17 website
 *  rewrite. */
function defaultsFor(stepIndex, refusal) {
  if (stepIndex === 1) {
    if (refusal) {
      return {
        title: "That refusal was the demonstration.",
        body: (
          "Akki declined to weight scenarios because the evidence was thin. "
          + "This is the editorial discipline you can trust into a board room."
        ),
      };
    }
    return {
      title: "Solva did the work you saw.",
      body: (
        "Three grounded questions, one synthesis, scenarios with confidence "
        + "intervals — and an honest read of where the evidence runs out."
      ),
    };
  }
  if (stepIndex === 2) {
    return {
      title: "Patterns become visible across boards.",
      body: (
        "Three signals. Each routes back to a source document. None is a "
        + "headline; each is a question you can take into the next agenda."
      ),
    };
  }
  if (stepIndex === 3) {
    return {
      title: "Composition with provenance, not autocomplete.",
      body: (
        "Every sentence carried a citation back to the source materials. "
        + "When you tried to add a claim that wasn't there, Akki refused."
      ),
    };
  }
  if (stepIndex === 4) {
    return {
      title: "Three cycles, one structural memory.",
      body: (
        "Open items stay visible until they're resolved. Pulse signals "
        + "enter the cycle. Strategic baseline is the line everything is "
        + "measured against."
      ),
    };
  }
  return {
    title: "Continue.",
    body: "",
  };
}

export default function StepReveal({
  stepIndex = 1,
  refusal = false,
  // Optional editorial overrides. When supplied they take precedence
  // over the default copy.
  title: titleOverride = null,
  body: bodyOverride = null,
  // Primary continue control.
  onAdvance,
  advanceLabel = "Continue \u2192",
  // Secondary "conversion" control. Only renders when both label and
  // handler are present. Used by Step 4 reveal where the brief offers
  // a "Save and send" shortcut into closing.
  conversionLabel = null,
  onConversion = null,
}) {
  const reduced = usePrefersReducedMotion();
  const fallbacks = defaultsFor(stepIndex, refusal);
  const title = titleOverride || fallbacks.title;
  const body = bodyOverride || fallbacks.body;

  // 0=title-fading, 1=body-fading, 2=ctas-visible
  const [phase, setPhase] = useState(reduced ? 2 : 0);

  useEffect(() => {
    if (reduced) {
      setPhase(2);
      return undefined;
    }
    const t1 = window.setTimeout(() => setPhase(1), TITLE_FADE_MS + HOLD_MS);
    const t2 = window.setTimeout(
      () => setPhase(2),
      TITLE_FADE_MS + HOLD_MS + BODY_FADE_MS
    );
    return () => {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
    };
  }, [reduced]);

  const titleStyle = {
    fontFamily: FONT.GEORGIA,
    fontSize: 28,
    fontWeight: 700,
    color: TOKEN.INK,
    lineHeight: 1.25,
    margin: "0 0 24px 0",
    textAlign: "center",
    opacity: phase >= 0 ? 1 : 0,
    transition: reduced ? "none" : `opacity ${TITLE_FADE_MS}ms ease-out`,
  };
  const bodyStyle = {
    fontFamily: FONT.GEORGIA,
    fontSize: 18,
    fontStyle: "italic",
    color: TOKEN.DEEP,
    lineHeight: 1.6,
    margin: "0 auto",
    maxWidth: 580,
    textAlign: "center",
    opacity: phase >= 1 ? 1 : 0,
    transition: reduced ? "none" : `opacity ${BODY_FADE_MS}ms ease-out`,
  };
  const ctaWrapStyle = {
    marginTop: 56,
    display: "flex",
    gap: 16,
    justifyContent: "center",
    flexWrap: "wrap",
    opacity: phase >= 2 ? 1 : 0,
    transition: reduced ? "none" : `opacity ${CTA_FADE_MS}ms ease-out`,
  };

  return (
    <section
      data-testid={`sandbox-v2-reveal-${stepIndex}`}
      data-reveal-phase={phase}
      style={{ padding: "64px 16px 24px" }}
    >
      {/* aria-live wrapper carries the full reveal text from frame 0
       *  so AT users hear it once, intact, regardless of the visual
       *  fade choreography. The visual title + body underneath are
       *  aria-hidden because they would otherwise re-announce. */}
      <div role="status" aria-live="polite" style={visuallyHidden}>
        {title}
        {body ? `. ${body}` : ""}
      </div>

      <h2 aria-hidden="true" style={titleStyle}>{title}</h2>
      {body && (
        <p aria-hidden="true" style={bodyStyle}>{body}</p>
      )}

      <div style={ctaWrapStyle}>
        {conversionLabel && onConversion && (
          <button
            type="button"
            onClick={onConversion}
            disabled={phase < 2}
            data-testid={`sandbox-v2-reveal-${stepIndex}-conversion`}
            style={{
              fontFamily: FONT.CALIBRI,
              fontSize: 14,
              background: "transparent",
              color: TOKEN.INK,
              border: `1px solid ${TOKEN.RULE}`,
              padding: "12px 24px",
              cursor: phase < 2 ? "not-allowed" : "pointer",
              borderRadius: 2,
              letterSpacing: 0.4,
            }}
          >
            {conversionLabel}
          </button>
        )}
        <button
          type="button"
          onClick={onAdvance}
          disabled={phase < 2}
          data-testid={`sandbox-v2-reveal-${stepIndex}-continue`}
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 14,
            background: TOKEN.ACCENT_DARK,
            color: TOKEN.LIGHT,
            border: "none",
            padding: "12px 28px",
            cursor: phase < 2 ? "not-allowed" : "pointer",
            borderRadius: 2,
            letterSpacing: 0.5,
          }}
        >
          {advanceLabel}
        </button>
      </div>
    </section>
  );
}

const visuallyHidden = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0,0,0,0)",
  whiteSpace: "nowrap",
  border: 0,
};
