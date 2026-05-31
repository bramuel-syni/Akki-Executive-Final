/**
 * Phase J.4 — Closing step.
 *
 * Brief §7 — three things must happen:
 *
 *   1) "Hope loop": surface the user's `hope` answer back to them.
 *      The structural framing here is brand-aligned scaffolding;
 *      the user-typed string is never re-written. If the user
 *      skipped Hope on Welcome, we surface a generic acknowledgement
 *      keyed off their name.
 *
 *   2) Equal-weight 3-CTA conversion block:
 *        - Demo:        external mailto/scheduling link
 *        - Early access: routes to /early-access
 *        - Save & send: opens an inline form that POSTs the user's
 *          email to /api/sandbox/v2/sessions/{sid}/save-and-send
 *
 *   3) Quiet "Exit Sandbox" return-to-home below the fold.
 *
 * The save-and-send sub-flow surfaces the new `test_mode_restricted`
 * delivery mode the email_service can return and renders the friendly
 * notice rather than a hard error.
 */
import React, { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { TOKEN, FONT } from "./tokens";
import { Actions, writeResumeToken } from "@/lib/sandboxV2Flow";

import { resolveBackendOrigin } from "@/lib/api";
const API = resolveBackendOrigin();
const api = axios.create({
  baseURL: `${API}/api/sandbox/v2`,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

export default function ClosingStep({ flow, dispatch }) {
  const navigate = useNavigate();
  const name = (flow?.welcome?.name || "").trim();
  const hope = (flow?.welcome?.hope || "").trim();
  const sid = flow?.sessionId;

  const [emailDraft, setEmailDraft] = useState(flow?.capturedEmail || "");
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveResult, setSaveResult] = useState(null); // {ok, delivery_mode, message, resume_url}
  const [showSaveForm, setShowSaveForm] = useState(false);

  const submitSaveAndSend = async () => {
    const e = emailDraft.trim();
    if (!e || !sid) return;
    setSaveBusy(true);
    try {
      const r = await api.post(`/sessions/${sid}/save-and-send`, { email: e });
      setSaveResult(r.data);
      dispatch(Actions.captureEmail(e));
    } catch (err) {
      setSaveResult({
        ok: false,
        delivery_mode: "error",
        message: err?.response?.data?.detail || err.message || "Could not save your session.",
      });
    } finally {
      setSaveBusy(false);
    }
  };

  const goExit = () => {
    writeResumeToken(null);
    navigate("/");
  };

  return (
    <div data-testid="sandbox-v2-closing" style={{ width: "100%", padding: "24px 8px 64px" }}>
      <div style={{ width: 56, height: 1, background: TOKEN.ACCENT, margin: "0 auto 28px" }} />

      <h1 style={{
        fontFamily: FONT.GEORGIA, fontSize: 32, fontWeight: 700,
        color: TOKEN.INK, textAlign: "center", margin: "0 0 16px 0", lineHeight: 1.2,
      }}>
        This is Akki.
      </h1>

      <HopeLoop name={name} hope={hope} />

      <div style={{
        margin: "44px auto 0", maxWidth: 640,
        fontFamily: FONT.GEORGIA, fontStyle: "italic", fontSize: 15,
        color: TOKEN.MUTED, textAlign: "center", lineHeight: 1.6,
      }}>
        Three things you can do next. Pick whichever fits.
      </div>

      <div style={ctaRowStyle}>
        <CtaCard
          testId="sandbox-v2-cta-demo"
          kicker="Talk to us"
          title="Book a demo"
          body="Thirty minutes with the team — your context, your questions."
          actionLabel="Book a demo \u2192"
          onClick={() => {
            // External scheduling link. mailto fallback so the CTA never dead-ends.
            window.open("mailto:hello@akki.ai?subject=Akki%20demo%20request", "_self");
          }}
          variant="ghost"
        />
        <CtaCard
          testId="sandbox-v2-cta-early-access"
          kicker="Get the product"
          title="Request early access"
          body="Join the cohort already running their boards on Akki."
          actionLabel="Request access \u2192"
          onClick={() => navigate("/early-access")}
          variant="ghost"
        />
        <CtaCard
          testId="sandbox-v2-cta-save"
          kicker="Take it with you"
          title="Save and send"
          body="Email yourself the resume link — and a copy of what Solva produced."
          actionLabel={showSaveForm ? "Hide \u2191" : "Save and send \u2192"}
          onClick={() => setShowSaveForm((v) => !v)}
          variant="primary"
        />
      </div>

      {showSaveForm && (
        <SaveAndSendForm
          email={emailDraft}
          setEmail={setEmailDraft}
          busy={saveBusy}
          onSubmit={submitSaveAndSend}
          result={saveResult}
        />
      )}

      <div style={{ marginTop: 56, textAlign: "center" }}>
        <button
          type="button"
          onClick={goExit}
          data-testid="sandbox-v2-closing-exit"
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 12,
            color: TOKEN.MUTED,
            background: "transparent",
            border: "none",
            textDecoration: "underline",
            textUnderlineOffset: 4,
            cursor: "pointer",
            padding: 0,
          }}
        >
          Exit Sandbox
        </button>
      </div>
    </div>
  );
}

