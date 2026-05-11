/**
 * Website v7 — /for-executives  (v7 §8.1)
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection } from "../components/PagePrimitives";
import { AUDIENCE_PAGES, INVERTED_CTA } from "../copy";
import heroImg from "../assets/v7/for-executives-hero.webp";

export default function ForExecutives() {
  const p = AUDIENCE_PAGES["for-executives"];
  return (
    <WebsiteShell
      title="For executives — Akki"
      description="A workspace for the operating executive running the cycle. CEO, CFO, COO, CRO."
      pathname="/for-executives"
    >
      <HeroWithLift
        kicker={p.kicker} headline={p.headline} lift={p.lift} dek={p.dek}
        primaryCta={{ label: "Join the founding cohort", href: "/cohort" }}
        secondaryCta={{ label: "See pricing", href: "/pricing" }}
        image={heroImg} imageAlt={p.image_alt}
        testId="for-executives"
      />
      <section className="website-section section-reveal" data-testid="for-executives-moments">
        <p className="kicker">THREE MOMENTS</p>
        <h2 className="section">Where Akki shows up in the cycle.</h2>
        <span className="website-rule" />
        <div className="three-col">
          {p.moments.map((m, i) => (
            <div key={i} className="three-col-card" data-testid={`for-executives-moment-${i}`}>
              <h3>{m.title}</h3>
              <p style={{ color: "var(--graphite)" }}>{m.body}</p>
            </div>
          ))}
        </div>
        <p className="website-label" style={{ marginTop: 40 }} data-testid="for-executives-pricing-line">
          {p.pricing_line}
        </p>
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="See your own board pack analysed in sixty seconds."
        body="The sandbox runs Solva against a paragraph from your last board paper. Nothing is retained."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="for-executives-inverted-cta"
      />
    </WebsiteShell>
  );
}
