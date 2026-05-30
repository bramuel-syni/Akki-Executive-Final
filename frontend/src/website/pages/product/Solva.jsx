/**
 * Website v7 — /solva
 * v7 §7.2. Synisense, Solva, Agent Cycle named technically — but the
 * lift word here is "Structured" (oxblood italic).
 */
import React from "react";
import WebsiteShell from "../../WebsiteShell";
import { HeroWithLift, InvertedCtaSection, CitationPills } from "../../components/PagePrimitives";
import { PRODUCTS, INVERTED_CTA } from "../../copy";

export default function Solva() {
  const p = PRODUCTS.solva;
  return (
    <WebsiteShell
      title="Solva — Structured reasoning · Akki"
      description="Solva runs a five-layer reasoning pipeline behind every answer: frame audit, candidates, tension, probability weighting, reflection."
      pathname="/solva"
    >
      <HeroWithLift
        kicker={p.kicker}
        headline={p.headline}
        lift={p.lift}
        dek={p.dek}
        primaryCta={{ label: "Try Solva in the sandbox", href: "/sandbox" }}
        secondaryCta={{ label: "How Solva reasons", href: "/methodology#solva" }}
        testId="solva-page"
      />

      <section className="website-section section-reveal" data-testid="solva-modes">
        <p className="kicker">FOUR MODES</p>
        <h2 className="section">Each mode is a faithful answer to a moment in executive thinking.</h2>
        <span className="website-rule" />
        <div className="three-col" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
          {p.modes.map((m, i) => (
            <div key={m.name} className="three-col-card" data-testid={`solva-mode-${i}`}>
              <h3>{m.name}.</h3>
              <p style={{ color: "var(--graphite)" }}>{m.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="website-section section-reveal" data-testid="solva-layers">
        <p className="kicker">FIVE REASONING LAYERS</p>
        <h2 className="section">Same pipeline, every mode. Every layer recorded.</h2>
        <span className="website-rule" />
        <ol style={{ paddingLeft: 24, lineHeight: 1.7, maxWidth: "70ch" }}>
          {p.layers.map((l, i) => (
            <li key={i} style={{ marginBottom: 10 }} data-testid={`solva-layer-${i}`}>{l}</li>
          ))}
        </ol>
        <CitationPills pills={["audit-chain.sha256", "solva.session.trace", "frame-audit.v3"]} />
      </section>

      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="See Solva run on a real frame."
        body="Paste a paragraph from your own work — or generate a synthetic one for your sector. Nothing is retained."
        ctaLabel="Begin sandbox"
        ctaHref="/sandbox"
        meta={INVERTED_CTA.meta}
        testId="solva-inverted-cta"
      />
    </WebsiteShell>
  );
}
