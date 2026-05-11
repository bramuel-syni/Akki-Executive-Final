import React from "react";
import WebsiteShell from "../WebsiteShell";
import { TERMS } from "../copy/legal";
import "../style.css";

export default function TermsPage() {
  return (
    <WebsiteShell
      title="Terms of Service — Akki"
      description="The terms under which Akki is provided."
      pathname="/terms"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Terms</span>
        <h1>Terms of Service</h1>
        <span className="website-rule" />
        <p style={{ color: "var(--muted)", fontSize: 14 }}>{TERMS.effective}</p>
        {TERMS.blocks.map((b, i) => (
          <div key={i} style={{ marginTop: 24 }}>
            <h3>{b.h}</h3>
            <p>{b.p}</p>
          </div>
        ))}
      </section>
    </WebsiteShell>
  );
}
