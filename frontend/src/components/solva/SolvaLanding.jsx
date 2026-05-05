/**
 * Phase I.1 — Solva landing per UX Redesign Brief §3.
 *
 * REPLACES the Phase B.4 right-panel layout. The B.4 RecentSessionsPanel +
 * SessionHealthPanel + MarketingExplainer right-column components are gone —
 * the brief deprecates them. The B.4 wide centre input on the landing is
 * also gone; the framing textarea moves to the Framing screen (I.2).
 *
 * What ships here (brief §3.1):
 *   - Single-column, max-width 760px, centred.
 *   - Editorial title "Solva" (Georgia 44px desktop, 32px mobile, bold).
 *   - One-line subtitle "Pick what you came to do." (Georgia 18px italic, DEEP).
 *   - 4 picker cards stacked vertically, ~140px desktop / ~120px mobile.
 *   - Below the fold:
 *       - Recent Sessions collapsible (collapsed by default).
 *       - "How Solva reasons →" link to /solva/how-it-reasons.
 *
 * Card anatomy (brief §3.2):
 *   - Name top-left  (Georgia 22px bold INK).
 *   - When-to-use    (Calibri 14px regular DEEP).
 *   - Numeric marker top-right (Georgia italic ACCENT).
 *   - Hover: subtle ACCENT border 1pt.
 *
 * Card copy is verbatim from the brief; Card 04 label is "See Different
 * Perspectives" per user instruction (brief had "Get Perspective" — user
 * supersedes). Backend submodule key remains `get_perspective` — that's
 * an internal identifier, not user-facing.
 *
 * Variant prop:
 *   - "auth"      → mounted from /app/solva. Recent Sessions block visible.
 *   - "marketing" → mounted from /solva. Recent Sessions block hidden;
 *                   primary action is sign-in CTA.
 *
 * No clusters, no architectural visibility, no toggles. Brief §3.4
 * deprecation list strictly applied.
 */
import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/lib/api";

// Tokens (brief §7.1) — kept inline so the component is portable.
const TOKEN = {
  INK: "#2A1B1D",
  DEEP: "#5A4A4D",
  MUTED: "#6B6B6B",
  RULE: "#D5C9B6",
  CREAM: "#F5EFE6",
  CREAM_DEEP: "#E8DCC8",
  ACCENT: "#C25A38",
  PAPER: "#FAF7F2",
  LIGHT: "#FFFFFF",
};

// Brief §3.2 — verbatim card copy. Card 04 label per user instruction.
const CARDS = [
  {
    n: "01",
    key: "seek_clarity",
    title: "Seek Clarity",
    when: "When you don't know what's actually going on. Solva runs the diagnostic that narrows possible causes and surfaces what's underneath your framing.",
  },
  {
    n: "02",
    key: "develop_strategy",
    title: "Develop Strategy",
    when: "When you need a direction and want to test your thinking. Solva produces probability-weighted options with sensitivity analysis.",
  },
  {
    n: "03",
    key: "simulate_hypothesis",
    title: "Simulate Hypothesis",
    when: "When you want to stress-test an assumption before you commit. Solva runs the simulation and flags tensions before they become decisions.",
  },
  {
    n: "04",
    key: "get_perspective",
    title: "See Different Perspectives",
    when: "When you want to see your situation through a different mind — a CFO's view, an investor's view, a regulator's view, a counterparty's view.",
  },
];


