/**
 * Framing screen — the first prompt after the user picks a sub-module.
 * Brief §4.2. Single column, max 720px, primary action = "Begin".
 *
 * Material attach button is present and visible but disabled in v3 first
 * pass (the brief makes it optional and the existing /api/contexts/*
 * upload pipeline isn't wired into solva sessions yet — Phase I.6).
 */
import React, { useState, useEffect, useRef } from "react";
import { TOKEN, FONT, SUBMODULE_LABELS } from "./tokens";
import ProgressIndicator from "./ProgressIndicator";
import PrimaryButton, { GhostLink } from "./PrimaryButton";

export default function FramingScreen({
  submodule,
  persona,
  framingDraft,
  setFramingDraft,
  onSubmit,
  onBack,
  busy = false,
  error = null,
  onPersonaChange,
}) {
  const taRef = useRef(null);
  useEffect(() => { taRef.current?.focus(); }, []);

  const handleKeyDown = (e) => {
    // Ctrl/Cmd + Enter submits.
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <>
      <ProgressIndicator state="FRAMING" />

      <div
        style={{
          fontFamily: FONT.GEORGIA,
          fontSize: 14,
          color: TOKEN.MUTED,
          textAlign: "center",
          textTransform: "uppercase",
          letterSpacing: 1.6,
          marginBottom: 12,
        }}
      >
        {SUBMODULE_LABELS[submodule] || "Solva session"}
      </div>
      <h1
        style={{
          fontFamily: FONT.GEORGIA,
          fontSize: 28,
          color: TOKEN.INK,
          fontWeight: "normal",
          margin: "0 0 36px 0",
          textAlign: "center",
          lineHeight: 1.25,
        }}
      >
        Tell me about the situation you're trying to think through.
      </h1>

      {submodule === "get_perspective" && (
        <div style={{ marginBottom: 24 }}>
          <label
            htmlFor="solva-persona"
            style={{
              fontFamily: FONT.CALIBRI,
              fontSize: 12,
              textTransform: "uppercase",
              letterSpacing: 1.2,
              color: TOKEN.DEEP,
              display: "block",
              marginBottom: 6,
            }}
          >
            Whose perspective?
          </label>
          <input
            id="solva-persona"
            type="text"
            value={persona || ""}
            onChange={(e) => onPersonaChange(e.target.value)}
            placeholder="Chair · CFO · Investor · Regulator · Auditor · or free text"
            style={{
              width: "100%",
              fontFamily: FONT.GEORGIA,
              fontSize: 16,
              padding: "12px 14px",
              border: `1px solid ${TOKEN.RULE}`,
              background: TOKEN.LIGHT,
              color: TOKEN.INK,
              outline: "none",
            }}
          />
        </div>
      )}

      <textarea
        ref={taRef}
        value={framingDraft}
        onChange={(e) => setFramingDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="What's the situation? Be plain. Detail the numbers, the people, and what you're trying to decide."
        rows={7}
        aria-label="Framing prompt"
        data-testid="solva-framing-textarea"
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

      {/* + Attach material — Phase I.6 wires the upload. Visible but muted now. */}
      <div
        style={{
          marginTop: 14,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontFamily: FONT.CALIBRI,
          fontSize: 13,
          color: TOKEN.MUTED,
        }}
      >
        <button
          type="button"
          disabled
          aria-disabled="true"
          title="Attach material — coming soon"
          style={{
            background: "transparent",
            border: "none",
            color: TOKEN.MUTED,
            cursor: "not-allowed",
            padding: 0,
            fontFamily: FONT.CALIBRI,
            fontSize: 13,
          }}
        >
          + Attach material
        </button>
        <span style={{ fontStyle: "italic" }}>Optional · never required.</span>
      </div>

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
        <GhostLink onClick={onBack} testId="solva-framing-back">← Back</GhostLink>
        <PrimaryButton
          onClick={onSubmit}
          busy={busy}
          ariaLabel="Begin Solva session"
          testId="solva-framing-begin"
          disabled={!framingDraft || framingDraft.trim().length < 20}
        >
          Begin
        </PrimaryButton>
      </div>
    </>
  );
}
