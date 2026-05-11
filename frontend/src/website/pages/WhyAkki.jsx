import React from "react";
import WebsiteShell from "../WebsiteShell";
import { WHY } from "../copy";
import "../style.css";

export default function WhyAkkiPage() {
  return (
    <WebsiteShell
      title="Why Akki"
      description="Senior work is private work. Decisions, not transcripts. A peer, not a vendor."
      pathname="/why-akki"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Why Akki</span>
        <h1>Built for the kind of work most AI products were not built for.</h1>
        <span className="website-rule" />
        <div style={{ display: "grid", gap: 36, marginTop: 36 }}>
          {WHY.map((w, i) => (
            <div key={i} data-testid={`why-block-${i}`}>
              <h3>{w.title}</h3>
              <p>{w.body}</p>
            </div>
          ))}
        </div>
      </section>
    </WebsiteShell>
  );
}
