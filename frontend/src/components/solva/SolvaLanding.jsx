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
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/lib/api";
// Phase D.1 (2026-05-26) — pre-conversation briefing deck.
import SolvaBriefingDeck from "@/components/solva/SolvaBriefingDeck";
import { SUBMODULE_TO_AREA } from "@/data/solva-briefings";

// Tokens (brief §7.1) — kept inline so the component is portable.
const TOKEN = {
  INK: "var(--ink)",
  DEEP: "var(--graphite)",
  MUTED: "var(--graphite)",
  RULE: "var(--graphite-light)",
  CREAM: "var(--parchment-light)",
  CREAM_DEEP: "var(--parchment)",
  ACCENT: "var(--oxblood)",
  PAPER: "var(--parchment-light)",
  LIGHT: "var(--parchment-light)",
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
        // Phase G — 2x2 grid uses CSS gap for both axes; per-card
        // marginBottom is dropped so vertical and horizontal spacing
        // remain symmetric. Mobile single-column gap is identical.
        marginBottom: 0,
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


function RecentSessionsCollapsible({ sessions, onResume, onDiscard, onStartGuided }) {
  const [open, setOpen] = useState(sessions && sessions.length === 0);
  // Wave 1.4 (UAT pack 2026-05-10) — when there are no recent sessions
  // we OPEN the panel by default and render an explainer card with a
  // "Run a guided first session" CTA. When there ARE sessions the
  // collapsible behaves as before (closed by default).
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
              data-testid="solva-empty-state-card"
              style={{
                listStyle: "none",
                background: "var(--parchment-light)",
                border: `1px solid ${TOKEN.RULE}`,
                borderRadius: 4,
                padding: "20px 24px",
              }}
            >
              <p
                style={{
                  fontFamily: "Georgia, serif",
                  fontSize: 15,
                  color: TOKEN.INK,
                  lineHeight: 1.55,
                  margin: "0 0 12px 0",
                }}
              >
                Solva is structured reasoning for situations that don&apos;t fit a
                quick chat. We work through five layers — framing, surface,
                depth, synthesis, reflection — to produce a defensible
                artefact you can revisit or share.
              </p>
              <button
                type="button"
                onClick={onStartGuided}
                data-testid="solva-empty-cta-guided"
                style={{
                  background: TOKEN.ACCENT,
                  color: "var(--parchment-light)",
                  border: "none",
                  padding: "8px 16px",
                  borderRadius: 2,
                  cursor: "pointer",
                  fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
                  fontSize: 13,
                  fontWeight: 500,
                  letterSpacing: 0.3,
                }}
              >
                Run a guided first session
              </button>
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


export default function SolvaLanding({ variant = "auth", intakeSeed = null, intakeStarter = null }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [recent, setRecent] = useState([]);
  const [focusIdx, setFocusIdx] = useState(-1);
  // Wave 1.3 (UAT pack 2026-05-10) — disambiguator dialog.
  const [pickerHelpOpen, setPickerHelpOpen] = useState(false);
  // Phase D.1 (2026-05-26) — briefing deck state.
  const [briefingOpen, setBriefingOpen] = useState(false);
  const [briefingArea, setBriefingArea] = useState(null);
  const [briefingPendingCard, setBriefingPendingCard] = useState(null);

  // F.6 W2 (2026-05-26) — URL-driven briefing-deck fire.
  // When a user lands here from a Task Drawer / Document Drawer CTA
  // like `/app/solva?ctx_type=task&ctx_id=...&submodule=develop_strategy`,
  // the briefing deck for that area must fire (unless suppressed). The
  // deck's own suppression logic handles the "Don't show me again"
  // ticked state; if suppressed it closes immediately and we navigate
  // straight through to Phase D.
  useEffect(() => {
    if (variant !== "auth") return;
    const sp = new URLSearchParams(location.search);
    const submodule = sp.get("submodule");
    if (!submodule) return;
    const briefArea = SUBMODULE_TO_AREA[submodule];
    if (!briefArea) return;
    setBriefingPendingCard({
      key: submodule,
      __fromUrl: true,
      __urlSearch: location.search,
    });
    setBriefingArea(briefArea);
    setBriefingOpen(true);
    // Only run on mount (URL params are read once); the user-initiated
    // card-click flow still drives `onSelectCard` after this.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      // Phase D.1 (2026-05-26) — open the briefing deck FIRST (per
      // area). The deck owns its own suppression logic via
      // `/api/solva/briefing/state`; if the user has previously
      // ticked "Don't show me again" for this area, the deck closes
      // itself immediately and we navigate straight through.
      // Force-open (i.e., bypass suppression) is NOT used here —
      // only the (i) reopen icon next to the composer forces.
      const briefArea = SUBMODULE_TO_AREA[card.key];
      if (briefArea) {
        setBriefingPendingCard(card);
        setBriefingArea(briefArea);
        setBriefingOpen(true);
        return;
      }
      // Fallback — unknown submodule → skip the deck.
      _navigateAfterCard(card);
    } else {
      navigate("/signin");
    }
  };

  const _navigateAfterCard = (card) => {
    // Phase F + E.5 (2026-05-16) — Phase D framing now supports
    // seed-handoff payloads (`seed_payload` on POST /sessions),
    // so seed-bearing flows (cycle / work-studio / document-
    // journal) route to Phase D too. Legacy /app/solva/session/new
    // is no longer exercised for new sessions.
    const params = new URLSearchParams();
    params.set("submodule", card.key);
    if (intakeSeed?.kind && intakeSeed?.id) {
      params.set("seed_kind", intakeSeed.kind);
      params.set("seed_id", intakeSeed.id);
      if (intakeSeed.preview) params.set("seed_preview", intakeSeed.preview);
    }
    // J4 (2026-05-25, G30 ratified) — forward the de-identified
    // first-session "starter" (intake.top_of_mind, Shield-redacted
    // by J1's G18) onto the framing surface so the Phase D composer
    // pre-fills with the user's stated concern.
    if (intakeStarter) {
      params.set("starter", intakeStarter);
    }
    navigate(`/app/solva/phase-d/session/new?${params.toString()}`);
  };

  const onBriefingClose = (_reason) => {
    setBriefingOpen(false);
    const card = briefingPendingCard;
    setBriefingPendingCard(null);
    if (!card) return;
    // F.6 W2 (2026-05-26) — URL-driven entry: preserve all original
    // URL params (ctx_type / ctx_id / starter / submodule) and route
    // straight to the Phase D session-new surface.
    if (card.__fromUrl) {
      navigate(`/app/solva/phase-d/session/new${card.__urlSearch}`);
      return;
    }
    if (card) {
      _navigateAfterCard(card);
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
      <div className="akki-w-medium">
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
          data-testid="page-subtext"
        >
          Pick what you came to do.
        </p>

        {/* Phase G — 2×2 grid (1×4 → 2×2). Mobile collapses back to
            single column via the @media rule in the <style> block
            below. Layout-only change; copy, ordering, focus
            behaviour, and arrow-key nav all preserved. */}
        <div
          className="solva-picker-grid"
          role="list"
          aria-label="Solva sub-modules"
          data-testid="solva-picker-grid"
        >
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

        {/* Wave 1.3 (UAT pack 2026-05-10) — disambiguator entry point.
            Subtle text link; opens a one-question routing dialog. */}
        {variant === "auth" && (
          <div style={{ textAlign: "center", marginTop: 24 }}>
            <button
              type="button"
              onClick={() => setPickerHelpOpen(true)}
              data-testid="solva-not-sure-link"
              style={{
                background: "none",
                border: "none",
                fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
                fontSize: 13,
                color: TOKEN.MUTED,
                textDecoration: "underline",
                cursor: "pointer",
                padding: 0,
              }}
            >
              Not sure which to pick?
            </button>
          </div>
        )}

        {variant === "auth" && (
          <RecentSessionsCollapsible
            sessions={recent}
            onResume={onResume}
            onDiscard={onDiscard}
            onStartGuided={() => setPickerHelpOpen(true)}
          />
        )}

        {/* Wave 3.3 (UAT pack 2026-05-10) — full sessions list link.
            Sits below the collapsed Recent Sessions block. */}
        {variant === "auth" && (
          <div style={{ textAlign: "center", marginTop: 18 }}>
            <Link
              to="/app/solva/sessions"
              data-testid="solva-view-all-sessions-link"
              style={{
                fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
                fontSize: 13,
                color: TOKEN.MUTED,
                textDecoration: "underline",
              }}
            >
              View all sessions
            </Link>
          </div>
        )}

        {/* Wave 1.3 — disambiguator dialog. Plain HTML+inline-style
            implementation to avoid pulling Radix here for a single
            modal; the rest of the page is already inline-styled. */}
        {pickerHelpOpen && (
          <DisambiguatorDialog
            onPick={(key) => {
              setPickerHelpOpen(false);
              const found = CARDS.find((c) => c.key === key);
              if (found) onSelectCard(found);
            }}
            onClose={() => setPickerHelpOpen(false)}
          />
        )}

        <div style={{ marginTop: 40, textAlign: "center" }}>
          <Link
            to="/solva"
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

      {/* Phase D.1 (2026-05-26) — pre-conversation briefing deck.
          Lives in the SolvaLanding scope (not inside DisambiguatorDialog)
          so it can access briefingArea / briefingOpen / onBriefingClose.
          Suppression logic owned by the deck itself; we pass `force=false`
          (default) — only the (i) icon on the session page forces. */}
      {briefingArea && (
        <SolvaBriefingDeck
          area={briefingArea}
          open={briefingOpen}
          onClose={onBriefingClose}
        />
      )}

      {/* Brief §7.6 responsive — title 32px on mobile.
          Phase G — solva-picker-grid renders 2×2 on desktop/tablet,
          collapses to 1-column on mobile (≤640px). */}
      <style>{`
        .solva-picker-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 24px;
        }
        @media (max-width: 640px) {
          .solva-landing-title { font-size: 32px !important; }
          .solva-picker-grid { grid-template-columns: 1fr; }
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


// =============================================================================
// Wave 1.3 (UAT pack 2026-05-10) — Disambiguator dialog
// =============================================================================
// One routing question, four radios, each radio maps to a task tile.
// Shipped as a plain HTML modal (no Radix dependency added) to match
// the rest of the page's inline-style aesthetic. Closes on backdrop
// click, on Escape, and after a selection is made.

function DisambiguatorDialog({ onPick, onClose }) {
  const [choice, setChoice] = useState("");

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const options = [
    { key: "seek_clarity",       label: "Are you trying to understand a situation that feels foggy?" },
    { key: "develop_strategy",   label: "Are you trying to decide between paths?" },
    { key: "simulate_hypothesis", label: "Are you trying to stress-test an idea or hypothesis?" },
    { key: "get_perspective",    label: "Are you trying to see a situation from a different angle?" },
  ];

  return (
    <div
      role="presentation"
      onClick={onClose}
      data-testid="solva-disambiguator-backdrop"
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(31, 28, 24, 0.55)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="solva-disambig-title"
        onClick={(e) => e.stopPropagation()}
        data-testid="solva-disambiguator-dialog"
        style={{
          background: "var(--parchment-light)",
          borderRadius: 6,
          maxWidth: 520,
          width: "100%",
          padding: "28px 28px 24px",
          boxShadow: "0 20px 60px rgba(0,0,0,0.22)",
        }}
      >
        <h2
          id="solva-disambig-title"
          style={{
            fontFamily: "Georgia, serif",
            fontSize: 22,
            color: TOKEN.INK,
            margin: "0 0 6px 0",
            fontWeight: 600,
          }}
        >
          Which of these fits?
        </h2>
        <p
          style={{
            fontFamily: "Georgia, serif",
            fontStyle: "italic",
            fontSize: 14,
            color: TOKEN.DEEP,
            margin: "0 0 18px 0",
          }}
        >
          We&apos;ll pick the right surface for you.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {options.map((o) => (
            <label
              key={o.key}
              data-testid={`solva-disambig-option-${o.key}`}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                padding: "10px 12px",
                border: `1px solid ${choice === o.key ? TOKEN.ACCENT : TOKEN.RULE}`,
                borderRadius: 4,
                cursor: "pointer",
                background: choice === o.key ? "rgba(139,29,44,0.04)" : "transparent",
              }}
            >
              <input
                type="radio"
                name="solva-disambig"
                value={o.key}
                checked={choice === o.key}
                onChange={() => setChoice(o.key)}
                style={{ marginTop: 3, accentColor: TOKEN.ACCENT }}
              />
              <span
                style={{
                  fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
                  fontSize: 14,
                  color: TOKEN.INK,
                  lineHeight: 1.5,
                }}
              >
                {o.label}
              </span>
            </label>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 22 }}>
          <button
            type="button"
            onClick={onClose}
            data-testid="solva-disambig-cancel"
            style={{
              background: "none",
              border: `1px solid ${TOKEN.RULE}`,
              padding: "8px 16px",
              borderRadius: 2,
              cursor: "pointer",
              fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
              fontSize: 13,
              color: TOKEN.MUTED,
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!choice}
            onClick={() => onPick(choice)}
            data-testid="solva-disambig-confirm"
            style={{
              background: choice ? TOKEN.ACCENT : TOKEN.MUTED,
              color: "var(--parchment-light)",
              border: "none",
              padding: "8px 18px",
              borderRadius: 2,
              cursor: choice ? "pointer" : "not-allowed",
              fontFamily: 'Calibri, "Segoe UI", system-ui, sans-serif',
              fontSize: 13,
              fontWeight: 500,
              letterSpacing: 0.3,
              opacity: choice ? 1 : 0.6,
            }}
          >
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}
