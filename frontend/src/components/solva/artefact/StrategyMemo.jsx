/**
 * StrategyMemo — Wave 2.2 (UAT pack 2026-05-10).
 *
 * Artefact body for the `develop_strategy` submodule. Sections:
 *   1. Weighted options (existing ProbabilityBar per scenario)
 *   2. Strongest case for the leading option
 *   3. Conditions of failure
 *   4. Recommendations
 *
 * Confidence intervals come from the existing scenario.low / .high.
 * Strongest-case body and conditions-of-failure are pulled from
 * the "sensitivity" / "tensions" callouts respectively when
 * available; otherwise we synthesise short placeholders from the
 * scenario set.
 */
import React from "react";
import { TOKEN, FONT } from "../flow/tokens";
import ProbabilityBar from "./ProbabilityBar";

export default function StrategyMemo({ scenarios, sensitivity, tensions, recommendations }) {
  const leading = (scenarios || [])
    .slice()
    .sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0))[0];

  return (
    <section data-testid="solva-strategy-memo">
      {/* Weighted options */}
      <SectionKicker>Weighted options</SectionKicker>
      {(scenarios || []).length > 0 ? (
        <div data-testid="strategy-memo-options" style={{ marginBottom: 36 }}>
          {scenarios.map((s, i) => (
            <ProbabilityBar
              key={i}
              label={s.label}
              desc={s.desc}
              pct={s.pct}
              low={s.low}
              high={s.high}
              tier={s.tier}
              testId={`strategy-memo-option-${i}`}
            />
          ))}
        </div>
      ) : (
        <p style={italicMuted}>Options are still being weighted.</p>
      )}

      {/* Strongest case */}
      <SectionKicker>Strongest case for {leading?.label || "the leading option"}</SectionKicker>
      {sensitivity && sensitivity.length > 0 ? (
        <ul data-testid="strategy-memo-strongest-case" style={{ paddingLeft: 22, margin: "0 0 36px 0" }}>
          {sensitivity.map((s, i) => (
            <li key={i} style={{ ...paragraph, marginBottom: 10 }}>{s}</li>
          ))}
        </ul>
      ) : leading?.desc ? (
        <p style={paragraph}>{leading.desc}</p>
      ) : (
        <p style={italicMuted}>
          The strongest-case scaffolding will sharpen as more grounding
          arrives.
        </p>
      )}

      {/* Conditions of failure */}
      <SectionKicker>Conditions of failure</SectionKicker>
      {tensions && tensions.length > 0 ? (
        <ul data-testid="strategy-memo-failure-conditions" style={{ paddingLeft: 22, margin: "0 0 36px 0" }}>
          {tensions.map((t, i) => (
            <li key={i} style={{ ...paragraph, marginBottom: 10 }}>{t}</li>
          ))}
        </ul>
      ) : (
        <p style={italicMuted}>
          We don&rsquo;t see a clear failure mode in the current evidence.
          Stress-test in a separate Solva session if you want one.
        </p>
      )}

      {/* Recommendations */}
      {(recommendations || []).length > 0 && (
        <>
          <SectionKicker>Recommendations</SectionKicker>
          <ol data-testid="strategy-memo-recommendations" style={{ paddingLeft: 22, margin: 0 }}>
            {recommendations.map((r, i) => {
              const text = typeof r === "string" ? r : (r.body || r.text || "");
              const head = typeof r === "string"
                ? (text.match(/Recommendation\s*\d+:\s*/i)?.[0] || `Recommendation ${i + 1}: `)
                : (r.heading || `Recommendation ${i + 1}`);
              const body = typeof r === "string"
                ? text.replace(/^\s*Recommendation\s*\d+:\s*/i, "").trim()
                : (text || "").trim();
              return (
                <li key={i} style={{ ...paragraph, marginBottom: 12 }}>
                  <strong>{head}</strong>{body ? <> {body.replace(/^—\s*/, "")}</> : null}
                </li>
              );
            })}
          </ol>
        </>
      )}
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
        marginBottom: 14, marginTop: 0, ...(style || {}),
      }}
    >
      {children}
    </div>
  );
}

const paragraph = {
  fontFamily: FONT.GEORGIA, fontSize: 16,
  color: TOKEN.INK, lineHeight: 1.65,
  margin: "0 0 12px 0",
};
const italicMuted = {
  ...paragraph, fontStyle: "italic", color: TOKEN.MUTED,
};
