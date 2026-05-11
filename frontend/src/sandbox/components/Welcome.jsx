import React from "react";

export default function SandboxWelcome({ session, onContinue }) {
  const profile = (session.artefacts || {}).visitor_profile || {};
  const org = (session.artefacts || {}).fictional_org || {};
  const firstName = (profile.name || "there").split(/\s+/)[0];
  return (
    <div className="sb-shell" data-testid="sandbox-welcome">
      <span className="sb-label">Welcome · fictional working session</span>
      <h1>{firstName}, here is what is happening at {org.name || "the organisation"}.</h1>
      <span className="sb-rule" />
      <p style={{ fontSize: 19, color: "var(--sb-slate)" }}>
        {org.industry ? `${org.industry} · ${org.size_band || ""} — ` : ""}
        {org.situation || "A board cycle in motion, a regulatory consultation in flight, and a senior departure under quiet review."}
      </p>
      <p style={{ color: "var(--sb-muted)" }}>
        You are the {(profile.role || "executive").toLowerCase()}. Take ninety seconds. Akki will
        walk you through four moments that real days are made of.
      </p>
      <div style={{ marginTop: 36 }}>
        <button type="button" className="sb-cta-primary" onClick={onContinue} data-testid="sandbox-welcome-continue">
          Begin the session
        </button>
      </div>
    </div>
  );
}
