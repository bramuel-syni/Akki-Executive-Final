/**
 * CycleList — Cycle Manager landing page (Feel pass, Patch 2 of 4).
 *
 * Layout (top → bottom):
 *   1. Quick Action Bar (always renders 4 actions; agent cycle role)
 *   2. ListingShell (title + subtitle + Add Cycle button + search +
 *      4 filter tabs + 4 sort options + paginated card grid)
 *
 * URL-backed state for q / status / sort / page so refresh + back/forward
 * preserve the user's view.
 */
import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog";
import { Plus, Loader2 } from "lucide-react";
import { toast } from "sonner";
import WorkspaceEntryGate from "@/components/transitions/WorkspaceEntryGate";
import ListingShell from "@/components/common/ListingShell";
import CycleCard from "@/components/cycle/CycleCard";
import QuickActionBar from "@/components/cycle/QuickActionBar";
import CycleSetupWizard from "@/components/cycle/CycleSetupWizard";
import CompilationReadinessSection from "@/components/cycle/CompilationReadinessSection";
import CompilationWizard from "@/components/work_studio/CompilationWizard";
import { api } from "@/lib/api";


const SUBTITLE = "Cycle Manager is where you organise your team to produce collaborative outputs. Set the agenda, assign contributors, and commission Agent Cycle to follow up and keep readiness moving until you ship.";


