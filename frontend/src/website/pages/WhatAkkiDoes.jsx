/**
 * Website v7 — /what-akki-does  (v7 §6 — product overview).
 * "Product" in the top nav routes here.
 */
import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection } from "../components/PagePrimitives";
import { WHAT_AKKI_DOES, INVERTED_CTA } from "../copy";

export default function WhatAkkiDoes() {
  return (
    <WebsiteShell
      title="What Akki does — Seven surfaces, one workspace"
      description="A workspace for senior people. Solva, Akki Chat, Work Studio, Cycle Manager, Monitor, Pulse, Document Journal."
      pathname="/what-akki-does"
    >
      <HeroWithLift
        kicker={WHAT_AKKI_DOES.kicker} headline={WHAT_AKKI_DOES.headline}
        lift={WHAT_AKKI_DOES.lift} dek={WHAT_AKKI_DOES.dek}
        primaryCta={{ label: "Try the sandbox", href: "/sandbox" }}
        secondaryCta={{ label: "Why Akki", href: "/why-akki" }}
        testId="what-page"
      />
      <section className="website-section section-reveal" data-testid="what-surfaces">
        <p className="kicker">SEVEN SURFACES</p>
        <h2 className="section">Each surface answers a recurring moment in senior work.</h2>
        <span className="website-rule" />
        <div className="three-col">
          {WHAT_AKKI_DOES.surfaces.map((s) => (
            <div key={s.slug} className="three-col-card" data-testid={`what-surface-${s.slug}`}>
              <h3>{s.name}.</h3>
              <p style={{ fontStyle: "italic", color: "var(--graphite)", marginBottom: 8 }}>{s.sub}</p>
              <p style={{ color: "var(--graphite)" }}>{s.body}</p>
              <Link to={s.href} className="btn-tertiary">Read about {s.name} →</Link>
            </div>
          ))}
        </div>
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker} headline={INVERTED_CTA.headline}
        body={INVERTED_CTA.body} ctaLabel={INVERTED_CTA.cta.label}
        ctaHref={INVERTED_CTA.cta.href} meta={INVERTED_CTA.meta}
        testId="what-inverted-cta"
      />
    </WebsiteShell>
  );
}
