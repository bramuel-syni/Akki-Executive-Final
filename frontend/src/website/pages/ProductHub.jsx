import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../WebsiteShell";
import "../style.css";

/**
 * Phase J.2 — Product hub. Routes to the 6 surface pages.
 * Pattern B (overview): kicker + headline + dek, then 6 tile cards.
 */
const SURFACES = [
  { slug: "solva",         label: "Solva",          sub: "Structured reasoning, four modes.",      blurb: "Frame audit and audit-gap surfacing before any answer. Refusal artefacts when grounding is thin." },
  { slug: "akki-chat",     label: "Akki Chat",      sub: "Trust-first multi-model chat.",          blurb: "Claude, Gemini, GPT. Every turn appended to a hash-chained audit log with an offline verifier." },
  { slug: "work-studio",   label: "Work Studio",    sub: "Deterministic outputs at board grade.",  blurb: "DOCX, PPTX, PDF. Byte-deterministic, hashed, banned-word grep on every render." },
  { slug: "cycle-manager", label: "Cycle Manager",  sub: "Setup. Run. Ship.",                      blurb: "Board cycle workflow with real outbound email under opaque aliases. Inbound replies thread back in." },
  { slug: "monitor",       label: "Monitor",        sub: "Goals at risk, role-scoped.",            blurb: "Per-role function whitelists. Surfaces signals that match what this role is actually accountable for." },
  { slug: "pulse",         label: "Pulse",          sub: "Quiet attention, never an alarm.",       blurb: "Same-context signal feed plus a metadata-only cross-board view. Comments, lifecycle, take-to-Solva." },
];

export default function ProductHubPage() {
  return (
    <WebsiteShell
      title="Product — six surfaces, one working environment"
      description="Six product surfaces for senior decision work. Solva, Akki Chat, Work Studio, Cycle Manager, Monitor, Pulse — plus Document Journal."
      pathname="/product"
    >
      <section className="website-section">
        <span className="website-label">Product</span>
        <h1>Six surfaces. One working environment.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441", maxWidth: "56ch" }}>
          Each surface is calm by default. Each is in service of a real decision
          you would otherwise be making in a Word document at 9pm.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 18, marginTop: 32 }}>
          {SURFACES.map(s => (
            <Link
              key={s.slug}
              to={`/product/${s.slug}`}
              className="website-tile"
              style={{ textDecoration: "none", color: "inherit", display: "block" }}
              data-testid={`product-tile-${s.slug}`}
            >
              <div style={{ fontSize: 12, letterSpacing: "0.15em", textTransform: "uppercase", color: "#6B7480", marginBottom: 8 }}>
                {s.sub}
              </div>
              <h3>{s.label}</h3>
              <p style={{ fontSize: 15, color: "#2A3441" }}>{s.blurb}</p>
              <p style={{ fontSize: 13, color: "#8B6F3E", fontStyle: "italic", margin: 0, marginTop: 8 }}>Read more →</p>
            </Link>
          ))}
        </div>
      </section>
      <section className="website-section website-section--narrow">
        <Link to="/sandbox" className="website-cta-primary" data-testid="product-hub-cta">
          Try the sandbox
        </Link>
      </section>
    </WebsiteShell>
  );
}
