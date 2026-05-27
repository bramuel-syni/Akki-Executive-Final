/**
 * CompanyHome — Phase I.1 layout shell (2026-05-27).
 *
 * Active-context home surface. Rendered by AppHome's dispatcher when
 * `activeContext != null` (replaces the legacy Home2.jsx).
 *
 * I.1 SCOPE: layout shell only. NO data wiring. All counts are `—`,
 * all subtext is "Awaiting wiring..." placeholders, all surfaces
 * deep-link via static routes. I.2/I.3/I.4/I.5 progressively wire:
 *
 *   I.2  Header KPI strip (Readiness composite) + 5 attention card
 *        counts + subtext
 *   I.3  Right-rail Top Signals (Pulse/Monitor/Documents chips)
 *   I.4  Events system (manual / doc-extraction / calendar sync)
 *   I.5  Open Questions wiring via cycle_questions + asker_role
 *   I.6  Archive Home2.jsx + final hygiene
 *
 * Layout (per sketch 2):
 *   LEFT — ← Back to Portfolio · 32px H1 `Inside {Company}.` ·
 *          subtitle · Readiness strip · 5 stacked attention cards
 *   RIGHT — Add Document + All Docs · Top Signals heading ·
 *          Pulse/Monitor/Documents segmented chips · Coming-soon body
 *
 * Per-page font-size override (32px) on the H1 is INLINE, not via
 * .akki-greeting token (which stays at 28px — guarded by tests/
 * test_portfolio_h1_size_guard.py).
 */
import React, { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import AppShell from "@/components/layout/AppShell";
import {
  ArrowLeft, Mail, ClipboardCheck, AlertTriangle, MessageSquare,
  Calendar, ChevronRight, Plus, FolderOpen, Activity, FileText, Bell,
} from "lucide-react";

const ATTENTION_CARDS = [
  { id: "drafts",    title: "Email drafts ready for review", icon: Mail,            routeKey: "drafts" },
  { id: "reports",   title: "Reports ready to compile",      icon: ClipboardCheck,  routeKey: "reports" },
  { id: "pulse",     title: "New pulse updates",              icon: AlertTriangle,   routeKey: "pulse" },
  { id: "questions", title: "Open questions",                 icon: MessageSquare,   routeKey: "questions" },
  { id: "events",    title: "Upcoming events",                icon: Calendar,        routeKey: "events" },
];

// Phase I.2 (2026-05-27) — click → context-filtered surface route.
// `events` card is intentionally a no-op until I.4 ships the events
// collection.
function _routeForCard(routeKey, cid) {
  if (!cid) return null;
  switch (routeKey) {
    case "drafts":    return `/app/work-studio?tab=drafts&context_id=${cid}`;
    case "reports":   return `/app/task-manager?filter=ready_to_compile&context_id=${cid}`;
    case "pulse":     return `/app/pulse?context_id=${cid}`;
    case "questions": return `/app/questions?status=open&context_id=${cid}`;
    case "events":    return null;   // I.4
    default:          return null;
  }
}

const TOP_SIGNAL_CHIPS = [
  { id: "pulse",     label: "Pulse" },
  { id: "monitor",   label: "Monitor" },
  { id: "documents", label: "Documents" },
];


function AttentionCard({ card, data, onOpen }) {
  const Icon = card.icon;
  const count = data?.count;
  const subtext = data?.subtext;
  // Loading: count is undefined (no fetch yet). Show — / placeholder.
  // Loaded: count is a number; subtext is the act-now prompt.
  const renderedCount =
    typeof count === "number" ? String(count) : "—";
  const renderedSubtext =
    typeof subtext === "string" && subtext.length > 0
      ? subtext
      : "Awaiting wiring...";

  return (
    <button
      type="button"
      onClick={() => onOpen(card.routeKey)}
      aria-label={`Open ${card.title}`}
      className="w-full bg-white border border-[var(--rule)] hover:border-[var(--ink)]/30 rounded-md px-5 py-4 transition-colors text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 focus-visible:ring-offset-1"
      data-card-kind="attention"
      data-card-id={card.id}
      data-testid={`company-home-attention-${card.id}`}
    >
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 bg-[var(--cream-deep)] rounded-md flex items-center justify-center shrink-0 mt-0.5">
          <Icon className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.7} aria-hidden="true" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <p className="text-[15.5px] text-[var(--ink)] leading-snug">
              {card.title}
            </p>
            <span
              className="text-[15.5px] font-medium text-[var(--muted)] shrink-0 tabular-nums"
              data-testid={`company-home-attention-${card.id}-count`}
            >
              {renderedCount}
            </span>
          </div>
          <p
            className="text-[12px] text-[var(--muted)] italic mt-1"
            data-testid={`company-home-attention-${card.id}-subtext`}
          >
            {renderedSubtext}
          </p>
        </div>
        <ChevronRight className="w-3.5 h-3.5 text-[var(--muted)] shrink-0 mt-1.5" strokeWidth={1.8} aria-hidden="true" />
      </div>
    </button>
  );
}


