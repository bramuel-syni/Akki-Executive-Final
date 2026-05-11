import React from "react";
import WebsiteShell from "../WebsiteShell";
import { SURFACES } from "../copy";
import "../style.css";

export default function WhatAkkiDoesPage() {
  return (
    <WebsiteShell
      title="What Akki Does"
      description="Six product surfaces for senior decision work. Solva, Akki Chat, Work Studio, Cycle Manager, Monitor, Pulse — plus Document Journal."
      pathname="/what-akki-does"
    >
      <section className="website-section">
        <span className="website-label">What Akki does</span>
        <h1>Six surfaces. One working environment.</h1>
        <span className="website-rule" />
        <p style={{ maxWidth: "60ch", marginBottom: 36, fontSize: 18, color: "var(--muted)" }}>
          Each surface is calm by default. Each is in service of a real decision
          you would otherwise be making in a Word document at 9pm.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 18 }}>
          {SURFACES.map((s) => (
            <div key={s.id} className="website-tile" data-testid={`surface-tile-${s.id}`}>
              <h3>{s.title}</h3>
              <p className="website-tile-sub">{s.subtitle}</p>
              <p style={{ fontSize: 15, color: "var(--ink)" }}>{s.body}</p>
              <p style={{ fontSize: 13, color: "var(--muted)", fontStyle: "italic", margin: 0, marginTop: 12 }}>
                Coming soon — full detail post-launch.
              </p>
            </div>
          ))}
        </div>
      </section>
    </WebsiteShell>
  );
}
