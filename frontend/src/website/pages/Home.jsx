import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../WebsiteShell";
import EvidencePanel from "../components/EvidencePanel";
import heroImg from "../assets/hero-library.jpg";
import "../style.css";

/**
 * Phase J.2 — Home page restructured per Website Experience
 * Architecture v1 §2.A (Pattern A: Home).
 * The 5 Layers, in order:
 *   L1: Kicker + Headline + Italic Dek
 *   L2: Three-Point Argument (Safety / Workspace / Inventions)
 *   L3: Evidence Panel (Solva reasoning trace excerpt + chat audit strip + Pulse signal)
 *   L4: Methodology link (muted, leads to /methodology)
 *   L5: ONE primary CTA per viewport
 */
export default function HomePage() {
  return (
    <WebsiteShell
      title="Akki — for senior people who want to use AI fully, without governance exposure."
      description="A private working environment for operating executives and NEDs. Use AI on the work that actually matters — with full audit trail and no training-data exposure."
      pathname="/"
    >
      {/* L1 — Kicker + Headline + Dek */}
      <section className="website-section" style={{ paddingBottom: 24 }}>
        <span className="website-label">For senior people</span>
        <h1 style={{ maxWidth: "22ch" }}>For senior people who want to use AI fully — without governance exposure.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, 'Times New Roman', serif", fontStyle: "italic", fontSize: 18, color: "#2A3441", maxWidth: "56ch" }}>
          Akki gives operating executives and non-executive directors a private,
          audit-defensible way to think with AI on the work that actually matters.
        </p>
        <img
          src={heroImg} alt="" aria-hidden="true"
          width={2000} height={1125}
          style={{
            display: "block", width: "100%", height: "auto",
            maxHeight: 480, objectFit: "cover", marginTop: 32,
            borderTop: "1px solid #D8D2C5", borderBottom: "1px solid #D8D2C5",
          }}
          data-testid="home-hero-image"
        />
      </section>

      {/* L2 — Three-Point Argument */}
      <section className="website-section website-section--paper">
        <span className="website-label">Three commitments</span>
        <h2>Safety. Workspace. Inventions.</h2>
        <span className="website-rule" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 36, marginTop: 24 }}>
          <div data-testid="home-tier-safety">
            <span className="website-label" style={{ marginBottom: 0 }}>01 · Safety</span>
            <h3>Sovereign by construction.</h3>
            <p style={{ fontSize: 16 }}>
              Prompts and documents are de-identified by a three-layer engine before any
              model sees them. Every reasoning step is auditable. Your data does not train
              anything.
            </p>
          </div>
          <div data-testid="home-tier-workspace">
            <span className="website-label" style={{ marginBottom: 0 }}>02 · Workspace</span>
            <h3>A working environment, not a chat box.</h3>
            <p style={{ fontSize: 16 }}>
              Document Journal. Cycle Manager. Work Studio. Pulse. Six surfaces that match
              how senior decisions actually get made — together, over weeks, across boards.
            </p>
          </div>
          <div data-testid="home-tier-inventions">
            <span className="website-label" style={{ marginBottom: 0 }}>03 · Inventions</span>
            <h3>Two original tools you cannot get elsewhere.</h3>
            <p style={{ fontSize: 16 }}>
              Synisense Shield, a three-layer de-identification engine. Solva, a
              multi-mode reasoning surface. Both built for the way executives and
              NEDs actually think.
            </p>
          </div>
        </div>
      </section>

      {/* L3 — Evidence Panel (REAL artefacts, not marketing mockups) */}
      <section className="website-section">
        <span className="website-label">Evidence — not a screenshot tour</span>
        <h2>What it looks like in practice.</h2>
        <span className="website-rule" />
        <EvidencePanel
          kind="solva_trace"
          caption="A Solva reasoning excerpt before any answer is drafted. Anonymised; the live trace persists with hash-chained provenance."
          testId="home-evidence-solva"
        />
        <EvidencePanel
          kind="chat_audit"
          caption="The audit metric strip live in Akki Chat. Counts come from db.synisense_runs and update as redactions accumulate."
          testId="home-evidence-audit"
        />
        <EvidencePanel
          kind="pulse_card"
          caption="A Pulse signal as it appears in the feed. No LLM is invoked in the render. Cross-board view never reads foreign signal content."
          testId="home-evidence-pulse"
        />
      </section>

      {/* L4 — Methodology link, muted */}
      <section className="website-section website-section--narrow" style={{ paddingTop: 16, paddingBottom: 16 }}>
        <p style={{ color: "#6B7480", fontSize: 14 }}>
          Read about how Akki is built and the choices behind it — <Link to="/methodology" className="website-link-inline" data-testid="home-methodology-link">Methodology</Link>.
        </p>
      </section>

      {/* L5 — ONE primary CTA */}
      <section className="website-section website-section--narrow" style={{ paddingTop: 16 }}>
        <span className="website-label">See it for yourself</span>
        <h2 style={{ fontSize: 28 }}>Compose a fictional working session in ninety seconds.</h2>
        <span className="website-rule" />
        <Link to="/sandbox" className="website-cta-primary" style={{ marginTop: 12 }} data-testid="home-cta-primary">
          Try the sandbox
        </Link>
      </section>
    </WebsiteShell>
  );
}
