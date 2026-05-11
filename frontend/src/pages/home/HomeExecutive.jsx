/**
 * HomeExecutive — Phase K.1 self-contained executive role shell.
 *
 * Phase K.1 retired `pages/ExecutiveHomeShell.jsx` (the pre-Phase-5
 * "LegacyAppHome" monolith — 579 ll. with the `?home=v2` opt-in
 * toggle, a duplicate first-session gate, and 4 sandbox-only widgets
 * superseded by the Sandbox v2 surface at /sandbox). This file is the
 * sole executive home now, mirroring the brand-aligned dense layout of
 * `HomeNed.jsx` / `HomeDual.jsx`.
 *
 * What survives from the legacy shell:
 *   - The "Continue onboarding" card (Phase B.6) when
 *     `activeContext.progress_state.onboarding_completed === false`.
 *     This is the only piece not already covered elsewhere.
 *   - The compact `WorkStudioPreview` band at the top (already a
 *     local component).
 *
 * What was dropped — explicitly redundant with shipped surfaces:
 *   - `?home=v2` toggle           — single canonical home now
 *   - Duplicate first-session gate — handled by FirstSessionGuard in App.js
 *   - SandboxTutorial / SandboxPackDrop / SandboxSampleDoc / ObjectiveCheck
 *                                  — superseded by /sandbox (Sandbox v2)
 *   - DraggableHomeBoard          — replaced by deterministic role layout
 *   - ContextChooser              — moved to PortfolioRail in the shell
 *   - WorkflowsHub / InSummaryTiles / NextBestActionCard / RecentActivity
 *                                  — covered by Cycle Manager Overview,
 *                                    Activity page, Work Studio respectively
 *
 * Calibri sans for body, Georgia for the H1, accent only twice on the
 * page (Executive overline + Work Studio open arrow) per UI/UX brief.
 */
import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import CycleStrip from "@/components/cycle/CycleStrip";
import useIsMobile from "@/hooks/useIsMobile";
import { Button } from "@/components/ui/button";
import {
  Briefcase,
  ScrollText,
  Presentation,
  FileText,
  ArrowRight,
  Activity,
  Inbox,
  Sparkles,
  Clock,
} from "lucide-react";
import AddDocumentCard from "@/components/home/AddDocumentCard";
import AllDocumentsButton from "@/components/home/AllDocumentsButton";
import ExcoTeamsCard from "@/components/home/ExcoTeamsCard";

function greeting(name) {
  const h = new Date().getHours();
  const g = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  return `${g}, ${name}.`;
}

/**
 * Compact Work Studio preview — mounts at the very top of the executive
 * home as a single, dense row. Click any segment to land on Work Studio
 * with the right tab active. Only renders when there is something
 * in flight.
 */
function WorkStudioPreview({ contextId }) {
  const [counts, setCounts] = useState({ briefings: 0, decks: 0, reports: 0 });
  useEffect(() => {
    if (!contextId) return undefined;
    let dead = false;
    Promise.all([
      api
        .get(`/contexts/${contextId}/briefings`)
        .then(({ data }) => (data?.items || data?.briefings || []).filter((b) => (b.status || "draft") !== "sent").length)
        .catch(() => 0),
      api
        .get(`/contexts/${contextId}/decks`)
        .then(({ data }) => (data?.items || data?.decks || []).filter((d) => (d.status || "draft") !== "sent").length)
        .catch(() => 0),
      api
        .get(`/contexts/${contextId}/cycle/reports/inbox`)
        .then(({ data }) => {
          const items = data?.reports || data?.items || [];
          return items.filter((r) => {
            const s = (r.status || "draft").toLowerCase();
            return s !== "sent" && s !== "finalised" && s !== "finalized";
          }).length;
        })
        .catch(() => 0),
    ]).then(([b, d, r]) => {
      if (!dead) setCounts({ briefings: b, decks: d, reports: r });
    });
    return () => {
      dead = true;
    };
  }, [contextId]);

  const total = counts.briefings + counts.decks + counts.reports;
  if (total === 0) return null;

  return (
    <div className="mb-6" data-testid="home-exec-work-studio-preview">
      <Link
        to="/app/work-studio"
        className="block px-5 py-3 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors"
      >
        <div className="flex items-center gap-6 flex-wrap">
          <p className="akki-overline text-[var(--muted)] flex items-center gap-2">
            <Briefcase className="w-3 h-3" /> Work Studio · in flight
          </p>
          <div className="flex items-center gap-5 text-[13px] text-[var(--ink)]">
            <span className="inline-flex items-center gap-1.5">
              <ScrollText className="w-3.5 h-3.5 text-[var(--deep)]" strokeWidth={1.7} />{" "}
              {counts.briefings} briefings
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Presentation className="w-3.5 h-3.5 text-[var(--deep)]" strokeWidth={1.7} />{" "}
              {counts.decks} decks
            </span>
            <span className="inline-flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-[var(--deep)]" strokeWidth={1.7} />{" "}
              {counts.reports} reports
            </span>
          </div>
          <span className="ml-auto text-[12px] text-[var(--accent)] inline-flex items-center gap-1">
            Open Work Studio <ArrowRight className="w-3 h-3" />
          </span>
        </div>
      </Link>
    </div>
  );
}

