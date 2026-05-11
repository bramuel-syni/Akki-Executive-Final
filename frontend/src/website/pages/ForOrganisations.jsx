import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../WebsiteShell";
import EvidencePanel from "../components/EvidencePanel";
import "../style.css";

export default function ForOrgsPage() {
  return (
    <WebsiteShell
      title="For organisations — Akki for funds and leadership teams"
      description="For organisations rolling Akki out to a leadership team or a portfolio. SSO, tenancy controls, dedicated Solva tuning."
      pathname="/for-organisations"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">For organisations</span>
        <h1>For organisations rolling Akki out to a leadership team or a portfolio.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          SSO. Tenancy controls. Dedicated Solva tuning. Governance reporting on use.
        </p>
        <h2 style={{ marginTop: 56 }}>What organisations get.</h2>
        <div style={{ display: "grid", gap: 28, marginTop: 24 }}>
          <div><h3>One tenant per company, no comingling.</h3><p>Each company is a hard-isolated tenant. The wall projects every cross-tenant query through the field-projection guard.</p></div>
          <div><h3>Company Secretary sharing model.</h3><p>The CoSec can prepare a board pack for an entire ExCo and the chair without any model retraining and without cross-tenant exposure.</p></div>
          <div><h3>Governance reporting on use.</h3><p>Audit-tracked rollout. Per-account telemetry on what Akki was used for, by whom, when — surfaced for governance committees.</p></div>
        </div>
        <EvidencePanel kind="audit_log" caption="A slice of the hash-chained audit log. Auditors verify the chain end-to-end with a single Python file." />

        <p style={{ color: "#6B7480", fontSize: 14, marginTop: 24 }}>
          Read about the choices behind multi-tenancy — <Link to="/methodology" className="website-link-inline">Methodology</Link>.
        </p>
        <div style={{ marginTop: 36 }}>
          <Link to="/sandbox" className="website-cta-primary" data-testid="for-orgs-cta">Try the sandbox</Link>
        </div>
      </section>
    </WebsiteShell>
  );
}
