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

  useEffect(() => {
    if (!enabled) return;
    api.get("/solva/clusters")
      .then((r) => setClusters(r.data?.clusters || []))
      .catch(() => setClusters([]))
      .finally(() => setLoadingClusters(false));
  }, [enabled]);

  const start = async () => {
    if (!activeCluster || intent.trim().length < 20) return;
    setBusy(true);
    setError(null);
    try {
      const { data } = await api.post("/solva/v2/sessions", {
        cluster_id: activeCluster.id,
        intent,
        submodule: "seek_clarity",
        pro_tier: false,
      });
      setSession(data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Start failed");
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
    const lastTurnId = log[log.length - 1].turn_id;
    return log.filter((e) => e.turn_id === lastTurnId);
  }, [session]);

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

  // No session yet — show picker + intent form
  if (!session) {
    return (
      <AppShell>
        <div style={{ maxWidth: 760, margin: "40px auto", padding: 24 }}>
          <p className="akki-overline" style={{ marginBottom: 8 }}>Solva v2 · Seek Clarity (POC)</p>
          <h1 style={{ fontFamily: "Georgia, serif", fontSize: 28, marginBottom: 8 }}>Start a Seek Clarity session</h1>
          <p style={{ color: "var(--muted)", fontSize: 13, marginBottom: 24 }}>
            Phase 15.0 POC. One sub-module, four layers: Framing → Grounding →
            Synthesis → Reflection. Every LLM call is audited; every synthesis
            sentence carries a grounding-tier marker.
          </p>

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

          <div style={{ marginBottom: 16 }}>
            <label className="akki-overline" style={{ display: "block", marginBottom: 8 }}>
              Intent (20–1200 chars)
            </label>
            <textarea
              data-testid="v2poc-intent"
              rows={6}
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
              placeholder={activeCluster?.example_question || "What’s the problem you’ve been carrying?"}
              style={{ width: "100%", padding: 12, fontSize: 14, border: "1px solid var(--rule)", borderRadius: 3, fontFamily: "inherit" }}
            />
          </div>

          {error && <p style={{ color: "var(--risk)", marginBottom: 12, fontSize: 13 }}>{error}</p>}

          <button
            data-testid="v2poc-start"
            disabled={!activeCluster || intent.trim().length < 20 || busy}
            onClick={start}
            style={{
              padding: "10px 18px", background: "var(--chrome)", color: "white",
              border: "none", borderRadius: 3, fontSize: 14, cursor: "pointer",
              opacity: (!activeCluster || intent.trim().length < 20 || busy) ? 0.5 : 1,
            }}
          >
            {busy ? "Starting…" : "Start session"}
          </button>
        </div>
      </AppShell>
    );
  }

  // Session view — turns + reasoning log
  const synthesis = session.synthesis;
  return (
    <AppShell>
      <div style={{ maxWidth: 960, margin: "24px auto", padding: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div>
            <p className="akki-overline">Solva v2 · Seek Clarity · {session.cluster_label}</p>
            <h1 style={{ fontFamily: "Georgia, serif", fontSize: 20, margin: 0 }}>
              Layer: {LAYER_LABELS[session.layer] || session.layer} · Status: {session.status}
            </h1>
          </div>
          <button onClick={abandon} style={{ fontSize: 12, color: "var(--muted)", background: "none", border: "1px solid var(--rule)", padding: "6px 12px", borderRadius: 3, cursor: "pointer" }}>
            Abandon
          </button>
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

        {/* Reasoning log — latest turn only */}
        {latestAudit.length > 0 && (
          <div style={{ background: "#fafaf5", border: "1px solid var(--rule)", padding: 16, marginBottom: 16 }}>
            <p className="akki-overline" style={{ marginBottom: 8 }}>
              Reasoning log · latest turn ({latestAudit.length} entries)
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
                {latestAudit.map((e) => (
                  <tr key={e.id} style={{ borderTop: "1px solid var(--rule)" }}>
                    <td style={{ padding: "4px 6px" }}>{e.layer}</td>
                    <td style={{ padding: "4px 6px" }}>{e.engine}</td>
                    <td style={{ padding: "4px 6px" }}>{e.engine_version}</td>
                    <td style={{ padding: "4px 6px" }}>{(e.tier_labels || []).join(",") || "—"}</td>
                    <td style={{ padding: "4px 6px" }}>{e.latency_ms}ms</td>
                    <td style={{ padding: "4px 6px" }}>{e.model || "—"}</td>
                    <td style={{ padding: "4px 6px" }}>
                      {e.synisense_run_id
                        ? <span title={e.synisense_run_id} style={{ color: "var(--opportunity)" }}>ok</span>
                        : <span style={{ color: "var(--muted)" }}>—</span>}
                    </td>
                  </tr>
                ))}
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
