/**
 * Solva v2 POC page (Phase 15.0).
 *
 * Gated by `account.solva_v2_poc === true`. Users without the flag see a
 * plain "not enabled for your account" card. No AppShell changes, no nav
 * entry; direct URL only: /app/solva/v2-poc.
 *
 * UI intentionally minimal — the surface here is the architecture, not the
 * design. Polish lands in Phase 15.3.
 */
import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "../components/layout/AppShell";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../lib/api";

const LAYER_LABELS = {
  framing: "Framing",
  grounding: "Grounding",
  synthesis: "Synthesis",
  reflection: "Reflection",
};

const TIER_COLOURS = {
  corpus: "#0F1E3A",
  comparable: "#3D6F3D",
  domain_prior: "#6F6A5D",
  user_assertion: "#A67C00",
  speculation: "#8B2E2B",
};

const TIER_MARKER_RE = /\[T:(corpus|comparable|domain_prior|user_assertion|speculation)\]/g;

function renderSynthesisWithTierChips(body) {
  if (!body) return null;
  const out = [];
  let last = 0;
  let match;
  let i = 0;
  TIER_MARKER_RE.lastIndex = 0;
  while ((match = TIER_MARKER_RE.exec(body)) !== null) {
    if (match.index > last) {
      out.push(<span key={`t-${i}`}>{body.slice(last, match.index)}</span>);
    }
    const tier = match[1];
    out.push(
      <span
        key={`m-${i}`}
        style={{
          background: TIER_COLOURS[tier] || "#6F6A5D",
          color: "white",
          padding: "1px 6px",
          borderRadius: 2,
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: 0.4,
          margin: "0 3px",
        }}
        title={tier}
      >
        {tier.replace("_", " ")}
      </span>
    );
    last = match.index + match[0].length;
    i += 1;
  }
  if (last < body.length) {
    out.push(<span key="tail">{body.slice(last)}</span>);
  }
  return out;
}

