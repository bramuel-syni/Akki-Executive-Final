import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../../WebsiteShell";
import EvidencePanel from "../../components/EvidencePanel";
import "../../style.css";

export default function ProductPulsePage() {
  return (
    <WebsiteShell
      title="Pulse — quiet attention, never an alarm"
      description="Same-context signal feed plus a metadata-only cross-board view. Comments, lifecycle, take-to-Solva."
      pathname="/product/pulse"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Product · Pulse</span>
        <h1>What is worth attention right now — not what is loudest.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          Same-context feed inside the workspace. Metadata-only cross-board view
          for non-executives who sit on multiple boards.
        </p>
        <h2 style={{ marginTop: 56 }}>Three commitments inside Pulse.</h2>
        <div style={{ display: "grid", gap: 28, marginTop: 24 }}>
          <div><h3>Quiet by default.</h3><p>Volume cap of seven on the Active tab. Priority sorted by confidence × recency. Never an alarm.</p></div>
          <div><h3>Cross-board metadata only.</h3><p>The cross-board view reads only metadata signatures — regulatory_ref, governance_theme, pulse_class. Foreign signal content is never accessed.</p></div>
          <div><h3>Lifecycle as a first-class thing.</h3><p>Active → Bookmarked → Resolved. Comments scoped per signal. Take into Solva turns a signal into a real working session.</p></div>
        </div>
        <EvidencePanel kind="pulse_card" caption="A live Pulse signal as it appears in the feed. No LLM is invoked during render. Cross-board view never reads foreign signal content." />

        <p style={{ color: "#6B7480", fontSize: 14, marginTop: 24 }}>
          Read about the choices behind Pulse — <Link to="/methodology" className="website-link-inline">Methodology</Link>.
        </p>
        <div style={{ marginTop: 36 }}>
          <Link to="/sandbox" className="website-cta-primary">Try the sandbox</Link>
        </div>
      </section>
    </WebsiteShell>
  );
}
