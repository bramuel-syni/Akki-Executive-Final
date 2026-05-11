import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../WebsiteShell";
import EvidencePanel from "../components/EvidencePanel";
import "../style.css";

export default function ForNedsPage() {
  return (
    <WebsiteShell
      title="For Non-Executive Directors — Akki for chairs and NEDs"
      description="Cross-board attention without leakage. Personal memory for the boards you sit on. A peer voice, not a vendor."
      pathname="/for-non-executive-directors"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">For non-executive directors</span>
        <h1>For the chair and the non-executive who sits on multiple boards.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          Cross-board attention without leakage. Personal memory scoped to your
          account. A peer voice, never a vendor pitch.
        </p>
        <h2 style={{ marginTop: 56 }}>What Akki commits to non-executives.</h2>
        <div style={{ display: "grid", gap: 28, marginTop: 24 }}>
          <div><h3>Hard separation, by construction.</h3><p>You cannot accidentally leak between the boards you sit on. The Privacy Wall enforces it in code, not in policy.</p></div>
          <div><h3>Cross-board metadata only.</h3><p>The cross-board pulse view reads regulatory and governance signatures — never foreign signal content.</p></div>
          <div><h3>NED-voice followups.</h3><p>When the NED phase calls for an outbound, the system speaks in a peer-board register — not in vendor copy.</p></div>
        </div>
        <EvidencePanel kind="pulse_card" caption="A Pulse signal scoped to one board. The cross-board view shows only metadata signatures, never the signal body." />

        <p style={{ color: "#6B7480", fontSize: 14, marginTop: 24 }}>
          Read about the choices behind the wall — <Link to="/methodology" className="website-link-inline">Methodology</Link>.
        </p>
        <div style={{ marginTop: 36 }}>
          <Link to="/sandbox" className="website-cta-primary" data-testid="for-neds-cta">Try the sandbox</Link>
        </div>
      </section>
    </WebsiteShell>
  );
}
