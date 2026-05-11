/**
 * CycleList — the landing page for Cycle Manager v2.
 *
 * Surfaces: header + Add Cycle CTA, search bar (real-time filter),
 * sort dropdown, paginated card grid (12/page). Preserves search +
 * sort across pagination.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
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
import { Plus, Search, Loader2, ChevronLeft, ChevronRight, ArrowUpDown } from "lucide-react";
import { toast } from "sonner";
import WorkspaceEntryGate from "@/components/transitions/WorkspaceEntryGate";
import CycleCard from "@/components/cycle/CycleCard";
import { createCycle, listCycles } from "@/lib/cycleApi";


const SORTS = [
  { id: "recent", label: "Most recent" },
  { id: "oldest", label: "Oldest first" },
  { id: "alpha",  label: "Alphabetical A–Z" },
  { id: "status", label: "Status (Active > Draft > Completed)" },
];


export default function CycleList() {
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const activeContextId = activeContext?.id;
  const [search, setSearch] = useSearchParams();

  // URL-backed state so refresh + back-button preserves the view.
  const q = search.get("q") || "";
  const sort = search.get("sort") || "recent";
  const page = parseInt(search.get("page") || "1", 10) || 1;
  const setParam = (k, v) => {
    const next = new URLSearchParams(search);
    if (v === "" || v === null || v === undefined) next.delete(k);
    else next.set(k, String(v));
    if (k !== "page") next.delete("page");  // reset page on search/sort change
    setSearch(next, { replace: true });
  };

  const [loading, setLoading] = useState(false);
  const [data, setData] = useState({ cycles: [], total: 0, total_pages: 1 });
  const [addOpen, setAddOpen] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const searchRef = useRef(null);
  const debounce = useRef(null);

  const load = async () => {
    if (!activeContextId) return;
    setLoading(true);
    try {
      const d = await listCycles(activeContextId, { q, sort, page, page_size: 12 });
      setData(d);
    } catch (e) { toast.error("Failed to load cycles."); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [activeContextId, q, sort, page]);

  // Real-time search with 250ms debounce
  const onSearchChange = (val) => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => setParam("q", val), 250);
  };

  // Keyboard shortcut: `c` opens new cycle dialog
  useEffect(() => {
    const onKey = (e) => {
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
      if (e.key === "c" || e.key === "C") setAddOpen(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const create = async () => {
    const title = newTitle.trim();
    if (!title) { toast.error("Title is required."); return; }
    setCreating(true);
    try {
      const created = await createCycle(activeContextId, { title });
      setAddOpen(false);
      setNewTitle("");
      toast.success("Cycle created.");
      navigate(created.redirect_url || `/app/cycle/${created.id}?tab=agenda`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to create cycle.");
    } finally { setCreating(false); }
  };

  const showPagination = (data.total || 0) > 12;
  const canPrev = page > 1;
  const canNext = page < (data.total_pages || 1);

  return (
    <AppShell>
      <WorkspaceEntryGate workspace="cycle">
        <div className="akki-w-medium akki-vmedium" data-testid="cycle-list-page">
          <header className="flex items-end justify-between gap-4 mb-6">
            <div>
              <p className="akki-meta text-[11px] uppercase tracking-[0.16em]">Cycle Manager</p>
              <h1 className="akki-serif text-[28px] text-[var(--ink)] mt-1">
                Your reporting cycles.
              </h1>
            </div>
            <Button
              size="sm"
              onClick={() => setAddOpen(true)}
              className="bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
              data-testid="cycle-list-add-cycle"
            >
              <Plus className="w-3.5 h-3.5 mr-1" /> Add Cycle
            </Button>
          </header>

          {/* Search + sort row */}
          <div className="flex items-center gap-3 mb-5">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" />
              <Input
                ref={searchRef}
                placeholder="Search by title…"
                defaultValue={q}
                onChange={(e) => onSearchChange(e.target.value)}
                className="rounded-sm pl-9 text-[13.5px]"
                data-testid="cycle-list-search"
              />
            </div>
            <div className="relative">
              <ArrowUpDown className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)] pointer-events-none" />
              <select
                value={sort}
                onChange={(e) => setParam("sort", e.target.value)}
                className="text-[12.5px] font-mono uppercase tracking-[0.08em] pl-7 pr-7 py-2 border border-[var(--rule)] rounded-sm bg-white text-[var(--ink)]"
                data-testid="cycle-list-sort"
              >
                {SORTS.map((s) => (
                  <option key={s.id} value={s.id}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>

          {loading ? (
            <div
              className="flex items-center justify-center py-16 text-[var(--muted)]"
              data-testid="cycle-list-loading"
            >
              <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Loading cycles…
            </div>
          ) : (data.cycles || []).length === 0 ? (
            <div
              className="border border-dashed border-[var(--rule)] bg-[var(--parchment)] rounded-sm px-6 py-12 text-center"
              data-testid="cycle-list-empty"
            >
              <p className="akki-serif text-[16px] text-[var(--ink)]">No cycles yet.</p>
              <p className="akki-meta text-[12.5px] mt-2 max-w-prose mx-auto">
                Start a draft cycle, add agenda items and team members, then activate it when ready.
              </p>
              <Button
                size="sm"
                onClick={() => setAddOpen(true)}
                className="mt-4 bg-[color:var(--oxblood)] hover:bg-[color:var(--oxblood-deep)] text-white"
                data-testid="cycle-list-empty-add"
              >
                <Plus className="w-3.5 h-3.5 mr-1" /> Start your first cycle
              </Button>
            </div>
          ) : (
            <div
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3"
              data-testid="cycle-list-grid"
            >
              {data.cycles.map((c) => (
                <CycleCard key={c.id} cycle={c} contextId={activeContextId} />
              ))}
            </div>
          )}

          {showPagination && (
            <div
              className="flex items-center justify-between mt-6 pt-4 border-t border-[var(--rule)]"
              data-testid="cycle-list-pagination"
            >
              <p className="akki-meta text-[11.5px] font-mono">
                Page {page} of {data.total_pages} · {data.total} total
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm" variant="outline"
                  disabled={!canPrev}
                  onClick={() => setParam("page", page - 1)}
                  className="text-[12.5px]"
                  data-testid="cycle-list-prev"
                >
                  <ChevronLeft className="w-3.5 h-3.5 mr-1" /> Previous
                </Button>
                <Button
                  size="sm" variant="outline"
                  disabled={!canNext}
                  onClick={() => setParam("page", page + 1)}
                  className="text-[12.5px]"
                  data-testid="cycle-list-next"
                >
                  Next <ChevronRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
            </div>
          )}

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