function RightRail({ chip, setChip, onAddDoc, onAllDocs }) {
  return (
    <aside
      className="w-full lg:w-[320px] shrink-0 space-y-5"
      data-testid="company-home-right-rail"
    >
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onAllDocs}
          aria-label="View all documents"
          className="w-8 h-8 flex items-center justify-center text-[var(--muted)] hover:text-[var(--ink)] border border-[var(--rule)] rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50"
          data-testid="company-home-all-docs-btn"
        >
          <FolderOpen className="w-4 h-4" strokeWidth={1.7} aria-hidden="true" />
        </button>
        <button
          type="button"
          onClick={onAddDoc}
          aria-label="Add a document to this company"
          className="inline-flex items-center gap-1.5 text-[12.5px] uppercase tracking-[0.06em] font-mono px-3 h-8 border border-[var(--ink)] bg-[var(--ink)] text-white hover:bg-[var(--ink)]/90 rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50"
          data-testid="company-home-add-doc-btn"
        >
          <Plus className="w-3 h-3" strokeWidth={2} aria-hidden="true" />
          Add Document
        </button>
      </div>

      <div>
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} aria-hidden="true" />
          <h2 className="akki-overline" id="company-home-top-signals-heading">
            Top Signals
          </h2>
        </div>

        <div
          className="grid grid-cols-3 border border-[var(--rule)] rounded-sm bg-white overflow-hidden mb-3"
          role="tablist"
          aria-label="Top signals filter"
          data-testid="company-home-top-signals-chips"
        >
          {TOP_SIGNAL_CHIPS.map((c) => (
            <button
              key={c.id}
              type="button"
              role="tab"
              aria-selected={chip === c.id}
              aria-controls={`company-home-top-signals-${c.id}-panel`}
              onClick={() => setChip(c.id)}
              className={`text-[11.5px] uppercase tracking-[0.14em] font-mono py-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--accent)]/50 ${
                chip === c.id
                  ? "bg-[var(--ink)] text-white"
                  : "text-[var(--muted)] hover:text-[var(--ink)] bg-white"
              }`}
              data-testid={`company-home-top-signals-chip-${c.id}`}
            >
              {c.label}
            </button>
          ))}
        </div>

        <div
          role="tabpanel"
          id={`company-home-top-signals-${chip}-panel`}
          aria-labelledby="company-home-top-signals-heading"
          className="bg-white border border-dashed border-[var(--rule)] rounded-md px-5 py-8 text-center"
          data-testid={`company-home-top-signals-${chip}-empty`}
        >
          <p className="text-[12.5px] italic text-[var(--muted)]">
            Coming soon
          </p>
        </div>
      </div>
    </aside>
  );
}


