/**
 * Website v7 — /monitor
 */
import React from "react";
import WebsiteShell from "../../WebsiteShell";
import { HeroWithLift, InvertedCtaSection, CitationPills } from "../../components/PagePrimitives";
import { PRODUCTS, INVERTED_CTA } from "../../copy";

export default function Monitor() {
  const p = PRODUCTS.monitor;
  return (
    <WebsiteShell
      title="Monitor — Goals at risk, signals filtered"
      description="Strategic goals tracked against where you actually are. Per function, per company. Every figure cites the document."
      pathname="/monitor"
    >
      <HeroWithLift
        kicker={p.kicker} headline={p.headline} lift={p.lift} dek={p.dek}
        primaryCta={{ label: "Walk through Monitor", href: "/sandbox" }}
        secondaryCta={{ label: "Methodology", href: "/methodology#monitor" }}
        testId="monitor-page"
      />
      <section className="website-section section-reveal" data-testid="monitor-bullets">
        <p className="kicker">HOW MONITOR READS</p>
        <h2 className="section">Quiet readings, cited.</h2>
        <span className="website-rule" />
        <ul style={{ listStyle: "none", padding: 0, maxWidth: 70 + "ch" }}>
          {p.bullets.map((b, i) => (
            <li key={i} style={{ marginBottom: 16, paddingLeft: 22, position: "relative" }} data-testid={`monitor-bullet-${i}`}>
              <span style={{ position: "absolute", left: 0, top: 12, width: 12, height: 1.5, background: "var(--oxblood)" }} />
              {b}
            </li>
          ))}
        </ul>
        <CitationPills pills={["monitor.signal.confidence", "score.sparkline.12"]} />
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="Watch Monitor read a strategic goal in real time."
        body="The sandbox surfaces what's drifting against a sample plan and cites every figure back to source."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="monitor-inverted-cta"
      />
    </WebsiteShell>
  );
}
