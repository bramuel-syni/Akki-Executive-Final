/**
 * Website v7 — Home page.
 *
 * v7 §4 — exact 10-section sequence:
 *   1. Nav        (shell)
 *   2. Hero       (F1 + F2 marginalia + F3 reveal)
 *   3. Evidence   (F4)
 *   4. Tier 1 Safety  (§4.4 verbatim + G2 image band)
 *   5. Tier 2 Workspace (§4.5 — 4 capabilities, NO product names)
 *   6. Tier 3 Inventions (§4.6 — Solva, Synisense, Agent Cycle)
 *   7. Three Audiences  (§4.7 + G3 triptych)
 *   8. Before Akki Ships cohort teaser (§4.8)
 *   9. Inverted CTA     (F5)
 *  10. Footer    (shell)
 *
 * One-word lift in hero h1 = "Safe" (oxblood italic) per A5.
 */
import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../WebsiteShell";
import {
  HERO, EVIDENCE, TIER_1, TIER_2, TIER_3, AUDIENCES,
  COHORT_TEASER, INVERTED_CTA,
} from "../copy";
import heroImg     from "../assets/v7/home-hero.webp";
import tier1Band   from "../assets/v7/tier1-safety-band.webp";
import audienceImg from "../assets/v7/audience-triptych.webp";

