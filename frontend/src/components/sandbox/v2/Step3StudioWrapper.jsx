/**
 * Phase J.3 — Step 3 Work Studio split view.
 *
 * Brief §6 layout: two-column on desktop, stacked on mobile.
 *
 *   ┌────────────────────────┬────────────────────────────────────┐
 *   │ SOURCE MATERIALS       │ COMPOSITION                        │
 *   │  ─ chips (3 source     │  Phase 1: rotating narration line  │
 *   │    docs from corpus)   │           every 12-18s for ~75s    │
 *   │  ─ click chip → modal  │  Phase 2: composed paragraphs with │
 *   │    body + reset        │           hover-citation on        │
 *   │                        │           [Doc N] markers          │
 *   │                        │  Phase 3: "Add a sentence" probe   │
 *   │                        │           → server provenance      │
 *   │                        │           check, refuses if no     │
 *   │                        │           keyword overlap.         │
 *   └────────────────────────┴────────────────────────────────────┘
 *
 * Backend touchpoints:
 *   GET  /api/sandbox/v2/sessions/{sid}/studio-sources
 *   GET  /api/sandbox/v2/sessions/{sid}/composed-draft
 *   POST /api/sandbox/v2/sessions/{sid}/studio/add-sentence
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";

import { TOKEN, FONT } from "./tokens";
import { Actions } from "@/lib/sandboxV2Flow";
import usePrefersReducedMotion from "@/components/solva/flow/usePrefersReducedMotion";

const API = process.env.REACT_APP_BACKEND_URL || "";
const api = axios.create({
  baseURL: `${API}/api/sandbox/v2`,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
});

/* The 5 narration lines the agent rotates through over ~75s.
 * Brief-locked phrasing (§6.2). */
const NARRATION_LINES = [
  "Reading what's in your materials.",
  "Finding the through-lines that hold up.",
  "Mapping each claim back to a source.",
  "Building the position statement, paragraph by paragraph.",
  "Editing for the voice you'd actually use.",
];

const TOTAL_NARRATION_MS = 75_000;
const PER_LINE_MS = Math.round(TOTAL_NARRATION_MS / NARRATION_LINES.length);

