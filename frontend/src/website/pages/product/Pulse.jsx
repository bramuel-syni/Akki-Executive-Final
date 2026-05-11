/**
 * Website v7 — /pulse
 */
import React from "react";
import WebsiteShell from "../../WebsiteShell";
import { HeroWithLift, InvertedCtaSection, CitationPills } from "../../components/PagePrimitives";
import { PRODUCTS, INVERTED_CTA } from "../../copy";

export default function Pulse() {
  const p = PRODUCTS.pulse;
  return (
    <WebsiteShell
      title="Pulse — Quiet signals with confidence floors"
      description="A restrained feed for the noise of operating life. Cross-board patterns visible, never cross-board content."
      pathname="/pulse"
    >
      <HeroWithLift
        kicker={p.kicker} headline={p.headline} lift={p.lift} dek={p.dek}
        primaryCta={{ label: "See Pulse in motion", href: "/sandbox" }}
        secondaryCta={{ label: "How signals are scored", href: "/methodology#pulse" }}
        testId="pulse-page"
      />
      <section className="website-section section-reveal" data-testid="pulse-bullets">
        <p className="kicker">HOW PULSE FILTERS</p>
        <h2 className="section">Less, but cleaner.</h2>
        <span className="website-rule" />
        <ul style={{ listStyle: "none", padding: 0, maxWidth: 70 + "ch" }}>
          {p.bullets.map((b, i) => (
            <li key={i} style={{ marginBottom: 16, paddingLeft: 22, position: "relative" }} data-testid={`pulse-bullet-${i}`}>
              <span style={{ position: "absolute", left: 0, top: 12, width: 12, height: 1.5, background: "var(--oxblood)" }} />
              {b}
            </li>
          ))}
        </ul>
        <CitationPills pills={["pulse.confidence.floor", "pulse.lifecycle.state"]} />
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="See Pulse score a quiet signal against a confidence floor."
        body="The sandbox shows the same lifecycle and reasoning that runs across boards in production."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="pulse-inverted-cta"
      />
    </WebsiteShell>
  );
}
