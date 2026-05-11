import React from "react";
import WebsiteShell from "../WebsiteShell";
import "../style.css";

/**
 * Phase J.2 — Exco360 publishing surface.
 *
 * Editorial voice demonstration. Phase J.2 ships the landing scaffold
 * with placeholder treatment until the editorial team commissions the
 * first three pieces. Spec permits "Coming soon" provided it is honest.
 */
export default function Exco360Page() {
  return (
    <WebsiteShell
      title="Exco360 — editorial work from the Akki team"
      description="Exco360 is the Akki team's editorial channel: pattern-recognition pieces from across our work with executive committees and boards."
      pathname="/exco360"
    >
      <section className="website-section website-section--narrow">
        <span className="website-label">Exco360 · editorial</span>
        <h1>Pattern recognition from across exec committees.</h1>
        <span className="website-rule" />
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic", fontSize: 18, color: "#2A3441" }}>
          Once a week, occasionally less. One piece. No bylines.
        </p>
        <p>
          Exco360 is the Akki team's editorial channel. We publish what we are
          seeing across the executive committees and boards we work with — anonymised,
          slow, and never opinion-as-content. If you read this surface, expect a
          slower clock.
        </p>

        <hr className="website-section-divider" />

        <h2>First pieces</h2>
        <div data-testid="exco360-placeholder" style={{
          marginTop: 24, padding: "24px 28px",
          background: "#FAFAF5", border: "1px solid #D8D2C5",
        }}>
          <span style={{ fontSize: 11, letterSpacing: "0.15em", textTransform: "uppercase", color: "#6B7480" }}>
            Coming with the launch
          </span>
          <h3 style={{ marginTop: 8 }}>The going-concern paragraph that almost wasn't.</h3>
          <p style={{ color: "#2A3441", margin: "8px 0 0" }}>
            How a CFO and a chair re-drafted seven words in a 60-page board pack,
            and what it changed about the next quarter. Publishing week of launch.
          </p>
        </div>
        <div style={{ marginTop: 16, padding: "24px 28px", background: "#FAFAF5", border: "1px solid #D8D2C5" }}>
          <span style={{ fontSize: 11, letterSpacing: "0.15em", textTransform: "uppercase", color: "#6B7480" }}>
            Coming with the launch
          </span>
          <h3 style={{ marginTop: 8 }}>What chairs notice that CEOs don't.</h3>
          <p style={{ color: "#2A3441", margin: "8px 0 0" }}>
            Three patterns we keep seeing in NED feedback at audit and remuneration
            committees.
          </p>
        </div>
      </section>
    </WebsiteShell>
  );
}
