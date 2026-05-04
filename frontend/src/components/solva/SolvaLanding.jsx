/**
 * Phase B.4 — Solva landing surface.
 *
 * One layout, two variants:
 *   variant="auth"       → mounted from /app/solva (SolvaApp.jsx).
 *                          Right panel shows the user's recent sessions
 *                          and session-health (active count vs. cap,
 *                          plan tier).
 *   variant="marketing"  → mounted from /solva (SolvaLanding.jsx).
 *                          Right panel becomes a "What Solva is"
 *                          explainer with a sign-in CTA.
 *
 * Layout (desktop ≥1024px):
 *   ┌──────────────────────────────────┬───────────────────┐
 *   │ 4-tile picker                    │  Right panel      │
 *   │ ┌────────────┬────────────┐      │  ┌──────────────┐ │
 *   │ │ Seek       │ Develop    │      │  │ Recent       │ │
 *   │ │ Clarity    │ Strategy   │      │  │ sessions     │ │
 *   │ ├────────────┼────────────┤      │  │ (or          │ │
 *   │ │ Simulate   │ See Another│      │  │ marketing    │ │
 *   │ │ Hypothesis │ Perspective│      │  │ explainer)   │ │
 *   │ └────────────┴────────────┘      │  └──────────────┘ │
 *   │                                  │  ┌──────────────┐ │
 *   │ ┌──────────────────────────┐ →   │  │ Session      │ │
 *   │ │ <single-line input>      │     │  │ health       │ │
 *   │ └──────────────────────────┘     │  └──────────────┘ │
 *   └──────────────────────────────────┴───────────────────┘
 *
 * Below 1024px the right panel collapses below the picker.
 *
 * Palette: Ink / Oxblood / Navy / Cream (CSS vars from index.css).
 * Typography: Georgia for tile titles + the prompt input,
 *             Calibri-stack for everything else (Phase A).
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";

const SUBMODULES = [
  {
    key: "seek_clarity",
    title: "Seek Clarity",
    blurb: "Diagnose first. One layer at a time.",
    examples: [
      "What's actually going wrong with our Q1 cash flow?",
      "Why is the executive team's confidence in the strategy slipping?",
      "What's the real cause of customer churn in our top decile?",
    ],
  },
  {
    key: "develop_strategy",
    title: "Develop Strategy",
    blurb: "Diagnosis to recommendation. Specific. Owner-assignable.",
    examples: [
      "How should we sequence restructure vs. raise over the next two quarters?",
      "What does a credible cost-out programme look like for our SG&A line?",
      "Pick three moves that would shift our gross margin by 200 bps within 18 months.",
    ],
  },
  {
    key: "simulate_hypothesis",
    title: "Simulate Hypothesis",
    blurb: "Test a what-if. Surface tensions. Map second-order effects.",
    examples: [
      "What happens to retention if we double our pricing on the enterprise tier?",
      "If we exit the SMB segment in 12 months, what knock-on hits the platform team?",
      "Our biggest customer concentrates on one product line — what if they renegotiate?",
    ],
  },
  {
    key: "get_perspective",
    title: "See Another Perspective",
    blurb: "Hear it in another voice — Chair, NED, Investor, Regulator, Auditor.",
    examples: [
      "How would a non-executive Chair frame the succession question?",
      "What would a sceptical institutional investor ask about our capital plan?",
      "How would the regulator read our last quarter's KPI deck?",
    ],
  },
];


function SubmoduleTile({ tile, active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-active={active ? "true" : "false"}
      data-testid={`solva-tile-${tile.key}`}
      className={[
        "text-left p-5 border rounded-md transition-all",
        "bg-[var(--cream)] hover:bg-[var(--warm-white)]",
        active
          ? "border-[var(--accent)] shadow-[0_0_0_1px_var(--accent)] bg-[var(--warm-white)]"
          : "border-[var(--rule)]",
      ].join(" ")}
    >
      <h3
        className="akki-serif font-medium text-[18px] leading-snug mb-2"
        style={{ color: active ? "var(--accent)" : "var(--ink)" }}
      >
        {tile.title}
      </h3>
      <p className="text-[13px] leading-relaxed text-[var(--muted)]">
        {tile.blurb}
      </p>
    </button>
  );
}


function RotatingPlaceholder({ examples, intervalMs = 4000 }) {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % examples.length), intervalMs);
    return () => clearInterval(t);
  }, [examples.length, intervalMs]);
  return examples[idx];
}


function MarketingExplainer() {
  return (
    <aside className="border border-[var(--rule)] bg-[var(--cream)] p-5 rounded-md">
      <p className="akki-overline text-[11px] mb-3" style={{ color: "var(--muted)" }}>
        What Solva is
      </p>
      <p className="text-[14px] leading-relaxed mb-4" style={{ color: "var(--ink)" }}>
        Solva is a reasoning surface, not a chat. It asks one layer of questions at a time —
        framing, grounding, synthesis, reflection — and refuses to volunteer a personal opinion.
        Every assertion carries a tier marker: corpus, comparable, domain prior, user assertion,
        or speculation. You see how the case is built, not just what it says.
      </p>
      <Link
        to="/signin"
        className="inline-flex items-center gap-2 text-[14px] font-medium"
        style={{ color: "var(--accent)" }}
      >
        Sign in to start a session <ArrowRight className="w-4 h-4" />
      </Link>
    </aside>
  );
}


function RecentSessionsPanel({ sessions }) {
  if (!sessions || sessions.length === 0) {
    return (
      <aside className="border border-[var(--rule)] bg-[var(--cream)] p-5 rounded-md">
        <p className="akki-overline text-[11px] mb-2" style={{ color: "var(--muted)" }}>
          Recent sessions
        </p>
        <p className="text-[13px] leading-relaxed" style={{ color: "var(--muted)" }}>
          You have no Solva sessions yet. Pick a tile above to start one.
        </p>
      </aside>
    );
  }
  const top5 = sessions.slice(0, 5);
  return (
    <aside className="border border-[var(--rule)] bg-[var(--cream)] p-5 rounded-md">
      <p className="akki-overline text-[11px] mb-3" style={{ color: "var(--muted)" }}>
        Recent sessions
      </p>
      <ul className="space-y-3">
        {top5.map((s) => (
          <li key={s.id} className="text-[13px]">
            <div className="flex items-start gap-3">
              <span
                className="inline-block px-2 py-[2px] text-[10px] uppercase tracking-wide rounded-sm border whitespace-nowrap"
                style={{
                  borderColor: "var(--rule)",
                  color: s.status === "completed" ? "var(--accent)" : "var(--muted)",
                }}
              >
                {s.status}
              </span>
              <span className="flex-1 truncate" title={s.intent || s.cluster_label}>
                {s.intent || s.cluster_label}
              </span>
            </div>
            <p className="text-[11px] mt-1 ml-[64px]" style={{ color: "var(--muted)" }}>
              {s.submodule || "—"} · {s.updated_at ? new Date(s.updated_at).toLocaleDateString() : ""}
            </p>
          </li>
        ))}
      </ul>
    </aside>
  );
}


function SessionHealthPanel({ activeCount, planTier }) {
  const cap = 3; // MAX_CONCURRENT_ACTIVE — kept in sync with backend
  const overCap = activeCount >= cap;
  return (
    <aside className="border border-[var(--rule)] bg-[var(--cream)] p-5 rounded-md">
      <p className="akki-overline text-[11px] mb-3" style={{ color: "var(--muted)" }}>
        Session health
      </p>
      <p className="text-[13px] leading-relaxed mb-2" style={{ color: "var(--ink)" }}>
        <strong style={{ color: overCap ? "var(--accent)" : "var(--ink)" }}>
          {activeCount}
        </strong>{" "}
        active sessions out of {cap} allowed.
      </p>
      <p className="text-[12px] mt-2" style={{ color: "var(--muted)" }}>
        Plan: {planTier || "free"}.{" "}
        {overCap
          ? "You've reached the concurrent limit. Finish or abandon a session to start a new one."
          : "Stale sessions are auto-abandoned after 30 days."}
      </p>
    </aside>
  );
}


/**
 * SolvaLanding — the new tile + input + right panel surface.
 *
 * @param {object} props
 * @param {"auth"|"marketing"} props.variant — picks the right panel content.
 * @param {(payload: {submodule: string, intent: string}) => void} props.onSubmit
 *        — auth variant calls this with the picked submodule and intent.
 *        Marketing variant ignores it (button becomes a sign-in link).
 * @param {object[]=} props.recentSessions — auth variant only (top 5).
 * @param {string=} props.planTier — auth variant only.
 */
