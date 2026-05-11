import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../../WebsiteShell";
import EvidencePanel from "../../components/EvidencePanel";
import "../../style.css";

export default function ProductWorkStudioPage() {
  return (
    <WebsiteShell
      title="Work Studio — deterministic board-grade outputs"
      description="DOCX, PPTX, PDF — byte-deterministic, hashed, banned-word grep on every render."
      pathname="/product/work-studio"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Product · Work Studio</span>
        <h1>Boardpacks that audit themselves.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          Brand-grade DOCX, PPTX and PDF. Byte-deterministic, every render hashed,
          banned-word grep on every output.
        </p>
        <h2 style={{ marginTop: 56 }}>Discipline by construction.</h2>
        <div style={{ display: "grid", gap: 28, marginTop: 24 }}>
          <div><h3>Deterministic.</h3><p>Two renders, same input, same bytes. The SHA-256 is persisted with every export.</p></div>
          <div><h3>Sensitivity-scored.</h3><p>Every output is auto-classified — PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED — by a deterministic scorer.</p></div>
          <div><h3>Cross-document validation.</h3><p>An independent second-pass validator catches numeric inconsistencies before the chair sees them.</p></div>
        </div>

        <EvidencePanel kind="work_studio_diff" caption="A cross-document inconsistency surfaced before sign-off. Anonymised; the live flag includes byte hashes and validator notes." />

        <p style={{ color: "#6B7480", fontSize: 14, marginTop: 24 }}>
          Read about the choices behind Work Studio — <Link to="/methodology" className="website-link-inline">Methodology</Link>.
        </p>
        <div style={{ marginTop: 36 }}>
          <Link to="/sandbox" className="website-cta-primary">Try the sandbox</Link>
        </div>
      </section>
    </WebsiteShell>
  );
}
