/**
 * Portfolio Landing (Home 1) — Phase H.1 layout shell (2026-05-26).
 *
 * Post-sign-in landing surface. Used in two routing modes:
 *   1. /app/companies (canonical)  → this page directly
 *   2. /app  (no active context)   → this page via AppHome dispatcher
 *
 * H.1 is SHELL ONLY. No data wiring — metric tile values render as
 * `—` placeholders; the 3 main sections render `Coming soon` empty
 * states. H.3 will wire real data sources.
 *
 * Layout (per sketch 1):
 *   LEFT  — eyebrow + time-aware greeting H1 (32px) + subtitle +
 *           4 metric tiles + 3 sections (Boards to watch / Where you
 *           left off / The world around you)
 *   RIGHT — rail with "+ Add Company" button + NED/Executive segmented
 *           tabs + vertical stack of calm company cards
 *
 * Out of scope (deferred):
 *   • Real data for metric tiles + 3 sections          → H.3
 *   • Full /app/news page                              → H.3
 *   • Phase I (Company Home / Home2 redesign)          → Phase I
 *
 * Per-page font-size override (32px) on the greeting H1 is INLINE,
 * not via .akki-greeting token (token stays at 28px — guarded by
 * tests/test_portfolio_h1_size_guard.py).
 */
import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import {
  Landmark, Briefcase, Plus, Layers, Flame, History, Newspaper,
  ArrowRight,
} from "lucide-react";


/* ─────────────────────────────────────────────────────────────────── */
/* Helpers                                                             */
/* ─────────────────────────────────────────────────────────────────── */

function timeAwareGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function classifyRole(c) {
  if (!c || !c.type) return "executive";
  return c.type.startsWith("ned") ? "ned" : "executive";
}


/* ─────────────────────────────────────────────────────────────────── */
/* Company card — calm, lighter, full-rail-width                       */
/* ─────────────────────────────────────────────────────────────────── */

function CompanyCard({ c, active, onOpen }) {
  const sponsored =
    c.provisioning === "sponsored" ||
    c.type === "ned_sponsored" ||
    c.type === "executive_enterprise";
  const Icon = c.type?.startsWith("ned") ? Landmark : Briefcase;

  return (
    <button
      type="button"
      onClick={onOpen}
      className={`relative w-full text-left bg-white border rounded-md px-4 py-3 transition-colors ${
        active
          ? "border-[var(--accent)]"
          : "border-[var(--rule)] hover:border-[var(--ink)]/30"
      }`}
      data-testid={`portfolio-card-${c.id}`}
    >
      {sponsored && (
        <span
          className="absolute top-2 right-2 text-[9px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] border border-[var(--rule)] rounded-sm px-1.5 py-[1px]"
          data-testid={`portfolio-card-${c.id}-sponsored`}
        >
          Sponsored
        </span>
      )}
      <div className="flex items-start gap-2.5">
        <div className="w-7 h-7 bg-[var(--cream-deep)] rounded-md flex items-center justify-center shrink-0 mt-0.5">
          <Icon className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.7} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[16px] font-normal text-[var(--ink)] leading-snug pr-12">
            {c.name}
          </p>
          <p className="text-[11.5px] text-[var(--muted)] mt-0.5 truncate">
            {[c.industry, c.region].filter(Boolean).join(" · ") || " "}
          </p>
        </div>
      </div>
    </button>
  );
}


/* ─────────────────────────────────────────────────────────────────── */
/* Right-rail company list                                              */
/* ─────────────────────────────────────────────────────────────────── */

function RailCompanyList({ contexts, activeContextId, onOpen, onAdd }) {
  const nedList  = useMemo(() => contexts.filter((c) => classifyRole(c) === "ned"), [contexts]);
  const execList = useMemo(() => contexts.filter((c) => classifyRole(c) === "executive"), [contexts]);
  // Default to first non-empty tab. Re-evaluates only when counts change.
  const defaultTab = nedList.length > 0 ? "ned" : "executive";
  const [tab, setTab] = useState(defaultTab);
  useEffect(() => {
    if (tab === "ned" && nedList.length === 0 && execList.length > 0) setTab("executive");
    if (tab === "executive" && execList.length === 0 && nedList.length > 0) setTab("ned");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nedList.length, execList.length]);

  const visible = tab === "ned" ? nedList : execList;

  return (
    <aside
      className="w-[340px] shrink-0 hidden xl:flex flex-col gap-4"
      data-testid="portfolio-right-rail"
    >
      <div className="flex items-center justify-end">
        <Button
          onClick={onAdd}
          className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-9 px-3 text-[12.5px] font-medium"
          data-testid="portfolio-add-company-btn"
        >
          <Plus className="w-3.5 h-3.5 mr-1" /> Add Company
        </Button>
      </div>

      {/* Segmented tabs — NED · n / Executive · n */}
      <div
        className="grid grid-cols-2 border border-[var(--rule)] rounded-sm bg-white overflow-hidden"
        role="tablist"
        data-testid="portfolio-rail-tabs"
      >
        <button
          type="button"
          role="tab"
          aria-selected={tab === "ned"}
          onClick={() => setTab("ned")}
          className={`text-[11.5px] uppercase tracking-[0.14em] font-mono py-2 transition-colors ${
            tab === "ned"
              ? "bg-[var(--ink)] text-white"
              : "text-[var(--muted)] hover:text-[var(--ink)] bg-white"
          }`}
          data-testid="portfolio-rail-tab-ned"
        >
          NED · {nedList.length}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "executive"}
          onClick={() => setTab("executive")}
          className={`text-[11.5px] uppercase tracking-[0.14em] font-mono py-2 transition-colors ${
            tab === "executive"
              ? "bg-[var(--ink)] text-white"
              : "text-[var(--muted)] hover:text-[var(--ink)] bg-white"
          }`}
          data-testid="portfolio-rail-tab-executive"
        >
          Executive · {execList.length}
        </button>
      </div>

      {/* Vertical stack of company cards (rail-width parity) */}
      <div
        className="flex flex-col gap-2.5"
        data-testid={`portfolio-rail-list-${tab}`}
      >
        {visible.length === 0 ? (
          <p className="text-[12px] italic text-[var(--muted)] px-1 py-3" data-testid="portfolio-rail-empty">
            No {tab === "ned" ? "NED boards" : "executive companies"} yet.
          </p>
        ) : (
          visible.map((c) => (
            <CompanyCard
              key={c.id}
              c={c}
              active={c.id === activeContextId}
              onOpen={() => onOpen(c.id)}
            />
          ))
        )}
      </div>
    </aside>
  );
}


