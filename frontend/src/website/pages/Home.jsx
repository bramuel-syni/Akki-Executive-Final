import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../WebsiteShell";
import { HERO, HIERARCHY, COHORT_TEASER } from "../copy";
import "../style.css";

export default function HomePage() {
  return (
    <WebsiteShell
      title="Akki — for senior people who want to use AI fully, without governance exposure."
      description="A private working environment for operating executives and NEDs. Use AI on the work that actually matters — with full audit trail and no training-data exposure."
      pathname="/"
    >
      {/* Hero */}
      <section className="website-section">
        <span className="website-label">{HERO.eyebrow}</span>
        <h1>{HERO.headline}</h1>
        <span className="website-rule" />
        <p style={{ fontSize: 20, color: "#6B6B6B", maxWidth: "56ch", marginBottom: 36 }}>
          {HERO.subhead}
        </p>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <Link to={HERO.primaryCta.href} className="website-cta-primary" data-testid="home-cta-primary">
            {HERO.primaryCta.label}
          </Link>
          <Link to={HERO.secondaryCta.href} className="website-cta-secondary" data-testid="home-cta-secondary">
            {HERO.secondaryCta.label}
          </Link>
        </div>
      </section>

      {/* Three-tier hierarchy */}
      <section className="website-section" style={{ background: "#FAF7F2" }}>
        <span className="website-label">Three commitments</span>
        <h2>Safety. Workspace. Inventions.</h2>
        <span className="website-rule" />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 32, marginTop: 32 }}>
          {HIERARCHY.map((t) => (
            <div key={t.tier} data-testid={`home-tier-${t.label.toLowerCase()}`}>
              <span className="website-label" style={{ marginBottom: 0 }}>{t.tier} · {t.label}</span>
              <h3 style={{ marginTop: 8 }}>{t.title}</h3>
              <p style={{ fontSize: 16 }}>{t.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Cohort teaser */}
      <section className="website-section website-section--narrow">
        <span className="website-label">{COHORT_TEASER.label}</span>
        <h2 style={{ fontSize: 28 }}>{COHORT_TEASER.body}</h2>
        <Link to={COHORT_TEASER.cta.href} className="website-cta-primary" style={{ marginTop: 12 }}>
          {COHORT_TEASER.cta.label}
        </Link>
      </section>
    </WebsiteShell>
  );
}
