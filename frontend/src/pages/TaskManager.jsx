/**
 * TaskManager — Phase F (2026-05-26).
 *
 * The renamed surface. Lives at `/app/task-manager` (canonical) +
 * `/app/cycle` (backwards-compat alias dispatches to <CycleList /> in
 * App.js — this page is ONLY rendered at /app/task-manager). 3-tab
 * listing (Active / Draft / Closed) with a primary "Set up new task"
 * CTA that opens the 4-step setup wizard.
 *
 * Right-rail cards (F.2):
 *   • Ready to Compile        — relocated from CompilationRail (E.2)
 *   • At Risk                 — relocated from CompilationRail (E.2)
 *   • Follow Up Drafts for You — F.2 new card
 *
 * F.3+ (Task Drawer, Compile flow, Contributor modes, side panel
 * polish) are queued. Clicking a task card opens a placeholder
 * "Task drawer coming soon" sheet via TaskListing.
 */
import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import TaskListing from "@/components/tasks/TaskListing";
import TaskSetupWizard from "@/components/tasks/TaskSetupWizard";
import TaskDrawer from "@/components/tasks/TaskDrawer";
import DocumentDrawer from "@/components/documents/DocumentDrawer";
import CompilationReadinessSection from "@/components/cycle/CompilationReadinessSection";
import FollowUpDraftsCard from "@/components/tasks/FollowUpDraftsCard";
import RecentTaskActivityCard from "@/components/tasks/RecentTaskActivityCard";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";

