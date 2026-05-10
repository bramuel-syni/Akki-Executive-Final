/**
 * FrameAuditScreen — Wave 2.1 (UAT pack 2026-05-10).
 *
 * Layer 0 of the Solva flow. Sits between FRAMING and Q1 in the
 * state machine. Renders the deterministic frame_audit summary the
 * backend produced (in plain language — NOT a table per spec rule
 * 27) and offers three CTAs.
 *
 * The audit POST has already fired in the background when the user
 * submitted FRAMING (`SolvaSession.handleFramingSubmit` calls it
 * fire-and-forget). This component refreshes it via a GET-on-mount,
 * so the data is there before the user sees the screen.
 *
 * Severity badge:
 *   - severity="none"      — no badge; brief "we have what we need" line.
 *   - severity="advisory"  — muted badge "a couple of pieces are thin".
 *   - severity="critical"  — accent-coloured badge.
 *
 * Three CTAs (per spec):
 *   - Proceed       → dispatch FRAME_AUDIT_DECISION proceed, hit /frame-audit-decision
 *   - I'll get more → dispatch get_more, pop back to FRAMING
 *   - Pause for now → dispatch pause, status=paused, navigate to picker
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

const SEVERITY_BADGE = {
  advisory: {
    label: "A couple of pieces are thin",
    bg: "rgba(180, 130, 50, 0.10)",
    color: "#7B541E",
  },
  critical: {
    label: "Several structural pieces are missing",
    bg: "rgba(139, 29, 44, 0.10)",
    color: "#8B1D2C",
  },
  none: null,
};

export default function FrameAuditScreen({ sessionId, onProceed, onGetMore, onPause }) {
  const [audit, setAudit] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    if (!sessionId) { setLoading(false); return; }
    api.post(`/solva/v2/sessions/${sessionId}/frame-audit`)
      .then((res) => { if (!cancelled) setAudit(res.data?.frame_audit || null); })
      .catch((err) => { if (!cancelled) toast.error(apiErrorMessage(err)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sessionId]);

  const decide = async (decision) => {
    if (!sessionId) return;
    setBusy(true);
    try {
      await api.post(`/solva/v2/sessions/${sessionId}/frame-audit-decision`, { decision });
      if (decision === "proceed") onProceed?.();
      else if (decision === "get_more") onGetMore?.();
      else if (decision === "pause") {
        toast.success("Session paused. You can resume it from your sessions list.");
        onPause?.();
        navigate("/app/solva");
      }
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <div data-testid="frame-audit-loading" style={{ padding: 32, textAlign: "center", color: "#6B6358" }}>
        <p style={{ fontFamily: "Georgia, serif", fontStyle: "italic" }}>
          Reading what you wrote…
        </p>
      </div>
    );
  }

  if (!audit) {
    return (
      <div data-testid="frame-audit-error" style={{ padding: 32 }}>
        <p style={{ color: "#6B6358" }}>Couldn&rsquo;t fetch the frame audit.</p>
        <button onClick={() => onProceed?.()} style={btnPrimary}>Proceed anyway</button>
      </div>
    );
  }

  const badge = SEVERITY_BADGE[audit.severity] || null;

  return (
    <section
      data-testid="frame-audit-screen"
      data-severity={audit.severity}
      style={{ maxWidth: 640, margin: "0 auto", padding: "24px 24px 40px" }}
    >
      <p style={metaLine}>Layer 0 — Frame Audit</p>
      <h2
        style={{
          fontFamily: "Georgia, serif",
          fontSize: 24,
          color: "#1F1C18",
          margin: "6px 0 16px 0",
          fontWeight: 600,
          lineHeight: 1.3,
        }}
      >
        Here&rsquo;s what we noticed in your framing.
      </h2>

      {badge && (
        <span
          data-testid="frame-audit-severity-badge"
          style={{
            display: "inline-block",
            padding: "3px 10px",
            borderRadius: 999,
            background: badge.bg,
            color: badge.color,
            fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
            fontSize: 11,
            letterSpacing: 0.4,
            textTransform: "uppercase",
            fontWeight: 600,
            marginBottom: 18,
          }}
        >
          {badge.label}
        </span>
      )}

      {/* Plain-language observations (per spec: NOT a table). */}
      {(audit.observations || []).length > 0 && (
        <div
          data-testid="frame-audit-observations"
          style={{
            background: "rgba(0,0,0,0.02)",
            border: "1px solid rgba(0,0,0,0.06)",
            borderRadius: 4,
            padding: "16px 18px",
            marginBottom: 18,
          }}
        >
          {audit.observations.map((o, i) => (
            <p
              key={i}
              style={{
                fontFamily: "Georgia, serif",
                fontSize: 15,
                color: "#1F1C18",
                lineHeight: 1.65,
                margin: i === 0 ? "0" : "10px 0 0 0",
              }}
            >
              {o}
            </p>
          ))}
        </div>
      )}

      {/* Recommendations — muted, slightly smaller. */}
      {(audit.recommendations || []).length > 0 && (
        <div data-testid="frame-audit-recommendations" style={{ marginBottom: 22 }}>
          {audit.recommendations.map((r, i) => (
            <p
              key={i}
              style={{
                fontFamily: "Georgia, serif",
                fontSize: 14,
                fontStyle: "italic",
                color: "#6B6358",
                lineHeight: 1.6,
                margin: i === 0 ? "0" : "6px 0 0 0",
              }}
            >
              {r}
            </p>
          ))}
        </div>
      )}

      <p
        data-testid="frame-audit-summary"
        style={{
          fontFamily: "Georgia, serif",
          fontSize: 15,
          color: "#1F1C18",
          lineHeight: 1.65,
          margin: "0 0 28px 0",
        }}
      >
        {audit.summary}
      </p>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        <button
          type="button"
          disabled={busy}
          onClick={() => decide("proceed")}
          data-testid="frame-audit-proceed"
          style={btnPrimary}
        >
          Proceed
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => decide("get_more")}
          data-testid="frame-audit-get-more"
          style={btnGhost}
        >
          I&rsquo;ll get more
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => decide("pause")}
          data-testid="frame-audit-pause"
          style={btnGhost}
        >
          Pause for now
        </button>
      </div>
    </section>
  );
}

const metaLine = {
  fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
  fontSize: 11,
  letterSpacing: 0.6,
  textTransform: "uppercase",
  color: "#6B6358",
  margin: 0,
};
const btnPrimary = {
  background: "#8B1D2C",
  color: "#FFFFFF",
  border: "none",
  padding: "9px 18px",
  borderRadius: 2,
  cursor: "pointer",
  fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
  fontSize: 13,
  fontWeight: 500,
  letterSpacing: 0.3,
};
const btnGhost = {
  background: "transparent",
  color: "#1F1C18",
  border: "1px solid rgba(0,0,0,0.16)",
  padding: "9px 18px",
  borderRadius: 2,
  cursor: "pointer",
  fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
  fontSize: 13,
  fontWeight: 400,
  letterSpacing: 0.3,
};
