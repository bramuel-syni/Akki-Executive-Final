/**
 * "How Solva reasoned this" — collapsed by default. Brief §5.4. Four
 * sub-sections rendered from the shaped data returned by
 * GET /api/solva/v2/sessions/{sid}/artefact-reasoning:
 *
 *   1. The candidates Solva considered.
 *   2. What the triangulation found.
 *   3. How the probabilities were weighted.
 *   4. The full reasoning audit log.
 *
 * Animates 200ms slide-down on expand; instant under prefers-reduced-motion.
 */
import React, { useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { TOKEN, FONT } from "../flow/tokens";
import usePrefersReducedMotion from "../flow/usePrefersReducedMotion";

export default function ReasoningExpandable({ sessionId, testId = "solva-reasoning" }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    if (!open || data || loading) return;
    setLoading(true);
    api
      .get(`/solva/v2/sessions/${sessionId}/artefact-reasoning`)
      .then((res) => setData(res.data))
      .catch((e) => setError(e?.response?.data?.detail || e.message || "Failed to load reasoning."))
      .finally(() => setLoading(false));
  }, [open, data, loading, sessionId]);

  return (
    <section
      data-testid={testId}
      style={{
        marginTop: 64,
        borderTop: `1px solid ${TOKEN.RULE}`,
        paddingTop: 24,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="solva-reasoning-body"
        data-testid="solva-reasoning-toggle"
        style={{
          background: "transparent",
          border: "none",
          cursor: "pointer",
          padding: 0,
          display: "flex",
          alignItems: "center",
          gap: 8,
          color: TOKEN.DEEP,
          fontFamily: FONT.GEORGIA,
          fontSize: 14,
          fontStyle: "italic",
        }}
      >
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        How Solva reasoned this
      </button>

      {open && (
        <div
          id="solva-reasoning-body"
          style={{
            marginTop: 18,
            transition: reduced ? "none" : "opacity 200ms ease-out 100ms",
            fontFamily: FONT.CALIBRI,
            fontSize: 13,
            color: TOKEN.DEEP,
            lineHeight: 1.55,
          }}
        >
          {loading && <div>Loading reasoning trace…</div>}
          {error && <div role="alert" style={{ color: TOKEN.ACCENT }}>{error}</div>}
          {!loading && !error && data && (
            <>
              <Section heading="The candidates Solva considered">
                {data.candidates?.length ? (
                  <ul style={ulStyle}>
                    {data.candidates.map((c, i) => (
                      <li key={i}>
                        <span style={{ color: TOKEN.INK }}>{c.hypothesis || `Candidate ${i + 1}`}</span>
                        {c.tentative_tier ? <em style={{ color: TOKEN.MUTED }}> · {c.tentative_tier}</em> : null}
                        {typeof c.weight === "number" ? (
                          <span style={{ color: TOKEN.MUTED }}> · weight {Math.round(c.weight * 100)}%</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : <Empty>No candidates recorded.</Empty>}
              </Section>
              <Section heading="What the triangulation found">
                {data.triangulation?.length ? (
                  <ul style={ulStyle}>
                    {data.triangulation.map((t, i) => (
                      <li key={i}>
                        <span style={{ color: TOKEN.INK }}>{t.summary}</span>
                        {t.severity ? <em style={{ color: TOKEN.MUTED }}> · {t.severity}</em> : null}
                        {t.source ? <span style={{ color: TOKEN.MUTED }}> · {t.source}</span> : null}
                      </li>
                    ))}
                  </ul>
                ) : <Empty>No divergences recorded.</Empty>}
              </Section>
              <Section heading="How the probabilities were weighted">
                {data.weighting?.breakdown ? (
                  <ul style={ulStyle}>
                    {Object.entries(data.weighting.breakdown).map(([k, v]) => (
                      <li key={k}>
                        <span style={{ color: TOKEN.INK }}>{k.replace(/_/g, " ")}</span>
                        <span style={{ color: TOKEN.MUTED }}> · {Math.round((typeof v === "number" ? v : 0) * 100)}%</span>
                      </li>
                    ))}
                  </ul>
                ) : <Empty>Weighting breakdown not available.</Empty>}
              </Section>
              <Section heading="The full reasoning audit log">
                {data.log_entries?.length ? (
                  <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: FONT.CONSOLAS, fontSize: 12 }}>
                    <thead>
                      <tr style={{ textAlign: "left", color: TOKEN.MUTED }}>
                        <th style={th}>engine</th>
                        <th style={th}>layer</th>
                        <th style={th}>tiers</th>
                        <th style={th}>verdict</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.log_entries.map((e, i) => (
                        <tr key={i} style={{ borderTop: `1px solid ${TOKEN.RULE}` }}>
                          <td style={td}>{e.engine}</td>
                          <td style={td}>{e.layer}</td>
                          <td style={td}>{(e.tiers_cited || []).join(", ") || "—"}</td>
                          <td style={td}>{e.verdict || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : <Empty>The reasoning trace is not available for this session.</Empty>}
              </Section>
            </>
          )}
        </div>
      )}
    </section>
  );
}

const ulStyle = { paddingLeft: 20, margin: 0 };
const th = { padding: "4px 8px 4px 0", fontWeight: 400, color: TOKEN.MUTED };
const td = { padding: "6px 8px 6px 0", color: TOKEN.INK };

function Section({ heading, children }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <div
        style={{
          fontFamily: FONT.GEORGIA,
          fontStyle: "italic",
          fontSize: 13,
          color: TOKEN.ACCENT,
          textTransform: "uppercase",
          letterSpacing: 1.6,
          marginBottom: 8,
        }}
      >
        {heading}
      </div>
      {children}
    </div>
  );
}

function Empty({ children }) {
  return <div style={{ color: TOKEN.MUTED, fontStyle: "italic" }}>{children}</div>;
}