export default function TaskManager() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [params, setParams] = useSearchParams();
  // F.1 — accept BOTH `task_id` and legacy `cycle_id`. task_id wins.
  // The TaskDrawer mounted below also reads `task_id` directly.
  // Initial tab from URL (defaults to active).
  const initialTab = params.get("state") || "active";
  const [tab, setTab] = useState(initialTab);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Track B Phase B2 (2026-06-04) — live count badges per tab.
  // Refreshed whenever `refreshKey` bumps (drawer-driven reload) or
  // the active context changes. No cache; one round-trip per refresh.
  const [counts, setCounts] = useState({ active: 0, draft: 0, closed: 0 });
  useEffect(() => {
    let dead = false;
    const qs = cid ? `?context_id=${encodeURIComponent(cid)}` : "";
    api.get(`/tasks/counts${qs}`)
      .then(({ data }) => { if (!dead) setCounts(data || {}); })
      .catch(() => { /* badge omission is benign */ });
    return () => { dead = true; };
  }, [cid, refreshKey]);

  // F.1 backwards-compat: if URL still carries the legacy `cycle_id`
  // param, rewrite it to the canonical `task_id` so the TaskDrawer
  // mount picks it up. This is the entire alias path — task_id wins.
  useEffect(() => {
    const legacy = params.get("cycle_id");
    if (legacy && !params.get("task_id")) {
      const next = new URLSearchParams(params);
      next.set("task_id", legacy);
      next.delete("cycle_id");
      setParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Phase P5.17 (2026-02) — origin filter (`all` / `email_akki` /
  // `manual`). Default `all`. Drives `TaskListing`'s API call.
  const initialOrigin = params.get("origin") || "all";
  const [originFilter, setOriginFilter] = useState(initialOrigin);
  useEffect(() => {
    const next = new URLSearchParams(params);
    if (originFilter === "all") next.delete("origin");
    else next.set("origin", originFilter);
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [originFilter]);

  // Keep the ?state=… param sticky as the user switches tabs.
  useEffect(() => {
    const next = new URLSearchParams(params);
    if (tab === "active") next.delete("state");
    else next.set("state", tab);
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const onTaskCreated = () => {
    setWizardOpen(false);
    setRefreshKey((k) => k + 1);
  };

  return (
    <AppShell>
      <main className="akki-w-medium py-8 flex-1 relative" data-testid="task-manager-page">
        <header className="flex items-end justify-between mb-6">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mb-1.5">
              Task Manager
            </p>
            <h1
              className="akki-serif text-[28px] text-[var(--ink)] leading-tight"
              data-testid="page-h1"
            >
              Set the work · See it through
            </h1>
            <p
              className="text-[13.5px] text-[var(--muted)] mt-1.5"
              data-testid="page-subtext"
            >
              Cycles, contributions, and the work that delivers your strategy.
            </p>
          </div>
          <Button
            onClick={() => setWizardOpen(true)}
            className="bg-[var(--oxblood)] hover:bg-[var(--oxblood-deep)] text-white rounded-sm"
            data-testid="task-manager-setup-new-task"
          >
            <Plus className="w-3.5 h-3.5 mr-1.5" /> Set up new task
          </Button>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-8">
          {/* ── Listing column. The vertical hairline divider follows
                the sign-in pattern (SignIn.jsx:73) but uses an
                absolute-positioned hairline (below) so it can touch
                the top + bottom horizontal rules with zero gap. ── */}
          <section
            className="lg:pr-8"
            data-testid="task-manager-listing-column"
            data-divider-id="task-manager-vertical-divider"
          >
            {/* 3 sort tabs: Active / Draft / Closed (no "All") */}
            <div
              className="flex gap-6 border-b border-[var(--rule)] mb-4"
              data-testid="task-manager-tabs"
            >
              {[
                { key: "active", label: "Active" },
                { key: "draft",  label: "Draft" },
                { key: "closed", label: "Closed" },
              ].map((t) => (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setTab(t.key)}
                  data-testid={`task-manager-tab-${t.key}`}
                  className={`pb-2 text-[12.5px] tracking-wide transition-colors inline-flex items-center gap-2 ${
                    tab === t.key
                      ? "text-[var(--ink)] border-b-2 border-[var(--ink)]"
                      : "text-[var(--muted)] hover:text-[var(--ink)] border-b-2 border-transparent"
                  }`}
                >
                  {t.label}
                  {/* Track B Phase B2 (2026-06-04) — live count badge.
                      Renders only when the count is known and >0 so
                      empty tabs don't carry visual noise. */}
                  {typeof counts[t.key] === "number" && counts[t.key] > 0 && (
                    <span
                      className={`inline-flex items-center justify-center min-w-[18px] h-[16px] px-1 text-[10px] font-mono rounded-full ${
                        tab === t.key
                          ? "bg-[var(--ink)] text-[var(--parchment)]"
                          : "bg-[var(--cream-deep)] text-[var(--ink)]"
                      }`}
                      data-testid={`task-manager-tab-${t.key}-badge`}
                    >
                      {counts[t.key]}
                    </span>
                  )}
                </button>
              ))}
              {/* P5.17 — origin filter dropdown (defaults All, sticky in URL). */}
              <select
                value={originFilter}
                onChange={(e) => setOriginFilter(e.target.value)}
                className="ml-auto self-center text-[11.5px] font-mono px-2 py-1 border border-[var(--rule)] rounded-sm bg-white text-[var(--ink)] hover:border-[var(--ink)]"
                data-testid="task-manager-origin-filter"
              >
                <option value="all">Origin · All</option>
                <option value="email_akki">Origin · Email Akki</option>
                <option value="manual">Origin · Manual</option>
              </select>
            </div>
            <TaskListing
              contextId={cid}
              state={tab}
              refreshKey={refreshKey}
              originFilter={originFilter}
            />
          </section>

          {/* ── Right rail ───────────────────────────────────────── */}
          <aside
            className="hidden lg:block w-[340px] shrink-0 space-y-5"
            data-testid="task-manager-right-rail"
          >
            <CompilationReadinessSection contextId={cid} layout="stack" />
            <FollowUpDraftsCard
              contextId={cid}
              refreshKey={refreshKey}
            />
            <RecentTaskActivityCard refreshKey={refreshKey} />
          </aside>
        </div>

        {/* ── Vertical hairline divider (Item 6 redo, 2026-02 fork-resume).
              Absolute-positioned inside the `relative` <main>; top:0
              and bottom:0 anchor to <main>'s padding box. <main> is
              `flex-1` inside AppShell's main flex-col, so its top edge
              flushes with the bottom of the (now-collapsed) back-slot
              = the secondary nav's horizontal rule, and its bottom
              edge flushes with the footer's top horizontal rule. The
              hairline therefore touches both rules with zero gap.
              X position: from akki-w-medium's right edge, walk left
              by (right-rail 340px + gap-8 32px) = 372px. ── */}
        <div
          className="hidden lg:block absolute top-0 bottom-0 w-px bg-[var(--rule)] pointer-events-none"
          style={{ right: 'calc(340px + 32px)' }}
          data-testid="task-manager-vertical-divider"
          aria-hidden="true"
        />
      </main>

      <TaskSetupWizard
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onCreated={onTaskCreated}
        contextId={cid}
      />
      {/* Phase F.3 (2026-05-26) — Universal Task Drawer mounts here.
          Opens automatically when the URL carries `?task_id=`. */}
      <TaskDrawer />
      {/* DocumentDrawer mount supports the F.3 stack pattern: when a
          user opens a draft from inside the Task Drawer's Drafts tab,
          the URL adds `?doc_id=…` on top of `?task_id=…` and this
          drawer opens stacked above the Task Drawer. */}
      <DocumentDrawer contextId={cid} />
    </AppShell>
  );
}
