import React from "react";
import WebsiteShell from "../WebsiteShell";
import { TRUST } from "../copy";
import trustImg from "../assets/trust-wax-seal.jpg";
import "../style.css";

export default function TrustPage() {
  return (
    <WebsiteShell
      title="Trust & sovereignty — Akki"
      description="How Akki protects your data: Synisense Shield, Privacy Wall, hash-chained audit, sovereignty by construction."
      pathname="/trust"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Trust & sovereignty</span>
        <h1>Built so your governance team has nothing to discover later.</h1>
        <span className="website-rule" />
        <img
          src={trustImg}
          alt=""
          aria-hidden="true"
          loading="lazy"
          width={1200}
          height={800}
          style={{
            display: "block", width: "100%", height: "auto",
            margin: "32px 0", objectFit: "cover",
            borderTop: "1px solid var(--rule)",
            borderBottom: "1px solid var(--rule)",
          }}
          data-testid="trust-supporting-image"
        />
        <p style={{ fontSize: 18, color: "var(--muted)" }}>{TRUST.intro}</p>
        <div style={{ display: "grid", gap: 28, marginTop: 36 }}>
          {TRUST.pillars.map((p, i) => (
            <div key={i} className="website-tile" data-testid={`trust-pillar-${i}`}>
              <h3>{p.title}</h3>
              <p className="website-tile-sub">{p.sub}</p>
              <p>{p.body}</p>
            </div>
          ))}
        </div>
      </section>
    </WebsiteShell>
  );
}
