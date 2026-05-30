/**
 * Website v7 — /why-akki  (v7 §5).
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift, InvertedCtaSection } from "../components/PagePrimitives";
import { WHY, INVERTED_CTA } from "../copy";

export default function WhyAkki() {
  return (
    <WebsiteShell
      title="Why Akki — Executive work has structure"
      description="AI products are mostly built for two-thumb consumers or for engineers. Executive work is neither."
      pathname="/why-akki"
    >
      <HeroWithLift
        kicker={WHY.kicker} headline={WHY.headline} lift={WHY.lift} dek={WHY.dek}
        primaryCta={{ label: "Read the methodology", href: "/methodology" }}
        secondaryCta={{ label: "What Akki does", href: "/what-akki-does" }}
        testId="why-page"
      />
      {WHY.sections.map((s, i) => (
        <section key={i} className="website-section--narrow section-reveal" data-testid={`why-section-${i}`}>
          <p className="kicker">{`COMMITMENT ${String(i + 1).padStart(2, "0")}`}</p>
          <h2 className="section">{s.title}</h2>
          <span className="website-rule" />
          <p style={{ maxWidth: 70 + "ch", lineHeight: 1.7, color: "var(--graphite)" }}>{s.body}</p>
        </section>
      ))}
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker} headline={INVERTED_CTA.headline}
        body={INVERTED_CTA.body} ctaLabel={INVERTED_CTA.cta.label}
        ctaHref={INVERTED_CTA.cta.href} meta={INVERTED_CTA.meta}
        testId="why-inverted-cta"
      />
    </WebsiteShell>
  );
}
