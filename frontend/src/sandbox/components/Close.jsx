import React from "react";
import { Link } from "react-router-dom";

export default function SandboxClose({ session, onRestart }) {
  const art = session.artefacts || {};
  return (
    <div className="sb-shell" data-testid="sandbox-close">
      <span className="sb-label">Close · what you have just seen</span>
      <h1>That was Akki, in 90 seconds.</h1>
      <span className="sb-rule" />
      <p style={{ fontSize: 19, color: "var(--sb-slate)" }}>
        {art.closing_synthesis ||
          "In ninety seconds you have seen Akki frame a question, surface what is worth attention, " +
          "find an inconsistency between two drafts, and show how it lands in the reporting cycle. " +
          "This is one signed-in tenant. It does not train on your data."}
      </p>
      <h2 style={{ marginTop: 48 }}>Two paths from here.</h2>
      <div style={{ marginTop: 24, display: "grid", gap: 24 }}>
        <div className="sb-tile" data-testid="sandbox-close-path-cohort">
          <div className="sb-tile-meta">Founding cohort</div>
          <h3>Join the first twenty.</h3>
          <p className="sb-tile-body">
            Twenty senior executives. Two years of founding pricing. We work with you on the
            implementation; you keep your tenant and your audit trail.
          </p>
          <div style={{ marginTop: 12 }}>
            <Link to="/cohort" className="sb-cta-primary" data-testid="sandbox-close-cohort-cta">
              Request early access
            </Link>
          </div>
        </div>
        <div className="sb-tile" data-testid="sandbox-close-path-session">
          <div className="sb-tile-meta">Working session</div>
          <h3>Bring a real situation.</h3>
          <p className="sb-tile-body">
            A short conversation with the team about a specific board moment you are working
            on. We come prepared.
          </p>
          <div style={{ marginTop: 12 }}>
            <Link to="/contact" className="sb-cta-secondary" data-testid="sandbox-close-session-cta">
              Talk to the team
            </Link>
          </div>
        </div>
      </div>
      <div style={{ marginTop: 48, fontSize: 14, color: "var(--sb-muted)" }}>
        <button type="button"
          onClick={onRestart}
          style={{ background: "none", border: "none", color: "var(--sb-muted)", cursor: "pointer", padding: 0, textDecoration: "underline" }}
          data-testid="sandbox-close-restart">
          Compose another session
        </button>
      </div>
    </div>
  );
}
