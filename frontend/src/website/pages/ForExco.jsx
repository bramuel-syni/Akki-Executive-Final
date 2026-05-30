/**
 * Website v7 — /for-exco
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection } from "../components/PagePrimitives";
import { AUDIENCE_PAGES, INVERTED_CTA } from "../copy";

export default function ForExco() {
  const p = AUDIENCE_PAGES["for-exco"];
  return (
    <WebsiteShell
      title="For Exco — Akki"
      description="A workspace for the executive committee preparing what the board will read."
      pathname="/for-exco"
    >
      <HeroWithLift
        kicker={p.kicker} headline={p.headline} lift={p.lift} dek={p.dek}
        primaryCta={{ label: "Join the founding cohort", href: "/cohort" }}
        secondaryCta={{ label: "How the workspace works", href: "/what-akki-does" }}
        testId="for-exco"
      />
      <section className="website-section section-reveal" data-testid="for-exco-moments">
        <p className="kicker">THREE MOMENTS</p>
        <h2 className="section">Where Akki shows up across the leadership team.</h2>
        <span className="website-rule" />
        <div className="three-col">
          {p.moments.map((m, i) => (
            <div key={i} className="three-col-card" data-testid={`for-exco-moment-${i}`}>
              <h3>{m.title}</h3>
              <p style={{ color: "var(--graphite)" }}>{m.body}</p>
            </div>
          ))}
        </div>
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="See the workspace hold cross-document consistency."
        body="The sandbox surfaces the kind of mismatch the chair would otherwise find first."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="for-exco-inverted-cta"
      />
    </WebsiteShell>
  );
}
