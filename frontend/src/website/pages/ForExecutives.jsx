import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../WebsiteShell";
import EvidencePanel from "../components/EvidencePanel";
import "../style.css";

export default function ForExecutivesPage() {
  return (
    <WebsiteShell
      title="For Executives — Akki for CEOs, CFOs, COOs"
      description="How Akki fits the operating executive's working day — cycle prep, board pack analysis, judgement-grade reasoning."
      pathname="/for-executives"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">For executives</span>
        <h1>For the operating executive who runs the cycle.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          Cycle prep that lands. Board pack analysis that doesn't leak. Judgement
          that survives audit.
        </p>
        <h2 style={{ marginTop: 56 }}>Three working moments Akki makes easier.</h2>
        <div style={{ display: "grid", gap: 28, marginTop: 24 }}>
          <div><h3>The Sunday board pack read.</h3><p>Reading View with paragraph anchors, Ask-Akki deep links, and on-demand commentary that respects Privacy Wall scope.</p></div>
          <div><h3>The Friday compilation.</h3><p>Cycle Manager turns contributions and follow-ups into a deterministic brief, validated and audit-tracked, ready for chair sign-off.</p></div>
          <div><h3>The board-paper rework at 9pm.</h3><p>Work Studio enhance — silent Pass 1 reasoning, strict Pass 2 render. The output you would have stayed up writing.</p></div>
        </div>
        <EvidencePanel kind="cycle_agenda" caption="A real cycle agenda close to ship. Reportee aliases are opaque; replies thread back automatically." />

        <p style={{ color: "#6B7480", fontSize: 14, marginTop: 24 }}>
          Read about the choices behind Akki — <Link to="/methodology" className="website-link-inline">Methodology</Link>.
        </p>
        <div style={{ marginTop: 36 }}>
          <Link to="/sandbox" className="website-cta-primary" data-testid="for-executives-cta">Try the sandbox</Link>
        </div>
      </section>
    </WebsiteShell>
  );
}
