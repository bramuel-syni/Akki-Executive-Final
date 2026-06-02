/**
 * Portfolio Landing — Phase H.1/H.2/H.3/H.4 (2026-05-26 / -27).
 *
 * Post-sign-in landing surface. Canonical route since Phase H.5
 * route consolidation:
 *   • /app  (no active context)  → this page via AppHome dispatcher
 *   • /app/portfolio + /app/companies + /app/contexts all redirect to /app
 *
 * Phase H.3 wires live data:
 *   • Metric tiles            ← GET /api/me/portfolio-metrics
 *   • Boards to watch         ← GET /api/me/boards-to-watch?limit=3
 *   • Where you left off      ← GET /api/me/last-action
 *   • The world around you    ← <NewsStrip quality="executive">
 *
 * Layout (per sketch 1):
 *   LEFT  — eyebrow + time-aware greeting H1 (32px) + subtitle +
 *           4 metric tiles + 3 sections (Boards to watch / Where you
 *           left off / The world around you)
 *   RIGHT — rail with "+ Add Company" button + NED/Executive segmented
 *           tabs + vertical stack of calm company cards
 *
 * Out of scope (deferred):
 *   • Phase H.4: Calm pass on Portfolio Landing
 *   • Phase I:   Company Home / Home2 redesign
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
import { api } from "@/lib/api";
import NewsStrip from "@/components/news/NewsStrip";
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

  // H.4 — Compose verbose aria-label so screen readers announce
  // company name + role + sponsored status in one breath instead of
  // reading the icon-svg + ellipsis-truncated metadata separately.
  const role = c.type?.startsWith("ned") ? "NED board" : "Executive context";
  const ariaLabel = [
    `Open ${c.name}`,
    role,
    sponsored ? "sponsored seat" : null,
    active ? "currently active" : null,
  ].filter(Boolean).join(" · ");

  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={ariaLabel}
      aria-current={active ? "true" : undefined}
      className={`relative w-full text-left bg-white border rounded-md px-4 py-3 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 focus-visible:ring-offset-1 ${
        active
          ? "border-[var(--accent)]"
          : "border-[var(--rule)] hover:border-[var(--ink)]/30"
      }`}
      data-testid={`portfolio-card-${c.id}`}
      data-rail-card-id={c.id}
      data-rail-card-role={c.type?.startsWith("ned") ? "ned" : "executive"}
    >
      {/* H.2 — Stable alias testid for rail-row Playwright assertions.
          We render an invisible sentinel so the testid query is
          unambiguous (the parent already carries `portfolio-card-<id>`
          for back-compat with H.1 tests). */}
      <span
        data-testid={`rail-company-card-${c.id}`}
        className="sr-only"
        aria-hidden="true"
      />
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
          <Icon className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.7} aria-hidden="true" />
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

  // H.2 (2026-05-26) — tab persistence via localStorage. Falls back
  // to first non-empty tab when nothing was persisted yet, or when
  // the persisted tab is now empty.
  const _readPersisted = () => {
    try {
      if (typeof window === "undefined") return null;
      const v = window.localStorage.getItem("akki.portfolio.rail.tab");
      return v === "ned" || v === "executive" ? v : null;
    } catch {
      return null;
    }
  };

  const _firstNonEmpty = () => (nedList.length > 0 ? "ned" : "executive");
  const _initialTab = () => {
    const persisted = _readPersisted();
    if (persisted === "ned"       && nedList.length  > 0) return "ned";
    if (persisted === "executive" && execList.length > 0) return "executive";
    return _firstNonEmpty();
  };

  const [tab, setTabRaw] = useState(_initialTab);
  const setTab = (next) => {
    setTabRaw(next);
    try {
      if (typeof window !== "undefined") {
        window.localStorage.setItem("akki.portfolio.rail.tab", next);
      }
    } catch {
      // localStorage unavailable (private mode, quota); ignore.
    }
  };

  useEffect(() => {
    if (tab === "ned" && nedList.length === 0 && execList.length > 0) setTab("executive");
    if (tab === "executive" && execList.length === 0 && nedList.length > 0) setTab("ned");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nedList.length, execList.length]);

  const visible = tab === "ned" ? nedList : execList;

  return (
    <aside
      className="w-[340px] shrink-0 hidden lg:flex flex-col gap-4"
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
        aria-label="Filter companies by your role"
        data-testid="portfolio-rail-tabs"
      >
        <button
          type="button"
          role="tab"
          aria-selected={tab === "ned"}
          aria-controls={`portfolio-rail-list-ned`}
          aria-label={`Show NED boards (${nedList.length})`}
          onClick={() => setTab("ned")}
          className={`text-[11.5px] uppercase tracking-[0.14em] font-mono py-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--accent)]/50 ${
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
          aria-controls={`portfolio-rail-list-executive`}
          aria-label={`Show executive companies (${execList.length})`}
          onClick={() => setTab("executive")}
          className={`text-[11.5px] uppercase tracking-[0.14em] font-mono py-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--accent)]/50 ${
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
        role="tabpanel"
        id={`portfolio-rail-list-${tab}`}
        aria-labelledby={`portfolio-rail-tab-${tab}`}
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
/* Boards to watch — Section 1                                          */
/* ─────────────────────────────────────────────────────────────────── */

function BoardsToWatchSection({ items, onOpen }) {
  const loading = items === null;
  return (
    <section data-testid="portfolio-section-boards-to-watch" aria-labelledby="portfolio-boards-heading">
      <div className="flex items-center gap-2 mb-3">
        <Flame className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} aria-hidden="true" />
        <h2 className="akki-overline" id="portfolio-boards-heading">Boards to watch this week</h2>
      </div>
      {loading ? (
        <p className="akki-meta italic px-1 py-3" data-testid="portfolio-section-boards-to-watch-loading">
          Loading…
        </p>
      ) : items.length === 0 ? (
        <p
          className="text-[12.5px] italic text-[var(--muted)] bg-white border border-dashed border-[var(--rule)] rounded-md px-6 py-8 text-center"
          data-testid="portfolio-section-boards-to-watch-empty"
        >
          Nothing flagged this week. Sign in to a board to start.
        </p>
      ) : (
        <ul className="space-y-2.5" data-testid="portfolio-section-boards-to-watch-list">
          {items.map((b) => (
            <li key={b.context_id}>
              <button
                type="button"
                onClick={() => onOpen(b.context_id)}
                aria-label={`Open ${b.name}${b.reasons?.length ? ` — ${b.reasons.slice(0, 2).join(", ")}` : ""}`}
                className="w-full text-left bg-white border border-[var(--rule)] hover:border-[var(--ink)]/40 rounded-md px-4 py-3 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 focus-visible:ring-offset-1"
                data-testid={`boards-to-watch-row-${b.context_id}`}
              >
                <p className="text-[15px] font-medium text-[var(--ink)]">{b.name}</p>
                {b.reasons?.length > 0 && (
                  <p className="text-[12px] text-[var(--muted)] mt-1">
                    {b.reasons.slice(0, 2).join(" · ")}
                  </p>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}


/* ─────────────────────────────────────────────────────────────────── */
/* Where you left off — Section 2                                       */
/* ─────────────────────────────────────────────────────────────────── */

function WhereYouLeftOffSection({ row, onResume }) {
  const loading = row === null;
  const empty = !loading && !row?.context_id;
  return (
    <section data-testid="portfolio-section-where-you-left-off" aria-labelledby="portfolio-resume-heading">
      <div className="flex items-center gap-2 mb-3">
        <History className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} aria-hidden="true" />
        <h2 className="akki-overline" id="portfolio-resume-heading">Where you left off</h2>
      </div>
      {loading ? (
        <p className="akki-meta italic px-1 py-3" data-testid="portfolio-section-where-you-left-off-loading">
          Loading…
        </p>
      ) : empty ? (
        <p
          className="text-[12.5px] italic text-[var(--muted)] bg-white border border-dashed border-[var(--rule)] rounded-md px-6 py-8 text-center"
          data-testid="portfolio-section-where-you-left-off-empty"
        >
          Open a board to start working.
        </p>
      ) : (
        <div
          className="bg-white border border-[var(--rule)] rounded-md px-4 py-3 flex items-start justify-between gap-3"
          data-testid="portfolio-section-where-you-left-off-row"
        >
          <div className="min-w-0 flex-1">
            <p className="text-[15px] text-[var(--ink)]">
              <span className="font-medium">{row.context_name || "Unknown company"}</span>
              {" · "}
              <span className="text-[var(--muted)]">
                {row.action || "visited"} {row.surface || "page"}
              </span>
            </p>
            {row.artefact_title && (
              <p className="text-[12.5px] text-[var(--muted)] mt-1 truncate">
                &ldquo;{row.artefact_title}&rdquo;
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={() => onResume(row.deep_link || "/app")}
            aria-label={`Continue working on ${row.artefact_title || row.context_name || "your last item"}`}
            className="text-[12.5px] text-[var(--accent)] hover:text-[var(--ink)] inline-flex items-center gap-1 shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 rounded-sm px-1"
            data-testid="portfolio-section-where-you-left-off-continue"
          >
            Continue <ArrowRight className="w-3 h-3" aria-hidden="true" />
          </button>
        </div>
      )}
    </section>
  );
}


/* ─────────────────────────────────────────────────────────────────── */
/* News — Section 3 (shared NewsStrip)                                  */
/* ─────────────────────────────────────────────────────────────────── */

function NewsSection({ onReadMore }) {
  return (
    <section data-testid="portfolio-section-news" aria-labelledby="portfolio-news-heading">
      <div className="flex items-center gap-2 mb-3">
        <Newspaper className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} aria-hidden="true" />
        <h2 className="akki-overline" id="portfolio-news-heading">The world around you</h2>
      </div>
      <div className="bg-white border border-[var(--rule)] rounded-md px-5 py-4">
        <NewsStrip
          limit={5}
          quality="executive"
          variant="compact"
          testIdRoot="portfolio-news-strip"
        />
      </div>
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={onReadMore}
          aria-label="Read more news on the full news page"
          className="text-[12.5px] text-[var(--accent)] hover:text-[var(--ink)] inline-flex items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 rounded-sm px-1 py-0.5"
          data-testid="portfolio-section-news-read-more"
        >
          Read more <ArrowRight className="w-3 h-3" aria-hidden="true" />
        </button>
      </div>
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

  // H.3 (2026-05-26) — live data wiring.
  const [metrics,       setMetrics]       = useState(null);   // null = loading
  const [boards,        setBoards]        = useState(null);
  const [lastAction,    setLastAction]    = useState(null);

  useEffect(() => {
    let alive = true;
    api.get("/me/portfolio-metrics")
      .then(({ data }) => { if (alive) setMetrics(data); })
      .catch(() => { if (alive) setMetrics({ companies: 0, signals: 0, briefings: 0, documents: 0 }); });
    api.get("/me/boards-to-watch", { params: { limit: 3 } })
      .then(({ data }) => { if (alive) setBoards(data?.items || []); })
      .catch(() => { if (alive) setBoards([]); });
    api.get("/me/last-action")
      .then(({ data }) => { if (alive) setLastAction(data); })
      .catch(() => { if (alive) setLastAction(null); });
    return () => { alive = false; };
  }, []);

  // H.2 (2026-05-26) — Card click → switchContext(cid). AuthContext
  // owns post-switch navigation; we don't navigate manually here.
  const openContext = (cid) => {
    if (!cid) return;
    switchContext(cid).catch(() => { /* AuthContext surfaces toasts */ });
  };

  // P-Cleanup B (2026-02) — defensive trim + emptiness check.
  // Pre-fix shape: `(account?.name || "there").split(" ")[0]` —
  // whitespace-only names ("   ") tripped the truthy branch and
  // rendered "Good morning, ." Locked by source-strict test in
  // backend/tests/test_p_cleanup_b_greeting_logic.py.
  // Canonical contract:
  //   • name="Sam Patel"  → firstName="Sam"
  //   • name="Yuki"        → firstName="Yuki"
  //   • name=null|""|" "   → firstName="there"
  const rawName = (account?.name || "").trim();
  const firstName = rawName ? rawName.split(/\s+/)[0] : "there";
  const greeting = timeAwareGreeting();

  // Format a metric value: number for >=0, "—" while loading.
  const _m = (key) =>
    metrics === null
      ? "—"
      : String(metrics[key] ?? 0);

  return (
    <AppShell>
      {/* P5.14.2 (2026-02) — `relative` added so the absolute-positioned
          divider below anchors to this wrapper instead of the viewport.
          Pre-fix at 1024×768 the divider's `right: calc(340 + 40 + 32)`
          resolved against the viewport, landing at x=611 which OVERLAPS
          listing.right=612 (the doubled-line bug user re-reported);
          at 1280×800 it hugged the rail (x=868) instead of sitting in
          the gap. Adding `relative` puts divider.left at
          wrap.right − 412 = 828 at 1280 and 612 at 1024, both inside
          the lg:pr-10 + gap-10 alley between the listing column and
          the rail. Closes the P5.14.1 deferred polish item. */}
      <div
        className="akki-w-medium px-8 pt-10 pb-12 flex gap-10 relative"
        data-testid="portfolio-landing"
      >
        {/* LEFT — main column. Phase P5.12.1 (2026-02) — removed the
            `lg:border-r lg:border-[var(--rule)]` rule from this
            column because the canonical edge-to-edge divider lives
            on the standalone absolute-positioned hairline below
            (data-testid `portfolio-vertical-divider`). The two
            stacked at the same X coordinate at the lg breakpoint
            (Playwright probe at 1024 viewport found
            DUPLICATE — 2 hairline hits before the fix), producing
            the visible double-line on the post-login portfolio
            home. `lg:pr-10` stays — it provides the breathing room
            between the listing content and the divider line. */}
        <div
          className="flex-1 min-w-0 space-y-10 lg:pr-10"
          data-testid="portfolio-listing-column"
          data-divider-id="portfolio-vertical-divider"
        >
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
            {/* Wave 8.3 (2026-05-27) — H1 subtext audit sentinel. Mirrors
                portfolio-subtitle text into the universal page-subtext
                testid for the Recurrence #5 CI guard. */}
            <span
              data-testid="page-subtext"
              className="sr-only"
              aria-hidden="true"
            >
              Here are your boards & operating companies.
            </span>
          </header>

          {/* 4 metric tiles — live values from /api/me/portfolio-metrics */}
          <div
            className="grid grid-cols-2 md:grid-cols-4 gap-4"
            data-testid="portfolio-metrics-row"
          >
            <MetricTile label="Companies" value={_m("companies")} />
            <MetricTile label="Signals"   value={_m("signals")} />
            <MetricTile label="Briefings" value={_m("briefings")} />
            <MetricTile label="Documents" value={_m("documents")} />
          </div>

          {/* Section 1 — Boards to watch this week (AI-composite ranking) */}
          <BoardsToWatchSection
            items={boards}
            onOpen={openContext}
          />

          {/* Section 2 — Where you left off (resume card) */}
          <WhereYouLeftOffSection
            row={lastAction}
            onResume={(href) => navigate(href)}
          />

          {/* Section 3 — The world around you (News strip) */}
          <NewsSection onReadMore={() => navigate("/app/news")} />
        </div>

        {/* ── Vertical hairline divider (Item 6 redo, 2026-02 fork-resume).
              Absolute-positioned; top:0 bottom:0 anchor to the portfolio-
              landing page wrapper's padding-box outer edge. `flex-1`
              ensures the wrapper fills <main>'s available height;
              combined with the back-slot collapse (BackButton hidden on
              /app via top-level gate), the divider touches the top
              horizontal nav rule and the trust-footer top border with
              zero gap.
              X position: rail-w 340 + gap-10 40 + px-8 right 32 = 412px
              from the wrapper's outer right edge. ── */}
        <div
          data-testid="portfolio-vertical-divider"
          data-divider-attached-to="portfolio-listing-column"
          className="hidden lg:block absolute top-0 bottom-0 w-px bg-[var(--rule)] pointer-events-none"
          style={{ right: 'calc(340px + 40px + 32px)' }}
          aria-hidden="true"
        />

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
