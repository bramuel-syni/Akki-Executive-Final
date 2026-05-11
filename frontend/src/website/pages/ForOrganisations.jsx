/**
 * Website v7 — /for-organisations  (v7 §8.3)
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection } from "../components/PagePrimitives";
import { AUDIENCE_PAGES, INVERTED_CTA } from "../copy";

export default function ForOrganisations() {
  const p = AUDIENCE_PAGES["for-organisations"];
  return (
    <WebsiteShell
      title="For organisations — Akki"
      description="SSO, tenancy, governance reporting. Anonymised reasoning across the whole Exco. $150–$300 per seat."
      pathname="/for-organisations"
    >
      <HeroWithLift
        kicker={p.kicker} headline={p.headline} lift={p.lift} dek={p.dek}
        primaryCta={{ label: "Contact for organisations", href: "/contact?form=organisation" }}
        secondaryCta={{ label: "See pricing", href: "/pricing" }}
        testId="for-organisations"
      />
      <section className="website-section section-reveal" data-testid="for-orgs-moments">
        <p className="kicker">THREE MOMENTS</p>
        <h2 className="section">Where Akki shows up at organisation scale.</h2>
        <span className="website-rule" />
        <div className="three-col">
          {p.moments.map((m, i) => (
            <div key={i} className="three-col-card" data-testid={`for-orgs-moment-${i}`}>
              <h3>{m.title}</h3>
              <p style={{ color: "var(--graphite)" }}>{m.body}</p>
            </div>
          ))}
        </div>
        <p className="website-label" style={{ marginTop: 40 }} data-testid="for-orgs-pricing-line">
          {p.pricing_line}
        </p>
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="Roll Akki out to your senior team."
        body="Tell us about your Exco size and tenancy needs. We reply personally."
        ctaLabel="Contact organisations" ctaHref="/contact?form=organisation" meta={INVERTED_CTA.meta}
        testId="for-orgs-inverted-cta"
      />
    </WebsiteShell>
  );
}