export default function SolvaV2Poc() {
  const { account } = useAuth();
  const enabled = !!(account && account.solva_v2_poc);

  const [clusters, setClusters] = useState([]);
  const [loadingClusters, setLoadingClusters] = useState(true);
  const [activeCluster, setActiveCluster] = useState(null);
  const [intent, setIntent] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [session, setSession] = useState(null);
  const [reply, setReply] = useState("");
  // Phase 15.1 demo: surface the most-recent completed session on landing
  // so the prospect sees a finished diagnosis with reasoning log, not an
  // empty "Start a session" form. The user can still start a new one via
  // the "Start a new session" button which clears `session` state.
  const [bootstrapping, setBootstrapping] = useState(true);
  const [showAllAudit, setShowAllAudit] = useState(false);
  // Phase 15.2 — sub-module picker. Default to seek_clarity. Persona only
  // surfaces when the chosen sub-module is get_perspective.
  const [submodule, setSubmodule] = useState("seek_clarity");
  const [persona, setPersona] = useState("");
  const [intentSuggestion, setIntentSuggestion] = useState(null);  // {submodule, confidence, reason}

  // Soft-suggest the most-fitting sub-module on intent input. Debounced —
  // only fires when the user pauses typing for 800ms AND the intent is
  // long enough for the classifier to be useful.
  useEffect(() => {
    if (!enabled || session) return;
    const t = setTimeout(async () => {
      const trimmed = intent.trim();
      if (trimmed.length < 30) {
        setIntentSuggestion(null);
        return;
      }
      try {
        const { data } = await api.post("/solva/v2/intent/classify", {
          intent: trimmed,
        });
        // Hide low-confidence suggestions per the 15.2 brief.
        if (data && data.confidence >= 0.6 && data.submodule) {
          setIntentSuggestion(data);
        } else {
          setIntentSuggestion(null);
        }
      } catch (_e) {
        setIntentSuggestion(null);
      }
    }, 800);
    return () => clearTimeout(t);
  }, [intent, enabled, session]);

  const SUBMODULE_TILES = [
    {
      key: "seek_clarity",
      label: "Seek Clarity",
      blurb: "Diagnose first. Walk a problem one layer at a time before deciding what to do.",
    },
    {
      key: "develop_strategy",
      label: "Develop Strategy",
      blurb: "Move from diagnosis to recommendation. Specific, testable, owner-assignable.",
    },
    {
      key: "simulate_hypothesis",
      label: "Simulate Hypothesis",
      blurb: "Explore a 'what-if?'. 2–3 scenarios, second-order effects, tension detection.",
    },
    {
      key: "get_perspective",
      label: "Get Perspective",
      blurb: "Hear it in another voice — Chair, NED, Investor, Regulator, Auditor, or your own.",
    },
  ];

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    Promise.all([
      api.get("/solva/clusters").catch(() => ({ data: { clusters: [] } })),
      api.get("/solva/v2/sessions", { params: { status: "completed" } })
        .catch(() => ({ data: { items: [] } })),
    ]).then(async ([clustersResp, sessionsResp]) => {
      if (cancelled) return;
      setClusters(clustersResp.data?.clusters || []);
      const items = sessionsResp.data?.items || [];
      // List is sorted desc by updated_at server-side, so items[0] is the
      // most-recent completed session. Hydrate the full record (turns +
      // reasoning_audit_log are NOT in the list response).
      if (items.length > 0) {
        try {
          const full = await api.get(`/solva/v2/sessions/${items[0].id}`);
          if (!cancelled) {
            setSession(full.data);
            setShowAllAudit(true); // completed sessions show the full log
          }
        } catch (_e) {
          /* fall through to landing */
        }
      }
    }).finally(() => {
      if (!cancelled) {
        setLoadingClusters(false);
        setBootstrapping(false);
      }
    });
    return () => { cancelled = true; };
  }, [enabled]);

  const start = async () => {
    if (!activeCluster || intent.trim().length < 20) return;
    if (submodule === "get_perspective" && !persona.trim()) {
      setError("Get Perspective requires a persona — pick or type one.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const body = {
        cluster_id: activeCluster.id,
        intent,
        submodule,
        pro_tier: false,
      };
      if (submodule === "get_perspective" && persona.trim()) {
        body.persona = persona.trim();
      }
      const { data } = await api.post("/solva/v2/sessions", body);
      setSession(data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Start failed");
    } finally {
      setBusy(false);
    }
  };

  const fork = async (toSubmodule, forkPersona) => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const body = { to_submodule: toSubmodule };
      if (forkPersona) body.persona = forkPersona;
      const { data } = await api.post(
        `/solva/v2/sessions/${session.id}/fork`,
        body,
      );
      setSession(data);
      setShowAllAudit(false);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Fork failed");
    } finally {
      setBusy(false);
    }
  };

  const postTurn = async () => {
    if (!session || reply.trim().length < 2) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await api.post(
        `/solva/v2/sessions/${session.id}/turn`,
        { user_text: reply }
      );
      setSession(data);
      setReply("");
    } catch (e) {
      const d = e?.response?.data?.detail;
      if (d && typeof d === "object" && d.error === "grounding_contract_violation") {
        setError(
          `Grounding contract violation after 3 attempts. Untagged: ${d.untagged_sentences?.length || 0}; malformed: ${d.malformed_markers?.length || 0}.`
        );
      } else {
        setError((typeof d === "string" ? d : e.message) || "Turn failed");
      }
    } finally {
      setBusy(false);
    }
  };

  const abandon = async () => {
    if (!session) return;
    try {
      await api.post(`/solva/v2/sessions/${session.id}/abandon`);
    } catch (_e) {
      /* ignore */
    }
    setSession(null);
    setIntent("");
    setReply("");
    setActiveCluster(null);
    setError(null);
  };

  const latestAudit = useMemo(() => {
    if (!session || !session.reasoning_audit_log) return [];
    const log = session.reasoning_audit_log;
    if (!log.length) return [];
    // For completed sessions or when explicitly toggled, show the full log;
    // for active sessions in flight, show only the latest turn so the user
    // isn't drinking from a firehose while they reply.
    if (showAllAudit || session.status === "completed") return log;
    const lastTurnId = log[log.length - 1].turn_id;
    return log.filter((e) => e.turn_id === lastTurnId);
  }, [session, showAllAudit]);

  const startNewSession = () => {
    setSession(null);
    setIntent("");
    setReply("");
    setActiveCluster(null);
    setError(null);
    setShowAllAudit(false);
  };

  if (!enabled) {
    return (
      <AppShell>
        <div style={{ maxWidth: 640, margin: "60px auto", padding: 24, background: "var(--warm-white)", border: "1px solid var(--rule)", borderRadius: 4 }}>
          <p className="akki-overline" style={{ marginBottom: 8 }}>Solva v2 · Phase 15.0 POC</p>
          <h1 style={{ fontFamily: "Georgia, serif", fontSize: 22, marginBottom: 12 }}>Not enabled for this account</h1>
          <p style={{ color: "var(--muted)", fontSize: 14, lineHeight: 1.5 }}>
            The Solva v2 POC is gated behind an account flag. Ask the admin to
            run <code>POST /api/admin/solva-v2/flag</code> with your email.
          </p>
          <Link to="/app/solva" style={{ display: "inline-block", marginTop: 16, color: "var(--chrome)", fontSize: 13 }}>
            ← Back to Solva v1
          </Link>
        </div>
      </AppShell>
    );
  }

  // Bootstrapping — brief loading splash while we check whether the user
  // has a previous completed session to replay before falling through to
  // the landing form. Without this, the landing form flashes for ~300ms.
  if (bootstrapping && !session) {
    return (
      <AppShell>
        <div style={{ maxWidth: 760, margin: "60px auto", padding: 24, textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
          <p className="akki-overline" style={{ marginBottom: 8 }}>Solva v2 · Seek Clarity</p>
          Loading…
        </div>
      </AppShell>
    );
  }

  // No session yet — show submodule picker + cluster + intent form
  if (!session) {
    return (
      <AppShell>
        <div style={{ maxWidth: 880, margin: "40px auto", padding: 24 }}>
          <p className="akki-overline" style={{ marginBottom: 8 }}>Solva v2 · Phase 15.2</p>
          <h1 style={{ fontFamily: "Georgia, serif", fontSize: 28, marginBottom: 8 }}>Start a Solva session</h1>
          <p style={{ color: "var(--muted)", fontSize: 13, marginBottom: 24 }}>
            Pick a sub-module, then a cluster, then state the problem in your
            own words. Every LLM call is audited; every assertive sentence
            carries a grounding-tier marker.
          </p>

          {/* Phase 15.2 — 4-tile sub-module picker. User picks explicitly;
              the suggestion chip below the intent field is soft-only. */}
          <div style={{ marginBottom: 20 }}>
            <label className="akki-overline" style={{ display: "block", marginBottom: 8 }}>
              Sub-module
            </label>
            <div
              data-testid="v2poc-submodule-picker"
              style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}
            >
              {SUBMODULE_TILES.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setSubmodule(t.key)}
                  data-testid={`v2poc-submodule-${t.key}`}
                  style={{
                    textAlign: "left", padding: 14,
                    border: `1.5px solid ${submodule === t.key ? "var(--accent)" : "var(--rule)"}`,
                    background: submodule === t.key ? "var(--cream)" : "var(--warm-white)",
                    fontSize: 13, borderRadius: 4, cursor: "pointer",
                    transition: "border-color 120ms",
                  }}
                >
                  <div style={{ fontFamily: "Georgia, serif", fontSize: 15, fontWeight: 600 }}>{t.label}</div>
                  <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 4, lineHeight: 1.4 }}>{t.blurb}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Persona field — only when get_perspective is selected. */}
          {submodule === "get_perspective" && (
            <div style={{ marginBottom: 20 }}>
              <label className="akki-overline" style={{ display: "block", marginBottom: 8 }}>
                Persona
              </label>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
                {["Chair", "Fellow NED", "Investor", "Regulator", "Auditor"].map((p) => (
                  <button
                    key={p}
                    onClick={() => setPersona(p)}
                    data-testid={`v2poc-persona-${p.toLowerCase().replace(/\s+/g, "-")}`}
                    style={{
                      padding: "6px 12px", fontSize: 12, borderRadius: 16,
                      border: `1px solid ${persona === p ? "var(--accent)" : "var(--rule)"}`,
                      background: persona === p ? "var(--cream)" : "var(--warm-white)",
                      cursor: "pointer",
                    }}
                  >
                    {p}
                  </button>
                ))}
              </div>
              <input
                data-testid="v2poc-persona-custom"
                type="text"
                value={persona}
                onChange={(e) => setPersona(e.target.value)}
                placeholder="…or type a custom persona (e.g. 'a sceptical institutional investor')"
                style={{ width: "100%", padding: 10, fontSize: 13, border: "1px solid var(--rule)", borderRadius: 3, fontFamily: "inherit" }}
              />
            </div>
          )}

          {/* Cluster picker (15.0/15.1 behaviour, unchanged). */}
          <div style={{ marginBottom: 20 }}>
            <label className="akki-overline" style={{ display: "block", marginBottom: 8 }}>
              Cluster
            </label>
            {loadingClusters ? (
              <p style={{ color: "var(--muted)" }}>Loading clusters…</p>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                {clusters.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setActiveCluster(c)}
                    data-testid={`v2poc-cluster-${c.id}`}
                    style={{
                      textAlign: "left", padding: 12,
                      border: `1px solid ${activeCluster?.id === c.id ? "var(--chrome)" : "var(--rule)"}`,
                      background: activeCluster?.id === c.id ? "var(--chrome-soft)" : "var(--warm-white)",
                      fontSize: 13, borderRadius: 3, cursor: "pointer",
                    }}
                  >
                    <div style={{ fontWeight: 600 }}>{c.label}</div>
                    <div style={{ color: "var(--muted)", fontSize: 12, marginTop: 4 }}>{c.blurb}</div>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div style={{ marginBottom: 8 }}>
            <label className="akki-overline" style={{ display: "block", marginBottom: 8 }}>
              Intent (20–1200 chars)
            </label>
            <textarea
              data-testid="v2poc-intent"
              rows={6}
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder={activeCluster?.example_question || "What's the problem you've been carrying?"}
              style={{ width: "100%", padding: 12, fontSize: 14, border: "1px solid var(--rule)", borderRadius: 3, fontFamily: "inherit" }}
            />
          </div>

          {/* Phase 15.2 — soft classifier suggestion chip. Renders only when
              confidence >= 0.6 and the suggestion differs from the user's
              currently-selected sub-module. Click to switch. */}
          {intentSuggestion && intentSuggestion.submodule !== submodule && (
            <div
              data-testid="v2poc-intent-suggestion"
              style={{ marginBottom: 16, fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 8 }}
            >
              <span>Intent classifier suggests:</span>
              <button
                onClick={() => setSubmodule(intentSuggestion.submodule)}
                style={{
                  padding: "3px 9px", fontSize: 11,
                  border: "1px solid var(--accent)", borderRadius: 12,
                  background: "var(--warm-white)", color: "var(--accent)",
                  cursor: "pointer", textTransform: "uppercase", letterSpacing: 0.4,
                }}
              >
                {SUBMODULE_TILES.find((t) => t.key === intentSuggestion.submodule)?.label || intentSuggestion.submodule}
                {" "}
                <span style={{ opacity: 0.7 }}>{Math.round(intentSuggestion.confidence * 100)}%</span>
              </button>
              <span style={{ fontStyle: "italic", maxWidth: 380, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {intentSuggestion.reason}
              </span>
            </div>
          )}

          {error && <p style={{ color: "var(--risk)", marginBottom: 12, fontSize: 13 }}>{typeof error === "string" ? error : JSON.stringify(error)}</p>}

          <button
            data-testid="v2poc-start"
            disabled={
              !activeCluster ||
              intent.trim().length < 20 ||
              busy ||
              (submodule === "get_perspective" && !persona.trim())
            }
            onClick={start}
            style={{
              padding: "10px 18px", background: "var(--chrome)", color: "white",
              border: "none", borderRadius: 3, fontSize: 14, cursor: "pointer",
              opacity: (!activeCluster || intent.trim().length < 20 || busy || (submodule === "get_perspective" && !persona.trim())) ? 0.5 : 1,
            }}
          >
            {busy ? "Starting…" : `Start ${SUBMODULE_TILES.find((t) => t.key === submodule)?.label || "session"}`}
          </button>
        </div>
      </AppShell>
    );
  }

  // Session view — turns + reasoning log. Reached either (a) by completing
  // /starting a session in this page-load, or (b) on bootstrap when the
  // user has a previous completed session to surface (Phase 15.1 demo).
  const synthesis = session.synthesis;
  const isCompletedReplay = session.status === "completed";
  return (
    <AppShell>
      <div style={{ maxWidth: 960, margin: "24px auto", padding: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, gap: 16 }}>
          <div style={{ flex: 1 }}>
            <p className="akki-overline" style={{ marginBottom: 8 }}>
              Solva v2 · {(session.submodule || "seek_clarity").replace(/_/g, " ")}
              {session.persona && (
                <span style={{ marginLeft: 8, opacity: 0.7 }}>· persona: {session.persona}</span>
              )}
              {session.parent_session_id && (
                <span style={{ marginLeft: 8, opacity: 0.7 }}>· forked</span>
              )}
              {" · "}{session.cluster_label}
            </p>
            <h1 style={{ fontFamily: "Georgia, serif", fontSize: 20, margin: "0 0 6px 0" }}>
              Layer: {LAYER_LABELS[session.layer] || session.layer} · Status: {session.status}
              {isCompletedReplay && (
                <span style={{ marginLeft: 10, fontSize: 11, padding: "2px 8px", background: "var(--cream)", border: "1px solid var(--rule)", color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6, fontFamily: "Inter, sans-serif", verticalAlign: "middle" }}>
                  Replay · most recent completed
                </span>
              )}
            </h1>
            {session.intent && (
              <p style={{ fontSize: 13, color: "var(--muted)", margin: 0, lineHeight: 1.5, fontStyle: "italic" }}>
                Intent: {session.intent}
              </p>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <button
              onClick={startNewSession}
              data-testid="v2poc-start-new"
              style={{ fontSize: 12, color: "var(--chrome)", background: "var(--warm-white)", border: "1px solid var(--chrome)", padding: "6px 12px", borderRadius: 3, cursor: "pointer", whiteSpace: "nowrap" }}
            >
              + Start a new session
            </button>
            {/* Phase 15.2 — Take this session into another sub-module. Only
                shown when the session is in a state that has accumulated
                content worth carrying forward. */}
            {(session.status === "completed" ||
              (session.turns || []).filter((t) => t.role === "user").length >= 1) && (
              <div data-testid="v2poc-fork-menu" style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 11 }}>
                <span className="akki-overline" style={{ fontSize: 9, marginTop: 2 }}>Take into…</span>
                {SUBMODULE_TILES
                  .filter((t) => t.key !== (session.submodule || "seek_clarity"))
                  .map((t) => (
                    <button
                      key={t.key}
                      data-testid={`v2poc-fork-${t.key}`}
                      onClick={() => {
                        if (t.key === "get_perspective") {
                          const p = window.prompt("Persona for Get Perspective?", "Chair");
                          if (!p) return;
                          fork(t.key, p);
                        } else {
                          fork(t.key);
                        }
                      }}
                      style={{ fontSize: 11, color: "var(--muted)", background: "transparent", border: "1px solid var(--rule)", padding: "3px 8px", borderRadius: 2, cursor: "pointer", textAlign: "left" }}
                    >
                      → {t.label}
                    </button>
                  ))}
              </div>
            )}
            {!isCompletedReplay && (
              <button onClick={abandon} style={{ fontSize: 12, color: "var(--muted)", background: "none", border: "1px solid var(--rule)", padding: "6px 12px", borderRadius: 3, cursor: "pointer" }}>
                Abandon
              </button>
            )}
          </div>
        </div>

        {/* Turns */}
        <div style={{ background: "var(--warm-white)", border: "1px solid var(--rule)", padding: 16, marginBottom: 16 }}>
          {(session.turns || []).map((t) => (
            <div key={t.id} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 10, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 4 }}>
                {t.role} · {LAYER_LABELS[t.layer] || t.layer}
              </div>
              <div style={{ fontSize: 14, lineHeight: 1.55, whiteSpace: "pre-wrap" }}>
                {t.role === "solva" && t.layer === "synthesis"
                  ? renderSynthesisWithTierChips(t.text)
                  : t.text}
              </div>
            </div>
          ))}
        </div>

        {/* Synthesis claims panel — shows parsed tier distribution */}
        {synthesis && synthesis.claims && synthesis.claims.length > 0 && (
          <div style={{ background: "var(--cream)", border: "1px solid var(--rule)", padding: 16, marginBottom: 16 }}>
            <p className="akki-overline" style={{ marginBottom: 8 }}>Parsed claims ({synthesis.claims.length})</p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 12, fontSize: 12 }}>
              {Object.entries(synthesis.tier_distribution || {}).map(([tier, n]) => (
                <span key={tier} style={{ color: TIER_COLOURS[tier] || "#6F6A5D" }}>
                  {tier}: <strong>{n}</strong>
                </span>
              ))}
            </div>
            <ol style={{ fontSize: 13, lineHeight: 1.55, paddingLeft: 20, margin: 0 }}>
              {synthesis.claims.map((c, i) => (
                <li key={i} style={{ marginBottom: 4 }}>
                  <span style={{ color: TIER_COLOURS[c.tier] || "#6F6A5D", fontSize: 10, textTransform: "uppercase", letterSpacing: 0.4, marginRight: 6 }}>
                    [{c.tier}]
                  </span>
                  {c.text}
                </li>
              ))}
            </ol>
            {synthesis.validation && (
              <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 12 }}>
                Validator: <strong>{synthesis.validation.verdict}</strong> ({synthesis.validation.confidence}%)
                {" · "}{synthesis.validation.validator_provider}/{synthesis.validation.validator_model}
              </p>
            )}
          </div>
        )}

        {/* Reasoning log — full for completed sessions, latest turn while active */}
        {latestAudit.length > 0 && (
          <div style={{ background: "#fafaf5", border: "1px solid var(--rule)", padding: 16, marginBottom: 16 }}>
            <p className="akki-overline" style={{ marginBottom: 8 }}>
              Reasoning log · {(showAllAudit || isCompletedReplay) ? "full session" : "latest turn"} ({latestAudit.length} entries)
            </p>
            <table style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 11, width: "100%" }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                  <th style={{ padding: "4px 6px" }}>Layer</th>
                  <th style={{ padding: "4px 6px" }}>Engine</th>
                  <th style={{ padding: "4px 6px" }}>Version</th>
                  <th style={{ padding: "4px 6px" }}>Tiers</th>
                  <th style={{ padding: "4px 6px" }}>Latency</th>
                  <th style={{ padding: "4px 6px" }}>Model</th>
                  <th style={{ padding: "4px 6px" }}>Shield</th>
                </tr>
              </thead>
              <tbody>
                {latestAudit.map((e) => {
                  const muted = e.engine === "placeholder";
                  return (
                    <tr key={e.id} style={{ borderTop: "1px solid var(--rule)", opacity: muted ? 0.55 : 1 }}>
                      <td style={{ padding: "4px 6px" }}>{e.layer}</td>
                      <td style={{ padding: "4px 6px", fontStyle: muted ? "italic" : "normal" }}>{e.engine}</td>
                      <td style={{ padding: "4px 6px" }}>{e.engine_version}</td>
                      <td style={{ padding: "4px 6px" }}>{(e.tier_labels || []).join(",") || "—"}</td>
                      <td style={{ padding: "4px 6px" }}>{e.latency_ms}ms</td>
                      <td style={{ padding: "4px 6px" }}>{e.model || "—"}</td>
                      <td style={{ padding: "4px 6px" }}>
                        {e.synisense_run_id
                          ? <span title={e.synisense_run_id} style={{ color: "var(--opportunity)" }}>ok</span>
                          : <span title={e.shield_bypassed_reason || ""} style={{ color: "var(--muted)" }}>
                              {e.shield_bypassed_reason ? "bypass" : "—"}
                            </span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {error && <p style={{ color: "var(--risk)", marginBottom: 12, fontSize: 13 }}>{error}</p>}

        {session.status === "active" && (
          <div style={{ marginBottom: 16 }}>
            <textarea
              data-testid="v2poc-reply"
              rows={3}
              value={reply}
              onChange={(e) => setReply(e.target.value)}
              placeholder="Your reply…"
              style={{ width: "100%", padding: 10, border: "1px solid var(--rule)", borderRadius: 3, fontSize: 14, fontFamily: "inherit", marginBottom: 8 }}
            />
            <button
              data-testid="v2poc-post-turn"
              disabled={busy || reply.trim().length < 2}
              onClick={postTurn}
              style={{ padding: "8px 16px", background: "var(--chrome)", color: "white", border: "none", borderRadius: 3, fontSize: 13, cursor: "pointer", opacity: (busy || reply.trim().length < 2) ? 0.5 : 1 }}
            >
              {busy ? "Thinking…" : "Post turn"}
            </button>
          </div>
        )}

        {session.status === "completed" && (
          <div style={{ padding: 12, background: "var(--cream)", border: "1px solid var(--rule)", fontSize: 13, color: "var(--muted)" }}>
            Session complete. POC flow ends at the Reflection placeholder.
          </div>
        )}
      </div>
    </AppShell>
  );
}