function PickerCard({ card, onSelect, isFocused, onArrowKey }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      type="button"
      data-testid={`solva-picker-${card.key}`}
      onClick={() => onSelect(card)}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onKeyDown={onArrowKey}
      tabIndex={0}
      aria-label={`${card.title}: ${card.when}`}
      style={{
        position: "relative",
        display: "block",
        width: "100%",
        textAlign: "left",
        padding: 32,
        marginBottom: 24,
        minHeight: 140,
        background: TOKEN.LIGHT,
        border: `1px solid ${hover || isFocused ? TOKEN.ACCENT : TOKEN.RULE}`,
        borderRadius: 4,
        cursor: "pointer",
        transition: "border-color 200ms ease-out",
        outline: "none",
        boxShadow: isFocused ? `0 0 0 2px ${TOKEN.ACCENT}33` : "none",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 24,
          right: 32,
          fontFamily: "Georgia, serif",
          fontStyle: "italic",
          fontSize: 28,
          color: TOKEN.ACCENT,
          fontWeight: 400,
        }}
        aria-hidden="true"
      >
        {card.n}
      </span>
      <h3
        style={{
          fontFamily: "Georgia, serif",
          fontSize: 22,
          fontWeight: 700,
          color: TOKEN.INK,
          margin: "0 80px 8px 0",
          lineHeight: 1.25,
        }}
      >
        {card.title}
      </h3>
      <p
        style={{
          fontFamily: 'Calibri, "Segoe UI", system-ui, -apple-system, sans-serif',
          fontSize: 14,
          fontWeight: 400,
          color: TOKEN.DEEP,
          margin: 0,
          lineHeight: 1.55,
          maxWidth: "calc(100% - 60px)",
        }}
      >
        {card.when}
      </p>
    </button>
  );
}


