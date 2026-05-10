/**
 * ClarityRead — Wave 2.2 (UAT pack 2026-05-10).
 *
 * Artefact body for the `seek_clarity` submodule. Reframes the
 * generic primary-diagnosis pattern as:
 *   1. Situation — articulated in plain language
 *   2. The defensible next question — what to actually ask next
 *   3. What's still unclear (subset of tensions, if any)
 *
 * Source data is the same `synthesis` payload the orchestrator
 * stores. We pull `diagnosis` (paragraphs) for the situation, the
 * first recommendation (or scenario label) for the next question,
 * and tensions for the "unclear" callout.
 */
import React from "react";
import { TOKEN, FONT } from "../flow/tokens";

export default function ClarityRead({ diagnosis, scenarios, tensions, recommendations }) {
  const situation = diagnosis && diagnosis.length ? diagnosis : null;
  // Defensible next question: prefer the first recommendation if it's
  // phrased as a question; else pick from scenarios; else fall back.
  const firstReco = (recommendations || [])[0];
  let nextQ = "";
  if (firstReco) {
    nextQ = (typeof firstReco === "string" ? firstReco : (firstReco.body || firstReco.text || "")).trim();
  } else if ((scenarios || []).length > 0) {
    nextQ = scenarios[0].desc || scenarios[0].label || "";
  }

  return (
    <section data-testid="solva-clarity-read">
      <SectionKicker>Situation</SectionKicker>
      {situation ? (
        situation.map((p, i) => (
          <p key={i} style={paragraph}>{p}</p>
        ))
      ) : (
        <p style={italicMuted}>The situation surfaced is still being assembled.</p>
      )}

      <SectionKicker style={{ marginTop: 32 }}>The defensible next question</SectionKicker>
      {nextQ ? (
        <p style={{ ...paragraph, fontSize: 19, color: TOKEN.INK }}>{nextQ}</p>
      ) : (
        <p style={italicMuted}>
          We don&rsquo;t have a sharp next question yet. The reflection round
          will help surface one.
        </p>
      )}

      {tensions && tensions.length > 0 && (
        <>
          <SectionKicker style={{ marginTop: 32 }}>What&rsquo;s still unclear</SectionKicker>
          <ul style={{ paddingLeft: 22, margin: 0 }}>
            {tensions.map((t, i) => (
              <li key={i} style={{ ...paragraph, marginBottom: 8 }}>{t}</li>
            ))}
          </ul>
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
