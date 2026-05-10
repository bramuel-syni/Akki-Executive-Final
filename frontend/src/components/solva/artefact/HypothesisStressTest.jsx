/**
 * HypothesisStressTest — Wave 2.2 (UAT pack 2026-05-10).
 *
 * Artefact body for the `simulate_hypothesis` submodule. Sections:
 *   1. The hypothesis (echoed back)
 *   2. Hypothesis-strength bar (single ProbabilityBar with the
 *      session's leading scenario, framed as "holds" vs. "breaks")
 *   3. Two-column layout:
 *        Supporting factors  |  Undermining factors
 *      Both columns derived from sensitivity (supporting) and
 *      tensions (undermining). When either is empty we render a
 *      muted italic placeholder.
 *   4. "What would have to be true" — surfaced from
 *      recommendations (the strategy/hypothesis layer often produces
 *      preconditions there).
 */
import React from "react";
import { TOKEN, FONT } from "../flow/tokens";
import ProbabilityBar from "./ProbabilityBar";

export default function HypothesisStressTest({ session, diagnosis, scenarios, sensitivity, tensions, recommendations }) {
  const hypothesis = (session?.intent || "").trim();
  const lead = (scenarios || []).slice().sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0))[0];

  return (
    <section data-testid="solva-hypothesis-stress-test">
      {/* The hypothesis */}
      <SectionKicker>The hypothesis</SectionKicker>
      <p style={paragraph}>{hypothesis || "(framing not captured)"}</p>

      {/* Strength bar */}
      {lead && (
        <div style={{ marginTop: 20, marginBottom: 36 }}>
          <SectionKicker>Hypothesis strength</SectionKicker>
          <ProbabilityBar
            label={lead.label}
            desc={lead.desc}
            pct={lead.pct}
            low={lead.low}
            high={lead.high}
            tier={lead.tier}
            testId="hypothesis-strength-bar"
          />
        </div>
      )}

      {/* Two-column supporting / undermining */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 28,
          marginBottom: 36,
        }}
        className="solva-hyp-twocol"
      >
        <div data-testid="hyp-supporting-factors">
          <SectionKicker>Supporting factors</SectionKicker>
          {sensitivity && sensitivity.length > 0 ? (
            <ul style={listReset}>
              {sensitivity.map((s, i) => <li key={i} style={listItem}>{s}</li>)}
            </ul>
          ) : (
            <p style={italicMuted}>None surfaced from the depth round.</p>
          )}
        </div>
        <div data-testid="hyp-undermining-factors">
          <SectionKicker>Undermining factors</SectionKicker>
          {tensions && tensions.length > 0 ? (
            <ul style={listReset}>
              {tensions.map((t, i) => <li key={i} style={listItem}>{t}</li>)}
            </ul>
          ) : (
            <p style={italicMuted}>None surfaced from the depth round.</p>
          )}
        </div>
      </div>

      {/* What would have to be true */}
      <SectionKicker>What would have to be true</SectionKicker>
      {(recommendations || []).length > 0 ? (
        <ul data-testid="hyp-what-would-be-true" style={listReset}>
          {recommendations.map((r, i) => {
            const text = typeof r === "string" ? r : (r.body || r.text || "");
            return <li key={i} style={listItem}>{text.replace(/^\s*Recommendation\s*\d+:\s*/i, "").trim()}</li>;
          })}
        </ul>
      ) : (diagnosis && diagnosis.length > 0) ? (
        <p style={paragraph}>{diagnosis[0]}</p>
      ) : (
        <p style={italicMuted}>
          The preconditions for this hypothesis to hold weren&rsquo;t teased
          out yet. The reflection round will surface them.
        </p>
      )}

      <style>{`@media (max-width: 720px) { .solva-hyp-twocol { grid-template-columns: 1fr !important; } }`}</style>
    </section>
  );
}

function SectionKicker({ children, style }) {
  return (
    <div
      style={{
        fontFamily: FONT.GEORGIA, fontStyle: "italic",
        fontSize: 13, color: TOKEN.ACCENT,
        textTransform: "uppercase", letterSpacing: 1.6,
        marginBottom: 14, ...(style || {}),
      }}
    >
      {children}
    </div>
  );
}

const paragraph = {
  fontFamily: FONT.GEORGIA, fontSize: 17,
  color: TOKEN.INK, lineHeight: 1.65,
  margin: "0 0 14px 0",
};
const italicMuted = {
  ...paragraph, fontStyle: "italic", color: TOKEN.MUTED,
};
const listReset = { paddingLeft: 22, margin: 0 };
const listItem = {
  fontFamily: FONT.GEORGIA, fontSize: 16,
  color: TOKEN.INK, lineHeight: 1.6,
  marginBottom: 10,
};