/* ─────────────────────────────────────────────────────────────────── */
/* Placeholder section card                                             */
/* ─────────────────────────────────────────────────────────────────── */

function PlaceholderSection({ icon: Icon, label, testid, footer = null }) {
  return (
    <section data-testid={testid}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
        <h2 className="akki-overline">{label}</h2>
      </div>
      <div
        className="bg-white border border-dashed border-[var(--rule)] rounded-md px-6 py-10 text-center"
        data-testid={`${testid}-empty`}
      >
        <p className="text-[12.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
          Coming soon
        </p>
      </div>
      {footer}
    </section>
  );
}


/* ─────────────────────────────────────────────────────────────────── */
/* Metric tile (4-in-a-row)                                             */
/* ─────────────────────────────────────────────────────────────────── */

function MetricTile({ label, value }) {
  return (
    <div
      className="bg-white border border-[var(--rule)] rounded-md px-4 py-3"
      data-testid={`portfolio-metric-${label.toLowerCase()}`}
    >
      <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] mb-1">
        {label}
      </p>
      <p className="akki-serif text-[24px] font-normal text-[var(--ink)] leading-none">
        {value}
      </p>
    </div>
  );
}


/* ─────────────────────────────────────────────────────────────────── */
/* Page                                                                 */
/* ─────────────────────────────────────────────────────────────────── */

export default function ContextPortfolio() {
  const { contexts, activeContextId, switchContext, account } = useAuth();
  const navigate = useNavigate();

  const openContext = (cid) => {
    switchContext(cid);
    navigate("/app");
  };

  const firstName = (account?.name || "there").split(" ")[0];
  const greeting = timeAwareGreeting();

  return (
    <AppShell>
      <div
        className="akki-w-medium px-8 pt-10 pb-12 flex gap-10"
        data-testid="portfolio-landing"
      >
        {/* LEFT — main column */}
        <div className="flex-1 min-w-0 space-y-10">
          {/* Header — eyebrow + greeting + subtitle */}
          <header className="akki-fade-up">
            <p className="akki-overline mb-2 flex items-center gap-2">
              <Layers className="w-3 h-3 text-[var(--accent)]" /> Portfolio
            </p>
            <h1
              className="akki-greeting"
              style={{ fontSize: "32px" }}
              data-testid="portfolio-greeting-h1"
            >
              {greeting}, {firstName}.
            </h1>
            <p className="akki-meta mt-2 max-w-2xl" data-testid="portfolio-subtitle">
              Here are your boards & operating companies.
            </p>
          </header>

          {/* 4 metric tiles — placeholders (H.3 wires real counts) */}
          <div
            className="grid grid-cols-2 md:grid-cols-4 gap-4"
            data-testid="portfolio-metrics-row"
          >
            <MetricTile label="Companies" value="—" />
            <MetricTile label="Signals"   value="—" />
            <MetricTile label="Briefings" value="—" />
            <MetricTile label="Documents" value="—" />
          </div>

          {/* Section 1 — Boards to watch this week */}
          <PlaceholderSection
            icon={Flame}
            label="Boards to watch this week"
            testid="portfolio-section-boards-to-watch"
          />

          {/* Section 2 — Where you left off */}
          <PlaceholderSection
            icon={History}
            label="Where you left off"
            testid="portfolio-section-where-you-left-off"
          />

          {/* Section 3 — The world around you (News) */}
          <PlaceholderSection
            icon={Newspaper}
            label="The world around you"
            testid="portfolio-section-news"
            footer={
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={() => navigate("/app/news")}
                  className="text-[12.5px] text-[var(--accent)] hover:text-[var(--ink)] inline-flex items-center gap-1"
                  data-testid="portfolio-section-news-read-more"
                >
                  Read more <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            }
          />
        </div>

        {/* RIGHT — company rail */}
        <RailCompanyList
          contexts={contexts}
          activeContextId={activeContextId}
          onOpen={openContext}
          onAdd={() => navigate("/app/contexts/new")}
        />
      </div>
    </AppShell>
  );
}
