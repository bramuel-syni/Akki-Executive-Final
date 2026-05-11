/**
 * Website v7 — /cohort  (v7 §10.1 light surface, no form this sprint).
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection } from "../components/PagePrimitives";
import { COHORT, INVERTED_CTA } from "../copy";

export default function Cohort() {
  return (
    <WebsiteShell
      title="Founding cohort — Akki"
      description="A small admitted cohort using Akki first. In exchange for honest feedback, founding price locked for two years."
      pathname="/cohort"
    >
      <HeroWithLift
        kicker={COHORT.kicker}
        headline={COHORT.headline}
        lift={COHORT.lift}
        dek={COHORT.dek}
        testId="cohort-page"
      />
      <section className="website-section--narrow section-reveal" data-testid="cohort-body">
        <p style={{ maxWidth: 70 + "ch", lineHeight: 1.7, color: "var(--graphite)" }}>{COHORT.body}</p>
        <a href={COHORT.cta.href} className="btn-primary btn-hero" style={{ marginTop: 24 }} data-testid="cohort-apply-cta" target="_blank" rel="noopener noreferrer">
          {COHORT.cta.label} →
        </a>
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="Try Akki before you apply."
        body="The sandbox shows the workspace in motion. No data is retained."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="cohort-inverted-cta"
      />
    </WebsiteShell>
  );
}
