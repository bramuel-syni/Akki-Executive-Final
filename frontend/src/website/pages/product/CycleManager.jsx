import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../../WebsiteShell";
import EvidencePanel from "../../components/EvidencePanel";
import "../../style.css";

export default function ProductCyclePage() {
  return (
    <WebsiteShell
      title="Cycle Manager — Setup. Run. Ship."
      description="Board cycle workflow with real outbound email under opaque aliases. Inbound replies thread back into the cycle."
      pathname="/product/cycle-manager"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Product · Cycle Manager</span>
        <h1>Setup. Run. Ship.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          The board cycle workflow as it actually runs — agenda, team, contributions,
          follow-ups, compilation, ship.
        </p>
        <h2 style={{ marginTop: 56 }}>Three acts that match the work.</h2>
        <div style={{ display: "grid", gap: 28, marginTop: 24 }}>
          <div><h3>Setup.</h3><p>Agenda and team in one place. Inline edits. Audit-tracked changes. Real reportee invitations under opaque cycle aliases.</p></div>
          <div><h3>Run.</h3><p>Contributions, readiness gate, follow-ups drafted in your own voice and sent under the cycle alias. Replies thread back automatically.</p></div>
          <div><h3>Ship.</h3><p>Compilation triggers a Work Studio brief, the brief renders deterministic DOCX, and the cycle closes with an audit trail anyone can verify.</p></div>
        </div>

        <EvidencePanel kind="cycle_agenda" caption="A live cycle agenda in production form. Aliases are deterministic UUIDv5 per reportee — reply addresses are opaque." />

        <p style={{ color: "#6B7480", fontSize: 14, marginTop: 24 }}>
          Read about the choices behind Cycle Manager — <Link to="/methodology" className="website-link-inline">Methodology</Link>.
        </p>
        <div style={{ marginTop: 36 }}>
          <Link to="/sandbox" className="website-cta-primary">Try the sandbox</Link>
        </div>
      </section>
    </WebsiteShell>
  );
}