/**
 * Continue-onboarding card — Phase B.6 carry-over, fixed in the
 * post-Phase-D bugfix.
 *
 * Gate: account-level `first_session.status`. We only render this
 * card when the account's first-session journey is still open
 * (i.e. NOT "completed" and NOT "skipped"). The legacy gate on
 * `activeContext.progress_state.onboarding_completed` is retired —
 * it was broken (the field is rarely written) and FirstSessionGuard
 * already covers brand-new accounts.
 *
 * Click handler uses `useNavigate()` directly on the button rather
 * than wrapping a <Button> inside a <Link>. The latter renders an
 * anchor wrapping a button, which is invalid HTML and causes some
 * browsers to drop the navigation when the inner button claims the
 * click — that was the "click does nothing" symptom users reported.
 */
function ContinueOnboardingCard({ account }) {
  const navigate = useNavigate();
  const status = account?.first_session?.status;
  if (status === "completed" || status === "skipped") return null;
  return (
    <div
      className="mb-8 bg-white border border-[var(--rule)] rounded-lg p-8 relative overflow-hidden"
      data-testid="home-exec-continue-onboarding"
    >
      <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)]" />
      <p className="akki-overline mb-3">Next · 7 minutes</p>
      <h2 className="akki-serif text-[22px] mb-3 text-[var(--ink)] leading-snug">
        Finish your profile to start receiving signals.
      </h2>
      <p className="akki-serif text-[14.5px] text-[var(--deep)] leading-relaxed mb-6 max-w-2xl">
        Seven role-specific questions establish your profile — the foundation for every
        signal, briefing, and lens session AKKI runs on your behalf.
      </p>
      <Button
        onClick={() => navigate("/app/first-session")}
        className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-10 px-5 font-medium"
        data-testid="start-onboarding-btn"
        aria-label="Continue onboarding"
      >
        Continue onboarding <ArrowRight className="w-4 h-4 ml-2" />
      </Button>
    </div>
  );
}