function HopeLoop({ name, hope }) {
  if (hope) {
    return (
      <div
        role="note"
        data-testid="sandbox-v2-hope-loop"
        style={{
          margin: "16px auto 0",
          maxWidth: 600,
          textAlign: "center",
          fontFamily: FONT.GEORGIA,
          fontSize: 17,
          color: TOKEN.DEEP,
          lineHeight: 1.65,
        }}
      >
        <p style={{ margin: 0, fontStyle: "italic" }}>
          {name ? `${name}, when you started you said you wanted` : "When you started you said you wanted"}
        </p>
        <p
          style={{
            margin: "10px 0 0",
            padding: "12px 18px",
            background: TOKEN.PAPER,
            borderLeft: `2px solid ${TOKEN.ACCENT}`,
            color: TOKEN.INK,
            fontStyle: "normal",
            textAlign: "left",
            display: "inline-block",
          }}
        >
          {hope}
        </p>
        <p style={{ margin: "14px 0 0", fontStyle: "italic" }}>
          What you just saw was Akki working against that hope. The
          architecture is real; the data was calibrated to you.
        </p>
      </div>
    );
  }
  return (
    <p
      data-testid="sandbox-v2-hope-loop"
      style={{
        margin: "8px auto 0",
        maxWidth: 600,
        textAlign: "center",
        fontFamily: FONT.GEORGIA,
        fontStyle: "italic",
        fontSize: 17,
        color: TOKEN.DEEP,
        lineHeight: 1.65,
      }}
    >
      {name ? `${name}, ` : ""}what you just saw was a calibrated demonstration.
      The architecture is real — every surface ships in production today.
    </p>
  );
}

function CtaCard({ testId, kicker, title, body, actionLabel, onClick, variant = "ghost" }) {
  const isPrimary = variant === "primary";
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      style={{
        flex: "1 1 240px",
        minWidth: 240,
        maxWidth: 320,
        background: isPrimary ? TOKEN.ACCENT_DARK : TOKEN.LIGHT,
        color: isPrimary ? TOKEN.LIGHT : TOKEN.INK,
        border: isPrimary ? "none" : `1px solid ${TOKEN.RULE}`,
        textAlign: "left",
        padding: "20px 22px",
        cursor: "pointer",
        borderRadius: 2,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        fontFamily: FONT.CALIBRI,
        transition: "background-color 150ms ease-out",
      }}
    >
      <span style={{
        fontSize: 11,
        textTransform: "uppercase",
        letterSpacing: 1.4,
        color: isPrimary ? TOKEN.LIGHT : TOKEN.MUTED,
        opacity: isPrimary ? 0.85 : 1,
      }}>
        {kicker}
      </span>
      <span style={{
        fontFamily: FONT.GEORGIA,
        fontSize: 19,
        fontWeight: 700,
        color: "inherit",
        lineHeight: 1.25,
      }}>
        {title}
      </span>
      <span style={{
        fontFamily: FONT.GEORGIA,
        fontSize: 14,
        fontStyle: "italic",
        lineHeight: 1.5,
        color: isPrimary ? TOKEN.LIGHT : TOKEN.DEEP,
        opacity: isPrimary ? 0.92 : 1,
      }}>
        {body}
      </span>
      <span style={{
        marginTop: 10,
        fontSize: 13,
        letterSpacing: 0.4,
        textDecoration: "underline",
        textUnderlineOffset: 3,
      }}>
        {actionLabel}
      </span>
    </button>
  );
}