export default function SolvaLanding({
  variant = "auth",
  onSubmit,
  recentSessions = [],
  planTier = "free",
}) {
  const [activeKey, setActiveKey] = useState("seek_clarity");
  const [intent, setIntent] = useState("");
  const inputRef = useRef(null);

  const activeTile = useMemo(
    () => SUBMODULES.find((t) => t.key === activeKey) || SUBMODULES[0],
    [activeKey],
  );

  const activeCount = useMemo(
    () => (recentSessions || []).filter((s) => s.status === "active").length,
    [recentSessions],
  );

  const submitDisabled = intent.trim().length < 20;

  const submit = (e) => {
    e?.preventDefault?.();
    if (variant !== "auth" || submitDisabled) return;
    onSubmit?.({ submodule: activeKey, intent: intent.trim() });
  };

  return (
    <div
      className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-8 p-6 md:p-10"
      data-testid="solva-landing"
      data-variant={variant}
    >
      {/* LEFT — tiles + input */}
      <div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          {SUBMODULES.map((tile) => (
            <SubmoduleTile
              key={tile.key}
              tile={tile}
              active={tile.key === activeKey}
              onClick={() => {
                setActiveKey(tile.key);
                inputRef.current?.focus();
              }}
            />
          ))}
        </div>

        <form onSubmit={submit} className="flex items-center gap-3">
          <input
            ref={inputRef}
            type="text"
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            placeholder={(
              activeTile.examples[0]
              + (activeTile.examples.length > 1 ? "" : "")
            )}
            data-testid="solva-landing-input"
            className="akki-serif flex-1 h-12 px-4 border border-[var(--rule)] rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/40"
            style={{ fontSize: 16, fontFamily: "Georgia, serif" }}
            aria-label={`Type your ${activeTile.title} prompt`}
            disabled={variant !== "auth"}
          />
          {variant === "auth" ? (
            <button
              type="submit"
              disabled={submitDisabled}
              data-testid="solva-landing-submit"
              className="bg-[var(--accent)] disabled:bg-[var(--muted)] text-white h-12 px-5 rounded-md font-medium inline-flex items-center gap-2"
            >
              Start <ArrowRight className="w-4 h-4" />
            </button>
          ) : (
            <Link
              to="/signin"
              data-testid="solva-landing-signin"
              className="bg-[var(--accent)] text-white h-12 px-5 rounded-md font-medium inline-flex items-center gap-2"
            >
              Sign in to start <ArrowRight className="w-4 h-4" />
            </Link>
          )}
        </form>

        <p className="text-[12px] mt-3" style={{ color: "var(--muted)" }}>
          Try:{" "}
          <em style={{ fontFamily: "Georgia, serif" }}>
            <RotatingPlaceholder examples={activeTile.examples} />
          </em>
        </p>
      </div>

      {/* RIGHT — recent sessions + health (auth) OR marketing explainer */}
      <div className="space-y-4">
        {variant === "auth" ? (
          <>
            <RecentSessionsPanel sessions={recentSessions} />
            <SessionHealthPanel activeCount={activeCount} planTier={planTier} />
          </>
        ) : (
          <MarketingExplainer />
        )}
      </div>
    </div>
  );
}


// Re-export the SUBMODULES constant so callers can drive their own
// state from the same source of truth.
export { SUBMODULES };
