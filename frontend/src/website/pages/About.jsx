/**
 * Website v7 — /about  (v7 §10.3, text-only, no platitudes, no stock photos).
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection } from "../components/PagePrimitives";
import { ABOUT, INVERTED_CTA } from "../copy";

export default function About() {
  return (
    <WebsiteShell
      title="About — Akki"
      description="Akki is built by operators in Nairobi who have spent decades inside the kinds of organisations Akki serves."
      pathname="/about"
    >
      <HeroWithLift
        kicker={ABOUT.kicker} headline={ABOUT.headline} lift={ABOUT.lift} dek={ABOUT.dek}
        testId="about-page"
      />
      <section className="website-section--narrow section-reveal" data-testid="about-body">
        {ABOUT.body.map((p, i) => (
          <p key={i} style={{ maxWidth: 70 + "ch", lineHeight: 1.7, color: "var(--graphite)", marginBottom: 20 }}>
            {p}
          </p>
        ))}
      </section>
      <section className="website-section--narrow section-reveal" data-testid="about-roles">
        <p className="kicker">NAMED ROLES</p>
        <h2 className="section">Who you reach.</h2>
        <span className="website-rule" />
        <div className="three-col">
          {ABOUT.named_roles.map((r, i) => (
            <div key={i} className="three-col-card" data-testid={`about-role-${i}`}>
              <h3>{r.role}</h3>
              <p>
                <a href={`mailto:${r.contact}`} className="website-link-inline">{r.contact}</a>
              </p>
            </div>
          ))}
        </div>
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="Try the sandbox before you write."
        body="The sandbox shows what we build. We read every application personally afterwards."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="about-inverted-cta"
      />
    </WebsiteShell>
  );
}
