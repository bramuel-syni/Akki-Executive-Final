/**
 * Website v7 — /akki-chat
 * v7 §7.3.
 */
import React from "react";
import WebsiteShell from "../../WebsiteShell";
import { HeroWithLift, InvertedCtaSection, CitationPills } from "../../components/PagePrimitives";
import { PRODUCTS, INVERTED_CTA } from "../../copy";

export default function AkkiChat() {
  const p = PRODUCTS["akki-chat"];
  return (
    <WebsiteShell
      title="Akki Chat — Multi-model with audit chain"
      description="Multi-model chat with Synisense anonymisation on every outbound prompt and a SHA-256 audit chain on every turn."
      pathname="/akki-chat"
    >
      <HeroWithLift
        kicker={p.kicker} headline={p.headline} lift={p.lift} dek={p.dek}
        primaryCta={{ label: "Try Akki Chat", href: "/sandbox" }}
        secondaryCta={{ label: "Audit chain & shielding", href: "/trust#synisense" }}
        testId="chat-page"
      />
      <section className="website-section section-reveal" data-testid="chat-bullets">
        <p className="kicker">HOW IT WORKS</p>
        <h2 className="section">Four commitments under every turn.</h2>
        <span className="website-rule" />
        <ul style={{ listStyle: "none", padding: 0, maxWidth: 70 + "ch" }}>
          {p.bullets.map((b, i) => (
            <li key={i} style={{ marginBottom: 16, paddingLeft: 22, position: "relative" }} data-testid={`chat-bullet-${i}`}>
              <span style={{ position: "absolute", left: 0, top: 12, width: 12, height: 1.5, background: "var(--oxblood)" }} />
              {b}
            </li>
          ))}
        </ul>
        <CitationPills pills={["chat.audit.sha256", "synisense.regex.presidio.judge"]} />
      </section>
      <InvertedCtaSection
        kicker={INVERTED_CTA.kicker}
        headline="A reasoning chat where the audit chain is visible."
        body="The sandbox shows the same audit-chain pattern that ships with every Akki conversation."
        ctaLabel="Begin sandbox" ctaHref="/sandbox" meta={INVERTED_CTA.meta}
        testId="chat-inverted-cta"
      />
    </WebsiteShell>
  );
}