function SaveAndSendForm({ email, setEmail, busy, onSubmit, result }) {
  return (
    <div
      data-testid="sandbox-v2-save-form"
      style={{
        margin: "28px auto 0",
        maxWidth: 560,
        background: TOKEN.LIGHT,
        border: `1px solid ${TOKEN.RULE}`,
        padding: "20px 22px",
        borderRadius: 2,
      }}
    >
      <div style={{
        fontFamily: FONT.CALIBRI, fontSize: 11, textTransform: "uppercase",
        letterSpacing: 1.4, color: TOKEN.MUTED, marginBottom: 10,
      }}>
        Email yourself the resume link
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@company.com"
          data-testid="sandbox-v2-save-email"
          style={{
            flex: 1,
            minWidth: 220,
            fontFamily: FONT.CALIBRI,
            fontSize: 14,
            padding: "10px 12px",
            border: `1px solid ${TOKEN.RULE}`,
            borderRadius: 2,
            background: TOKEN.LIGHT,
            color: TOKEN.INK,
            outline: "none",
          }}
        />
        <button
          type="button"
          onClick={onSubmit}
          disabled={busy || !email.trim()}
          data-testid="sandbox-v2-save-submit"
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 13,
            background: busy || !email.trim() ? TOKEN.RULE : TOKEN.INK,
            color: TOKEN.LIGHT,
            border: "none",
            padding: "10px 18px",
            cursor: busy || !email.trim() ? "not-allowed" : "pointer",
            borderRadius: 2,
            letterSpacing: 0.4,
          }}
        >
          {busy ? "Saving…" : "Send"}
        </button>
      </div>
      {result && <SaveResult result={result} />}
    </div>
  );
}

function SaveResult({ result }) {
  const mode = result.delivery_mode || (result.ok ? "sent" : "error");
  const isOk = result.ok && mode === "sent";
  const isNoop = mode === "noop";
  const isRestricted = mode === "test_mode_restricted";

  let body;
  if (isOk) {
    body = (
      <>
        We sent you a link. Check your inbox — your session is preserved for 7 days.
      </>
    );
  } else if (isRestricted) {
    body = (
      <>
        {result.message
          || "Resend is in test mode in this environment, so we can only deliver to the registered test address."}
        {" "}
        {result.resume_url && (
          <>Bookmark your resume link: <a href={result.resume_url}>{result.resume_url}</a>.</>
        )}
      </>
    );
  } else if (isNoop) {
    body = (
      <>
        Your session is saved for 7 days. Email isn't wired in this environment, so
        bookmark your resume link: <a href={result.resume_url}>{result.resume_url}</a>.
      </>
    );
  } else {
    body = (
      <>
        {result.message || "Email didn't go through, but your session is saved. "}
        {result.resume_url && (
          <>Resume here: <a href={result.resume_url}>{result.resume_url}</a>.</>
        )}
      </>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid={`sandbox-v2-save-result-${mode}`}
      style={{
        marginTop: 16,
        padding: 12,
        background: isOk ? TOKEN.CREAM : TOKEN.LIGHT,
        border: `1px solid ${isRestricted || (!isOk && !isNoop) ? TOKEN.ACCENT_DARK : TOKEN.RULE}`,
        fontFamily: FONT.GEORGIA,
        fontSize: 13,
        fontStyle: "italic",
        color: TOKEN.DEEP,
        lineHeight: 1.6,
        borderRadius: 2,
      }}
    >
      {body}
    </div>
  );
}

const ctaRowStyle = {
  marginTop: 32,
  display: "flex",
  gap: 16,
  justifyContent: "center",
  flexWrap: "wrap",
  alignItems: "stretch",
};
