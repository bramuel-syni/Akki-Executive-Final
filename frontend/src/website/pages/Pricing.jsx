/**
 * Website v7 — /pricing  (v7 §10.2 — REINSTATED).
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection } from "../components/PagePrimitives";
import { PRICING, INVERTED_CTA } from "../copy";

export default function Pricing() {
  return (
    <WebsiteShell
      title="Pricing — Akki"
      description="Three tiers plus organisation pricing. Founding cohort pricing locked for two years."
      pathname="/pricing"
    >
      <HeroWithLift
        kicker={PRICING.kicker} headline={PRICING.headline} lift={PRICING.lift} dek={PRICING.dek}
        primaryCta={{ label: "Join the founding cohort", href: "/cohort" }}
        secondaryCta={{ label: "For organisations", href: "/for-organisations" }}
        testId="pricing-page"
      />
      <section className="website-section--narrow section-reveal" data-testid="pricing-table-section">
        <table className="pricing-table" data-testid="pricing-table">
          <thead>
            <tr>
              <th>Tier</th>
              <th>Standard</th>
              <th>Founding (2 yrs)</th>
            </tr>
          </thead>
          <tbody>
            {PRICING.table.map((row, i) => (
              <tr key={row.tier} data-testid={`pricing-row-${i}`}>
                <td>{row.tier}</td>
                <td>{row.standard}</td>
                <td>{row.founding}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="website-label" style={{ marginTop: 24 }}>{PRICING.footnote}</p>
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="Apply for the founding cohort."
        body="Twenty executives will use Akki first. Pricing is locked for two years for everyone in the cohort."
        ctaLabel="Read about the cohort" ctaHref="/cohort" meta={INVERTED_CTA.meta}
        testId="pricing-inverted-cta"
      />
    </WebsiteShell>
  );
}
