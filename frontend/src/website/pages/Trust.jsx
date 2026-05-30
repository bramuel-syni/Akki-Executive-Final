/**
 * Website v7 — /trust  (v7 §9 verbatim + M.3 dispatch 18 additions).
 *
 * ONLY page where Solva / Synisense / Agent Cycle appear as technical
 * names in marketing copy.
 *
 * M.3 (2026-02) adds two appended sections:
 *   • Public velocity tile (PublicVelocityTile) reading
 *     `/api/public/observability/reasoning_velocity?window=30d`.
 *   • Architectural commitments block — "what Akki will never do".
 *
 * Per user directive, the existing v7 pillars are NOT touched.
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection, CitationPills } from "../components/PagePrimitives";
import PublicVelocityTile from "../components/PublicVelocityTile";
import { TRUST, INVERTED_CTA } from "../copy";

// Locked architectural commitments — voice-clean, UK English, no banned vocab.
// Each line begins with "Akki refuses" to mirror the hero verb.
const COMMITMENTS = [
  "Akki refuses to train on your data.",
  "Akki refuses to send raw personal identifiers to model providers.",
  "Akki refuses to claim what it cannot source.",
];

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

      <PublicVelocityTile />

      <section
        className="website-section section-reveal"
        data-testid="trust-commitments"
      >
        <p className="kicker">ARCHITECTURAL COMMITMENTS</p>
        <h2 className="section">What Akki will never do.</h2>
        <ul style={{ maxWidth: 70 + "ch", color: "var(--ink)", lineHeight: 1.9, paddingLeft: 0, listStyle: "none" }}>
          {COMMITMENTS.map((line, i) => (
            <li
              key={i}
              data-testid={`trust-commitment-${i + 1}`}
              style={{ paddingLeft: 16, borderLeft: "2px solid var(--ned-purple, #5a3a82)", marginBottom: 12 }}
            >
              {line}
            </li>
          ))}
        </ul>
      </section>

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
