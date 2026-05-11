/**
 * Website v7 — /exco360 (palette migration, copy preserved).
 */
import React from "react";
import WebsiteShell from "../WebsiteShell";

export default function Exco360Page() {
  return (
    <WebsiteShell
      title="Exco360 — editorial work from the Akki team"
      description="Exco360 is the Akki team's editorial channel: pattern-recognition pieces from across our work with executive committees and boards."
      pathname="/exco360"
    >
      <section className="website-section website-section--narrow">
        <p className="kicker">EXCO360 · EDITORIAL</p>
        <h1 className="hero">Pattern recognition from across executive committees.</h1>
        <span className="website-rule" />
        <p className="dek">Once a week, occasionally less. One piece. No bylines.</p>
        <p>
          Exco360 is the Akki team's editorial channel. We publish what we are
          seeing across the executive committees and boards we work with — anonymised,
          slow, and never opinion-as-content. If you read this surface, expect a
          slower clock.
        </p>

        <span className="website-rule--full" style={{ marginTop: 56 }} />

        <h2 className="section" style={{ marginTop: 48 }}>First pieces</h2>
        <div data-testid="exco360-placeholder-1" style={{
          marginTop: 24, padding: "24px 28px",
          background: "var(--parchment-light)", border: "1px solid var(--graphite-light)",
        }}>
          <p className="website-label" style={{ margin: 0 }}>Coming with the launch</p>
          <h3 style={{ marginTop: 8 }}>The going-concern paragraph that almost wasn't.</h3>
          <p style={{ color: "var(--graphite)", margin: "8px 0 0" }}>
            How a CFO and a chair re-drafted seven words in a 60-page board pack,
            and what it changed about the next quarter. Publishing week of launch.
          </p>
        </div>
        <div data-testid="exco360-placeholder-2" style={{
          marginTop: 16, padding: "24px 28px",
          background: "var(--parchment-light)", border: "1px solid var(--graphite-light)",
        }}>
          <p className="website-label" style={{ margin: 0 }}>Coming with the launch</p>
          <h3 style={{ marginTop: 8 }}>What chairs notice that CEOs don't.</h3>
          <p style={{ color: "var(--graphite)", margin: "8px 0 0" }}>
            Three patterns we keep seeing in NED feedback at audit and remuneration
            committees.
          </p>
        </div>
      </section>
    </WebsiteShell>
  );
}