function RecentSessionsCollapsible({ sessions, onResume, onDiscard }) {
  const [open, setOpen] = useState(false);
  const has = sessions && sessions.length > 0;

  return (
    <section
      data-testid="solva-recent-sessions"
      style={{
        borderTop: `1px solid ${TOKEN.RULE}`,
        paddingTop: 24,
        marginTop: 48,
      }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="solva-recent-list"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          background: "none",
          border: "none",
          padding: 0,
          cursor: "pointer",
          fontFamily: 'Calibri, "Segoe UI", system-ui, -apple-system, sans-serif',
          fontSize: 13,
          color: TOKEN.MUTED,
          textTransform: "uppercase",
          letterSpacing: 0.6,
        }}
      >
        Recent sessions
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <ul
          id="solva-recent-list"
          style={{ listStyle: "none", padding: 0, margin: "16px 0 0 0" }}
        >
          {!has && (
            <li
              style={{
                fontFamily: "Georgia, serif",
                fontStyle: "italic",
                fontSize: 15,
                color: TOKEN.MUTED,
              }}
            >
              Your sessions will appear here.
            </li>
          )}
          {has && sessions.map((s) => {
            const startedAt = s.started_at ? new Date(s.started_at) : null;
            const days = startedAt
              ? Math.floor((Date.now() - startedAt.getTime()) / 86400000)
              : 0;
            const isStale = days >= 30 && s.status !== "completed";
            const submoduleLabel = (s.submodule || "").replace(/_/g, " ");
            const framing = (s.intent || s.cluster_label || "—").slice(0, 96);
            const date = startedAt
              ? `${startedAt.toLocaleDateString()} · ${days === 0 ? "today" : `${days}d ago`}`
              : "";
            return (
              <li
                key={s.id}
                style={{
                  display: "flex",
                  alignItems: "baseline",
                  gap: 16,
                  padding: "12px 0",
                  borderBottom: `1px solid ${TOKEN.RULE}`,
                }}
              >
                <button
                  type="button"
                  onClick={() => onResume(s)}
                  data-testid={`solva-resume-${s.id}`}
                  style={{
                    flex: 1,
                    textAlign: "left",
                    background: "none",
                    border: "none",
                    padding: 0,
                    cursor: "pointer",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "Georgia, serif",
                      fontSize: 15,
                      color: TOKEN.INK,
                      textTransform: "capitalize",
                    }}
                  >
                    {submoduleLabel}
                  </span>
                  <span style={{ color: TOKEN.MUTED, margin: "0 8px" }}>·</span>
                  <span
                    style={{
                      fontFamily: "Georgia, serif",
                      fontStyle: "italic",
                      fontSize: 14,
                      color: TOKEN.DEEP,
                    }}
                  >
                    {framing}
                  </span>
                  <div
                    style={{
                      fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
                      fontSize: 12,
                      color: isStale ? TOKEN.ACCENT : TOKEN.MUTED,
                      marginTop: 4,
                    }}
                  >
                    {isStale ? `Started ${days} days ago — over the 30-day limit` : date}
                  </div>
                </button>
                {isStale && (
                  <button
                    type="button"
                    onClick={() => onDiscard(s)}
                    style={{
                      background: "none",
                      border: "none",
                      padding: 0,
                      cursor: "pointer",
                      fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
                      fontSize: 12,
                      color: TOKEN.MUTED,
                      textDecoration: "underline",
                    }}
                  >
                    Discard
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}


export default function SolvaLanding({ variant = "auth" }) {
  const navigate = useNavigate();
  const [recent, setRecent] = useState([]);
  const [focusIdx, setFocusIdx] = useState(-1);

  useEffect(() => {
    if (variant !== "auth") return;
    let cancelled = false;
    api
      .get("/solva/v2/sessions", { params: { limit: 5 } })
      .then((r) => {
        if (!cancelled) setRecent((r.data?.items || []).slice(0, 5));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [variant]);

  const onSelectCard = (card) => {
    if (variant === "auth") {
      navigate(`/app/solva/session/new?submodule=${encodeURIComponent(card.key)}`);
    } else {
      navigate("/signin");
    }
  };

  const onResume = (s) => {
    if (variant !== "auth") return;
    navigate(`/app/solva/session/${s.id}`);
  };

  const onDiscard = async (s) => {
    if (variant !== "auth") return;
    try {
      await api.post(`/solva/v2/sessions/${s.id}/abandon`,
        { reason: "stale_30d_user_discard" });
      setRecent((prev) => prev.filter((r) => r.id !== s.id));
    } catch (_e) { /* swallow */ }
  };

  // Brief §8.6 — arrow-key nav across cards with Enter to select.
  const onCardKey = (idx) => (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusIdx(Math.min(idx + 1, CARDS.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusIdx(Math.max(idx - 1, 0));
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelectCard(CARDS[idx]);
    }
  };

  return (
    <div
      data-testid="solva-landing"
      data-variant={variant}
      style={{
        background: TOKEN.PAPER,
        minHeight: "calc(100vh - 64px)",
        padding: "120px 24px 80px",
      }}
    >
      <div style={{ maxWidth: 760, margin: "0 auto" }}>
        <h1
          className="solva-landing-title"
          style={{
            fontFamily: "Georgia, serif",
            fontWeight: 700,
            fontSize: 44,
            color: TOKEN.INK,
            margin: "0 0 12px 0",
            lineHeight: 1.05,
            textAlign: "center",
          }}
        >
          Solva
        </h1>
        <p
          style={{
            fontFamily: "Georgia, serif",
            fontStyle: "italic",
            fontSize: 18,
            color: TOKEN.DEEP,
            margin: "0 0 64px 0",
            textAlign: "center",
          }}
        >
          Pick what you came to do.
        </p>

        <div role="list" aria-label="Solva sub-modules">
          {CARDS.map((c, i) => (
            <PickerCard
              key={c.key}
              card={c}
              isFocused={focusIdx === i}
              onSelect={onSelectCard}
              onArrowKey={onCardKey(i)}
            />
          ))}
        </div>

        {variant === "auth" && (
          <RecentSessionsCollapsible
            sessions={recent}
            onResume={onResume}
            onDiscard={onDiscard}
          />
        )}

        <div style={{ marginTop: 40, textAlign: "center" }}>
          <Link
            to="/solva/how-it-reasons"
            data-testid="how-solva-reasons-link"
            style={{
              fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
              fontSize: 14,
              color: TOKEN.ACCENT,
              textDecoration: "none",
            }}
          >
            How Solva reasons →
          </Link>
        </div>

        {variant === "marketing" && (
          <p
            style={{
              fontFamily: "Georgia, serif",
              fontStyle: "italic",
              fontSize: 13,
              color: TOKEN.MUTED,
              textAlign: "center",
              marginTop: 32,
            }}
          >
            Sign in to start a session.{" "}
            <Link to="/signin" style={{ color: TOKEN.ACCENT }}>
              Sign in →
            </Link>
          </p>
        )}
      </div>

      {/* Brief §7.6 responsive — title 32px on mobile. */}
      <style>{`
        @media (max-width: 640px) {
          .solva-landing-title { font-size: 32px !important; }
        }
        [data-testid^="solva-picker-"]:focus-visible {
          outline: 2px solid ${TOKEN.ACCENT};
          outline-offset: 2px;
        }
      `}</style>
    </div>
  );
}

export { CARDS };