export default function Step3StudioWrapper({ flow, dispatch, onComplete }) {
  const sid = flow.sessionId;
  const reduced = usePrefersReducedMotion();
  const [sources, setSources] = useState([]);
  const [draft, setDraft] = useState(null); // { title, paragraphs[] }
  const [phase, setPhase] = useState("LOADING"); // LOADING | NARRATING | COMPOSED
  const [narrationIdx, setNarrationIdx] = useState(0);
  const [openSourceId, setOpenSourceId] = useState(null);
  const [hoveredCitation, setHoveredCitation] = useState(null);
  const [addSentence, setAddSentence] = useState("");
  const [addBusy, setAddBusy] = useState(false);
  const [addResult, setAddResult] = useState(null); // { accepted, citation?, message? }
  const [bootError, setBootError] = useState(null);

  /* Fetch sources + composed draft up-front, then begin narration. */
  useEffect(() => {
    let cancelled = false;
    async function init() {
      if (!sid) return;
      try {
        const [src, dr] = await Promise.all([
          api.get(`/sessions/${sid}/studio-sources`),
          api.get(`/sessions/${sid}/composed-draft`),
        ]);
        if (cancelled) return;
        setSources(src.data?.sources || []);
        setDraft(dr.data?.draft || null);
        setPhase(reduced ? "COMPOSED" : "NARRATING");
        if (reduced) {
          dispatch(Actions.studioDraftBuilt());
        }
      } catch (e) {
        if (cancelled) return;
        setBootError("Could not load Sandbox sources.");
      }
    }
    init();
    return () => { cancelled = true; };
  }, [sid, reduced, dispatch]);

  /* Drive the narration timer. */
  useEffect(() => {
    if (phase !== "NARRATING") return undefined;
    if (narrationIdx >= NARRATION_LINES.length - 1) {
      // Final line — hold for the residual budget then reveal draft.
      const t = window.setTimeout(() => {
        setPhase("COMPOSED");
        dispatch(Actions.studioDraftBuilt());
      }, PER_LINE_MS);
      return () => window.clearTimeout(t);
    }
    const t = window.setTimeout(
      () => setNarrationIdx((i) => i + 1),
      PER_LINE_MS,
    );
    return () => window.clearTimeout(t);
  }, [phase, narrationIdx, dispatch]);

  /* Hover-source resolution: read [Doc N] from a span and look up the
   * nth source. Backed by source[] order from the corpus.            */
  const docByOrder = useMemo(() => {
    const out = {};
    sources.forEach((s, i) => { out[String(i + 1)] = s; });
    return out;
  }, [sources]);

  const onCitationHover = useCallback((label) => {
    // label like "Doc 1" or "Doc 2, Section 4"
    const m = /Doc\s+(\d+)/i.exec(label || "");
    if (!m) {
      setHoveredCitation(null);
      return;
    }
    const src = docByOrder[m[1]];
    if (src) {
      setHoveredCitation({ label, source: src });
    } else {
      setHoveredCitation({ label, source: null });
    }
  }, [docByOrder]);

  /* Provenance probe (POST add-sentence). */
  const submitAddSentence = useCallback(async () => {
    const txt = addSentence.trim();
    if (!txt || !sid) return;
    setAddBusy(true);
    try {
      const r = await api.post(`/sessions/${sid}/studio/add-sentence`, {
        sentence: txt,
      });
      const data = r.data || {};
      setAddResult(data);
      if (data.accepted) {
        dispatch(Actions.studioSentenceAccepted(txt));
      } else {
        dispatch(Actions.studioSentenceRefused(txt));
      }
    } catch (e) {
      setAddResult({
        accepted: false,
        message: e?.response?.data?.detail || e.message || "Could not check provenance.",
      });
    } finally {
      setAddBusy(false);
    }
  }, [addSentence, sid, dispatch]);

  if (bootError) {
    return (
      <div role="alert" style={errorBoxStyle}>{bootError}</div>
    );
  }

  return (
    <div data-testid="sandbox-v2-step3" style={{ width: "100%" }}>
      <Header />
      <div style={layoutStyle}>
        <SourceColumn
          sources={sources}
          openSourceId={openSourceId}
          setOpenSourceId={setOpenSourceId}
        />
        <CompositionColumn
          phase={phase}
          narrationIdx={narrationIdx}
          draft={draft}
          onCitationHover={onCitationHover}
          hoveredCitation={hoveredCitation}
          addSentence={addSentence}
          setAddSentence={setAddSentence}
          submitAddSentence={submitAddSentence}
          addBusy={addBusy}
          addResult={addResult}
          onComplete={onComplete}
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function Header() {
  return (
    <div style={{ marginBottom: 28, textAlign: "center" }}>
      <div style={{ width: 56, height: 1, background: TOKEN.ACCENT, margin: "0 auto 22px" }} />
      <h1 style={{
        fontFamily: FONT.GEORGIA, fontSize: 26, fontWeight: 700,
        color: TOKEN.INK, margin: 0, lineHeight: 1.2,
      }}>
        Composition with provenance.
      </h1>
      <p style={{
        fontFamily: FONT.GEORGIA, fontStyle: "italic", fontSize: 15,
        color: TOKEN.DEEP, margin: "10px auto 0", maxWidth: 620, lineHeight: 1.55,
      }}>
        Watch Akki build a position note from the materials on the left. Every
        claim is anchored. Hover any <span style={{ fontFamily: FONT.CALIBRI, fontSize: 12 }}>[Doc N]</span> marker to see its source.
      </p>
    </div>
  );
}

function SourceColumn({ sources, openSourceId, setOpenSourceId }) {
  return (
    <aside
      style={{
        background: TOKEN.PAPER,
        border: `1px solid ${TOKEN.RULE}`,
        padding: "20px 18px",
        borderRadius: 2,
        minHeight: 360,
      }}
    >
      <div style={kickerStyle}>Source materials</div>
      <ul style={{ margin: 0, padding: 0, listStyle: "none" }}>
        {sources.map((s, i) => {
          const open = openSourceId === s.id;
          return (
            <li key={s.id} style={{ marginBottom: 14 }}>
              <button
                type="button"
                onClick={() => setOpenSourceId(open ? null : s.id)}
                aria-expanded={open}
                aria-controls={`sandbox-v2-source-${s.id}`}
                data-testid={`sandbox-v2-source-chip-${i + 1}`}
                style={{
                  width: "100%",
                  textAlign: "left",
                  background: TOKEN.LIGHT,
                  border: `1px solid ${TOKEN.RULE}`,
                  padding: "12px 14px",
                  fontFamily: FONT.CALIBRI,
                  cursor: "pointer",
                  borderRadius: 2,
                }}
              >
                <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1.2, color: TOKEN.MUTED, marginBottom: 4 }}>
                  Doc {i + 1} · {s.kind}
                </div>
                <div style={{ fontSize: 13, color: TOKEN.INK, lineHeight: 1.4 }}>
                  {s.title}
                </div>
              </button>
              {open && (
                <div
                  id={`sandbox-v2-source-${s.id}`}
                  style={{
                    background: TOKEN.LIGHT,
                    border: `1px solid ${TOKEN.RULE}`,
                    borderTop: "none",
                    padding: "12px 14px",
                    fontFamily: FONT.GEORGIA,
                    fontSize: 13,
                    color: TOKEN.DEEP,
                    lineHeight: 1.6,
                    borderRadius: "0 0 2px 2px",
                  }}
                >
                  {s.body}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}

function CompositionColumn({
  phase, narrationIdx, draft, onCitationHover, hoveredCitation,
  addSentence, setAddSentence, submitAddSentence, addBusy, addResult,
  onComplete,
}) {
  return (
    <section
      style={{
        background: TOKEN.LIGHT,
        border: `1px solid ${TOKEN.RULE}`,
        padding: "22px 22px 28px",
        borderRadius: 2,
        minHeight: 360,
        position: "relative",
      }}
      aria-busy={phase === "NARRATING"}
    >
      <div style={kickerStyle}>Composition</div>

      {phase === "LOADING" && (
        <p style={{ fontFamily: FONT.GEORGIA, fontStyle: "italic", color: TOKEN.MUTED }}>
          Loading Akki's working set…
        </p>
      )}

      {phase === "NARRATING" && (
        <NarrationView idx={narrationIdx} />
      )}

      {phase === "COMPOSED" && draft && (
        <ComposedDraft
          draft={draft}
          onCitationHover={onCitationHover}
          hoveredCitation={hoveredCitation}
        />
      )}

      {phase === "COMPOSED" && (
        <ProvenanceProbe
          addSentence={addSentence}
          setAddSentence={setAddSentence}
          submitAddSentence={submitAddSentence}
          addBusy={addBusy}
          addResult={addResult}
        />
      )}

      {phase === "COMPOSED" && (
        <div style={{ marginTop: 28, textAlign: "right" }}>
          <button
            type="button"
            onClick={onComplete}
            data-testid="sandbox-v2-step3-continue"
            style={{
              fontFamily: FONT.CALIBRI,
              fontSize: 14,
              background: TOKEN.ACCENT_DARK,
              color: TOKEN.LIGHT,
              border: "none",
              padding: "11px 24px",
              cursor: "pointer",
              borderRadius: 2,
              letterSpacing: 0.5,
            }}
          >
            See what just happened &rarr;
          </button>
        </div>
      )}
    </section>
  );
}

function NarrationView({ idx }) {
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="sandbox-v2-step3-narration"
      style={{
        minHeight: 220,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "32px 16px",
      }}
    >
      <div>
        {NARRATION_LINES.map((line, i) => {
          const visible = i === idx;
          return (
            <p
              key={i}
              data-narration-active={visible ? "true" : "false"}
              style={{
                fontFamily: FONT.GEORGIA,
                fontStyle: "italic",
                fontSize: 18,
                color: TOKEN.DEEP,
                margin: 0,
                opacity: visible ? 1 : 0,
                position: visible ? "static" : "absolute",
                pointerEvents: visible ? "auto" : "none",
                transition: "opacity 350ms ease-out",
                lineHeight: 1.55,
              }}
            >
              {line}
            </p>
          );
        })}
        <div style={{ marginTop: 28, fontFamily: FONT.CALIBRI, fontSize: 11, color: TOKEN.MUTED, letterSpacing: 1.2, textTransform: "uppercase" }}>
          {idx + 1} of {NARRATION_LINES.length}
        </div>
      </div>
    </div>
  );
}

/** Render a paragraph, splitting on [Doc N] / [Doc N, ...] / [synthesis ...] /
 *  [CBK Thematic Review ...] markers and replacing each with a hover
 *  span that surfaces the source. The marker text is preserved
 *  verbatim — the corpus drafts already follow this convention. */
function ComposedDraft({ draft, onCitationHover, hoveredCitation }) {
  const re = /\[(Doc[^\]]+|synthesis[^\]]*|CBK[^\]]+|External[^\]]+)\]/g;
  return (
    <div data-testid="sandbox-v2-step3-composed">
      {draft.title && (
        <h2 style={{
          fontFamily: FONT.GEORGIA,
          fontSize: 22,
          fontWeight: 700,
          color: TOKEN.INK,
          margin: "0 0 18px 0",
        }}>
          {draft.title}
        </h2>
      )}
      {(draft.paragraphs || []).map((p, i) => {
        const parts = [];
        let last = 0;
        let m;
        const localRe = new RegExp(re.source, "g");
        while ((m = localRe.exec(p)) !== null) {
          if (m.index > last) parts.push({ kind: "text", text: p.slice(last, m.index) });
          parts.push({ kind: "cite", text: m[0], label: m[1] });
          last = m.index + m[0].length;
        }
        if (last < p.length) parts.push({ kind: "text", text: p.slice(last) });
        return (
          <p
            key={i}
            style={{
              fontFamily: FONT.GEORGIA,
              fontSize: 16,
              color: TOKEN.INK,
              lineHeight: 1.65,
              margin: "0 0 14px 0",
            }}
          >
            {parts.map((part, j) => {
              if (part.kind === "text") return <span key={j}>{part.text}</span>;
              return (
                <CitationPill
                  key={j}
                  label={part.label}
                  text={part.text}
                  onHover={onCitationHover}
                />
              );
            })}
          </p>
        );
      })}
      {hoveredCitation && (
        <CitationTooltip cite={hoveredCitation} />
      )}
    </div>
  );
}

function CitationPill({ label, text, onHover }) {
  return (
    <span
      tabIndex={0}
      role="button"
      aria-label={`Source: ${label}`}
      onMouseEnter={() => onHover(label)}
      onMouseLeave={() => onHover(null)}
      onFocus={() => onHover(label)}
      onBlur={() => onHover(null)}
      data-testid="sandbox-v2-citation"
      style={{
        fontFamily: FONT.CALIBRI,
        fontSize: 12,
        color: TOKEN.ACCENT_DARK,
        background: TOKEN.CREAM,
        padding: "0 4px",
        marginLeft: 2,
        borderRadius: 2,
        cursor: "help",
        whiteSpace: "nowrap",
      }}
    >
      {text}
    </span>
  );
}

function CitationTooltip({ cite }) {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        marginTop: 18,
        padding: "12px 14px",
        background: TOKEN.CREAM,
        border: `1px solid ${TOKEN.RULE}`,
        borderRadius: 2,
        fontFamily: FONT.CALIBRI,
        fontSize: 13,
        color: TOKEN.DEEP,
        lineHeight: 1.55,
      }}
    >
      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1.2, color: TOKEN.MUTED, marginBottom: 4 }}>
        {cite.label}
      </div>
      {cite.source ? (
        <>
          <div style={{ color: TOKEN.INK, marginBottom: 6 }}>{cite.source.title}</div>
          <div style={{ fontFamily: FONT.GEORGIA, fontSize: 12 }}>{cite.source.body.slice(0, 280)}{cite.source.body.length > 280 ? "…" : ""}</div>
        </>
      ) : (
        <div style={{ fontStyle: "italic" }}>External or synthesis citation — no document body.</div>
      )}
    </div>
  );
}

