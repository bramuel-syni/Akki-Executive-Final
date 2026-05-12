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

  // Patch 2B.1 — "Add Cycle" → "+ Add Agenda". UI label only; backend stays
  // on `cycles`. Primary parchment/ink style (no oxblood — reserved for
  // severity). Mounted in the search-bar row via ListingShell's
  // `controlsRight` slot.
  const addAgendaButton = (
    <Button
      size="sm"
      onClick={() => setAddOpen(true)}
      className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
      data-testid="cycle-list-add-cycle"
    >
      <Plus className="w-3.5 h-3.5 mr-1" /> Add Agenda
    </Button>
  );

  const emptyState = (
    <div
      className="border border-dashed border-[var(--rule)] bg-[var(--parchment)] rounded-sm px-6 py-12 text-center"
      data-testid="cycle-list-empty"
    >
      <p className="akki-serif text-[16px] text-[var(--ink)]">No agendas yet.</p>
      <p className="akki-meta text-[12.5px] mt-2 max-w-prose mx-auto">
        Use a Quick Action above to start with a structured template, or add a new agenda from the top-right of the list.
      </p>
    </div>
  );

  return (
    <AppShell>
      <WorkspaceEntryGate workspace="cycle">
        <div className="akki-w-medium akki-vmedium" data-testid="cycle-list-page">

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
                <CycleCard key={c.id} cycle={c} />
              ))}
            </div>
          </ListingShell>

          <AlertDialog open={addOpen} onOpenChange={setAddOpen}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle className="akki-serif">Start a new cycle</AlertDialogTitle>
                <AlertDialogDescription className="akki-meta">
                  Give it a name. You can rename, add agenda items, and activate from inside.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <Input
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && newTitle.trim()) create(); }}
                placeholder="e.g. Q1 2026 Board Cycle"
                className="rounded-sm text-[13.5px]"
                data-testid="cycle-list-new-title"
                autoFocus
              />
              <AlertDialogFooter>
                <AlertDialogCancel disabled={creating} data-testid="cycle-list-new-cancel">Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={(e) => { e.preventDefault(); create(); }}
                  disabled={creating || !newTitle.trim()}
                  className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
                  data-testid="cycle-list-new-create"
                >
                  {creating ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null}
                  Create
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </WorkspaceEntryGate>
    </AppShell>
  );
}