export default function HomeExecutive() {
  const { account, activeContext } = useAuth();
  const cid = activeContext?.id;
  const isMobile = useIsMobile();
  const firstName = (account?.name || "there").split(" ")[0];
  const isAdmin =
    activeContext?.my_sub_role === "admin" ||
    activeContext?.owner_account_id === account?.id;

  return (
    <AppShell>
      <div className="akki-w-medium px-8 py-10" data-testid="home-executive">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Briefcase className="w-3 h-3" /> Executive home · {activeContext?.name || "—"}
        </p>
        <h1 className="akki-greeting mb-2">{greeting(firstName)}</h1>
        <p className="akki-meta max-w-2xl mb-6">
          The five things that move between meetings: in-flight briefings and decks,
          this week's submissions, pending action items, the next cycle phase.
        </p>

        {/* Phase E (D-006) — Document Journal entry-point hoisted into
            the page-title band so it's visible above the fold at
            1920×1100 without scrolling. */}
        <div className="mb-8" data-testid="home-exec-all-documents-strip">
          <AllDocumentsButton />
        </div>

        <ContinueOnboardingCard account={account} />
        <WorkStudioPreview contextId={cid} />

        {cid && <CycleStrip contextId={cid} isMobile={isMobile} />}

        {/* Phase M.1 — "Running the business" Quick Actions strip. The
            "Add a document" card is the first thing the user sees so
            uploading a board pack is one click from Home. */}
        <section className="mt-8" data-testid="home-exec-running-the-business">
          <h2 className="akki-serif text-[20px] text-[var(--ink)] inline-flex items-center gap-2 mb-3">
            <Briefcase className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Running the business
          </h2>
          <div className="grid sm:grid-cols-2 gap-4">
            <AddDocumentCard />
          </div>
        </section>

        {/* Two-column quick-link grid — every card lands on a real
            shipped surface; nothing is a placeholder. */}
        <div className="grid lg:grid-cols-2 gap-6 mt-8" data-testid="home-exec-grid">
          <Link
            to="/app/cycle?tab=overview"
            className="block p-6 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors"
            data-testid="home-exec-cycle-overview"
          >
            <p className="akki-overline mb-2 text-[var(--muted)]">Cycle Manager · Overview</p>
            <h2 className="akki-serif text-[19px] text-[var(--ink)] mb-2 leading-snug inline-flex items-center gap-2">
              <Activity className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> This
              week's submissions and the cycle you're driving
            </h2>
            <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mb-3">
              Reportee submissions, the question bank, and the report draft sitting on
              your desk for {activeContext?.name || "this company"}.
            </p>
            <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">
              Open Cycle Manager <ArrowRight className="w-3 h-3" />
            </span>
          </Link>

          <Link
            to="/app/cycle?tab=actions"
            className="block p-6 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors"
            data-testid="home-exec-actions"
          >
            <p className="akki-overline mb-2 text-[var(--muted)]">Pending action items</p>
            <h2 className="akki-serif text-[19px] text-[var(--ink)] mb-2 leading-snug inline-flex items-center gap-2">
              <Inbox className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Signal
              actions and submissions still open
            </h2>
            <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mb-3">
              Items raised at the last meeting, in-flight plays, and reportee replies
              waiting on you.
            </p>
            <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">
              Open Actions <ArrowRight className="w-3 h-3" />
            </span>
          </Link>

          <Link
            to="/app/cycle?tab=signals"
            className="block p-6 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors"
            data-testid="home-exec-signals"
          >
            <p className="akki-overline mb-2 text-[var(--muted)]">Signals on your desk</p>
            <h2 className="akki-serif text-[19px] text-[var(--ink)] mb-2 leading-snug inline-flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> What's
              drifted in the last pack
            </h2>
            <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mb-3">
              High-confidence signals AKKI surfaced from your latest documents, with
              citations back to the source paragraph.
            </p>
            <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">
              Open Signals <ArrowRight className="w-3 h-3" />
            </span>
          </Link>

          <Link
            to="/app/activity"
            className="block p-6 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors"
            data-testid="home-exec-activity"
          >
            <p className="akki-overline mb-2 text-[var(--muted)]">Recent activity</p>
            <h2 className="akki-serif text-[19px] text-[var(--ink)] mb-2 leading-snug inline-flex items-center gap-2">
              <Clock className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Everything
              in the last 14 days
            </h2>
            <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mb-3">
              Documents, signals, briefings, decks, shares, comments — one chronological
              feed across {activeContext?.name || "this company"}.
            </p>
            <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">
              Open Activity <ArrowRight className="w-3 h-3" />
            </span>
          </Link>
        </div>

        {/* HOME sprint (2026-05-12) — ExCo teams grouping function. */}
        <ExcoTeamsCard contextId={cid} isAdmin={isAdmin} />
      </div>
    </AppShell>
  );
}
