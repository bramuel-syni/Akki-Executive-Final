/**
 * Website v7 — /for-non-executive-directors  (v7 §8.2)
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection } from "../components/PagePrimitives";
import { AUDIENCE_PAGES, INVERTED_CTA } from "../copy";
import heroImg from "../assets/v7/for-neds-hero.webp";

export default function ForNeds() {
  const p = AUDIENCE_PAGES["for-non-executive-directors"];
  return (
    <WebsiteShell
      title="For non-executive directors — Akki"
      description="A workspace for the NED sitting on multiple boards. Private reading library per seat, cross-board patterns without content."
      pathname="/for-non-executive-directors"
    >
      <HeroWithLift
        kicker={p.kicker} headline={p.headline} lift={p.lift} dek={p.dek}
        primaryCta={{ label: "Join the founding cohort", href: "/cohort" }}
        secondaryCta={{ label: "See pricing", href: "/pricing" }}
        image={heroImg} imageAlt={p.image_alt}
        testId="for-neds"
      />
      <section className="website-section section-reveal" data-testid="for-neds-moments">
        <p className="kicker">THREE MOMENTS</p>
        <h2 className="section">Where Akki shows up across boards.</h2>
        <span className="website-rule" />
        <div className="three-col">
          {p.moments.map((m, i) => (
            <div key={i} className="three-col-card" data-testid={`for-neds-moment-${i}`}>
              <h3>{m.title}</h3>
              <p style={{ color: "var(--graphite)" }}>{m.body}</p>
            </div>
          ))}
        </div>
        <p className="website-label" style={{ marginTop: 40 }} data-testid="for-neds-pricing-line">
          {p.pricing_line}
        </p>
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="See three questions a Solva pre-board pass surfaces."
        body="The sandbox runs against a synthetic board pack for your sector. Nothing is retained."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="for-neds-inverted-cta"
      />
    </WebsiteShell>
  );
}
