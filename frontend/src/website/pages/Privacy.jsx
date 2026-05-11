/**
 * Website v7 — /privacy (palette migration, copy preserved).
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { PRIVACY } from "../copy/legal";

export default function PrivacyPage() {
  return (
    <WebsiteShell
      title="Privacy Policy — Akki"
      description="How Akki collects, protects, and respects your data."
      pathname="/privacy"
    >
      <section className="website-section website-section--narrow">
        <p className="kicker">PRIVACY</p>
        <h1 className="hero">Privacy Policy</h1>
        <span className="website-rule" />
        <p className="website-label">{PRIVACY.effective}</p>
        {PRIVACY.blocks.map((b, i) => (
          <div key={i} style={{ marginTop: 32 }}>
            <h3>{b.h}</h3>
            <p>{b.p}</p>
          </div>
        ))}
      </section>
    </WebsiteShell>
  );
}
