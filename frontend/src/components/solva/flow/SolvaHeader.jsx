/**
 * SolvaHeader — Wave 1.6 (UAT pack 2026-05-10).
 *
 * Solva sessions previously had no header. This adds:
 *   - Active company context name ("in <company>") so the user is
 *     reminded which tenant the session is bound to. Synisense
 *     Shield runs server-side regardless; the UI just needs to
 *     surface the binding.
 *   - Auto-Shield (i) tooltip: explanatory only — Solva does NOT
 *     expose a per-session policy picker today (different from
 *     Chat). The (i) is informational so users know shielding is
 *     active.
 *
 * No state. Pure presentational. Pulled into SolvaSession.jsx as
 * the top of every screen swap.
 */
import React from "react";
import { Info } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export default function SolvaHeader() {
  const { activeContext } = useAuth();

  return (
    <div
      data-testid="solva-header"
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "12px 24px",
        borderBottom: "1px solid rgba(0,0,0,0.06)",
        background: "#FFFFFF",
      }}
    >
      <div
        style={{
          fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
          fontSize: 12,
          color: "#6B6358",
          letterSpacing: 0.3,
        }}
      >
        Solva
        {activeContext?.name && (
          <>
            <span style={{ margin: "0 6px", opacity: 0.6 }}>·</span>
            <span data-testid="solva-header-active-context">
              in <span style={{ color: "#1F1C18" }}>{activeContext.name}</span>
            </span>
          </>
        )}
      </div>
      <span
        tabIndex={0}
        aria-label="What is Auto-Shield?"
        data-testid="solva-auto-shield-tooltip-trigger"
        style={{
          position: "relative",
          display: "inline-flex",
          alignItems: "center",
          cursor: "help",
          color: "#6B6358",
        }}
        onMouseEnter={(e) => e.currentTarget.classList.add("akki-solva-tt-hover")}
        onMouseLeave={(e) => e.currentTarget.classList.remove("akki-solva-tt-hover")}
      >
        <Info width={14} height={14} />
        <span
          role="tooltip"
          className="akki-solva-tt"
          style={{
            position: "absolute",
            right: 0,
            top: "calc(100% + 6px)",
            zIndex: 60,
            display: "none",
            width: 280,
            padding: "10px 12px",
            borderRadius: 2,
            background: "#1F1C18",
            color: "#FAF6EE",
            fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
            fontSize: 11.5,
            lineHeight: 1.45,
            boxShadow: "0 8px 22px rgba(0,0,0,0.22)",
          }}
        >
          Auto-Shield redacts names and numbers before any AI sees them.
          <span style={{ display: "block", marginTop: 6 }}><b>Auto</b> — redact when sensitivity is detected.</span>
          <span style={{ display: "block" }}><b>Always</b> — redact every message.</span>
          <span style={{ display: "block" }}><b>Off</b> — send raw (use sparingly).</span>
          <span style={{ display: "block", marginTop: 6, opacity: 0.7 }}>
            Solva runs Auto-Shield by default on every layer.
          </span>
        </span>
        <style>{`.akki-solva-tt-hover .akki-solva-tt { display: block !important; }`}</style>
      </span>
    </div>
  );
}
