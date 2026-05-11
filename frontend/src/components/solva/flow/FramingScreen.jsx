/**
 * Framing screen — the first prompt after the user picks a sub-module.
 * Brief §4.2. Single column, max 720px, primary action = "Begin".
 *
 * Phase H4 (2026-05-11) — material attach is now REAL. The button
 * opens a file picker, uploads the file to the active context's
 * documents endpoint, and exposes the resulting `doc_id` via
 * `onMaterialAttached(doc)`. Parent components can then pass that
 * doc_id through to the session-creation call so the post-create
 * `POST /api/solva/v2/sessions/{sid}/attach-document` lands the
 * material on the new session. If no `onMaterialAttached` callback
 * is provided, the file still uploads but no further wiring happens
 * (defensive — older callers don't break).
 */
import React, { useState, useEffect, useRef } from "react";
import { TOKEN, FONT, SUBMODULE_LABELS, SUBMODULE_FRAMING_COPY } from "./tokens";
import ProgressIndicator from "./ProgressIndicator";
import PrimaryButton, { GhostLink } from "./PrimaryButton";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

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
  intakeSeed = null, // Wave 1.1 (UAT pack) — handoff seed pointer.
  onMaterialAttached = null,   // Phase H4 — receives the uploaded doc shape
}) {
  const taRef = useRef(null);
  const attachInputRef = useRef(null);
  const { activeContext } = useAuth() || {};
  const [attached, setAttached] = useState(null);
  const [attaching, setAttaching] = useState(false);
  const [attachErr, setAttachErr] = useState(null);
  useEffect(() => { taRef.current?.focus(); }, []);

  // Phase B.1 — submodule-specific framing copy (spec §5.1). Defaults
  // to seek_clarity copy if the key is unrecognised, so unknown
  // submodules degrade gracefully.
  const framingCopy =
    SUBMODULE_FRAMING_COPY[submodule] || SUBMODULE_FRAMING_COPY.seek_clarity;

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
        {framingCopy.headline}
      </h1>

      {/* Wave 1.1 (UAT pack 2026-05-10) — handoff seed indicator.
          Subtle card showing the source the user came from. The
          backend resolves the full seed payload (title, summary)
          on POST /sessions; here we render only the URL-carried
          {kind, id} pointer so the user has a visual confirmation
          that the seed is being applied. */}
      {intakeSeed?.kind && intakeSeed?.id && (
        <div
          data-testid="solva-framing-seed-pill"
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 11.5,
            color: TOKEN.MUTED,
            background: "rgba(0,0,0,0.025)",
            border: `1px solid ${TOKEN.RULE}`,
            borderRadius: 999,
            padding: "5px 12px",
            display: "inline-block",
            marginBottom: 16,
            letterSpacing: 0.4,
          }}
        >
          Drawing on: {seedKindLabel(intakeSeed.kind)}
        </div>
      )}

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
        placeholder={framingCopy.placeholder}
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

      {/* + Attach material — Phase H4 (2026-05-11): now REAL. Opens a
          file picker, uploads to the active context's docs endpoint,
          and exposes the doc_id via `onMaterialAttached`. */}
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
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            type="button"
            disabled={attaching || !activeContext?.id}
            onClick={() => attachInputRef.current?.click()}
            data-testid="solva-framing-attach-material-btn"
            style={{
              background: "transparent",
              border: "none",
              color: attached ? TOKEN.INK : TOKEN.MUTED,
              cursor: attaching || !activeContext?.id ? "not-allowed" : "pointer",
              padding: 0,
              fontFamily: FONT.CALIBRI,
              fontSize: 13,
              textDecoration: attached ? "none" : "underline",
            }}
          >
            {attaching
              ? "Uploading…"
              : attached
                ? `✓ Attached: ${attached.name}`
                : "+ Attach material"}
          </button>
          <input
            ref={attachInputRef}
            type="file"
            accept=".pdf,.docx,.pptx,.txt,.md,.csv,image/*"
            style={{ display: "none" }}
            data-testid="solva-framing-attach-material-input"
            onChange={async (e) => {
              const f = e.target.files?.[0];
              e.target.value = "";   // reset for retry
              if (!f || !activeContext?.id) return;
              setAttaching(true);
              setAttachErr(null);
              try {
                const fd = new FormData();
                fd.append("file", f);
                const { data } = await api.post(
                  `/contexts/${activeContext.id}/documents`,
                  fd,
                  { headers: { "Content-Type": "multipart/form-data" } },
                );
                const doc = data?.document || data;
                setAttached({ id: doc.id, name: doc.name || f.name });
                if (typeof onMaterialAttached === "function") {
                  onMaterialAttached({ id: doc.id, name: doc.name || f.name });
                }
              } catch (err) {
                setAttachErr(err?.response?.data?.detail?.message || "Couldn't upload.");
                setAttached(null);
              } finally {
                setAttaching(false);
              }
            }}
          />
        </div>
        <span style={{ fontStyle: "italic" }}>Optional · never required.</span>
      </div>
      {attachErr && (
        <p style={{ marginTop: 6, color: TOKEN.ACCENT, fontSize: 12, fontFamily: FONT.CALIBRI }}>
          {attachErr}
        </p>
      )}

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

function seedKindLabel(kind) {
  // Wave 1.1 (UAT pack 2026-05-10) — friendly label for the seed
  // indicator pill. Stays in sync with the resolver vocabulary in
  // backend/routers/solva_v2.py:_resolve_intake_seed.
  switch ((kind || "").toLowerCase()) {
    case "document":            return "an attached document";
    case "cycle_question":      return "a cycle question";
    case "cycle_contribution":  return "a cycle contribution";
    case "solva_artefact":      return "an earlier Solva artefact";
    case "pulse_signal":        return "a Pulse signal";
    default:                    return "the source you brought in";
  }
}
