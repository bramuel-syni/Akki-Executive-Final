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
      description="Three tiers plus organisation pricing. Early-access pricing locked for two years."
      pathname="/pricing"
    >
      <HeroWithLift
        kicker={PRICING.kicker} headline={PRICING.headline} lift={PRICING.lift} dek={PRICING.dek}
        primaryCta={{ label: "Request access", href: "/cohort" }}
        secondaryCta={{ label: "For organisations", href: "/for-organisations" }}
        testId="pricing-page"
      />
      <section className="website-section--narrow section-reveal" data-testid="pricing-table-section">
        <table className="pricing-table" data-testid="pricing-table">
          <thead>
            <tr>
              <th>Tier</th>
              <th>Standard</th>
              <th>Early access (2 yrs)</th>
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
        headline="Request early access."
        body="Twenty executives will use Akki first. Pricing is locked for two years for everyone admitted."
        ctaLabel="Request access" ctaHref="/cohort" meta={INVERTED_CTA.meta}
        testId="pricing-inverted-cta"
      />
    </WebsiteShell>
  );
}
