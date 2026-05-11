import React from "react";
import { Link } from "react-router-dom";
import WebsiteShell from "../../WebsiteShell";
import EvidencePanel from "../../components/EvidencePanel";
import "../../style.css";

export default function ProductMonitorPage() {
  return (
    <WebsiteShell
      title="Monitor — goals at risk, role-scoped"
      description="Per-role function whitelists. Surfaces signals that match what your role is actually accountable for."
      pathname="/product/monitor"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Product · Monitor</span>
        <h1>The signals you would otherwise miss — and only those.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          Per-role function whitelist. Goals-at-risk surfacing. Quiet.
        </p>
        <h2 style={{ marginTop: 56 }}>What Monitor commits to.</h2>
        <div style={{ display: "grid", gap: 28, marginTop: 24 }}>
          <div><h3>Role-scoped.</h3><p>A CFO sees CFO function signals. A COO sees COO function signals. The whitelist is explicit.</p></div>
          <div><h3>Goals-at-risk.</h3><p>Three counters surface the high-confidence risks, the opportunities, and the count that needs attention this week. No infographic theatre.</p></div>
          <div><h3>Verified, not generated.</h3><p>An event-driven pipeline writes signals — generate → verify → persist. Phase G.3 dedup at write paths.</p></div>
        </div>
        <EvidencePanel kind="monitor_signals" caption="The role-scoped counter strip live on the Monitor page. Older signals beyond the 50-item window are accessible via search." />

        <p style={{ color: "#6B7480", fontSize: 14, marginTop: 24 }}>
          Read about the choices behind Monitor — <Link to="/methodology" className="website-link-inline">Methodology</Link>.
        </p>
        <div style={{ marginTop: 36 }}>
          <Link to="/sandbox" className="website-cta-primary">Try the sandbox</Link>
        </div>
      </section>
    </WebsiteShell>
  );
}
