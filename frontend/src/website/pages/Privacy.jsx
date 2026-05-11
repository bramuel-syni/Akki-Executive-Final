import React from "react";
import WebsiteShell from "../WebsiteShell";
import { PRIVACY } from "../copy/legal";
import "../style.css";

export default function PrivacyPage() {
  return (
    <WebsiteShell
      title="Privacy Policy — Akki"
      description="How Akki collects, protects, and respects your data."
      pathname="/privacy"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Privacy</span>
        <h1>Privacy Policy</h1>
        <span className="website-rule" />
        <p style={{ color: "var(--muted)", fontSize: 14 }}>{PRIVACY.effective}</p>
        {PRIVACY.blocks.map((b, i) => (
          <div key={i} style={{ marginTop: 24 }}>
            <h3>{b.h}</h3>
            <p>{b.p}</p>
          </div>
        ))}
      </section>
    </WebsiteShell>
  );
}