export default function CompanyHome() {
  const navigate = useNavigate();
  const { activeContext, clearActiveContext } = useAuth();
  const [chip, setChip] = useState("pulse");
  const cid = activeContext?.id;

  // Phase I.2 (2026-05-27) — live data fetches. Two endpoints,
  // mounted in parallel. Loading state: leave undefined → `—`
  // placeholders. Error state: log to console, leave undefined →
  // placeholders. Never break the page.
  const [readiness, setReadiness] = useState(undefined);
  const [attention, setAttention] = useState({});

  useEffect(() => {
    if (!cid) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get(
          `/me/company-home/readiness?context_id=${encodeURIComponent(cid)}`
        );
        if (!cancelled) setReadiness(data);
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("[CompanyHome] readiness fetch failed:", err?.message);
      }
    })();
    (async () => {
      try {
        const { data } = await api.get(
          `/me/company-home/attention?context_id=${encodeURIComponent(cid)}`
        );
        if (!cancelled) setAttention(data || {});
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("[CompanyHome] attention fetch failed:", err?.message);
      }
    })();
    return () => { cancelled = true; };
  }, [cid]);

  const onBackToPortfolio = useCallback(() => {
    // Phase I.1 (2026-05-27) — Clear active context client-side then
    // route to /app. AppHome's no-active-context branch resolves to
    // the new Portfolio Landing.
    if (typeof clearActiveContext === "function") clearActiveContext();
    navigate("/app");
  }, [clearActiveContext, navigate]);

  const onAddDoc = useCallback(() => navigate("/app/work-studio"), [navigate]);
  const onAllDocs = useCallback(() => navigate("/app/work-studio"), [navigate]);
  const onOpenCard = useCallback((routeKey) => {
    const r = _routeForCard(routeKey, cid);
    if (r) navigate(r);
  }, [cid, navigate]);

  const companyName = activeContext?.name || "this company";
  const readinessRendered =
    readiness && typeof readiness.readiness_percent === "number"
      ? `${readiness.readiness_percent}%`
      : "—%";

  return (
    <AppShell>
      <div
        className="max-w-[1240px] mx-auto px-6 lg:px-8 py-8"
        data-testid="company-home"
      >
        {/* Breadcrumb */}
        <button
          type="button"
          onClick={onBackToPortfolio}
          aria-label="Back to portfolio"
          className="text-[11.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1.5 mb-6 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 rounded-sm px-1 py-0.5"
          data-testid="company-home-back-to-portfolio"
        >
          <ArrowLeft className="w-3 h-3" strokeWidth={1.8} aria-hidden="true" />
          Back to Portfolio
        </button>

        <div className="flex flex-col lg:flex-row gap-8">
          {/* LEFT column */}
          <main className="flex-1 min-w-0 space-y-6">
            {/* H1 — 32px per-page inline override (NOT the .akki-greeting token) */}
            <h1
              className="font-serif text-[32px] leading-[1.15] text-[var(--ink)]"
              style={{ fontSize: "32px" }}
              data-testid="company-home-h1"
            >
              Inside {companyName}.
            </h1>
            <p
              className="text-[14px] text-[var(--muted)] -mt-3"
              data-testid="company-home-subtitle"
            >
              Here is what's on your plate.
            </p>

            {/* Header KPI strip — Readiness (I.2 wired) */}
            <div
              className="inline-flex items-center gap-2 text-[12.5px] text-[var(--muted)] border border-[var(--rule)] bg-white rounded-md px-3 py-1.5"
              data-testid="company-home-readiness"
            >
              <Bell className="w-3 h-3 text-[var(--accent)]" strokeWidth={1.8} aria-hidden="true" />
              <span>Readiness</span>
              <span
                className="font-medium text-[var(--ink)] tabular-nums"
                data-testid="company-home-readiness-value"
              >
                {readinessRendered}
              </span>
            </div>

            {/* 5 attention cards stacked */}
            <div className="space-y-3" data-testid="company-home-attention-stack">
              {ATTENTION_CARDS.map((card) => (
                <AttentionCard
                  key={card.id}
                  card={card}
                  data={attention?.[card.id]}
                  onOpen={onOpenCard}
                />
              ))}
            </div>
          </main>

          {/* RIGHT rail */}
          <RightRail
            chip={chip}
            setChip={setChip}
            onAddDoc={onAddDoc}
            onAllDocs={onAllDocs}
          />
        </div>
      </div>
    </AppShell>
  );
}
