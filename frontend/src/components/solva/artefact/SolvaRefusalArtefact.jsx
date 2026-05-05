/**
 * Refusal artefact — brief §5.5. Same masthead, four sections instead
 * of five:
 *   1. Masthead (with REFUSAL pill)
 *   2. What's missing
 *   3. What Solva can offer (candidate set, no weighting)
 *   4. Recommended next action
 *
 * Same download dropdown.
 */
import React, { useEffect, useMemo, useState } from "react";
import { Download, AlertTriangle } from "lucide-react";
import { TOKEN, FONT, SUBMODULE_LABELS } from "../flow/tokens";
import ReasoningExpandable from "./ReasoningExpandable";

function stripTier(s) { return (s || "").replace(/\[T:[a-zA-Z_]+\]/g, "").trim(); }
function frameOneLine(intent) {
  const text = (intent || "").trim();
  if (!text) return "Solva session";
  const first = text.split(/(?<=[.!?])\s+/)[0] || text;
  const words = first.split(/\s+/);
  if (words.length > 18) return words.slice(0, 18).join(" ").replace(/[,.;:]$/, "") + "…";
  return first;
}
function formatDate(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleDateString(undefined, { day:"numeric", month:"long", year:"numeric" }); }
  catch (_e) { return iso; }
}

