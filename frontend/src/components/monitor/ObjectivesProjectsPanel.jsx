/**
 * ObjectivesProjectsPanel — Patch 5 Monitor v2.
 *
 * Lists Objectives or Projects for the active context.
 *
 *   • ListingShell foundation (Patch 1), 5/page, search, R/A/G filter tabs.
 *   • Pulse-style row spacing (more breathing room than Work Studio rows).
 *   • Click a row → opens a right-side drawer with details + timeline
 *     visual (vertical timeline of `timeline_events`).
 *   • Auto-suggest CTA — surfaces candidate items derived from existing
 *     cycles/Solva sessions; user can accept-as-objective.
 *
 * v7 palette only.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import {
  ArrowRight, Plus, Sparkles, TrendingUp, TrendingDown, Minus,
  Target, Layers, Loader2, X as XIcon,
} from "lucide-react";
import ListingShell from "@/components/common/ListingShell";


const RAG_COLOUR = {
  green: "bg-emerald-500",   // standard semantic — non-palette ok for the dot only
  amber: "bg-amber-500",
  red:   "bg-[color:var(--oxblood)]",  // severity — oxblood explicitly allowed
  // QA-2026-05-16-047 (2026-05-18) — extended status vocabulary.
  not_started: "bg-slate-400",
  achieved:    "bg-sky-600",
};
const RAG_LABEL = {
  green: "On Track",
  amber: "At Risk",
  red:   "Off Track",
  // QA-2026-05-16-047 (2026-05-18) — labels for the new statuses.
  not_started: "Not Started",
  achieved:    "Achieved",
};
const TREND_ICON = { up: TrendingUp, flat: Minus, down: TrendingDown };


function relTime(iso) {
  if (!iso) return "—";
  try {
    const ms = Date.now() - new Date(iso).getTime();
    const days = Math.floor(ms / (24 * 60 * 60 * 1000));
    if (days < 1) return "today";
    if (days < 30) return `${days}d ago`;
    const months = Math.floor(days / 30);
    if (months < 12) return `${months}mo ago`;
    return `${Math.floor(months / 12)}y ago`;
  } catch { return "—"; }
}


function ItemRow({ row, onOpen }) {
  const Trend = TREND_ICON[row.trend] || Minus;
  return (
    <button
      type="button"
      onClick={() => onOpen(row)}
      className="w-full text-left border border-[var(--rule)] rounded-sm bg-white px-5 py-4 hover:border-[var(--ink)] transition-colors"
      data-testid={`obj-row-${row.id}`}
    >
      <div className="flex items-center gap-4">
        <span
          className={`w-2.5 h-2.5 rounded-full ${RAG_COLOUR[row.rag_status] || "bg-[var(--muted)]"}`}
          aria-label={RAG_LABEL[row.rag_status] || row.rag_status}
          data-testid={`obj-row-rag-${row.id}`}
        />
        <div className="flex-1 min-w-0">
          <p className="akki-serif text-[15.5px] text-[var(--ink)] truncate" data-testid={`obj-row-title-${row.id}`}>
            {row.title}
          </p>
          <p className="text-[11.5px] text-[var(--muted)] font-mono mt-1">
            {RAG_LABEL[row.rag_status] || row.rag_status} · updated {relTime(row.updated_at || row.created_at)} · source {row.source}
          </p>
        </div>
        <div className="hidden sm:flex items-baseline gap-1.5 shrink-0">
          <span className="font-mono text-[16px] text-[var(--ink)] tabular-nums">{row.score ?? 0}</span>
          <span className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">Score</span>
          <Trend className="w-3.5 h-3.5 text-[var(--deep)] ml-2" strokeWidth={1.7} />
        </div>
        <ArrowRight className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" />
      </div>
    </button>
  );
}


function ItemDrawer({ row, onClose, onAssessed }) {
  const open = !!row;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [assessment, setAssessment] = useState(null);
  // QA-2026-05-16-047 (2026-05-18) — separate "no relevant data" state
  // so the drawer can render the verbatim copy + Document Journal link
  // instead of a generic error.
  const [noData, setNoData] = useState(null); // { message } | null

  // Reset assessment state whenever a different row is opened.
  React.useEffect(() => {
    setAssessment(row?.last_akki_assessment || null);
    setError(null);
    setNoData(null);
  }, [row?.id]);

  const updateGoal = async () => {
    if (!row?.id || !row?.context_id || !row?.kind) return;
    setBusy(true); setError(null); setNoData(null);
    try {
      const r = await api.post(
        `/contexts/${row.context_id}/monitor/${row.kind}/${row.id}/update-status`,
        {},
      );
      // QA-2026-05-16-047 — backend returns `{no_data: true, message}`
      // when there are no signals or documents to assess against.
      if (r.data?.no_data) {
        setNoData({ message: r.data.message || "" });
        setAssessment(null);
      } else {
        setAssessment(r.data?.assessment || null);
        if (onAssessed) onAssessed(r.data);
      }
    } catch (e) {
      setError(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose && onClose()}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[420px] sm:w-[420px] overflow-y-auto bg-[var(--paper)] p-0"
        data-testid="obj-drawer"
      >
        <div className="px-6 py-5 border-b border-[var(--rule)] flex items-start gap-3 sticky top-0 bg-[var(--paper)] z-10">
          <div className="min-w-0 flex-1">
            <SheetHeader className="text-left">
              <SheetTitle className="akki-serif text-[18px] text-[var(--ink)]">{row?.title}</SheetTitle>
              <SheetDescription className="text-[12px] text-[var(--muted)]">
                {row?.kind === "project" ? "Project" : "Objective"} · source {row?.source}
              </SheetDescription>
            </SheetHeader>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--muted)] hover:text-[var(--ink)] p-1"
            aria-label="Close drawer"
            data-testid="obj-drawer-close"
          >
            <XIcon className="w-4 h-4" />
          </button>
        </div>
        <div className="px-6 py-5 space-y-5">
          <div className="grid grid-cols-3 gap-3 border border-[var(--rule)] rounded-sm bg-white px-3 py-3">
            <div>
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Status</p>
              <p className="text-[14px] akki-serif text-[var(--ink)]" data-testid="obj-drawer-rag">{RAG_LABEL[row?.rag_status]}</p>
            </div>
            <div>
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Score</p>
              <p className="text-[14px] akki-serif text-[var(--ink)]">{row?.score ?? 0}</p>
            </div>
            <div>
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Trend</p>
              <p className="text-[14px] akki-serif text-[var(--ink)]">{row?.trend || "flat"}</p>
            </div>
          </div>

          {/* Phase F (2026-05-16) — "Update goal" mechanic. Non-overridable; */}
          {/* status is set by Akki from engine signals + recent docs.       */}
          <div className="border border-[var(--rule)] rounded-sm bg-white px-3 py-3" data-testid="obj-drawer-update-goal">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">Akki status</p>
                <p className="text-[12px] text-[var(--muted)]">Reads recent engine signals + documents.</p>
              </div>
              <Button
                size="sm"
                variant="outline"
                onClick={updateGoal}
                disabled={busy}
                data-testid="obj-drawer-update-goal-btn"
              >
                {busy ? "Analysing…" : "Update goal"}
              </Button>
            </div>
            {error && (
              <p className="mt-2 text-[12px] text-rose-700" data-testid="obj-drawer-update-goal-error">{error}</p>
            )}
            {/* QA-2026-05-16-047 (2026-05-18) — "no relevant data" path. */}
            {noData && (
              <div
                className="mt-3 text-[12.5px] text-[var(--ink)] space-y-2"
                data-testid="obj-drawer-no-data"
              >
                <p>{noData.message}</p>
                <p>
                  <Link
                    to="/app/workspace"
                    className="text-[12.5px] text-[var(--accent)] hover:underline underline-offset-2"
                    data-testid="obj-drawer-no-data-doc-journal-link"
                  >
                    Open Document Journal →
                  </Link>
                </p>
              </div>
            )}
            {assessment && (
              <div className="mt-3 text-[12.5px] text-[var(--ink)] space-y-2" data-testid="obj-drawer-assessment">
                <p>
                  <span className="font-mono uppercase tracking-[0.16em] text-[10.5px] text-[var(--muted)]">Rationale · </span>
                  <span data-testid="obj-drawer-assessment-rationale">{assessment.rationale}</span>
                </p>
                <p className="text-[11px] text-[var(--muted)]">
                  Confidence {Math.round((assessment.confidence || 0) * 100)}% · audit{" "}
                  <code className="font-mono text-[10.5px]" data-testid="obj-drawer-assessment-audit-id">{assessment.audit_id}</code>
                </p>
                {((assessment.supporting_signal_ids || []).length > 0) && (
                  <p className="text-[11px]">
                    <span className="text-[var(--muted)]">Signals: </span>
                    <span data-testid="obj-drawer-assessment-signals" className="font-mono">{(assessment.supporting_signal_ids || []).join(", ")}</span>
                  </p>
                )}
                {((assessment.supporting_doc_ids || []).length > 0) && (
                  <p className="text-[11px]">
                    <span className="text-[var(--muted)]">Docs: </span>
                    <span data-testid="obj-drawer-assessment-docs" className="font-mono">{(assessment.supporting_doc_ids || []).join(", ")}</span>
                  </p>
                )}
              </div>
            )}
          </div>

          {row?.description && (
            <div>
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] mb-2">Description</p>
              <p className="akki-serif text-[13.5px] text-[var(--ink)] leading-snug whitespace-pre-wrap">{row.description}</p>
            </div>
          )}
          <div data-testid="obj-drawer-timeline">
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] mb-2">Timeline</p>
            {(!row?.timeline_events || row.timeline_events.length === 0) ? (
              <p className="text-[12.5px] text-[var(--muted)] italic">No timeline events yet.</p>
            ) : (
              <ol className="relative border-l border-[var(--rule)] ml-2 pl-4 space-y-3">
                {[...row.timeline_events].reverse().map((ev, i) => (
                  <li key={i} className="text-[12.5px]" data-testid={`obj-drawer-timeline-event-${i}`}>
                    <span className="absolute -left-[5px] w-2 h-2 rounded-full bg-[var(--ink)]" />
                    <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)]">
                      {relTime(ev.ts)} · {ev.kind}
                    </p>
                    <p className="text-[var(--ink)]">{ev.label}</p>
                    {ev.note && <p className="text-[var(--muted)] italic">{ev.note}</p>}
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}


function CreateModal({ open, onClose, kind, contextId, onCreated }) {
  // QA-2026-05-16-047 (2026-05-18) — manual create no longer asks
  // the user to pick a status. Default to `not_started`; Akki
  // assigns the data-driven status via Update goal in the drawer
  // once documents/signals exist. The RAG picker is gone — keeping
  // it would let users silently misrepresent performance.
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) { setTitle(""); setDescription(""); }
  }, [open]);

  const submit = async () => {
    if (!title.trim()) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/monitor/${kind}`, {
        title: title.trim(),
        description: description.trim() || undefined,
        rag_status: "not_started",
        score: 0,
        trend: "flat",
        source: "manual",
      });
      toast.success(`${kind === "project" ? "Project" : "Objective"} added.`);
      onCreated && onCreated(data);
      onClose && onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e, "Could not save."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && !busy && onClose && onClose()}>
      <DialogContent className="bg-[var(--parchment)]" data-testid={`obj-create-${kind}`}>
        <DialogHeader>
          <DialogTitle className="akki-serif text-[18px] text-[var(--ink)]">
            Add {kind === "project" ? "project" : "objective"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label className="text-[12px]" htmlFor="obj-title">Title</Label>
            <Input
              id="obj-title"
              autoFocus
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="rounded-sm text-[13.5px] mt-1"
              data-testid="obj-create-title"
            />
          </div>
          <div>
            <Label className="text-[12px]" htmlFor="obj-desc">Description</Label>
            <textarea
              id="obj-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full mt-1 border border-[var(--rule)] rounded-sm px-2 py-2 text-[13px] bg-white"
              data-testid="obj-create-description"
            />
          </div>
          {/* QA-2026-05-16-047 (2026-05-18) — status is set by Akki, not by the user. */}
          <p
            className="text-[12px] text-[var(--muted)] italic"
            data-testid="obj-create-status-note"
          >
            Status starts as <span className="font-mono">Not Started</span>. Once documents are uploaded, click <span className="font-mono">Update {kind === "project" ? "project" : "goal"}</span> in the {kind} profile to let Akki assess.
          </p>
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button
            type="button"
            onClick={submit}
            disabled={busy || !title.trim()}
            className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
            data-testid="obj-create-submit"
          >
            {busy && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


// Chunk 6.5-REVISED Task F (2026-05-13) — canonical owner-role list.
// Mirrors the backend `CANONICAL_OWNER_ROLES` in `routers/monitor_v2.py`.
// "Other" is implicit — items whose `owner_role` falls outside this
// list (or is null) surface under the "Other" tab.
const CANONICAL_OWNER_ROLES = [
  "CEO", "CFO", "COO", "CCO", "CTO", "CRO", "CIO",
  "Audit Committee", "Risk Committee",
];
// URL query-param sentinel for the "Other" tab. Decoupled from the
// canonical labels so a role literally named "Other" doesn't collide.
const OWNER_OTHER_SENTINEL = "__other__";


export default function ObjectivesProjectsPanel({ contextId }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [kind, setKind] = useState("objective");
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [rag, setRag] = useState("all");
  // Chunk 6.5-REVISED Task F — owner-role filter state. `all` is the
  // default and means "no owner filter applied"; an empty string from
  // the URL is also coerced to `all`.
  const [ownerRole, setOwnerRole] = useState(searchParams.get("owner") || "all");
  const [ownerRoleCounts, setOwnerRoleCounts] = useState({ total: 0, roles: [] });
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ items: [], total: 0, total_pages: 1 });
  const [drawerRow, setDrawerRow] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [suggestions, setSuggestions] = useState([]);

  // Reflect owner-role changes back into the URL so users can deep-link
  // and bookmark a filter. We deliberately keep this on the existing
  // `useSearchParams` rather than `useLocation` so other query params
  // (e.g. cycle deep-links) aren't trampled.
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    if (!ownerRole || ownerRole === "all") {
      next.delete("owner");
    } else {
      next.set("owner", ownerRole);
    }
    // setSearchParams with `replace: true` to avoid filling the back
    // stack on every tab click.
    setSearchParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ownerRole]);

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    try {
      const params = { status: rag, page, page_size: 5 };
      // Chunk 6.5-REVISED Task F — only pass `owner_role` when not "all".
      // The "Other" sentinel is forwarded verbatim; the backend
      // recognises it and matches null/non-canonical rows.
      if (ownerRole && ownerRole !== "all") {
        params.owner_role = ownerRole;
      }
      const { data: d } = await api.get(`/contexts/${contextId}/monitor/${kind}`, { params });
      let items = d?.items || [];
      if (q) {
        const lc = q.toLowerCase();
        items = items.filter((r) => (r.title || "").toLowerCase().includes(lc));
      }
      setData({ ...d, items });
    } catch (e) {
      setData({ items: [], total: 0, total_pages: 1 });
    } finally { setLoading(false); }
  }, [contextId, kind, rag, page, q, ownerRole]);

  useEffect(() => { load(); }, [load]);

  // Chunk 6.5-REVISED Task F — fetch the owner-role counts so the tab
  // strip knows which canonical labels actually have data behind them.
  // Refetched whenever the user creates / deletes / accepts an item
  // (the `load` dep chain ensures this stays in sync via `loadOwnerCounts`).
  const loadOwnerCounts = useCallback(async () => {
    if (!contextId) return;
    try {
      const { data: d } = await api.get(`/contexts/${contextId}/monitor/owner-roles`);
      setOwnerRoleCounts({
        total: d?.total ?? 0,
        roles: Array.isArray(d?.roles) ? d.roles : [],
      });
    } catch {
      setOwnerRoleCounts({ total: 0, roles: [] });
    }
  }, [contextId]);

  useEffect(() => { loadOwnerCounts(); }, [loadOwnerCounts, kind]);

  const loadSuggestions = useCallback(async () => {
    if (!contextId) return;
    try {
      const { data: d } = await api.get(`/contexts/${contextId}/monitor/auto-suggest-${kind}s`);
      setSuggestions((d?.items || []).slice(0, 3));
    } catch { setSuggestions([]); }
  }, [contextId, kind]);

  useEffect(() => { loadSuggestions(); }, [loadSuggestions]);

  const acceptSuggestion = async (s) => {
    try {
      await api.post(`/contexts/${contextId}/monitor/${kind}`, {
        title: s.title,
        rag_status: s.rag_status,
        score: s.score,
        trend: "flat",
        source: "auto",
        source_refs: s.source_refs || [],
      });
      toast.success("Added.");
      loadSuggestions();
      loadOwnerCounts();
      load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  };

  // Chunk 6.5-REVISED Task F — derive the visible owner-tab list from
  // backend counts. Canonical roles render in their locked order; the
  // "Other" tab (sentinel) follows. Tabs with zero count are hidden;
  // "All" is always rendered first.
  const ownerTabs = useMemo(() => {
    const tabs = [{ key: "all", label: "All", count: ownerRoleCounts.total }];
    const seen = {};
    (ownerRoleCounts.roles || []).forEach((r) => { seen[r.role] = r.count; });
    CANONICAL_OWNER_ROLES.forEach((r) => {
      if ((seen[r] || 0) > 0) tabs.push({ key: r, label: r, count: seen[r] });
    });
    if ((seen.Other || 0) > 0) {
      tabs.push({ key: OWNER_OTHER_SENTINEL, label: "Other", count: seen.Other });
    }
    return tabs;
  }, [ownerRoleCounts]);

  // QA-2026-05-16-045 — filter tabs now carry per-status counts from
  // `data.status_counts` so the user can see at a glance how many
  // items live in each bucket. Achieved + Not Started added as new
  // tabs (the backend already supports both states).
  const sc = data?.status_counts || {};
  const filterTabs = [
    { key: "all",         label: "All",         count: sc.all },
    { key: "green",       label: "On Track",    count: sc.green },
    { key: "amber",       label: "At Risk",     count: sc.amber },
    { key: "red",         label: "Off Track",   count: sc.red },
    { key: "achieved",    label: "Achieved",    count: sc.achieved },
    { key: "not_started", label: "Not Started", count: sc.not_started },
  ];

  return (
    <section className="mt-2 mb-10" data-testid="objectives-projects-panel">
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <p className="akki-overline">Objectives & Projects</p>
        <div className="flex items-center gap-2">
          {[
            { k: "objective", label: "Objectives", icon: Target },
            { k: "project",   label: "Projects",   icon: Layers },
          ].map((t) => {
            const Icon = t.icon;
            const active = kind === t.k;
            return (
              <button
                key={t.k}
                type="button"
                onClick={() => { setKind(t.k); setPage(1); }}
                className={[
                  "inline-flex items-center gap-1.5 text-[12.5px] px-3 py-1.5 rounded-sm",
                  active
                    ? "bg-white border border-[var(--ink)] text-[var(--ink)]"
                    : "text-[var(--muted)] hover:text-[var(--ink)]",
                ].join(" ")}
                data-testid={`obj-panel-kind-${t.k}${active ? "-active" : ""}`}
              >
                <Icon className="w-3.5 h-3.5" strokeWidth={1.7} /> {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {suggestions.length > 0 && (
        <div
          className="mb-4 border border-dashed border-[var(--rule)] bg-[var(--parchment)] rounded-sm px-4 py-3"
          data-testid="obj-panel-suggestions"
        >
          <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] mb-2 inline-flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-[var(--accent)]" strokeWidth={1.7} /> Suggested from your cycles
          </p>
          <ul className="space-y-1.5">
            {suggestions.map((s, i) => (
              <li key={i} className="flex items-center gap-2 text-[12.5px]">
                <span className="flex-1 truncate text-[var(--ink)]">{s.title}</span>
                <span className="text-[10.5px] font-mono uppercase tracking-[0.14em] text-[var(--muted)]">
                  {RAG_LABEL[s.rag_status]}
                </span>
                <button
                  type="button"
                  onClick={() => acceptSuggestion(s)}
                  className="text-[11.5px] px-2 py-0.5 border border-[var(--rule)] rounded-sm hover:bg-white inline-flex items-center gap-1"
                  data-testid={`obj-panel-suggestion-accept-${i}`}
                >
                  <Plus className="w-3 h-3" /> Add
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Chunk 6.5-REVISED Task F (2026-05-13) — owner-role tab strip.
          Renders BELOW the panel header + suggestions, ABOVE the
          ListingShell's RAG filter tabs (the two strips are
          orthogonal — owner × status). Tabs with zero count are
          hidden; "All" is always rendered first. Visually distinct
          from the RAG strip: smaller chip, no border, single
          underline accent on the active tab. */}
      {ownerTabs.length > 1 && (
        <div
          className="mb-3 pb-2 border-b border-[var(--rule)] flex items-center gap-1 flex-wrap"
          data-testid="obj-panel-owner-tabs"
          role="tablist"
          aria-label="Filter by owner role"
        >
          <span className="text-[10px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mr-2 shrink-0">
            Owner
          </span>
          {ownerTabs.map((t) => {
            const isActive = ownerRole === t.key;
            return (
              <button
                key={t.key}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => { setOwnerRole(t.key); setPage(1); }}
                className={[
                  "inline-flex items-center gap-1 px-2 py-1 rounded-sm text-[11.5px] transition-colors",
                  isActive
                    ? "bg-[var(--ink)] text-[var(--parchment)]"
                    : "text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)]",
                ].join(" ")}
                data-testid={`obj-panel-owner-tab-${t.key}`}
              >
                <span>{t.label}</span>
                <span className="font-mono text-[10px] opacity-80">{t.count}</span>
              </button>
            );
          })}
        </div>
      )}

      <ListingShell
        testId="obj-panel-listing"
        searchValue={q}
        onSearchChange={(v) => { setQ(v); setPage(1); }}
        searchPlaceholder={`Search ${kind}s by title…`}
        filterTabs={filterTabs}
        activeFilterKey={rag}
        onFilterChange={(k) => { setRag(k); setPage(1); }}
        sortOptions={[{ key: "score", label: "By score" }]}
        activeSortKey="score"
        pageSize={5}
        page={page}
        totalCount={data.total}
        onPageChange={(n) => setPage(n)}
        isLoading={loading}
        controlsRight={
          <Button
            type="button"
            size="sm"
            onClick={() => setCreateOpen(true)}
            className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
            data-testid="obj-panel-add"
          >
            <Plus className="w-3.5 h-3.5 mr-1" /> Add {kind}
          </Button>
        }
        emptyState={
          <div className="border border-dashed border-[var(--rule)] rounded-sm bg-[var(--parchment)] px-6 py-8 text-center" data-testid="obj-panel-empty">
            <p className="akki-serif text-[15px] text-[var(--ink)]">No {kind}s yet.</p>
            <p className="text-[12.5px] text-[var(--muted)] mt-1">
              Add one above, or accept a suggestion from your cycles.
            </p>
          </div>
        }
      >
        <ul className="space-y-3" data-testid="obj-panel-list">
          {data.items.map((row) => (
            <ItemRow
              key={row.id}
              row={row}
              onOpen={(r) => setDrawerRow({ ...r, kind, context_id: contextId })}
            />
          ))}
        </ul>
      </ListingShell>

      <ItemDrawer
        row={drawerRow}
        onClose={() => setDrawerRow(null)}
        onAssessed={() => { load(); }}
      />
      <CreateModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        kind={kind}
        contextId={contextId}
        onCreated={() => { load(); loadSuggestions(); loadOwnerCounts(); }}
      />
    </section>
  );
}
