import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../../WebsiteShell";
import EvidencePanel from "../../components/EvidencePanel";
import "../../style.css";

/**
 * Phase J.2 — Product surface: Solva (Pattern B).
 * L1 kicker+headline+dek · L2 three-point argument · L3 evidence panel
 * · L4 methodology link · L5 one CTA.
 */
export default function ProductSolvaPage() {
  return (
    <WebsiteShell
      title="Solva — structured reasoning for senior decisions"
      description="Solva is the Akki reasoning surface. Four modes, frame audit, refusal artefacts when grounding is thin."
      pathname="/product/solva"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Product · Solva</span>
        <h1>Reasoning with the work, not on top of it.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          Four modes — seek clarity, develop strategy, simulate hypothesis, get
          perspective. Frame audit before any answer.
        </p>

        <h2 style={{ marginTop: 56 }}>Four modes, one disciplined surface.</h2>
        <div style={{ display: "grid", gap: 28, marginTop: 24 }}>
          <div data-testid="solva-l2-modes">
            <h3>Frame audit comes first.</h3>
            <p>Before Solva drafts anything, it tests the frame the user brought. If the framing is ambiguous, that ambiguity is named and recorded — not hidden under a confident-sounding answer.</p>
          </div>
          <div data-testid="solva-l2-refusal">
            <h3>Refusal is a first-class artefact.</h3>
            <p>When the grounding contract fails, Solva refuses to speculate. The refusal itself is a watermarked artefact you can attach to the cycle or send to the chair.</p>
          </div>
          <div data-testid="solva-l2-handoff">
            <h3>Built to hand off.</h3>
            <p>Take to Cycle. Take into Chat. Take into Work Studio. The four modes always end in a place — not in a long scroll of text.</p>
          </div>
        </div>

        <EvidencePanel kind="solva_trace" caption="A Solva trace excerpt from a develop_strategy session, anonymised. The live trace persists with hash-chained provenance." />

        <p style={{ color: "#6B7480", fontSize: 14, marginTop: 24 }}>
          Read about the choices behind Solva — <Link to="/methodology" className="website-link-inline">Methodology</Link>.
        </p>

        <div style={{ marginTop: 36 }}>
          <Link to="/sandbox" className="website-cta-primary" data-testid="solva-cta">Try the sandbox</Link>
        </div>
      </section>
    </WebsiteShell>
  );
}
