/**
 * Website v7 — /terms (palette migration, copy preserved).
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";
import { TERMS } from "../copy/legal";

export default function TermsPage() {
  return (
    <WebsiteShell
      title="Terms of Service — Akki"
      description="The terms under which Akki is provided."
      pathname="/terms"
    >
      <section className="website-section website-section--narrow">
        <p className="kicker">TERMS</p>
        <h1 className="hero">Terms of Service</h1>
        <span className="website-rule" />
        <p className="website-label">{TERMS.effective}</p>
        {TERMS.blocks.map((b, i) => (
          <div key={i} style={{ marginTop: 32 }}>
            <h3>{b.h}</h3>
            <p>{b.p}</p>
          </div>
        ))}
      </section>
    </WebsiteShell>
  );
}