export default function Home() {
  return (
    <WebsiteShell
      title="Akki — Safe AI for executive work"
      description="A workspace for executives who want to use AI fully — without governance exposure. From Syni.ai, Nairobi."
      pathname="/"
      ogImage="/static/media/home-hero.webp"
    >
      {/* HERO (F1) */}
      <section className="hero" aria-labelledby="home-hero-h1">
        <span className="marginalia" aria-hidden="true">AKKI / 0.1 / SYNI.AI</span>
        <div className="hero-grid">
          <div className="hero-text">
            <p className="kicker reveal-1">{HERO.kicker}</p>
            <h1 id="home-hero-h1" className="hero reveal-2" data-testid="home-hero-h1">
              <em className="lift">{HERO.lift}</em>{HERO.headline.replace(HERO.lift, "")}
            </h1>
            <p className="dek reveal-3">{HERO.dek}</p>
            <div className="hero-actions reveal-4">
              <Link to={HERO.primaryCta.href} className="btn-primary btn-hero" data-testid="home-cta-primary">
                {HERO.primaryCta.label}
              </Link>
              <a href={HERO.tertiary.href} className="btn-tertiary" data-testid="home-cta-tertiary">
                {HERO.tertiary.label} →
              </a>
            </div>
          </div>
          <div className="hero-image-wrap reveal-4">
            <img
              src={heroImg}
              alt="An executive at a desk, reading paper materials in a quiet study."
              width="800" height="1000"
              loading="eager"
              fetchPriority="high"
              data-testid="home-hero-img"
            />
          </div>
        </div>
      </section>

      {/* EVIDENCE STRIP (F4) */}
      <section className="evidence-strip section-reveal" aria-labelledby="evidence-h2" data-testid="home-evidence-strip">
        <p className="kicker">WHAT THIS LOOKS LIKE IN PRACTICE</p>
        <h2 id="evidence-h2" className="section" style={{ position: "absolute", left: -9999 }}>
          What this looks like in practice
        </h2>
        <div className="evidence-grid">
          {EVIDENCE.map((e, i) => (
            <div key={i} className="evidence-cell" data-testid={`evidence-cell-${i}`}>
              <p className="evidence-numeral">{e.numeral}</p>
              <p className="evidence-caption">{e.caption}</p>
            </div>
          ))}
        </div>
      </section>

      {/* TIER 1 — SAFETY (§4.4) */}
      <section id="safety" className="website-section section-reveal" aria-labelledby="tier1-h2" data-testid="home-tier1">
        <p className="kicker">{TIER_1.kicker}</p>
        <h2 id="tier1-h2" className="section">{TIER_1.headline}</h2>
        <span className="website-rule" />
        <p className="dek" style={{ maxWidth: "62ch" }}>{TIER_1.body}</p>
        <ul style={{ listStyle: "none", padding: 0, marginTop: 24, display: "grid", gap: 12 }}>
          {TIER_1.bullets.map((b, i) => (
            <li key={i} style={{ paddingLeft: 18, position: "relative", maxWidth: 70 + "ch" }} data-testid={`tier1-bullet-${i}`}>
              <span style={{
                position: "absolute", left: 0, top: 11, width: 8, height: 1.5,
                background: "var(--oxblood)",
              }} />
              {b}
            </li>
          ))}
        </ul>
      </section>
      <figure className="tier1-band section-reveal" data-testid="home-tier1-band">
        <img
          src={tier1Band}
          alt="Detail of an institutional ledger open on a wooden surface, marginalia in fountain pen."
          width="1600" height="900"
          loading="lazy"
        />
        <figcaption className="tier1-band-overlay">{TIER_1.band_overlay}</figcaption>
      </figure>

      {/* TIER 2 — THE WORKSPACE (§4.5) */}
      <section className="website-section section-reveal" aria-labelledby="tier2-h2" data-testid="home-tier2">
        <p className="kicker">{TIER_2.kicker}</p>
        <h2 id="tier2-h2" className="section">{TIER_2.headline}</h2>
        <p className="dek">{TIER_2.dek}</p>
        <span className="website-rule" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 40 }}>
          {TIER_2.capabilities.map((c, i) => (
            <div key={i} style={{ borderTop: "1.5px solid var(--graphite-light)", paddingTop: 20 }} data-testid={`tier2-cap-${i}`}>
              <h3>{c.title}</h3>
              <p style={{ color: "var(--graphite)" }}>{c.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* TIER 3 — THE INVENTIONS (§4.6) */}
      <section className="website-section section-reveal" aria-labelledby="tier3-h2" data-testid="home-tier3">
        <p className="kicker">{TIER_3.kicker}</p>
        <h2 id="tier3-h2" className="section">{TIER_3.headline}</h2>
        <p className="dek">{TIER_3.dek}</p>
        <span className="website-rule" />
        <div className="three-col">
          {TIER_3.cards.map((card, i) => (
            <div key={card.title} className="three-col-card" data-testid={`tier3-${card.title.toLowerCase().replace(/\s+/g,"-")}`}>
              <h3>{card.title}</h3>
              <p style={{ color: "var(--graphite)", fontStyle: "italic", marginBottom: 8 }}>{card.sub}</p>
              <p style={{ color: "var(--graphite)" }}>{card.body}</p>
              <Link to={card.cta.href} className="btn-tertiary" style={{ marginTop: 8 }}>
                {card.cta.label} →
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* THREE AUDIENCES (§4.7) + G3 triptych */}
      <section className="website-section section-reveal" aria-labelledby="audiences-h2" data-testid="home-audiences">
        <p className="kicker">THREE AUDIENCES</p>
        <h2 id="audiences-h2" className="section">Executive work, three shapes.</h2>
        <p className="dek">One workspace; three faithful answers to the people who actually sit in the room.</p>
        <span className="website-rule" />
        <div className="three-col">
          {AUDIENCES.map((a) => (
            <div key={a.title} className="three-col-card" data-testid={`audience-${a.cta.href.replace(/^\//,"")}`}>
              <h3>{a.title}</h3>
              <p style={{ color: "var(--graphite)", fontStyle: "italic", marginBottom: 8 }}>{a.sub}</p>
              <p style={{ color: "var(--graphite)" }}>{a.body}</p>
              <Link to={a.cta.href} className="btn-tertiary" style={{ marginTop: 8 }}>
                {a.cta.label} →
              </Link>
            </div>
          ))}
        </div>
        <figure style={{ marginTop: 56 }}>
          <img
            src={audienceImg}
            alt="Three executives reading in private study and library settings."
            width="1600" height="600"
            loading="lazy"
            style={{ width: "100%", height: "auto", display: "block" }}
            data-testid="home-audience-triptych"
          />
        </figure>
      </section>

      {/* BEFORE AKKI SHIPS (§4.8) */}
      <section className="website-section--narrow section-reveal" aria-labelledby="cohort-teaser-h2" data-testid="home-cohort-teaser">
        <p className="kicker">{COHORT_TEASER.kicker}</p>
        <h2 id="cohort-teaser-h2" className="section">{COHORT_TEASER.headline}</h2>
        <p className="dek">{COHORT_TEASER.body}</p>
        <Link to={COHORT_TEASER.cta.href} className="btn-tertiary" data-testid="home-cohort-teaser-cta">
          {COHORT_TEASER.cta.label} →
        </Link>
      </section>

      {/* INVERTED CTA (F5) */}
      <section className="inverted-cta section-reveal" aria-labelledby="inverted-cta-h2" data-testid="home-inverted-cta">
        <div className="inverted-cta-inner">
          <div>
            <p className="kicker">{INVERTED_CTA.kicker}</p>
            <h2 id="inverted-cta-h2">{INVERTED_CTA.headline}</h2>
            <p className="dek">{INVERTED_CTA.body}</p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 12 }}>
            <Link to={INVERTED_CTA.cta.href} className="btn-cta-section" data-testid="home-inverted-cta-button">
              {INVERTED_CTA.cta.label} →
            </Link>
            <p className="inverted-cta-meta">{INVERTED_CTA.meta}</p>
          </div>
        </div>
      </section>
    </WebsiteShell>
  );
}
