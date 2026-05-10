/**
 * Solva v3 Artefact — brief §5. Five fixed sections:
 *   1. Masthead
 *   2. Primary diagnosis
 *   3. Scenario block (animated probability bars)
 *   4. Sensitivity drivers callout
 *   5. Surfaced tensions callout
 *
 * Top-right download dropdown: PDF / DOCX. Both hit
 * GET /api/solva/v2/sessions/{sid}/export.pdf|docx (auth-gated).
 *
 * The session prop is the dict returned by
 * GET /api/solva/v2/sessions/{sid} — same shape as the orchestrator stores.
 */
import React, { useMemo, useState } from "react";
import { Download, MessageSquare, RefreshCw, Workflow } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, apiErrorMessage } from "@/lib/api";
import { TOKEN, FONT, SUBMODULE_LABELS } from "../flow/tokens";
import ProbabilityBar from "./ProbabilityBar";
import ReasoningExpandable from "./ReasoningExpandable";
// Wave 2.2 (UAT pack 2026-05-10) — task-specific artefact bodies.
import ClarityRead from "./ClarityRead";
import StrategyMemo from "./StrategyMemo";
import HypothesisStressTest from "./HypothesisStressTest";
import PerspectiveRead from "./PerspectiveRead";

// Wave 2.2 (UAT pack 2026-05-10) — task-specific artefact body
// router. Each entry is a React component receiving the same
// extracted props (diagnosis, scenarios, sensitivity, tensions,
// recommendations, stripTierMarkers). When the submodule key is
// missing or unknown, we fall through to the existing generic
// 5-section body — which is also what the backend export pipeline
// renders (preservation rule 9: backend keeps the generic
// template; frontend differentiates).
const TASK_BODIES = {
  seek_clarity:        ClarityRead,
  develop_strategy:    StrategyMemo,
  simulate_hypothesis: HypothesisStressTest,
  get_perspective:     PerspectiveRead,
};


const BAND_HALF_WIDTH = {
  Unlikely: 15,
  Possible: 10,
  Likely: 8,
  "High-conviction": 5,
};

const TIER_MARKER_RE = /\[T:[a-zA-Z_]+\]/g;

function stripTierMarkers(text) {
  return (text || "").replace(TIER_MARKER_RE, "").replace(/\s+/g, " ").trim();
}

function splitParagraphs(body) {
  if (!body) return [];
  const cleaned = stripTierMarkers(body);
  return cleaned.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
}

function scenariosFromClaims(claims = []) {
  return claims
    .filter((c) => c && c.text)
    .map((c) => {
      const text = stripTierMarkers(c.text);
      const words = text.split(/\s+/);
      const head = words.slice(0, 8).join(" ") + (words.length > 8 ? "…" : "");
      const rest = words.length > 8 ? words.slice(8).join(" ") : "";
      const pct = typeof c.confidence_pct === "number" ? c.confidence_pct : 50;
      const half = BAND_HALF_WIDTH[c.confidence_band] ?? 10;
      return {
        label: head,
        desc: rest,
        pct,
        low: Math.max(0, pct - half),
        high: Math.min(100, pct + half),
        band: c.confidence_band || "Possible",
        tier: c.tier || "",
      };
    })
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 5);
}

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
  try {
    return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
  } catch (_e) { return iso; }
}

function formatDuration(start, end) {
  if (!start || !end) return null;
  try {
    const ms = new Date(end).getTime() - new Date(start).getTime();
    const min = Math.round(ms / 60000);
    if (min < 1) return "under a minute";
    if (min === 1) return "1 minute";
    if (min < 90) return `${min} minutes`;
    const h = Math.floor(min / 60);
    const r = min % 60;
    return r ? `${h}h ${r}m` : `${h} hours`;
  } catch (_e) { return null; }
}

