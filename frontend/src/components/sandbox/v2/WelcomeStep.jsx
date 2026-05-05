/**
 * Phase J — Sandbox v2 Welcome screen (brief §3).
 *
 * Single column, max-width 720px, PAPER background. Four questions:
 *   1. Name (text)
 *   2. Role (single-select, 8 options)
 *   3. Org type (single-select, 8 options)
 *   4. What you hope to get (open text, 200ish char limit, optional)
 *
 * On submit, the page handler POSTs /api/sandbox/v2/sessions and pushes
 * the reducer to STEP_1_SOLVA.
 */
import React, { useEffect, useRef } from "react";
import { TOKEN, FONT, SANDBOX_V2_ROLES, SANDBOX_V2_ORG_TYPES, WELCOME_LEAD } from "./tokens";
import { Actions } from "@/lib/sandboxV2Flow";

export default function WelcomeStep({ welcome, dispatch, onSubmit, busy = false, error = null }) {
  const nameRef = useRef(null);
  useEffect(() => { nameRef.current?.focus(); }, []);

  const handleKey = (e) => {
    // Cmd/Ctrl+Enter submits from anywhere in the form.
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); onSubmit(); }}
      onKeyDown={handleKey}
      data-testid="sandbox-v2-welcome"
      style={{ width: "100%" }}
    >
      <div
        style={{
          width: 56,
          height: 1,
          background: TOKEN.ACCENT,
          margin: "0 auto 28px",
        }}
      />
      <h1
        style={{
          fontFamily: FONT.GEORGIA,
          fontSize: 32,
          color: TOKEN.INK,
          fontWeight: 700,
          textAlign: "center",
          margin: "0 0 14px 0",
          lineHeight: 1.2,
        }}
      >
        Welcome to the Sandbox.
      </h1>
      <p
        style={{
          fontFamily: FONT.GEORGIA,
          fontSize: 16,
          color: TOKEN.DEEP,
          textAlign: "center",
          margin: "0 0 48px 0",
          lineHeight: 1.55,
          fontStyle: "italic",
        }}
      >
        {WELCOME_LEAD}
      </p>

      {/* 1. Name */}
      <Field label="Your name">
        <input
          ref={nameRef}
          type="text"
          value={welcome.name}
          onChange={(e) => dispatch(Actions.setWelcomeField("name", e.target.value))}
          placeholder="First name is fine."
          data-testid="sandbox-v2-welcome-name"
          maxLength={120}
          style={inputStyle}
        />
      </Field>

      {/* 2. Role */}
      <Field label="Your role">
        <Picker
          options={SANDBOX_V2_ROLES}
          value={welcome.role}
          onChange={(v) => dispatch(Actions.setWelcomeField("role", v))}
          testId="sandbox-v2-welcome-role"
        />
      </Field>

      {/* 3. Org type */}
      <Field label="Your organisation">
        <Picker
          options={SANDBOX_V2_ORG_TYPES}
          value={welcome.org_type}
          onChange={(v) => dispatch(Actions.setWelcomeField("org_type", v))}
          testId="sandbox-v2-welcome-orgtype"
        />
      </Field>

      {/* 4. Hope */}
      <Field label={<>What do you hope to get out of this? <span style={optionalStyle}>(optional)</span></>}>
        <textarea
          value={welcome.hope}
          onChange={(e) => dispatch(Actions.setWelcomeField("hope", e.target.value))}
          placeholder="A sentence or two is plenty."
          rows={3}
          maxLength={400}
          data-testid="sandbox-v2-welcome-hope"
          style={{ ...inputStyle, fontFamily: FONT.GEORGIA, resize: "vertical" }}
        />
      </Field>

      {error && (
        <div
          role="alert"
          style={{
            margin: "24px 0 0",
            padding: 12,
            color: TOKEN.ACCENT_DARK,
            border: `1px solid ${TOKEN.ACCENT_DARK}`,
            background: TOKEN.LIGHT,
            fontFamily: FONT.CALIBRI,
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      <div style={{ marginTop: 40, textAlign: "center" }}>
        <button
          type="submit"
          disabled={busy}
          data-testid="sandbox-v2-welcome-submit"
          aria-busy={busy ? "true" : undefined}
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 15,
            background: busy ? TOKEN.RULE : TOKEN.ACCENT_DARK,
            color: TOKEN.LIGHT,
            border: "none",
            padding: "14px 36px",
            cursor: busy ? "not-allowed" : "pointer",
            borderRadius: 2,
            letterSpacing: 0.5,
          }}
        >
          {busy ? "…" : "Begin"}
        </button>
      </div>
      <div
        style={{
          marginTop: 24,
          textAlign: "center",
          fontFamily: FONT.CALIBRI,
          fontSize: 11,
          color: TOKEN.MUTED,
        }}
      >
        We don't ask for an email yet. You can stop at any step.
      </div>
    </form>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 26 }}>
      <label
        style={{
          display: "block",
          fontFamily: FONT.CALIBRI,
          fontSize: 12,
          textTransform: "uppercase",
          letterSpacing: 1.4,
          color: TOKEN.DEEP,
          marginBottom: 8,
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

function Picker({ options, value, onChange, testId }) {
  return (
    <div
      role="radiogroup"
      data-testid={testId}
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
        gap: 8,
      }}
    >
      {options.map((o) => {
        const active = value === o.key;
        return (
          <button
            key={o.key}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.key)}
            data-testid={`${testId}-${o.key}`}
            style={{
              padding: "12px 14px",
              fontFamily: FONT.CALIBRI,
              fontSize: 14,
              textAlign: "left",
              cursor: "pointer",
              border: `1px solid ${active ? TOKEN.INK : TOKEN.RULE}`,
              background: active ? TOKEN.INK : TOKEN.LIGHT,
              color: active ? TOKEN.LIGHT : TOKEN.INK,
              borderRadius: 2,
              transition: "background-color 150ms ease-out, color 150ms ease-out",
            }}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

const inputStyle = {
  width: "100%",
  fontFamily: FONT.CALIBRI,
  fontSize: 16,
  padding: "14px 14px",
  border: `1px solid ${TOKEN.RULE}`,
  borderRadius: 2,
  background: TOKEN.LIGHT,
  color: TOKEN.INK,
  outline: "none",
};

const optionalStyle = { color: TOKEN.MUTED, fontWeight: 400, textTransform: "none", letterSpacing: 0 };
