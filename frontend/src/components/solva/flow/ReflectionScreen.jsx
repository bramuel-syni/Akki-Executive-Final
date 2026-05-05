/**
 * Reflection screen — three Layer 4 questions, one at a time. Brief §6.
 * Skip option present but visually muted. The 3 questions are
 * locked-text per the brief; for the refusal flow, question 1 is
 * replaced with a refusal-aware prompt (brief §8.3).
 */
import React, { useEffect, useRef } from "react";
import { TOKEN, FONT } from "./tokens";
import ProgressIndicator from "./ProgressIndicator";
import PrimaryButton, { GhostLink } from "./PrimaryButton";

export const REFLECTION_QUESTIONS = Object.freeze({
  REFLECT_1: "Are you disappointed by this diagnosis, and if so, why?",
  REFLECT_2: "What would have to be true for you to be wrong about how you came in?",
  REFLECT_3: "What would the explanation be in six months if you ignored this?",
});

export const REFUSAL_REFLECTION_QUESTIONS = Object.freeze({
  REFLECT_1: "What did you learn from this refusal?",
  REFLECT_2: "What would have to be true for you to be wrong about how you came in?",
  REFLECT_3: "What would the explanation be in six months if you ignored this?",
});

export default function ReflectionScreen({
  state,
  refusal = false,
  draft,
  setDraft,
  onContinue,
  onSkip,
}) {
  const taRef = useRef(null);
  useEffect(() => { taRef.current?.focus(); }, [state]);

  const QUESTIONS = refusal ? REFUSAL_REFLECTION_QUESTIONS : REFLECTION_QUESTIONS;
  const question = QUESTIONS[state] || "Reflection";

  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      onContinue();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      onSkip();
    }
  };

  return (
    <>
      <ProgressIndicator state={state} />

      <h1
        style={{
          fontFamily: FONT.GEORGIA,
          fontSize: 24,
          color: TOKEN.INK,
          fontWeight: "normal",
          margin: "0 0 36px 0",
          lineHeight: 1.4,
        }}
        data-testid="solva-reflection-question"
      >
        {question}
      </h1>

      <textarea
        ref={taRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Optional. Tap Skip to leave it blank."
        rows={5}
        aria-label="Reflection answer"
        data-testid="solva-reflection-textarea"
        style={{
          width: "100%",
          fontFamily: FONT.GEORGIA,
          fontSize: 16,
          lineHeight: 1.6,
          padding: 18,
          border: `1px solid ${TOKEN.RULE}`,
          borderRadius: 2,
          background: TOKEN.LIGHT,
          color: TOKEN.INK,
          outline: "none",
          resize: "vertical",
        }}
      />

      <div style={{ marginTop: 32, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <GhostLink onClick={onSkip} testId="solva-reflection-skip">prefer not to answer</GhostLink>
        <PrimaryButton
          onClick={onContinue}
          ariaLabel="Save and continue"
          testId="solva-reflection-continue"
        >
          Continue
        </PrimaryButton>
      </div>
    </>
  );
}
