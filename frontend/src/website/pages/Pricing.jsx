import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../WebsiteShell";
import { PRICING } from "../copy";
import "../style.css";

export default function PricingPage() {
  return (
    <WebsiteShell
      title="Pricing — Akki"
      description="Tiers for Executive, NED, Dual and Organisation. Founding-cohort rate locks for life."
      pathname="/pricing"
    >
      <section className="website-section">
        <span className="website-label">Pricing</span>
        <h1>Four ways to use Akki.</h1>
        <span className="website-rule" />
        <p style={{ fontSize: 18, color: "#6B6B6B", marginBottom: 36 }}>{PRICING.intro}</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 18 }}>
          {PRICING.tiers.map((t) => (
            <div key={t.id} className="website-tile" data-testid={`pricing-tier-${t.id}`}>
              <h3>{t.name}</h3>
              <p style={{ fontSize: 28, fontFamily: "Georgia, serif", color: "#2A1B1D", margin: "0 0 4px", fontWeight: 700 }}>
                {t.price} <span style={{ fontSize: 14, color: "#6B6B6B", fontWeight: 400 }}>{t.period}</span>
              </p>
              <p style={{ fontSize: 14, color: "#6B6B6B", fontStyle: "italic", minHeight: 56 }}>{t.audience}</p>
              <ul style={{ paddingLeft: 0, listStyle: "none", margin: "16px 0 0" }}>
                {t.includes.map((it, i) => (
                  <li key={i} style={{ fontSize: 14, padding: "6px 0", borderTop: "1px solid #E8DECB" }}>{it}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p style={{ marginTop: 36, fontSize: 14, color: "#C25A38", letterSpacing: "0.05em" }}>
          {PRICING.footnote}
        </p>
        <Link to="/cohort" className="website-cta-primary" style={{ marginTop: 12 }}>
          Request early access
        </Link>
      </section>
    </WebsiteShell>
  );
}
