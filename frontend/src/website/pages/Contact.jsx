/**
 * Website v7 — /contact  (v7 §10.4 — three paths).
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { HeroWithLift } from "../components/PagePrimitives";
import { CONTACT } from "../copy";

export default function Contact() {
  return (
    <WebsiteShell
      title="Contact — Akki"
      description="Three ways to reach Akki: cohort, organisation, general. We reply personally."
      pathname="/contact"
    >
      <HeroWithLift
        kicker={CONTACT.kicker}
        headline={CONTACT.headline}
        lift={CONTACT.lift}
        dek={CONTACT.dek}
        testId="contact-page"
      />
      <section className="website-section section-reveal" data-testid="contact-paths">
        <p className="kicker">PICK THE PATH</p>
        <h2 className="section">One of these is yours.</h2>
        <span className="website-rule" />
        <div className="three-col">
          {CONTACT.paths.map((path, i) => (
            <div key={i} className="three-col-card" data-testid={`contact-path-${i}`}>
              <h3>{path.label}</h3>
              <p style={{ color: "var(--graphite)" }}>{path.body}</p>
              <a href={path.cta_href} className="btn-primary" style={{ marginTop: 12 }} data-testid={`contact-path-${i}-cta`}>
                {path.cta_label}
              </a>
            </div>
          ))}
        </div>
      </section>
    </WebsiteShell>
  );
}
