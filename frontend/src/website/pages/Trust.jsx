/**
 * Website v7 — /trust  (v7 §9 verbatim).
 *
 * ONLY page where Solva / Synisense / Agent Cycle appear as technical
 * names in marketing copy.
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection, CitationPills } from "../components/PagePrimitives";
import { TRUST, INVERTED_CTA } from "../copy";

export default function Trust() {
  return (
    <WebsiteShell
      title="Trust & Sovereignty — Akki"
      description="Synisense at depth, Solva at depth, Agent Cycle at depth. Memory and provenance. Four architectural commitments, each enforced in code."
      pathname="/trust"
    >
      <HeroWithLift
        kicker={TRUST.kicker} headline={TRUST.headline} lift={TRUST.lift} dek={TRUST.dek}
        primaryCta={{ label: "Read the methodology", href: "/methodology" }}
        secondaryCta={{ label: "See the audit chain", href: "/sandbox" }}
        testId="trust-page"
      />
      {TRUST.pillars.map((pillar, i) => (
        <section
          key={pillar.anchor}
          id={pillar.anchor}
          className="website-section section-reveal"
          data-testid={`trust-pillar-${pillar.anchor}`}
        >
          <p className="kicker">{`PILLAR ${String(i + 1).padStart(2, "0")}`}</p>
          <h2 className="section">{pillar.title}</h2>
          <p className="dek">{pillar.sub}</p>
          <span className="website-rule" />
          <p style={{ maxWidth: 70 + "ch", color: "var(--graphite)", lineHeight: 1.7 }}>
            {pillar.body}
          </p>
          <CitationPills pills={[`${pillar.anchor}.audit.hash`, `${pillar.anchor}.architecture.v1`]} />
        </section>
      ))}
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="See the audit chain on a live conversation."
        body="The sandbox surfaces the same hash-chained pattern that runs in production."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="trust-inverted-cta"
      />
    </WebsiteShell>
  );
}