function sensitivityFrom(scenarios) {
  const weak = scenarios.filter((s) =>
    ["domain_prior", "user_assertion", "speculation"].includes(s.tier),
  );
  return weak.slice(0, 3).map((s) =>
    `If the assumption that ${s.label.toLowerCase()} no longer holds, the ${s.pct}% read would move materially.`
  );
}

function tensionsFromSession(session) {
  if (session?._hypothesis_tensions?.length) {
    return session._hypothesis_tensions
      .map((t) => (typeof t === "string" ? t : t.description || t.text || t.summary || ""))
      .filter(Boolean)
      .slice(0, 3);
  }
  if (session?.synthesis?.tensions?.length) {
    return session.synthesis.tensions
      .map((t) => (typeof t === "string" ? t : t.description || t.text || t.summary || ""))
      .filter(Boolean)
      .slice(0, 3);
  }
  const audit = session?.reasoning_audit_log || [];
  for (const e of audit) {
    if ((e.engine || "").toLowerCase() === "tension_detector") {
      const out = e.output || {};
      const list = out.tensions || out.found || [];
      return list
        .map((t) => (typeof t === "string" ? t : t.description || t.text || t.summary || ""))
        .filter(Boolean)
        .slice(0, 3);
    }
  }
  return [];
}

export default function SolvaArtefact({ session, onStartReflection, savedToast = false }) {
  const [downloadOpen, setDownloadOpen] = useState(false);
  const sessionId = session?.id;

  const synthesis = session?.synthesis || {};
  const claims = synthesis.claims || [];

  const scenarios = useMemo(() => scenariosFromClaims(claims), [claims]);
  const diagnosis = useMemo(() => splitParagraphs(synthesis.body || synthesis.stripped_text || ""), [synthesis.body, synthesis.stripped_text]);
  const sensitivity = useMemo(() => sensitivityFrom(scenarios), [scenarios]);
  const tensions = useMemo(() => tensionsFromSession(session), [session]);
  const recommendations = synthesis.recommendations || [];

  const submoduleLabel = SUBMODULE_LABELS[session?.submodule] || "Solva";
  const persona = session?.persona;

  const downloadHref = (kind) =>
    `${process.env.REACT_APP_BACKEND_URL}/api/solva/v2/sessions/${sessionId}/export.${kind}`;

  return (
    <article
      data-testid="solva-artefact"
      style={{ background: TOKEN.LIGHT, padding: "56px 56px 80px", borderRadius: 2, boxShadow: "0 1px 0 rgba(0,0,0,.04)" }}
    >
      {/* Masthead */}
      <header style={{ position: "relative", borderBottom: `1px solid ${TOKEN.RULE}`, paddingBottom: 18, marginBottom: 32 }}>
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
          {formatDuration(session?.started_at, session?.completed_at || session?.updated_at) && (
            <><span style={{ color: TOKEN.RULE }}>·</span><span>{formatDuration(session?.started_at, session?.completed_at || session?.updated_at)}</span></>
          )}
          {session?.cluster_label && (
            <><span style={{ color: TOKEN.RULE }}>·</span><span style={{ fontStyle: "italic" }}>{session.cluster_label}</span></>
          )}
        </div>

        {/* Download dropdown */}
        <div style={{ position: "absolute", top: 0, right: 0 }}>
          <button
            type="button"
            onClick={() => setDownloadOpen((o) => !o)}
            data-testid="solva-artefact-download"
            aria-haspopup="menu"
            aria-expanded={downloadOpen}
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
            <div
              role="menu"
              style={{
                position: "absolute",
                right: 0,
                top: "100%",
                marginTop: 4,
                background: TOKEN.LIGHT,
                border: `1px solid ${TOKEN.RULE}`,
                minWidth: 220,
                boxShadow: "0 4px 16px rgba(0,0,0,.06)",
                zIndex: 5,
              }}
            >
              <a
                href={downloadHref("pdf")}
                role="menuitem"
                target="_blank"
                rel="noreferrer"
                onClick={() => setDownloadOpen(false)}
                data-testid="solva-artefact-download-pdf"
                style={menuItem}
              >
                <span style={{ fontFamily: FONT.GEORGIA, color: TOKEN.INK, fontSize: 14 }}>PDF</span>
                <span style={{ fontFamily: FONT.CALIBRI, color: TOKEN.MUTED, fontSize: 11 }}>For sharing or printing.</span>
              </a>
              <a
                href={downloadHref("docx")}
                role="menuitem"
                target="_blank"
                rel="noreferrer"
                onClick={() => setDownloadOpen(false)}
                data-testid="solva-artefact-download-docx"
                style={menuItem}
              >
                <span style={{ fontFamily: FONT.GEORGIA, color: TOKEN.INK, fontSize: 14 }}>DOCX</span>
                <span style={{ fontFamily: FONT.CALIBRI, color: TOKEN.MUTED, fontSize: 11 }}>For further editing.</span>
              </a>
            </div>
          )}
        </div>
      </header>

      {/* Wave 2.2 (UAT pack 2026-05-10) — task-specific artefact body.
          Each submodule renders its own structure. The Generic body
          (Primary diagnosis + Scenarios + Sensitivity + Tensions +
          Recommendations) remains the fallback for sessions where
          submodule is missing or unrecognised, AND is the path the
          backend PDF/DOCX exporter still hits (preservation rule 9). */}
      {(() => {
        const TaskBody = TASK_BODIES[session?.submodule] || null;
        if (TaskBody) {
          return (
            <TaskBody
              session={session}
              diagnosis={diagnosis}
              scenarios={scenarios}
              sensitivity={sensitivity}
              tensions={tensions}
              recommendations={recommendations}
              stripTierMarkers={stripTierMarkers}
            />
          );
        }
        return null;
      })()}

      {/* Generic body — rendered only when no task-specific template
          matched (e.g. legacy sessions or unknown submodule). */}
      {!TASK_BODIES[session?.submodule] && (
        <>
          {/* Primary diagnosis */}
          <section style={{ marginBottom: 56 }}>
            <Kicker>Primary diagnosis</Kicker>
            {diagnosis.length ? (
              diagnosis.map((p, i) => (
                <p
                  key={i}
                  style={{
                    fontFamily: FONT.GEORGIA,
                    fontSize: 18,
                    color: TOKEN.INK,
                    lineHeight: 1.65,
                    margin: "0 0 14px 0",
                  }}
                >
                  {p}
                </p>
              ))
            ) : (
              <p style={{ fontFamily: FONT.GEORGIA, fontStyle: "italic", color: TOKEN.MUTED }}>
                Diagnosis not yet available for this session.
              </p>
            )}
          </section>

          {/* Scenarios */}
          {scenarios.length > 0 && (
            <section style={{ marginBottom: 56 }}>
              <Kicker>Scenarios</Kicker>
              {scenarios.map((s, i) => (
                <ProbabilityBar
                  key={i}
                  label={s.label}
                  desc={s.desc}
                  pct={s.pct}
                  low={s.low}
                  high={s.high}
                  tier={s.tier}
                  testId={`solva-scenario-${i}`}
                />
              ))}
            </section>
          )}

          {/* Sensitivity callout */}
          {sensitivity.length > 0 && (
            <Callout
              variant="sensitivity"
              kicker="What would change this read"
              items={sensitivity}
              testId="solva-sensitivity"
            />
          )}

          {/* Tension callout */}
          {tensions.length > 0 && (
            <Callout
              variant="tension"
              kicker="Where your framing and the evidence diverge"
              items={tensions}
              testId="solva-tension"
            />
          )}

          {/* Recommendations — develop_strategy carries these */}
          {recommendations.length > 0 && (
            <section style={{ marginBottom: 56 }}>
              <Kicker>Recommendations</Kicker>
              <ol style={{ paddingLeft: 22, margin: 0 }}>
                {recommendations.map((r, i) => {
                  const text = typeof r === "string" ? r : (r.body || r.text || "");
                  const head = typeof r === "string"
                    ? (text.match(/Recommendation\s*\d+:\s*/i)?.[0] || `Recommendation ${i + 1}: `)
                    : (r.heading || `Recommendation ${i + 1}`);
                  const body = typeof r === "string"
                    ? text.replace(/^\s*Recommendation\s*\d+:\s*/i, "").replace(TIER_MARKER_RE, "").trim()
                    : (text || "").replace(TIER_MARKER_RE, "").trim();
                  return (
                    <li key={i} style={{ marginBottom: 12, fontFamily: FONT.GEORGIA, fontSize: 16, color: TOKEN.INK, lineHeight: 1.55 }}>
                      <strong>{head}</strong>{body ? <> {body.replace(/^—\s*/, "")}</> : null}
                    </li>
                  );
                })}
              </ol>
            </section>
          )}
        </>
      )}

      {/* Footer */}
      <footer style={{ borderTop: `1px solid ${TOKEN.RULE}`, paddingTop: 14, marginTop: 64, color: TOKEN.MUTED, fontFamily: FONT.CALIBRI, fontSize: 12, lineHeight: 1.55 }}>
        Session {(sessionId || "").slice(0, 8)} · Audit log {(session?.reasoning_audit_log || []).length} entries
      </footer>

      {/* Reasoning expandable — collapsed by default */}
      {sessionId && <ReasoningExpandable sessionId={sessionId} />}

      {/* Wave 1.5 (UAT pack 2026-05-10) — handoff bar.
          Continue in Chat → mints a chat tethered to this artefact.
          Use as input → opens picker with seed_kind=solva_artefact.
          Take to Cycle → currently a TODO (toast); cycle-question
          minting from a Solva session is a Wave 3 stretch. */}
      {(session?.status === "complete" || session?.status === "refused") && (
        <SolvaArtefactHandoffBar session={session} sessionId={sessionId} />
      )}

      {/* Continue to reflection — muted CTA, only when reflection not yet started */}
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

      {savedToast && (
        <div
          role="status"
          aria-live="polite"
          style={{
            position: "fixed",
            bottom: 32,
            left: "50%",
            transform: "translateX(-50%)",
            background: TOKEN.INK,
            color: TOKEN.LIGHT,
            fontFamily: FONT.CALIBRI,
            fontSize: 13,
            padding: "10px 18px",
            borderRadius: 2,
            boxShadow: "0 4px 16px rgba(0,0,0,.18)",
          }}
        >
          Session saved
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

function Callout({ kicker, items, variant, testId }) {
  const isSens = variant === "sensitivity";
  return (
    <aside
      data-testid={testId}
      style={{
        background: isSens ? TOKEN.CREAM : TOKEN.CREAM_DEEP,
        borderTop: isSens ? `1.5px solid ${TOKEN.ACCENT}` : "none",
        borderBottom: isSens ? `1.5px solid ${TOKEN.ACCENT}` : "none",
        borderLeft: !isSens ? `3px solid ${TOKEN.ACCENT}` : "none",
        padding: 22,
        marginBottom: 40,
      }}
    >
      <div
        style={{
          fontFamily: FONT.GEORGIA,
          fontStyle: "italic",
          fontSize: 13,
          color: TOKEN.ACCENT,
          marginBottom: 8,
        }}
      >
        {kicker}
      </div>
      {items.length === 1 ? (
        <p style={{ fontFamily: FONT.GEORGIA, fontSize: 16, color: TOKEN.INK, margin: 0, lineHeight: 1.55 }}>
          {items[0]}
        </p>
      ) : (
        <ul style={{ paddingLeft: 20, margin: 0 }}>
          {items.map((it, i) => (
            <li key={i} style={{ fontFamily: FONT.GEORGIA, fontSize: 15, color: TOKEN.INK, marginBottom: 6, lineHeight: 1.55 }}>
              {it}
            </li>
          ))}
        </ul>
      )}
    </aside>
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


// =============================================================================
// Wave 1.5 (UAT pack 2026-05-10) — Solva artefact handoff bar.
// =============================================================================
// Three actions:
//   - Continue in Chat — POST /sessions/{sid}/continue-chat → mints a chat
//     tethered to this artefact, navigates to /app/chat?chat_id=<id>.
//   - Use as input — opens picker with seed_kind=solva_artefact pre-loaded.
//   - Take to Cycle — Wave 3 stretch; today renders a "coming soon" toast.

function SolvaArtefactHandoffBar({ session, sessionId }) {
  const navigate = useNavigate();
  const [continuing, setContinuing] = useState(false);

  const onContinueInChat = async () => {
    if (!sessionId) return;
    setContinuing(true);
    try {
      const { data } = await api.post(`/solva/v2/sessions/${sessionId}/continue-chat`);
      if (data?.chat_id) {
        navigate(`/app/chat?chat_id=${encodeURIComponent(data.chat_id)}`);
      } else {
        toast.error("Could not open chat handoff.");
      }
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setContinuing(false);
    }
  };

  const onUseAsInput = () => {
    if (!sessionId) return;
    navigate(`/app/solva?seed_kind=solva_artefact&seed_id=${encodeURIComponent(sessionId)}`);
  };

  const onTakeToCycle = () => {
    // Stretch — wired in Wave 3 if budget allows. For UAT we surface
    // the affordance and tell the user it's coming.
    toast.info("Take-to-Cycle from Solva is coming next. For now, use Continue in Chat.");
  };

  const status = session?.status;
  return (
    <div
      data-testid="solva-artefact-handoff-bar"
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 10,
        marginTop: 28,
        paddingTop: 18,
        borderTop: `1px solid ${TOKEN.RULE}`,
      }}
    >
      <button
        type="button"
        disabled={continuing}
        onClick={onContinueInChat}
        data-testid="solva-handoff-continue-chat"
        style={{
          background: TOKEN.ACCENT, color: "#FFFFFF", border: "none",
          padding: "9px 16px", borderRadius: 2, cursor: "pointer",
          fontFamily: FONT.CALIBRI, fontSize: 13, fontWeight: 500,
          letterSpacing: 0.3, display: "inline-flex", alignItems: "center", gap: 6,
        }}
      >
        <MessageSquare width={14} height={14} />
        {continuing ? "Opening…" : "Continue in Chat"}
      </button>
      {status !== "refused" && (
        <button
          type="button"
          onClick={onUseAsInput}
          data-testid="solva-handoff-use-as-input"
          style={{
            background: "transparent", color: TOKEN.INK,
            border: `1px solid ${TOKEN.RULE}`,
            padding: "9px 16px", borderRadius: 2, cursor: "pointer",
            fontFamily: FONT.CALIBRI, fontSize: 13,
            display: "inline-flex", alignItems: "center", gap: 6,
          }}
        >
          <RefreshCw width={14} height={14} />
          Use as input for a new session
        </button>
      )}
      <button
        type="button"
        onClick={onTakeToCycle}
        data-testid="solva-handoff-take-to-cycle"
        style={{
          background: "transparent", color: TOKEN.MUTED,
          border: `1px solid ${TOKEN.RULE}`,
          padding: "9px 16px", borderRadius: 2, cursor: "pointer",
          fontFamily: FONT.CALIBRI, fontSize: 13,
          display: "inline-flex", alignItems: "center", gap: 6,
        }}
        title="Add this as a question for an upcoming cycle"
      >
        <Workflow width={14} height={14} />
        Take to Cycle
      </button>
    </div>
  );
}
