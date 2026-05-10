/**
 * PerspectiveRead — Wave 2.2 (UAT pack 2026-05-10).
 *
 * Artefact body for the `get_perspective` submodule. Sections:
 *   1. Persona / framing kicker (echoes the chosen perspective)
 *   2. 3-5 perspective cards. Source: each scenario in the
 *      synthesis is a perspective; we render `label` as the
 *      framing, `desc` as the voice, and the `tier` chip as the
 *      grounding.
 *   3. "Where this lands for you" — a closing section that reflects
 *      the user's framing back. Pulled from diagnosis paragraphs.
 */
import React from "react";
import { TOKEN, FONT } from "../flow/tokens";

export default function PerspectiveRead({ session, diagnosis, scenarios, tensions }) {
  const persona = session?.persona;
  const perspectives = (scenarios || []).slice(0, 5); // 3–5 max per spec

  return (
    <section data-testid="solva-perspective-read">
      <SectionKicker>
        {persona ? `Perspectives, voiced as ${persona}` : "Perspectives"}
      </SectionKicker>

      {perspectives.length > 0 ? (
        <div
          data-testid="perspective-read-cards"
          style={{ display: "flex", flexDirection: "column", gap: 18, marginBottom: 36 }}
        >
          {perspectives.map((p, i) => (
            <article
              key={i}
              data-testid={`perspective-card-${i}`}
              style={{
                background: "rgba(0,0,0,0.02)",
                border: "1px solid rgba(0,0,0,0.06)",
                borderRadius: 4,
                padding: "16px 18px",
              }}
            >
              <h3
                style={{
                  fontFamily: FONT.GEORGIA, fontSize: 17,
                  color: TOKEN.INK, margin: "0 0 6px 0",
                  fontWeight: 600, lineHeight: 1.4,
                }}
              >
                {p.label || `Perspective ${i + 1}`}
              </h3>
              {p.desc && (
                <p
                  style={{
                    fontFamily: FONT.GEORGIA, fontSize: 15,
                    color: TOKEN.DEEP, lineHeight: 1.6,
                    margin: 0, fontStyle: "italic",
                  }}
                >
                  {p.desc}
                </p>
              )}
              {p.tier && (
                <p
                  style={{
                    fontFamily: FONT.CALIBRI, fontSize: 11,
                    color: TOKEN.MUTED, marginTop: 8,
                    textTransform: "uppercase", letterSpacing: 0.5,
                  }}
                >
                  Grounding: {p.tier}
                </p>
              )}
            </article>
          ))}
        </div>
      ) : (
        <p style={italicMuted}>
          No distinct perspectives surfaced — we likely needed more
          framing context.
        </p>
      )}

      {/* Where this lands for you */}
      <SectionKicker style={{ marginTop: 28 }}>Where this lands for you</SectionKicker>
      {diagnosis && diagnosis.length > 0 ? (
        diagnosis.map((p, i) => (
          <p key={i} style={paragraph}>{p}</p>
        ))
      ) : (
        <p style={italicMuted}>
          The reflection round below will pin down where this leaves you.
        </p>
      )}

      {tensions && tensions.length > 0 && (
        <>
          <SectionKicker style={{ marginTop: 28 }}>Where the perspectives diverge from your framing</SectionKicker>
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