export default function SolvaRefusalArtefact({ session, onStartReflection }) {
  const [downloadOpen, setDownloadOpen] = useState(false);
  const sessionId = session?.id;

  const submoduleLabel = SUBMODULE_LABELS[session?.submodule] || "Solva";
  const persona = session?.persona;

  const refusalContent = useMemo(() => {
    const audit = session?.reasoning_audit_log || [];
    const refs = audit.filter((e) => (e.engine || "").toLowerCase() === "refusal");
    const last = refs.length ? refs[refs.length - 1] : null;
    const out = (last && last.output) || {};
    let whatsMissing = out.missing_evidence || out.reason ||
      "Solva does not have enough grounded evidence to weight scenarios honestly for this question.";
    if (Array.isArray(whatsMissing)) whatsMissing = whatsMissing.join(" ");
    let candidates = out.candidates_for_user || out.candidate_set || [];
    if (!candidates.length) {
      // fallback to candidate_generation engine output
      for (const e of audit) {
        if ((e.engine || "").toLowerCase() === "candidate_generation") {
          const cands = (e.output || {}).candidates || [];
          candidates = cands.map((c) => (typeof c === "string" ? c : c.hypothesis));
          break;
        }
      }
    }
    let nextActions = out.next_actions || out.user_next_steps || [];
    if (!nextActions.length) {
      nextActions = [
        "Pull the source records that would let Solva weight scenarios.",
        "Return for a full synthesis once the evidence gap is closed.",
      ];
    }
    return {
      whatsMissing: stripTier(String(whatsMissing)),
      candidates: candidates.filter(Boolean).map((c) => stripTier(String(c))),
      nextActions: nextActions.filter(Boolean).map((c) => stripTier(String(c))),
    };
  }, [session]);

  const downloadHref = (kind) =>
    `${process.env.REACT_APP_BACKEND_URL}/api/solva/v2/sessions/${sessionId}/export.${kind}`;

  return (
    <article
      data-testid="solva-refusal-artefact"
      style={{ background: TOKEN.LIGHT, padding: "56px 56px 80px", borderRadius: 2, boxShadow: "0 1px 0 rgba(0,0,0,.04)" }}
    >
      <header style={{ position: "relative", borderBottom: `1px solid ${TOKEN.RULE}`, paddingBottom: 18, marginBottom: 32 }}>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            padding: "3px 10px",
            border: `1px solid ${TOKEN.ACCENT_DARK}`,
            color: TOKEN.ACCENT_DARK,
            fontFamily: FONT.CALIBRI,
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: 1.4,
            marginBottom: 14,
          }}
        >
          <AlertTriangle size={12} />
          Honest refusal
        </div>
        <div
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 12,
            color: TOKEN.MUTED,
            textTransform: "uppercase",
            letterSpacing: 1.6,
            marginBottom: 6,
          }}
        >
          {submoduleLabel}{persona ? <> · <span style={{ fontStyle: "italic" }}>{persona}</span></> : null}
        </div>
        <h1
          style={{
            fontFamily: FONT.GEORGIA,
            fontSize: 32,
            color: TOKEN.INK,
            fontWeight: 700,
            margin: "0 0 14px 0",
            lineHeight: 1.2,
            paddingRight: 160,
          }}
        >
          {frameOneLine(session?.intent)}
        </h1>
        <div style={{ display: "flex", gap: 12, fontFamily: FONT.CALIBRI, fontSize: 13, color: TOKEN.DEEP }}>
          <span>{formatDate(session?.completed_at || session?.started_at)}</span>
          {session?.cluster_label && (
            <><span style={{ color: TOKEN.RULE }}>·</span><span style={{ fontStyle: "italic" }}>{session.cluster_label}</span></>
          )}
        </div>
        <div style={{ position: "absolute", top: 0, right: 0 }}>
          <button
            type="button"
            onClick={() => setDownloadOpen((o) => !o)}
            data-testid="solva-artefact-download"
            style={{
              fontFamily: FONT.CALIBRI,
              fontSize: 13,
              padding: "8px 14px",
              background: "transparent",
              color: TOKEN.DEEP,
              border: `1px solid ${TOKEN.RULE}`,
              borderRadius: 2,
              cursor: "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Download size={14} />
            Download
          </button>
          {downloadOpen && (
            <div role="menu" style={{ position: "absolute", right: 0, top: "100%", marginTop: 4, background: TOKEN.LIGHT, border: `1px solid ${TOKEN.RULE}`, minWidth: 220, boxShadow: "0 4px 16px rgba(0,0,0,.06)", zIndex: 5 }}>
              <a href={downloadHref("pdf")} role="menuitem" target="_blank" rel="noreferrer" data-testid="solva-artefact-download-pdf" style={menuItem}>
                <span style={{ fontFamily: FONT.GEORGIA, color: TOKEN.INK, fontSize: 14 }}>PDF</span>
                <span style={{ fontFamily: FONT.CALIBRI, color: TOKEN.MUTED, fontSize: 11 }}>Refusal artefact for sharing.</span>
              </a>
              <a href={downloadHref("docx")} role="menuitem" target="_blank" rel="noreferrer" data-testid="solva-artefact-download-docx" style={menuItem}>
                <span style={{ fontFamily: FONT.GEORGIA, color: TOKEN.INK, fontSize: 14 }}>DOCX</span>
                <span style={{ fontFamily: FONT.CALIBRI, color: TOKEN.MUTED, fontSize: 11 }}>For further editing.</span>
              </a>
            </div>
          )}
        </div>
      </header>

      <section style={{ marginBottom: 56 }}>
        <Kicker>What's missing</Kicker>
        <p style={{ fontFamily: FONT.GEORGIA, fontSize: 18, color: TOKEN.INK, lineHeight: 1.65, margin: 0 }}>
          {refusalContent.whatsMissing}
        </p>
      </section>

      {refusalContent.candidates.length > 0 && (
        <section style={{ marginBottom: 56 }}>
          <Kicker>What Solva can offer</Kicker>
          <p style={{ fontFamily: FONT.GEORGIA, fontStyle: "italic", color: TOKEN.DEEP, fontSize: 14, margin: "0 0 12px 0" }}>
            Here are the framings worth examining, without weighting.
          </p>
          <ul style={{ paddingLeft: 22, margin: 0 }}>
            {refusalContent.candidates.map((c, i) => (
              <li key={i} style={{ fontFamily: FONT.GEORGIA, fontSize: 16, color: TOKEN.INK, marginBottom: 8, lineHeight: 1.55 }}>
                {c}
              </li>
            ))}
          </ul>
        </section>
      )}

      {refusalContent.nextActions.length > 0 && (
        <section style={{ marginBottom: 56 }}>
          <Kicker>Recommended next action</Kicker>
          <ol style={{ paddingLeft: 22, margin: 0 }}>
            {refusalContent.nextActions.map((step, i) => (
              <li key={i} style={{ fontFamily: FONT.GEORGIA, fontSize: 16, color: TOKEN.INK, marginBottom: 8, lineHeight: 1.55 }}>
                {step}
              </li>
            ))}
          </ol>
        </section>
      )}

      <footer style={{ borderTop: `1px solid ${TOKEN.RULE}`, paddingTop: 14, marginTop: 64, color: TOKEN.MUTED, fontFamily: FONT.CALIBRI, fontSize: 12, lineHeight: 1.55 }}>
        Refusal artefact · Session {(sessionId || "").slice(0, 8)} · Audit log {(session?.reasoning_audit_log || []).length} entries
      </footer>

      {sessionId && <ReasoningExpandable sessionId={sessionId} />}

      {onStartReflection && (
        <div style={{ marginTop: 40, textAlign: "right" }}>
          <button
            type="button"
            onClick={onStartReflection}
            data-testid="solva-artefact-reflect"
            style={{
              fontFamily: FONT.CALIBRI,
              fontSize: 13,
              background: "transparent",
              color: TOKEN.DEEP,
              border: `1px solid ${TOKEN.RULE}`,
              padding: "10px 20px",
              cursor: "pointer",
              borderRadius: 2,
            }}
          >
            Reflect on this →
          </button>
        </div>
      )}
    </article>
  );
}

function Kicker({ children }) {
  return (
    <div
      style={{
        fontFamily: FONT.GEORGIA,
        fontStyle: "italic",
        fontSize: 13,
        color: TOKEN.ACCENT,
        textTransform: "uppercase",
        letterSpacing: 1.6,
        marginBottom: 14,
      }}
    >
      {children}
    </div>
  );
}

const menuItem = {
  display: "flex",
  flexDirection: "column",
  gap: 2,
  padding: "10px 14px",
  borderBottom: `1px solid ${TOKEN.RULE}`,
  cursor: "pointer",
  textDecoration: "none",
};
