/**
 * Question screen — used for both Q1..Q3 and DEPTH_Q1..DEPTH_Q3.
 * Same anatomy; the only visual diff between rounds is the background
 * tint (CREAM vs CREAM_DEEP) and the progress label resets.
 * Brief §4.2.
 *
 * The question text comes from the most-recent solva turn we have on
 * record (i.e. the orchestrator's framing/grounding/hypothesis layer
 * response). The screen renders the question itself in Georgia and
 * the textarea below.
 */
import React, { useEffect, useRef } from "react";
import { TOKEN, FONT } from "./tokens";
import ProgressIndicator from "./ProgressIndicator";
import PrimaryButton, { GhostLink } from "./PrimaryButton";

export default function QuestionScreen({
  state,
  questionText,
  draft,
  setDraft,
  onContinue,
  onBack,
  canBack = true,
  busy = false,
  error = null,
}) {
  const taRef = useRef(null);
  useEffect(() => { taRef.current?.focus(); }, [state]);

  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      onContinue();
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
          lineHeight: 1.35,
        }}
        data-testid="solva-question-heading"
      >
        {questionText || "Loading question…"}
      </h1>

      <textarea
        ref={taRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type your answer…"
        rows={6}
        aria-label="Answer"
        data-testid="solva-answer-textarea"
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

      {error && (
        <div
          role="alert"
          style={{
            marginTop: 16,
            color: TOKEN.ACCENT,
            fontFamily: FONT.CALIBRI,
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      <div style={{ marginTop: 32, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        {canBack ? (
          <GhostLink onClick={onBack} testId="solva-question-back">← Back</GhostLink>
        ) : <span />}
        <PrimaryButton
          onClick={onContinue}
          busy={busy}
          ariaLabel="Continue to next question"
          testId="solva-question-continue"
        >
          Continue
        </PrimaryButton>
      </div>
    </>
  );
}