export default function CycleList() {
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const activeContextId = activeContext?.id;
  const [search, setSearch] = useSearchParams();

  const q = search.get("q") || "";
  const status = search.get("status") || "all";
  const sort = search.get("sort") || "recent";
  const page = parseInt(search.get("page") || "1", 10) || 1;
  const pageSize = 10;
  // T1.6 (2026-05-25) — D6 step 5: when navigating here from the
  // "Add to Cycle" attach flow, pulse-highlight the destination card.
  // The attaching component appends `?attached=<cycleId>` so we read
  // it here and forward to <CycleCard>. We clear the param ~1.5 s
  // later (the pulse window) so refresh/back doesn't re-pulse, and we
  // also force-flip to the All tab per spec D6 step 5a if the user is
  // on a different filter tab.
  const attachedCycleId = search.get("attached") || "";
  useEffect(() => {
    if (!attachedCycleId) return;
    // Clear the highlight query param after the pulse window settles.
    const t = setTimeout(() => {
      const next = new URLSearchParams(search);
      next.delete("attached");
      setSearch(next, { replace: true });
    }, 1700);
    return () => clearTimeout(t);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attachedCycleId]);
  // Force-flip to All tab on arrival from the attach flow (spec D6 5a).
  useEffect(() => {
    if (!attachedCycleId) return;
    if ((search.get("status") || "all") !== "all") {
      const next = new URLSearchParams(search);
      next.delete("status");
      setSearch(next, { replace: true });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attachedCycleId]);

  const setParam = (k, v, opts = {}) => {
    const next = new URLSearchParams(search);
    if (v === "" || v === null || v === undefined
        || (k === "status" && v === "all")
        || (k === "sort" && v === "recent")
        || (k === "page" && v === 1)) {
      next.delete(k);
    } else {
      next.set(k, String(v));
    }
    if (k !== "page" && !opts.preservePage) next.delete("page");
    setSearch(next, { replace: true });
  };

  const [loading, setLoading] = useState(false);
  const [data, setData] = useState({
    cycles: [], total: 0, total_pages: 1,
    counts_by_status: { all: 0, active: 0, draft: 0, completed: 0 },
  });
  const [addOpen, setAddOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);
  // Phase E.2 — Compilation wizard state for the relocated
  // Ready-to-Compile click handler.
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardPreselectType, setWizardPreselectType] = useState(null);
  const [wizardPreselectSourceId, setWizardPreselectSourceId] = useState(null);

  const load = async () => {
    if (!activeContextId) return;
    setLoading(true);
    try {
      const { data: d } = await api.get(`/contexts/${activeContextId}/cycles`, {
        params: {
          q: q || undefined, status, sort, page, page_size: pageSize,
        },
      });
      setData(d);
    } catch (e) { toast.error("Failed to load cycles."); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [activeContextId, q, status, sort, page]);

  // J2.3 (2026-05-25, G21 wiring fix) — cycle-door auto-opens the
  // wizard when the user arrives from FirstSession with
  // `?wizard=1`. Previously this query param was ignored; the user
  // landed on the cycle list and had to click "Add Cycle" manually,
  // which broke the spec §3 Stage 3 acceptance ("cycle door routes
  // to the T5 Cycle Setup Wizard"). Consumed-once: we strip the
  // param via replaceState so refresh doesn't re-open.
  useEffect(() => {
    if (search.get("wizard") !== "1") return;
    setAddOpen(true);
    const next = new URLSearchParams(search);
    next.delete("wizard");
    setSearch(next, { replace: true });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keyboard: `n` opens Add Cycle modal when on the cycle list.
  useEffect(() => {
    const onKey = (e) => {
      const inField = e.target && ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
      if ((e.key === "n" || e.key === "N") && !inField) {
        e.preventDefault();
        setAddOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const create = async () => {
    const t = newTitle.trim();
    if (!t) { toast.error("Title is required."); return; }
    setCreating(true);
    try {
      const { data: created } = await api.post(`/contexts/${activeContextId}/cycles`, { title: t });
      setAddOpen(false);
      setNewTitle("");
      toast.success("Cycle created.");
      navigate(created?.redirect_url || `/app/cycle/${created.id}?tab=agenda`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to create cycle.");
    } finally { setCreating(false); }
  };

  const cbs = data.counts_by_status || {};
  const filterTabs = [
    { key: "all",       label: "All",       count: cbs.all },
    { key: "active",    label: "Active",    count: cbs.active },
    { key: "draft",     label: "Draft",     count: cbs.draft },
    { key: "completed", label: "Completed", count: cbs.completed },
  ];

  // T5 (2026-05-25) — spec §4.B → C1 step 2: the primary CTA must be
  // labelled `Add Cycle`. Clicking it opens the CycleSetupWizard (C2/C3).
  // The pre-T5 button text was "Add Agenda" (a holdover from the
  // P2 internal naming) and the modal was a single-field title prompt
  // that bypassed the full setup flow.
  const addAgendaButton = (
    <Button
      size="sm"
      onClick={() => setAddOpen(true)}
      className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
      data-testid="cycle-list-add-cycle"
    >
      <Plus className="w-3.5 h-3.5 mr-1" /> Add Cycle
    </Button>
  );

  const emptyState = (
    <div
      className="border border-dashed border-[var(--rule)] bg-[var(--parchment)] rounded-sm px-6 py-12 text-center"
      data-testid="cycle-list-empty"
    >
      <p className="akki-serif text-[16px] text-[var(--ink)]">No cycles yet.</p>
      <p className="akki-meta text-[12.5px] mt-2 max-w-prose mx-auto">
        Use a Quick Action above to start with a structured template, or
        click <span className="font-medium">Add Cycle</span> on the right.
      </p>
    </div>
  );

  return (
    <AppShell>
      <WorkspaceEntryGate workspace="cycle">
        <div className="akki-w-medium akki-vmedium" data-testid="cycle-list-page">

          {/* Chunk 17 (QA-2026-05-16-014, 2026-05-21) — explicit
              spacing between the top menu (AppShell topbar) and the
              Agent Cycle Quick Actions card. Previously zero gap so
              the QuickActionBar sat flush against the topbar bottom
              border, creating visual crowding per the QA author. */}
          <div className="pt-6" data-testid="cycle-list-quickactions-spacer" />

          <QuickActionBar contextId={activeContextId} />

          <ListingShell
            testId="cycle-listing"
            title="Cycle Manager"
            subtitle={SUBTITLE}
            searchValue={q}
            onSearchChange={(v) => setParam("q", v)}
            searchPlaceholder="Search agendas by title…"
            controlsRight={addAgendaButton}
            filterTabs={filterTabs}
            activeFilterKey={status}
            onFilterChange={(k) => setParam("status", k)}
            sortOptions={[
              { key: "recent", label: "Most recent" },
              { key: "oldest", label: "Oldest" },
              { key: "alpha",  label: "A → Z" },
              { key: "status", label: "Status" },
            ]}
            activeSortKey={sort}
            onSortChange={(k) => setParam("sort", k)}
            pageSize={pageSize}
            page={page}
            totalCount={data.total || 0}
            onPageChange={(n) => setParam("page", n, { preservePage: true })}
            isLoading={loading}
            emptyState={emptyState}
          >
            <div
              className="flex flex-col gap-3"
              data-testid="cycle-list-grid"
            >
              {(data.cycles || []).map((c) => (
                <CycleCard
                  key={c.id}
                  cycle={c}
                  highlight={attachedCycleId && c.id === attachedCycleId}
                />
              ))}
            </div>
          </ListingShell>

          <AlertDialog open={false} onOpenChange={() => {}}>
            <AlertDialogContent />
          </AlertDialog>

          {/* T5 (2026-05-25) — Cycle Setup Wizard replaces the prior
              single-input AlertDialog. Spec §4.B → C2 + C3 with G4
              field-validation + G5 email-regex + dupe-block invariants.
              On finish, the wizard creates the cycle via the existing
              POST /contexts/{cid}/cycles endpoint then routes the
              user into the new cycle's page. */}
          <CycleSetupWizard
            open={addOpen}
            onOpenChange={setAddOpen}
            contextId={activeContextId}
            onCycleCreated={({ id }) => {
              navigate(`/app/cycle/${id}?tab=agenda&attached=${encodeURIComponent(id)}`);
            }}
          />

          {/* Phase E.2 (2026-05-26) — Ready-to-Compile + At-Risk cards
              relocated from the Work Studio rail (CompilationRail.jsx)
              to Cycle Manager per the Phase E brief. The new section
              shares CompilationWizard with Work Studio for the
              "Compile" click handler. The T5 side panel below remains
              untouched (it tracks cycle-status counters, a separate
              semantic surface). */}
          <CompilationReadinessSection
            contextId={activeContextId}
            onCompile={(opts) => {
              setWizardPreselectType(opts?.artefactType || null);
              setWizardPreselectSourceId(opts?.sourceId || null);
              setWizardOpen(true);
            }}
          />
          <CompilationWizard
            open={wizardOpen}
            onOpenChange={setWizardOpen}
            contextId={activeContextId}
            preselectArtefactType={wizardPreselectType}
            preselectSourceId={wizardPreselectSourceId}
            onCompiled={() => setWizardOpen(false)}
          />

          {/* T5 (2026-05-25) — C6 side panel. Two cards: Ready to
              Compile + Drafts Waiting for You. Counts come from
              existing cycle endpoints; "View More" links route to the
              C7 Draft Journal and C8 Ready Journal respectively. */}
          <aside
            className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4"
            data-testid="cycle-list-side-panel"
          >
            <div
              className="border border-[var(--rule)] rounded-sm bg-white px-4 py-3"
              data-testid="cycle-list-side-panel-ready"
            >
              <div className="flex items-center justify-between mb-2">
                <p className="text-[12px] uppercase tracking-[0.16em] font-mono text-[var(--ink)]">
                  Ready to Compile
                </p>
                <span
                  className="text-[12px] text-[var(--muted)] font-mono"
                  data-testid="cycle-list-side-panel-ready-count"
                >
                  {cbs.active || 0}
                </span>
              </div>
              <p className="text-[12px] text-[var(--muted)]" data-testid="cycle-list-side-panel-ready-empty">
                Active cycles meeting your readiness target will surface here.
              </p>
              <button
                type="button"
                onClick={() => navigate("/app/cycle/ready")}
                className="text-[12px] text-[var(--accent)] hover:underline underline-offset-2 mt-2"
                data-testid="cycle-list-side-panel-ready-view-more"
              >
                View More →
              </button>
            </div>
            <div
              className="border border-[var(--rule)] rounded-sm bg-white px-4 py-3"
              data-testid="cycle-list-side-panel-drafts"
            >
              <div className="flex items-center justify-between mb-2">
                <p className="text-[12px] uppercase tracking-[0.16em] font-mono text-[var(--ink)]">
                  Drafts Waiting for You
                </p>
                <span
                  className="text-[12px] text-[var(--muted)] font-mono"
                  data-testid="cycle-list-side-panel-drafts-count"
                >
                  {cbs.draft || 0}
                </span>
              </div>
              <p className="text-[12px] text-[var(--muted)]" data-testid="cycle-list-side-panel-drafts-empty">
                Follow-up emails drafted by the agent cycle awaiting your approval.
              </p>
              <button
                type="button"
                onClick={() => navigate("/app/cycle/drafts")}
                className="text-[12px] text-[var(--accent)] hover:underline underline-offset-2 mt-2"
                data-testid="cycle-list-side-panel-drafts-view-more"
              >
                View More →
              </button>
            </div>
          </aside>
        </div>
      </WorkspaceEntryGate>
    </AppShell>
  );
}
