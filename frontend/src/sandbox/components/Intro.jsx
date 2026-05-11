import React from "react";

export default function SandboxIntro({ onBegin }) {
  return (
    <div className="sb-shell" data-testid="sandbox-intro">
      <span className="sb-label">Akki · sandbox</span>
      <h1>Test Akki in 90 seconds.</h1>
      <span className="sb-rule" />
      <p style={{ fontSize: 20, color: "var(--sb-slate)" }}>
        Tell us a little about you. We will compose a brief working session
        for a fictional organisation that fits, so you can see how Akki
        thinks, what it surfaces, and where it stops.
      </p>
      <p>
        This is not a tour and not a recording. The session is generated
        for you in the next few seconds. Nothing you enter trains anything.
        We retain the session for 24 hours then delete it.
      </p>
      <div style={{ marginTop: 36 }}>
        <button type="button" className="sb-cta-primary" onClick={onBegin} data-testid="sandbox-intro-begin">
          Begin
        </button>
      </div>
    </div>
  );
}
