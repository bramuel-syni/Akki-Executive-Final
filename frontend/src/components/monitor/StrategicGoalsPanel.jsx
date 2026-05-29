import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import StrategicRow, { ScoreBar as SharedScoreBar } from "@/components/strategic_row/StrategicRow";
import StatusFilterTabs from "@/components/monitor/StatusFilterTabs";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import {
  Target, Sparkles, FileText, ChevronRight, ChevronDown, Loader2, X,
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle2, Plus, Info,
  Layers, Pencil, Upload, Activity, Minus,
} from "lucide-react";

/**
 * StrategicGoalsPanel — the centerpiece of the Monitor surface.
 *
 * Shows board-level KPIs (e.g. "Migrate to new ERP by Dec 2026") with
 * current score, target, owner, and probability of success. Goals are
 * either entered manually OR extracted from an uploaded strategic
 * document by the LLM.
 *
 * Rendering modes:
 *   • Executive (CEO/CFO/COO/Commercial): rows scoped to their dept +
 *     all 'board' or 'ceo' goals (since they're cross-functional).
 *     Inline edit on score/probability/status.
 *   • NED: read-only scorecard view of every department's goals.
 *
 * Empty state: friendly upload-strategy prompt with document picker.
 */

const STATUS_STYLE = {
  on_track:  { label: "On track",   tone: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  at_risk:   { label: "At risk",    tone: "text-amber-700 bg-amber-50 border-amber-200" },
  off_track: { label: "Off track",  tone: "text-red-700 bg-red-50 border-red-200" },
  achieved:  { label: "Achieved",   tone: "text-blue-700 bg-blue-50 border-blue-200" },
  // W4.2 (2026-05-27) — neutral states swap grey → light brand purple
  // (matches W4.1 "Active" marker + Phase V AdminUsers precedent).
  abandoned: { label: "Abandoned",  tone: "text-[var(--ned-purple)] bg-ned-purple/10 border-ned-purple/20" },
  not_started: { label: "Not Started", tone: "text-[var(--ned-purple)] bg-ned-purple/10 border-ned-purple/20" },
};

// T2.4 (2026-05-25) — X8 status filter tabs (6 buckets).
// Order matches spec verbatim: All / On Track / At Risk / Off Track /
// Achieved / Not Started. `key` is the goal.status backing value; "all"
// is the no-filter sentinel.
const STATUS_FILTER_TABS = [
  { key: "all",         label: "All" },
  { key: "on_track",    label: "On Track" },
  { key: "at_risk",     label: "At Risk" },
  { key: "off_track",   label: "Off Track" },
  { key: "achieved",    label: "Achieved" },
  { key: "not_started", label: "Not Started" },
];

// T2.4 (2026-05-25) — X6 G11 ratified: dual RAG bars.
// Performance bar follows the goal STATUS:
//   On Track / Achieved → green
//   At Risk             → amber
//   Off Track           → red
// Probability bar follows the G11 numeric bands, in the
// grey/purple scheme (Wave 1.5, 2026-05-27 — visual contrast
// vs. the Performance bar so users don't confuse the two
// signals on glance):
//   ≥ 70  → brand purple   (High confidence)
//   40-69 → muted purple   (Moderate confidence)
//   < 40  → grey           (Low confidence)
//   null  → grey           (unknown)
function statusBarClass(status) {
  if (status === "on_track" || status === "achieved") return "bg-emerald-600";
  if (status === "at_risk") return "bg-amber-500";
  if (status === "off_track") return "bg-[color:var(--oxblood)]";
  // not_started + abandoned have no semantic colour weight; render as muted.
  return "bg-slate-400";
}
function probabilityBarClass(value) {
  if (value === null || value === undefined) return "bg-slate-400";
  if (value >= 70) return "bg-[color:var(--ned-purple)]";
  if (value >= 40) return "bg-[color:var(--ned-purple)]/50";
  return "bg-slate-400";
}

// T2.4 (2026-05-25) — X8 G12 ratified: category filter source.
// Source from the active context's strategic_goals.department distinct
// values; fall back to the fixed example list (verbatim from G12) if
// no department values exist on the data.
const G12_FALLBACK_CATEGORIES = ["Operations", "People", "Compliance", "Product", "Commercial"];
function deriveCategoryOptions(goals) {
  const seen = new Set();
  for (const g of goals || []) {
    if (g.department) seen.add(g.department);
  }
  if (seen.size === 0) return G12_FALLBACK_CATEGORIES;
  return Array.from(seen);
}

const DEPT_LABEL = {
  ceo: "CEO", cfo: "CFO", coo: "COO", commercial: "Commercial", board: "Board",
};

function visibleGoalsForFunction(goals, fn, isNED) {
  if (isNED || fn === "ceo") return goals;
  // Each function sees its own department + 'board' + 'ceo' (cross-cutting)
  const allowed = new Set([fn, "board", "ceo"]);
  return goals.filter((g) => allowed.has(g.department));
}

function groupByDepartment(goals) {
  const groups = {};
  for (const g of goals) {
    const k = g.department || "ceo";
    if (!groups[k]) groups[k] = [];
    groups[k].push(g);
  }
  return groups;
}

export default function StrategicGoalsPanel({ contextId, fn, isNED, onChange, onCountChange }) {
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [extractOpen, setExtractOpen] = useState(false);
  // Patch 28F — drawer state for the Strategic Goals listing. Row
  // click now opens a side drawer showing full goal context + timeline
  // (parity with the Objectives & Projects panel).
  //
  // Chunk 17 cleanup (C17-001, 2026-05-21) — `editingId` state was
  // removed alongside the orphaned `EditGoalRow` component (lines
  // 653-708 deleted). The "Edit this goal" affordance was replaced
  // by the AI-driven "Update Goal" flow in Chunk 12 (QA-049); the
  // inline edit path had no remaining call site and rendered as
  // dead code.
  const [drawerGoal, setDrawerGoal] = useState(null);
  // T2.4 (2026-05-25) — X8 ratified filter state: status tab + category
  // dropdown. Both apply over `visibleGoalsForFunction` (the role-
  // filtered set) and combine — selecting both narrows the list.
  const [statusFilter, setStatusFilter] = useState("all");
  const [categoryFilter, setCategoryFilter] = useState("all");

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/contexts/${contextId}/strategic-goals`);
      const list = data.goals || [];
      setGoals(list);
      // AA-slice-4 (2026-05-27) — surface the total count up to the
      // Monitor capsule-tab badge.
      onCountChange && onCountChange(list.length);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId, onCountChange]);
  useEffect(() => { load(); }, [load]);

  const visible = useMemo(() => visibleGoalsForFunction(goals, fn, isNED), [goals, fn, isNED]);

  // T2.4 — X8 G12 ratified category source. The dropdown options are
  // derived from the role-filtered goals set so the user only sees
  // categories actually populated within their function's scope. Falls
  // back to the G12 fixed list when no department values exist.
  const categoryOptions = useMemo(() => deriveCategoryOptions(visible), [visible]);

  // T2.4 — apply status + category filters in combination.
  const filtered = useMemo(() => {
    return visible.filter((g) => {
      if (statusFilter !== "all" && g.status !== statusFilter) return false;
      if (categoryFilter !== "all" && g.department !== categoryFilter) return false;
      return true;
    });
  }, [visible, statusFilter, categoryFilter]);

  // T2.4 — per-tab live counts derived from the role-filtered set
  // (NOT the post-status-filter set) so each tab always reflects the
  // total in its bucket regardless of the currently active tab.
  const statusCounts = useMemo(() => {
    const c = { all: visible.length };
    for (const t of STATUS_FILTER_TABS) {
      if (t.key === "all") continue;
      c[t.key] = visible.filter((g) =>
        (categoryFilter === "all" || g.department === categoryFilter) &&
        g.status === t.key,
      ).length;
    }
    return c;
  }, [visible, categoryFilter]);

  const groups = useMemo(() => groupByDepartment(filtered), [filtered]);

  const orderedDepartments = ["board", "ceo", "cfo", "coo", "commercial"]
    .filter((d) => groups[d]?.length > 0);

  const refresh = () => { load(); onChange?.(); };

  if (loading) {
    return (
      <div className="bg-white border border-[var(--rule)] rounded-md p-8 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">
        Reading the strategy…
      </div>
    );
  }

  if (visible.length === 0) {
    return (
      <EmptyState
        contextId={contextId}
        onExtractOpen={() => setExtractOpen(true)}
        onChange={refresh}
        fn={fn}
        isNED={isNED}
        modalOpen={extractOpen}
        onModalClose={() => setExtractOpen(false)}
      />
    );
  }

  return (
    <section data-testid="strategic-goals-panel">
      <div className="flex items-end justify-between mb-3 flex-wrap gap-3">
        <div>
          <p className="akki-overline mb-1 flex items-center gap-2">
            <Target className="w-3 h-3 text-[var(--accent)]" /> Strategic goals
          </p>
          <h2 className="akki-serif text-[19px] text-[var(--ink)] leading-snug">
            {isNED
              ? "Board scorecard."
              : `${visible.length} goal${visible.length === 1 ? "" : "s"} on your function's plate.`}
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <ScoreMethodologyTip />
          {!isNED && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setExtractOpen(true)}
              className="border-[var(--rule)] text-[12px] h-8"
              data-testid="strategic-goals-add"
            >
              <Sparkles className="w-3 h-3 mr-1.5" /> Read from a strategy doc
            </Button>
          )}
        </div>
      </div>

      {/* T2.4 (2026-05-25) — X8 status filter tabs + category dropdown.
          Both controls sit on a single horizontal line above the
          goal groupings, per spec §4.D → X8: "On the same line as the
          filter tabs, add a category filter on the right side." Tabs
          and the dropdown combine — selecting both narrows the list.

          Phase Y followup (2026-02 fork-resume) — extracted the
          tab markup into the shared `<StatusFilterTabs>` primitive
          so the Tasks/Initiatives panel renders the same row, same
          rhythm, same accessibility contract. The wrapper here keeps
          the `data-testid="strategic-goals-filters"` outer container
          for back-compatibility with existing probes. */}
      <div
        className="mb-4 pb-2 border-b border-[var(--rule)] flex items-center gap-2 flex-wrap"
        data-testid="strategic-goals-filters"
      >
        <StatusFilterTabs
          tabs={STATUS_FILTER_TABS}
          activeKey={statusFilter}
          onSelect={setStatusFilter}
          counts={statusCounts}
          testIdPrefix="strategic-goals-status-tab"
          ariaLabel="Filter strategic goals by status"
        />
      </div>

      {/* Owner filter — Decision 1 (2026-02 fork-resume): single source
          of truth = capsule strip. The legacy dropdown
          (`strategic-goals-owner-select`) was removed; both Monitor tabs
          (Strategic Goals + Tasks/Initiatives) now use the same capsule
          pattern (single-tap interaction, more discoverable, no visual
          duplication). Capsule colors match the brand-purple Wave 4.2
          treatment used on Tasks/Initiatives. */}
      {categoryOptions.length > 0 && (
        <div
          className="flex items-center gap-2 mb-4 flex-nowrap overflow-x-auto"
          data-testid="strategic-goals-owner-capsules"
        >
          <button
            type="button"
            onClick={() => setCategoryFilter("all")}
            className={`px-3 py-1 rounded-full text-[11.5px] uppercase tracking-wider border transition-colors whitespace-nowrap ${
              categoryFilter === "all"
                ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                : "text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)] hover:bg-[var(--cream-deep)]/40"
            }`}
            data-testid="strategic-goals-owner-capsule-all"
          >
            All owners
          </button>
          {categoryOptions.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCategoryFilter(c)}
              className={`px-3 py-1 rounded-full text-[11.5px] uppercase tracking-wider border transition-colors whitespace-nowrap ${
                categoryFilter === c
                  ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                  : "text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)] hover:bg-[var(--cream-deep)]/40"
              }`}
              data-testid={`strategic-goals-owner-capsule-${c}`}
            >
              {DEPT_LABEL[c] || c}
            </button>
          ))}
        </div>
      )}

      <div className="space-y-5" data-testid="strategic-goals-groups">
        {/* T2.4 (2026-05-25) — empty state when status+category filters
            narrow the list to zero matches, but goals do exist in the
            unfiltered set. Distinct testid from the "no goals at all"
            EmptyState above. */}
        {filtered.length === 0 && (
          <div
            className="border border-dashed border-[var(--rule)] rounded-sm bg-[var(--parchment)] px-6 py-8 text-center"
            data-testid="strategic-goals-filtered-empty"
          >
            <p className="akki-serif text-[14px] text-[var(--ink)]">No goals match this filter.</p>
            <p className="text-[12px] text-[var(--muted)] mt-1">
              Try a different status tab or pick a different category.
            </p>
          </div>
        )}
        {orderedDepartments.map((dept) => (
          <div key={dept}>
            <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono mb-2">
              {DEPT_LABEL[dept] || dept}
            </p>
            <div className="bg-white border border-[var(--rule)] rounded-md overflow-hidden">
              {groups[dept].map((g, i) => (
                <GoalRow
                  key={g.id}
                  goal={g}
                  isLast={i === groups[dept].length - 1}
                  isNED={isNED}
                  onOpenDrawer={() => setDrawerGoal(g)}
                  contextId={contextId}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Patch 28F — Strategic Goal detail drawer.
          Opens on row click. Mirrors the ObjectivesProjectsPanel
          drawer pattern so the executive listings now have the same
          click-to-detail UX. */}
      <GoalDetailDrawer
        goal={drawerGoal}
        onClose={() => setDrawerGoal(null)}
        contextId={contextId}
        onGoalUpdated={(updated) => {
          // Update the locally-rendered drawer goal AND the row in
          // the listing so the new performance score / status surface
          // immediately without a refetch round-trip.
          setDrawerGoal(updated);
          setGoals((prev) => prev.map((g) => g.id === updated.id ? { ...g, ...updated } : g));
        }}
        isNED={isNED}
      />

      {extractOpen && (
        <ExtractFromDocModal
          contextId={contextId}
          onClose={() => setExtractOpen(false)}
          onExtracted={() => { setExtractOpen(false); refresh(); }}
        />
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Iter40 — Strategic Goal card overhaul.
//
// Per user feedback: replace the dual conic dials with progress bars on a
// single horizontal row, add a category marker (Revenue, Customer, etc.),
// surface initiatives count, and write a one-line narrative beneath each
// score so a 78 actually MEANS something. Reduce whitespace — everything
// reads as one tight editorial line, then a slim secondary row.
// ---------------------------------------------------------------------------

const CATEGORY_STYLE = {
  revenue:    { label: "Revenue",    bar: "bg-emerald-600", chip: "bg-emerald-50 text-emerald-800 border-emerald-200" },
  customer:   { label: "Customer",   bar: "bg-blue-600",    chip: "bg-blue-50 text-blue-800 border-blue-200" },
  product:    { label: "Product",    bar: "bg-violet-600",  chip: "bg-violet-50 text-violet-800 border-violet-200" },
  people:     { label: "People",     bar: "bg-amber-600",   chip: "bg-amber-50 text-amber-800 border-amber-200" },
  operations: { label: "Operations", bar: "bg-ned-purple/80",   chip: "bg-ned-purple/10 text-[var(--ink)] border-ned-purple/20" },
  compliance: { label: "Compliance", bar: "bg-red-700",     chip: "bg-red-50 text-red-800 border-red-200" },
};

function performanceNarrative(value) {
  if (value === null || value === undefined) return "Not yet scored.";
  if (value >= 90) return "Ahead of plan — convert this into a board talking-point.";
  if (value >= 80) return "On track. Keep the cadence.";
  if (value >= 65) return "At risk. Drift is real but recoverable.";
  if (value >= 40) return "Off track. Needs an intervention this cycle.";
  return "Materially behind plan. Escalate to the chair.";
}

function probabilityNarrative(value) {
  if (value === null || value === undefined) return "Confidence not yet calibrated.";
  if (value >= 80) return "High confidence in hitting the target.";
  if (value >= 60) return "Plausible — assumes the current trajectory holds.";
  if (value >= 40) return "Coin-flip. The next reporting period decides.";
  return "Unlikely without a different plan.";
}

function GoalRow({ goal, isLast, isNED, onOpenDrawer, contextId }) {
  const status = STATUS_STYLE[goal.status] || STATUS_STYLE.on_track;
  const score = typeof goal.current_score === "number" ? goal.current_score : null;
  const prob = typeof goal.probability === "number" ? goal.probability : null;
  const cat = CATEGORY_STYLE[goal.category] || CATEGORY_STYLE.operations;
  const initiatives = typeof goal.initiatives_count === "number" ? goal.initiatives_count : 0;

  // Decision 2 / Phase Y (2026-02 fork-resume) — Monitor goal row now
  // consumes the shared `<StrategicRow>` primitive. Visual output is
  // identical to the pre-extraction version; future surfaces (Task
  // Manager, AdminTenants drill, etc.) compose the same primitive.

  const categoryChip = (
    <span
      className={`inline-block px-1.5 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider border ${cat.chip}`}
      data-testid={`goal-category-${goal.id}`}
    >
      {cat.label}
    </span>
  );

  const statusChip = (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-wider border ${status.tone}`}>
      {goal.status === "on_track" || goal.status === "achieved" ? <CheckCircle2 className="w-2.5 h-2.5" /> :
       goal.status === "at_risk" || goal.status === "off_track" ? <AlertTriangle className="w-2.5 h-2.5" /> : null}
      {status.label}
    </span>
  );

  const rightSideScores = [
    {
      label:     "Performance",
      value:     score,
      barClass:  statusBarClass(goal.status),
      narrative: performanceNarrative(score),
      testId:    `goal-perf-bar-${goal.id}`,
    },
    {
      label:     "Probability",
      value:     prob,
      barClass:  probabilityBarClass(prob),
      narrative: probabilityNarrative(prob),
      testId:    `goal-prob-bar-${goal.id}`,
    },
  ];

  const metadataChildren = (
    <>
      <span className="inline-flex items-center gap-1" data-testid={`goal-initiatives-${goal.id}`}>
        <Layers className="w-3 h-3 text-[var(--muted)]" />
        <strong>{initiatives}</strong> {initiatives === 1 ? "initiative" : "initiatives"}
      </span>
      {goal.target_metric && goal.target_value && (
        <span><span className="text-[var(--muted)]">Target:</span> <strong>{goal.target_value}</strong> {goal.target_metric}</span>
      )}
      {goal.target_date && <span><span className="text-[var(--muted)]">By:</span> {goal.target_date}</span>}
      {goal.owner_name && <span><span className="text-[var(--muted)]">Owner:</span> {goal.owner_name}</span>}
      {goal.current_value && <span><span className="text-[var(--muted)]">Now:</span> {goal.current_value}</span>}
      {goal.source_doc_id && (
        <Link to={`/app/documents/${goal.source_doc_id}`} className="text-[var(--accent)] hover:underline inline-flex items-center gap-1">
          <FileText className="w-3 h-3" /> source
        </Link>
      )}
      {goal.last_akki_update?.assessed_at && (
        <span
          className="inline-flex items-center gap-1 text-[var(--muted)]"
          data-testid={`goal-card-last-update-${goal.id}`}
          title={new Date(goal.last_akki_update.assessed_at).toLocaleString(undefined, {
            dateStyle: "medium", timeStyle: "short",
          })}
        >
          <span className="text-[var(--muted)]">Reassessed:</span>{" "}
          {new Date(goal.last_akki_update.assessed_at).toLocaleDateString(undefined, {
            dateStyle: "medium",
          })}
        </span>
      )}
    </>
  );

  return (
    <StrategicRow
      categoryChip={categoryChip}
      statusChip={statusChip}
      title={goal.title}
      rightSideScores={rightSideScores}
      metadataChildren={metadataChildren}
      description={goal.description}
      onClick={onOpenDrawer}
      testId={`strategic-goal-${goal.id}`}
      isLast={isLast}
    />
  );
}

/**
 * GoalDetailDrawer — Patch 28F.
 *
 * Side drawer that opens when a row in the Strategic Goals listing is
 * clicked. Mirrors the visual language of the Objectives & Projects
 * drawer (border-rule + akki-serif heading + mono labels). Read-only
 * detail surface; an `Edit` button drops the user into the inline
 * edit mode for the same goal (used by execs to update score quickly).
 */
function GoalDetailDrawer({ goal, onClose, contextId, onGoalUpdated, isNED }) {
  // QA-2026-05-16-049 — "Edit this goal" replaced by "Update Goal".
  // Update Goal calls the Shield-gateway-routed reassessment endpoint.
  // On success: update timestamp + applied changes surface; on no-data:
  // verbatim spec copy + Document Journal link render in-drawer.
  const [updating, setUpdating] = useState(false);
  const [noDataMessage, setNoDataMessage] = useState(null);
  const [lastApplied, setLastApplied] = useState(null);

  // AA.followup.10 REVISED (2026-02 fork-resume) — Goal evolution feed
  // for the Progress timeline section. Auto-fetched on drawer open;
  // never user-edited.
  const [evolution, setEvolution] = useState({ events: [], loading: false });
  const [expandedEventId, setExpandedEventId] = useState(null);

  // Reset transient state whenever the drawer opens for a different goal.
  useEffect(() => {
    setNoDataMessage(null);
    setLastApplied(null);
    setUpdating(false);
    setEvolution({ events: [], loading: false });
    setExpandedEventId(null);
  }, [goal?.id]);

  // Fetch the goal evolution feed on open. Idempotent; the endpoint
  // is a read-only aggregator over existing collections.
  useEffect(() => {
    if (!goal?.id || !contextId) return;
    let cancelled = false;
    setEvolution((s) => ({ ...s, loading: true }));
    (async () => {
      try {
        const { data } = await api.get(
          `/contexts/${contextId}/strategic-goals/${goal.id}/evolution`,
        );
        if (cancelled) return;
        setEvolution({ events: data?.events || [], loading: false });
      } catch (_e) {
        if (cancelled) return;
        // Soft-fail — empty state is the right UX, not a toast.
        setEvolution({ events: [], loading: false });
      }
    })();
    return () => { cancelled = true; };
  }, [goal?.id, contextId, lastApplied]);

  const onUpdateGoal = useCallback(async () => {
    if (!goal || !contextId || updating) return;
    setUpdating(true); setNoDataMessage(null); setLastApplied(null);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/strategic-goals/${goal.id}/update`,
        {},
      );
      if (data?.no_data) {
        setNoDataMessage(data.message || "No additional information found for this goal. Please upload a document with updated performance data so Akki can reassess.");
        toast.info("Akki found no new evidence for this goal.");
        // Surface the assessment timestamp on the timeline even on no-data.
        if (onGoalUpdated) onGoalUpdated({
          ...goal,
          last_akki_update: data.last_akki_update,
        });
      } else {
        // Apply the returned values locally so the drawer reflects
        // the new score/probability/status without a full refetch.
        const applied = data.last_akki_update?.applied_changes || {};
        setLastApplied({
          ...applied,
          assessed_at: data.last_akki_update?.assessed_at,
          rationale: data.last_akki_update?.rationale,
        });
        toast.success("Akki updated the goal.");
        if (onGoalUpdated) onGoalUpdated({
          ...goal,
          current_score: data.current_score,
          probability: data.probability,
          status: data.status,
          last_akki_update: data.last_akki_update,
        });
      }
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setUpdating(false);
    }
  }, [goal, contextId, updating, onGoalUpdated]);

  const open = !!goal;
  const status = STATUS_STYLE[goal?.status] || STATUS_STYLE.on_track;
  const cat = CATEGORY_STYLE[goal?.category] || CATEGORY_STYLE.operations;
  const lastUpdateTs = goal?.last_akki_update?.assessed_at;
  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose && onClose()}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[460px] sm:w-[460px] overflow-y-auto bg-[var(--paper)] p-0"
        data-testid="goal-drawer"
      >
        <div className="px-6 py-5 border-b border-[var(--rule)] sticky top-0 bg-[var(--paper)] z-10">
          <div className="flex items-start justify-between gap-3">
            <SheetHeader className="text-left flex-1 min-w-0">
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">
                {cat.label} · Strategic goal
              </p>
              <SheetTitle className="akki-serif text-[18px] text-[var(--ink)] leading-snug">
                {goal?.title}
              </SheetTitle>
              <SheetDescription className="text-[12px] text-[var(--muted)]">
                Status · <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] border ${status.tone}`}>{status.label}</span>
              </SheetDescription>
            </SheetHeader>
            <button
              type="button"
              onClick={onClose}
              className="text-[var(--muted)] hover:text-[var(--ink)] p-1"
              aria-label="Close drawer"
              data-testid="goal-drawer-close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="px-6 py-5 space-y-5">
          <div className="grid grid-cols-2 gap-3 border border-[var(--rule)] rounded-sm bg-white px-3 py-3">
            <div>
              {/* QA-2026-05-16-049 — renamed "Current score" → "Performance Score" */}
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Performance Score</p>
              <p className="text-[14px] akki-serif text-[var(--ink)]" data-testid="goal-drawer-performance-score">
                {goal?.current_score != null ? `${goal.current_score}%` : "—"}
              </p>
            </div>
            <div>
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Probability</p>
              <p className="text-[14px] akki-serif text-[var(--ink)]">{goal?.probability != null ? `${goal.probability}%` : "—"}</p>
            </div>
            <div>
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Target</p>
              <p className="text-[14px] akki-serif text-[var(--ink)]">{goal?.target_value || "—"} {goal?.target_metric || ""}</p>
            </div>
            <div>
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Target date</p>
              <p className="text-[14px] akki-serif text-[var(--ink)]">{goal?.target_date || "—"}</p>
            </div>
          </div>

          {/* Phase AA.followup.4 → Item 4 (2026-02 fork-resume) — Monitoring intel.
              Surfaces the full client-side bucket-template narratives that match
              the closed-row snippets. Backend LLM-generated explanations don't
              exist yet (see Phase AA.followup.10 backlog) so this renders the
              same deterministic bucket text the row uses, full-width (not
              truncated). Score values use ned-purple accent per spec. */}
          <div data-testid="goal-drawer-intelligence" className="space-y-3">
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)]">
              Monitoring intel
            </p>
            <div className="space-y-2.5">
              <div className="border border-[var(--rule)] rounded-sm bg-white px-3 py-2.5" data-testid="goal-drawer-performance-signal">
                <div className="flex items-baseline justify-between gap-3 mb-1">
                  <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">Performance signal</p>
                  <p className="text-[13px] akki-serif text-ned-purple">{goal?.current_score != null ? `${goal.current_score}%` : "—"}</p>
                </div>
                <p className="text-[12.5px] text-[var(--ink)] leading-snug" data-testid="goal-drawer-performance-signal-text">
                  {goal?.performance_explanation || performanceNarrative(goal?.current_score)}
                </p>
              </div>
              <div className="border border-[var(--rule)] rounded-sm bg-white px-3 py-2.5" data-testid="goal-drawer-probability-signal">
                <div className="flex items-baseline justify-between gap-3 mb-1">
                  <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">Probability signal</p>
                  <p className="text-[13px] akki-serif text-ned-purple">{goal?.probability != null ? `${goal.probability}%` : "—"}</p>
                </div>
                <p className="text-[12.5px] text-[var(--ink)] leading-snug" data-testid="goal-drawer-probability-signal-text">
                  {goal?.probability_explanation || probabilityNarrative(goal?.probability)}
                </p>
              </div>
            </div>
          </div>

          {/* Recommended action — backend `recommended_action` field is not
              modelled yet (filed Phase AA.followup.10). Fall back to a hint
              derived from the performance bucket text. */}
          {(goal?.recommended_action || (goal?.current_score != null && goal.current_score < 65)) && (
            <div
              data-testid="goal-drawer-recommended-action"
              className="rounded-sm bg-ned-purple/10 border border-ned-purple/30 px-3 py-2.5"
            >
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-ned-purple mb-1">
                Recommended action
              </p>
              <p className="text-[12.5px] text-[var(--ink)] leading-snug" data-testid="goal-drawer-recommended-action-text">
                {goal?.recommended_action || performanceNarrative(goal?.current_score)}
              </p>
            </div>
          )}

          {/* Progress timeline — AA.followup.10 REVISED (2026-02 fork-resume).
              Auto-derived from existing time-series sources (score_history,
              audit_log, documents, extractions_log). Observational view —
              NO manual "+ Add" CTA. Replaces the prior milestone-tracker
              direction the user flagged as wrong. */}
          <div data-testid="goal-drawer-progress-timeline" className="border border-[var(--rule)] rounded-sm bg-white px-3 py-3">
            <div className="flex items-center justify-between mb-3">
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] flex items-center gap-1.5">
                <Activity className="w-3 h-3" /> Progress timeline
              </p>
              {evolution.events.length > 0 && (
                <span className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)]" data-testid="goal-drawer-progress-timeline-count">
                  {evolution.events.length} signal{evolution.events.length === 1 ? "" : "s"}
                </span>
              )}
            </div>

            {evolution.loading ? (
              <p className="text-[12px] text-[var(--muted)] italic">
                <Loader2 className="w-3 h-3 inline-block animate-spin mr-1.5" />Loading…
              </p>
            ) : evolution.events.length === 0 ? (
              <p
                className="text-[12.5px] text-[var(--muted)] italic leading-snug"
                data-testid="goal-drawer-progress-timeline-empty"
              >
                No progress signals recorded yet. Signals will appear here as
                documents are uploaded and AKKI reassesses this goal.
              </p>
            ) : (
              <>
                {/* Horizontal bar with markers. The bar itself is a
                    1px ned-purple/30 rule; each marker is a dot
                    positioned along it proportionally to its
                    timestamp. */}
                {(() => {
                  const items = evolution.events;
                  const times = items.map((e) => new Date(e.at).getTime() || 0).filter(Boolean);
                  const tMin = Math.min(...times);
                  const tMax = Math.max(...times);
                  const span = Math.max(tMax - tMin, 1);
                  const posPct = (iso) => {
                    const t = new Date(iso).getTime();
                    if (!isFinite(t)) return 0;
                    return ((t - tMin) / span) * 100;
                  };
                  const ICON = {
                    score_delta:     TrendingUp,
                    doc_upload:      Upload,
                    ai_reassessment: Sparkles,
                    status_change:   CheckCircle2,
                  };
                  return (
                    <>
                      <div
                        className="relative h-6 mb-3"
                        data-testid="goal-drawer-progress-timeline-bar"
                      >
                        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-ned-purple/30" />
                        {items.map((e) => {
                          const Icon = ICON[e.kind] || Activity;
                          const dirDown = e.delta?.direction === "down";
                          const ArrowIcon = e.kind === "score_delta"
                            ? (dirDown ? TrendingDown : (e.delta?.direction === "flat" ? Minus : TrendingUp))
                            : Icon;
                          return (
                            <button
                              key={e.id}
                              type="button"
                              onClick={() => setExpandedEventId(expandedEventId === e.id ? null : e.id)}
                              className={`absolute top-1/2 -translate-x-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-white border flex items-center justify-center transition-transform hover:scale-110 focus:outline-none focus-visible:ring-2 focus-visible:ring-ned-purple/40 ${
                                expandedEventId === e.id
                                  ? "border-ned-purple ring-2 ring-ned-purple/30"
                                  : "border-ned-purple/60"
                              }`}
                              style={{ left: `${posPct(e.at)}%` }}
                              title={e.trigger}
                              data-testid={`goal-drawer-progress-timeline-marker-${e.id}`}
                              data-marker-kind={e.kind}
                            >
                              <ArrowIcon className="w-2 h-2 text-ned-purple" strokeWidth={2.4} />
                            </button>
                          );
                        })}
                      </div>

                      {/* Expanded detail panel for the clicked marker. */}
                      {expandedEventId && (() => {
                        const ev = items.find((e) => e.id === expandedEventId);
                        if (!ev) return null;
                        const when = ev.at ? new Date(ev.at).toLocaleString(undefined, {
                          month: "short", day: "numeric", year: "numeric",
                          hour: "2-digit", minute: "2-digit",
                        }) : "—";
                        return (
                          <div
                            className="rounded-sm bg-ned-purple/5 border border-ned-purple/20 px-3 py-2"
                            data-testid={`goal-drawer-progress-timeline-detail-${ev.id}`}
                          >
                            <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1">
                              {when}
                            </p>
                            <p className="text-[12.5px] text-[var(--ink)] leading-snug">
                              {ev.trigger}
                            </p>
                            {ev.delta && (
                              <p className="text-[11px] text-[var(--muted)] mt-1">
                                {ev.delta.metric}: {ev.delta.from}% → {ev.delta.to}%
                                {ev.delta.direction === "up" && " ▲"}
                                {ev.delta.direction === "down" && " ▼"}
                              </p>
                            )}
                          </div>
                        );
                      })()}
                    </>
                  );
                })()}
              </>
            )}
          </div>

          {lastUpdateTs && (
            <div
              data-testid="goal-drawer-last-update-stamp"
              className="text-[11.5px] font-mono text-[var(--muted)]"
            >
              Akki last reassessed · {new Date(lastUpdateTs).toLocaleString(undefined, {
                dateStyle: "medium", timeStyle: "short",
              })}
            </div>
          )}

          {goal?.description && (
            <div>
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] mb-2">Description</p>
              <p className="akki-serif text-[13.5px] text-[var(--ink)] leading-snug whitespace-pre-wrap">{goal.description}</p>
            </div>
          )}

          <div data-testid="goal-drawer-timeline">
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] mb-2">Timeline</p>
            {!goal?.score_history || goal.score_history.length === 0 ? (
              <p className="text-[12.5px] text-[var(--muted)] italic">No score updates recorded yet.</p>
            ) : (
              <ol className="relative border-l border-[var(--rule)] ml-2 pl-4 space-y-3">
                {[...goal.score_history].slice(-8).reverse().map((ev, i) => (
                  <li key={i} className="text-[12.5px]">
                    <span className="absolute -left-[5px] w-2 h-2 rounded-full bg-[var(--ink)]" />
                    <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)]">
                      {ev.recorded_at?.slice(0, 10) || "—"}
                    </p>
                    <p className="text-[var(--ink)]">Score · {ev.score ?? "—"}</p>
                    {ev.note && <p className="text-[var(--muted)] italic">{ev.note}</p>}
                  </li>
                ))}
              </ol>
            )}
          </div>

          {/* QA-2026-05-16-049 — verbatim no-data copy + Document Journal link.
              Pre-fix the drawer had an "Edit this goal" button that allowed
              manual override. The spec replaces it with "Update Goal" (AI
              reassessment). On a no-data response, this block renders the
              verbatim spec copy and gives the user a one-click way to upload
              new evidence. */}
          {noDataMessage && (
            <div
              data-testid="goal-drawer-no-data"
              className="border border-amber-200 bg-amber-50 rounded-sm px-3 py-3"
            >
              <p className="text-[12.5px] text-amber-900 leading-relaxed">
                {noDataMessage}
              </p>
              <Link
                to="/app/workspace"
                data-testid="goal-drawer-no-data-doc-journal-link"
                className="inline-flex items-center gap-1 mt-2 text-[12px] underline text-amber-900 hover:text-amber-700"
              >
                <FileText className="w-3 h-3" /> Document Journal
              </Link>
            </div>
          )}

          {lastApplied && (
            <div
              data-testid="goal-drawer-just-applied"
              className="border border-emerald-200 bg-emerald-50 rounded-sm px-3 py-3"
            >
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-emerald-800 mb-1">
                Akki just updated
              </p>
              <p className="text-[12.5px] text-emerald-900 leading-relaxed">
                {lastApplied.rationale}
              </p>
            </div>
          )}

          {!isNED && (
            <div className="pt-2 border-t border-[var(--rule)]">
              {/* QA-2026-05-16-049 — "Edit this goal" → "Update Goal".
                  All manual-edit affordances are removed; this is now
                  the only way to modify the goal from the drawer. */}
              <Button
                type="button"
                onClick={onUpdateGoal}
                disabled={updating}
                aria-busy={updating}
                className="w-full inline-flex items-center justify-center"
                data-testid="goal-drawer-update-btn"
              >
                {updating
                  ? <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Updating…</>
                  : <><Sparkles className="w-3.5 h-3.5 mr-2" /> Update Goal</>}
              </Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

/**
 * ScoreBar — slim horizontal progress bar replacing the conic-gradient dial.
 * Editorial: thin track, sharp fill, value rendered to the right of the
 * label, no gradients. Empty state shown as a muted dashed track.
 */
function ScoreBar({ label, value, barClass, testId }) {
  const empty = value === null || value === undefined;
  const pct = empty ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div className="w-[150px]" data-testid={testId}>
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-[9.5px] uppercase tracking-wider text-[var(--muted)]">{label}</span>
        <span className={`akki-serif text-[14px] leading-none ${empty ? "text-[var(--muted)]" : "text-[var(--ink)]"}`}>
          {empty ? "—" : `${pct}%`}
        </span>
      </div>
      <div className={`h-1.5 rounded-sm w-full ${empty ? "border border-dashed border-[var(--rule)]" : "bg-[var(--cream-deep)]"} overflow-hidden`}>
        {!empty && (
          <div
            className={`h-full ${barClass}`}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  );
}

/**
 * ScoreMethodologyTip — discreet "How is this calculated?" affordance under
 * the dials. Hover/click reveals an editorial paragraph explaining that the
 * score is benchmarked automatically against the user's strategy document
 * and updates as new reports arrive. Replaces the earlier sparkline that
 * carried no narrative weight.
 */
function ScoreMethodologyTip() {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative mt-1.5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        className="text-[10.5px] text-[var(--muted)] hover:text-[var(--accent)] inline-flex items-center gap-1 italic underline-offset-2 hover:underline"
        data-testid="goal-score-methodology-trigger"
      >
        <Info className="w-3 h-3" /> How is this calculated?
      </button>
      {open && (
        <div
          className="absolute right-0 top-[20px] z-10 w-[280px] bg-white border border-[var(--rule)] rounded-md shadow-md p-3 text-[12px] text-[var(--deep)] leading-relaxed"
          data-testid="goal-score-methodology-popover"
          onMouseEnter={() => setOpen(true)}
          onMouseLeave={() => setOpen(false)}
        >
          <p className="akki-serif italic text-[12.5px] text-[var(--ink)] mb-1">
            The score is machine-generated.
          </p>
          <p>
            AKKI benchmarks reported performance against the strategic document
            (or any goal document) and re-scores automatically as new reports
            come in. It is not user-editable on purpose — it should reflect the
            data, not the desk that owns the goal.
          </p>
        </div>
      )}
    </div>
  );
}

function EmptyState({ contextId, onExtractOpen, modalOpen, onModalClose, onChange, fn, isNED }) {
  return (
    <section data-testid="strategic-goals-empty">
      <div className="bg-gradient-to-br from-white to-[var(--cream-deep)] border border-[var(--accent)]/20 rounded-md p-8 relative overflow-hidden">
        <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)]" />
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Target className="w-3 h-3 text-[var(--accent)]" /> Strategic goals
        </p>
        <h2 className="akki-serif text-[22px] text-[var(--ink)] leading-snug mb-3 max-w-2xl">
          {isNED
            ? "No strategic goals are being tracked yet."
            : "Upload your strategic plan. AKKI will surface the board-level goals tied to your function."}
        </h2>
        <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mb-6 max-w-2xl">
          Each goal becomes a row with a target, a current score, and a probability. {isNED
            ? "Once your executive team uploads the strategy document, the scorecard will populate here."
            : "Update the score weekly. Update the probability when assumptions change. The board will read the same view."}
        </p>
        {!isNED && (
          <div className="flex items-center gap-3 flex-wrap">
            <Button onClick={onExtractOpen} className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white" data-testid="strategic-goals-empty-cta">
              <Sparkles className="w-3.5 h-3.5 mr-2" /> Read goals from a document
            </Button>
            <Link to="/app/workspace" className="text-[13px] text-[var(--accent)] hover:underline inline-flex items-center gap-1">
              <FileText className="w-3.5 h-3.5" /> Upload a strategy doc first
            </Link>
          </div>
        )}
      </div>
      {modalOpen && (
        <ExtractFromDocModal
          contextId={contextId}
          onClose={onModalClose}
          onExtracted={() => { onModalClose(); onChange?.(); }}
        />
      )}
    </section>
  );
}

function ExtractFromDocModal({ contextId, onClose, onExtracted }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pickedId, setPickedId] = useState("");
  const [replace, setReplace] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/contexts/${contextId}/documents`);
        setDocs(data || []);
      } catch (e) { toast.error(apiErrorMessage(e)); }
      finally { setLoading(false); }
    })();
  }, [contextId]);

  const submit = async () => {
    if (!pickedId) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/strategic-goals/extract`, {
        doc_id: pickedId, replace_existing: replace,
      }, { timeout: 90000 });
      if (!data.count) {
        toast.message("AKKI couldn't find board-level goals in that document. Try a strategic plan, three-year roadmap, or a board OKR pack.");
        setBusy(false);
        return;
      }
      toast.success(`AKKI surfaced ${data.count} goal${data.count === 1 ? "" : "s"} from the strategy.`);
      onExtracted();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-md shadow-xl border border-[var(--rule)] w-full max-w-lg mx-4 p-6 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()} data-testid="goals-extract-modal">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="akki-overline mb-1">Strategic goals</p>
            <h2 className="akki-serif text-[18px] text-[var(--ink)]">Read the goals from your strategy.</h2>
          </div>
          <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--ink)]"><X className="w-4 h-4" /></button>
        </div>
        <p className="text-[12.5px] text-[var(--muted)] italic mb-4 leading-relaxed">
          Pick the strategic plan, board pack, or three-year roadmap. AKKI extracts measurable goals tied to deadlines, assigns them to a function, and seeds the tracker. You can edit each goal afterwards.
        </p>

        <div className="mb-4">
          <label className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] block mb-2">Strategy document</label>
          {loading ? (
            <p className="text-[12px] text-[var(--muted)]">Loading documents…</p>
          ) : docs.length === 0 ? (
            <p className="text-[12.5px] text-[var(--muted)] italic">
              No documents on this context yet. <Link to="/app/workspace" className="text-[var(--accent)] hover:underline">Upload one →</Link>
            </p>
          ) : (
            <div className="border border-[var(--rule)] rounded-sm max-h-60 overflow-y-auto">
              {docs.map((d) => (
                <button
                  key={d.id}
                  onClick={() => setPickedId(d.id)}
                  className={`w-full text-left px-3 py-2 border-b border-[var(--rule)] last:border-b-0 hover:bg-[var(--cream-deep)]/40 ${pickedId === d.id ? "bg-[var(--cream-deep)] border-l-2 border-l-[var(--accent)]" : ""}`}
                  data-testid={`goals-extract-doc-${d.id}`}
                >
                  <p className="text-[13px] text-[var(--ink)] truncate">{d.name}</p>
                  <p className="text-[10.5px] text-[var(--muted)]">{(d.extracted_chars / 1000).toFixed(1)}k chars</p>
                </button>
              ))}
            </div>
          )}
        </div>

        <label className="flex items-center gap-2 text-[12.5px] text-[var(--deep)] mb-4">
          <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} data-testid="goals-extract-replace" />
          Replace existing goals (otherwise new goals are added alongside)
        </label>

        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} className="text-[12px] h-8">Cancel</Button>
          <Button onClick={submit} disabled={busy || !pickedId} className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[12px] h-8" data-testid="goals-extract-submit">
            {busy ? <><Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> Reading…</> : <><Sparkles className="w-3 h-3 mr-1.5" /> Extract goals</>}
          </Button>
        </div>
      </div>
    </div>
  );
}
