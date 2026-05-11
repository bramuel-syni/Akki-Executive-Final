/**
 * Website v7 — /work-studio
 * v7 §7.4.
 */
import React from "react";
import WebsiteShell from "../../WebsiteShell";
import { HeroWithLift, InvertedCtaSection, CitationPills } from "../../components/PagePrimitives";
import { PRODUCTS, INVERTED_CTA } from "../../copy";

export default function WorkStudio() {
  const p = PRODUCTS["work-studio"];
  return (
    <WebsiteShell
      title="Work Studio — Deterministic board-ready outputs"
      description="Briefs, decks and reports rendered byte-deterministically. Every export hash-stamped for governance."
      pathname="/work-studio"
    >
      <HeroWithLift
        kicker={p.kicker} headline={p.headline} lift={p.lift} dek={p.dek}
        primaryCta={{ label: "See an output run", href: "/sandbox" }}
        secondaryCta={{ label: "How deterministic rendering works", href: "/methodology#determinism" }}
        testId="work-studio-page"
      />
      <section className="website-section section-reveal" data-testid="ws-bullets">
        <p className="kicker">WHAT YOU GET</p>
        <h2 className="section">Brand-grade outputs that survive committee scrutiny.</h2>
        <span className="website-rule" />
        <ul style={{ listStyle: "none", padding: 0, maxWidth: 70 + "ch" }}>
          {p.bullets.map((b, i) => (
            <li key={i} style={{ marginBottom: 16, paddingLeft: 22, position: "relative" }} data-testid={`ws-bullet-${i}`}>
              <span style={{ position: "absolute", left: 0, top: 12, width: 12, height: 1.5, background: "var(--oxblood)" }} />
              {b}
            </li>
          ))}
        </ul>
        <CitationPills pills={["render.byte.hash", "validator.brief.minutes.pack", "docx.pptx.pdf"]} />
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="Generate a board-ready brief in sixty seconds."
        body="The sandbox produces the same deterministic DOCX and PDF that ship with Akki."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="ws-inverted-cta"
      />
    </WebsiteShell>
  );
}
