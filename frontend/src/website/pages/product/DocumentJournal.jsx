/**
 * Website v7 — /document-journal (NEW PAGE)
 */
import React from "react";
import WebsiteShell from "../../WebsiteShell";
import { HeroWithLift, InvertedCtaSection, CitationPills } from "../../components/PagePrimitives";
import { PRODUCTS, INVERTED_CTA } from "../../copy";

export default function DocumentJournal() {
  const p = PRODUCTS["document-journal"];
  return (
    <WebsiteShell
      title="Document Journal — Your reading assistant"
      description="A reading library that threads documents across pre-board, in-meeting, and post-meeting work."
      pathname="/document-journal"
    >
      <HeroWithLift
        kicker={p.kicker} headline={p.headline} lift={p.lift} dek={p.dek}
        primaryCta={{ label: "See the Journal in use", href: "/sandbox" }}
        secondaryCta={{ label: "How reading momentum works", href: "/methodology#journal" }}
        testId="journal-page"
      />
      <section className="website-section section-reveal" data-testid="journal-bullets">
        <p className="kicker">WHAT THE JOURNAL HOLDS</p>
        <h2 className="section">A reading library that remembers how you read.</h2>
        <span className="website-rule" />
        <ul style={{ listStyle: "none", padding: 0, maxWidth: 70 + "ch" }}>
          {p.bullets.map((b, i) => (
            <li key={i} style={{ marginBottom: 16, paddingLeft: 22, position: "relative" }} data-testid={`journal-bullet-${i}`}>
              <span style={{ position: "absolute", left: 0, top: 12, width: 12, height: 1.5, background: "var(--oxblood)" }} />
              {b}
            </li>
          ))}
        </ul>
        <CitationPills pills={["journal.evolution.diff", "anchor.private.note"]} />
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="See the Journal thread a board pack across a full cycle."
        body="The sandbox uploads a sample pack, anchors a note, and shows the workspace pick it up at the next agenda item."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="journal-inverted-cta"
      />
    </WebsiteShell>
  );
}