function ProvenanceProbe({ addSentence, setAddSentence, submitAddSentence, addBusy, addResult }) {
  const accepted = addResult?.accepted === true;
  const refused = addResult?.accepted === false;
  return (
    <div
      style={{
        marginTop: 28,
        paddingTop: 22,
        borderTop: `1px dotted ${TOKEN.RULE}`,
      }}
    >
      <div style={kickerStyle}>Try adding your own claim</div>
      <p style={{
        fontFamily: FONT.GEORGIA,
        fontStyle: "italic",
        fontSize: 14,
        color: TOKEN.DEEP,
        margin: "6px 0 14px",
        lineHeight: 1.55,
      }}>
        Type a sentence you'd want this draft to make. Akki will accept it
        if it's grounded in the materials on the left — and refuse it if it
        isn't.
      </p>
      <textarea
        value={addSentence}
        onChange={(e) => setAddSentence(e.target.value)}
        placeholder="e.g. The provisioning trajectory should be reviewed at the next risk committee."
        rows={2}
        maxLength={400}
        data-testid="sandbox-v2-step3-add-input"
        style={{
          width: "100%",
          fontFamily: FONT.GEORGIA,
          fontSize: 14,
          padding: "10px 12px",
          border: `1px solid ${TOKEN.RULE}`,
          borderRadius: 2,
          background: TOKEN.LIGHT,
          color: TOKEN.INK,
          outline: "none",
          resize: "vertical",
          lineHeight: 1.55,
        }}
      />
      <div style={{ marginTop: 10, display: "flex", gap: 12, alignItems: "center" }}>
        <button
          type="button"
          onClick={submitAddSentence}
          disabled={addBusy || !addSentence.trim()}
          data-testid="sandbox-v2-step3-add-submit"
          style={{
            fontFamily: FONT.CALIBRI,
            fontSize: 13,
            background: addBusy || !addSentence.trim() ? TOKEN.RULE : TOKEN.INK,
            color: TOKEN.LIGHT,
            border: "none",
            padding: "9px 18px",
            cursor: addBusy || !addSentence.trim() ? "not-allowed" : "pointer",
            borderRadius: 2,
            letterSpacing: 0.4,
          }}
        >
          {addBusy ? "Checking…" : "Check provenance"}
        </button>
      </div>

      {accepted && (
        <div
          role="status"
          aria-live="polite"
          data-testid="sandbox-v2-step3-add-accepted"
          style={{
            marginTop: 14,
            padding: 12,
            background: TOKEN.CREAM,
            border: `1px solid ${TOKEN.RULE}`,
            fontFamily: FONT.CALIBRI,
            fontSize: 13,
            color: TOKEN.INK,
            lineHeight: 1.55,
            borderRadius: 2,
          }}
        >
          <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: 1.2, color: TOKEN.MUTED, marginBottom: 4 }}>
            Accepted with citation
          </div>
          {(addResult.citation?.sources || []).map((s, i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              [{s.kind}] {s.title}
            </div>
          ))}
        </div>
      )}

      {refused && (
        <div
          role="alert"
          data-testid="sandbox-v2-step3-add-refused"
          style={{
            marginTop: 14,
            padding: 12,
            background: TOKEN.LIGHT,
            border: `1px solid ${TOKEN.ACCENT_DARK}`,
            fontFamily: FONT.GEORGIA,
            fontStyle: "italic",
            fontSize: 14,
            color: TOKEN.ACCENT_DARK,
            lineHeight: 1.6,
            borderRadius: 2,
          }}
        >
          <div style={{ fontFamily: FONT.CALIBRI, fontStyle: "normal", fontSize: 11, textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 6 }}>
            Refused — no citation in materials
          </div>
          {addResult.message}
        </div>
      )}
    </div>
  );
}

const kickerStyle = {
  fontFamily: FONT.CALIBRI,
  fontSize: 11,
  textTransform: "uppercase",
  letterSpacing: 1.4,
  color: TOKEN.MUTED,
  marginBottom: 12,
};
const errorBoxStyle = {
  padding: 24,
  fontFamily: FONT.CALIBRI,
  color: TOKEN.ACCENT_DARK,
  border: `1px solid ${TOKEN.ACCENT_DARK}`,
  background: TOKEN.LIGHT,
  borderRadius: 2,
};
const layoutStyle = {
  display: "grid",
  gridTemplateColumns: "minmax(260px, 0.85fr) minmax(0, 1.5fr)",
  gap: 24,
  alignItems: "start",
  // Stack on narrow viewports.
  ...(typeof window !== "undefined" && window.innerWidth < 760 ? { gridTemplateColumns: "1fr" } : {}),
};
