/**
 * Website v7 — /cycle-manager
 * v7 §7.5.
 */
import React from "react";
import WebsiteShell from "../../WebsiteShell";
import { HeroWithLift, InvertedCtaSection, CitationPills } from "../../components/PagePrimitives";
import { PRODUCTS, INVERTED_CTA } from "../../copy";

export default function CycleManager() {
  const p = PRODUCTS["cycle-manager"];
  return (
    <WebsiteShell
      title="Cycle Manager — The work between meetings"
      description="Setup the agenda. Build the team. Score contributions. Send follow-ups under opaque alias. Compile the next pack."
      pathname="/cycle-manager"
    >
      <HeroWithLift
        kicker={p.kicker} headline={p.headline} lift={p.lift} dek={p.dek}
        primaryCta={{ label: "See a cycle compile", href: "/sandbox" }}
        secondaryCta={{ label: "How Agent Cycle works", href: "/trust#agent-cycle" }}
        testId="cycle-page"
      />
      <section className="website-section section-reveal" data-testid="cycle-steps">
        <p className="kicker">SIX STEPS</p>
        <h2 className="section">The cycle runs in steady passes, signed by you.</h2>
        <span className="website-rule" />
        <ol style={{ paddingLeft: 24, lineHeight: 1.7, maxWidth: 70 + "ch" }}>
          {p.steps.map((s, i) => (
            <li key={i} style={{ marginBottom: 10 }} data-testid={`cycle-step-${i}`}>{s}</li>
          ))}
        </ol>
        <CitationPills pills={["cycle.alias.opaque", "inbound.thread.routing", "scoreboard.contribution"]} />
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="See Cycle Manager prepare for a meeting that hasn't happened yet."
        body="The sandbox composes a sample agenda, scores a hypothetical contribution, and renders the next pack."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="cycle-inverted-cta"
      />
    </WebsiteShell>
  );
}
