/**
 * Phase AA-slice-4 (2026-05-27) — TasksInitiativesPanel
 *
 * Rich card listing for the `tasks_initiatives` Mongo collection
 * shipped in AA-slice-1, populated by AA-slice-2 (LLM extraction)
 * and AA-slice-3 (upload-modal trigger).
 *
 * Renders inside the Monitor "Tasks/Initiatives" capsule tab. The
 * Goals tab continues to mount the legacy <StrategicGoalsPanel>.
 *
 * Card anatomy (per AA-slice-4 spec):
 *   • Title (bold) + body 1-2 line truncation
 *   • Category pill (revenue/operations/people/etc.)
 *   • Status pill (on_track/at_risk/off_track/achieved/not_started)
 *   • Performance bar — status-driven RAG
 *   • Probability bar — purple bands (AA-slice-6 will refine)
 *   • Owner-role badge (clickable filter wires in AA-slice-5)
 *   • Last-reassessed relative timestamp
 *   • Provenance chip: "Extracted by Sonnet 4.5 from {doc} · {date}"
 *     IFF extracted_by === "llm". Manual rows omit it. The
 *     document name is a click-through opening the source doc
 *     drawer at `/app/documents?doc_id=…`.
 *
 * Notes:
 *   • Status filter pills mirror StrategicGoalsPanel's
 *     STATUS_FILTER_TABS so the visual rhythm matches across tabs.
 *   • Empty state copy locked per the AA-4 spec.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  Layers, AlertTriangle, CheckCircle2, FileText, Sparkles, Loader2, Plus,
} from "lucide-react";


// Status presentation — matches StrategicGoalsPanel's STATUS_STYLE
// where the tokens overlap; "not_started" replaces "abandoned" per
// the AA-1 spec.
const STATUS_STYLE = {
  on_track:    { label: "On Track",    tone: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  at_risk:     { label: "At Risk",     tone: "text-amber-700 bg-amber-50 border-amber-200" },
  off_track:   { label: "Off Track",   tone: "text-red-700 bg-red-50 border-red-200" },
  achieved:    { label: "Achieved",    tone: "text-blue-700 bg-blue-50 border-blue-200" },
  not_started: { label: "Not Started", tone: "text-[var(--ned-purple)] bg-[var(--ned-purple)]/10 border-[var(--ned-purple)]/20" },
};

const CATEGORY_LABEL = {
  revenue:    "Revenue",
  customer:   "Customer",
  product:    "Product",
  people:     "People",
  operations: "Operations",
  compliance: "Compliance",
};

const STATUS_FILTER_TABS = [
  { key: "all",         label: "All" },
  { key: "on_track",    label: "On Track" },
  { key: "at_risk",     label: "At Risk" },
  { key: "off_track",   label: "Off Track" },
  { key: "achieved",    label: "Achieved" },
  { key: "not_started", label: "Not Started" },
];


function statusBarClass(status) {
  if (status === "on_track" || status === "achieved") return "bg-emerald-600";
  if (status === "at_risk") return "bg-amber-500";
  if (status === "off_track") return "bg-[color:var(--oxblood)]";
  return "bg-slate-400";
}

function probabilityBarClass(value) {
  // AA-slice-6 (2026-05-27) — probability-bar fill bands locked to
  // brand-purple token. Three opacity tiers map to the founder's
  // mental model: high probability (≥70%) = strong purple, medium
  // (40-69%) = mid purple, low (<40%) = muted purple. We
  // deliberately stay within the brand-purple hue (no greys, no
  // amber RAG mixing) so the bar reads as "confidence in this
  // probability score", separate from the RAG performance bar.
  if (value === null || value === undefined) return "bg-[var(--ned-purple)]/15";
  if (value >= 70) return "bg-[var(--ned-purple)]";
  if (value >= 40) return "bg-[var(--ned-purple)]/60";
  return "bg-[var(--ned-purple)]/30";
}


function fmtRelative(iso) {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return null;
  }
}


function ScoreBar({ label, value, barClass, testId }) {
  const safe = typeof value === "number" ? Math.max(0, Math.min(100, value)) : null;
  return (
    <div className="flex flex-col gap-0.5 w-28" data-testid={testId}>
      <div className="flex items-center justify-between text-[10.5px] text-[var(--muted)] uppercase tracking-wider">
        <span>{label}</span>
        <span className="font-mono">{safe ?? "—"}%</span>
      </div>
      <div className="h-1 bg-slate-100 rounded-sm overflow-hidden">
        <div
          className={`h-full ${barClass}`}
          style={{ width: `${safe ?? 0}%` }}
        />
      </div>
    </div>
  );
}


function ProvenanceChip({ task, sourceDoc }) {
  // Manual entries get no chip.
  if (task.extracted_by !== "llm") return null;
  const docName = sourceDoc?.name || sourceDoc?.original_filename || "the source document";
  const docId = task.source_document_id;
  const rel = fmtRelative(task.created_at);
  return (
    <div
      className="mt-1.5 inline-flex items-center gap-1 text-[10.5px] text-[var(--muted)] italic"
      data-testid={`task-card-provenance-${task.id}`}
    >
      <Sparkles className="w-2.5 h-2.5 text-[var(--accent)]" />
      <span>Extracted by Sonnet&nbsp;4.5 from</span>
      {docId ? (
        <Link
          to={`/app/documents?doc_id=${docId}`}
          className="hover:text-[var(--accent)] hover:underline non-italic"
          data-testid={`task-card-provenance-doc-link-${task.id}`}
        >
          {docName}
        </Link>
      ) : (
        <span className="text-[var(--deep)]">{docName}</span>
      )}
      {rel && <span>·&nbsp;{rel}</span>}
    </div>
  );
}


function TaskCard({ task, sourceDoc, isLast, onOwnerClick }) {
  const status = STATUS_STYLE[task.status] || STATUS_STYLE.not_started;
  const catLabel = CATEGORY_LABEL[task.category] || "Operations";
  const lastRel = fmtRelative(task.last_reassessed_at || task.updated_at);

  return (
    <div
      className={`px-5 py-3.5 ${!isLast ? "border-b border-[var(--rule)]" : ""} hover:bg-[var(--cream-deep)]/30`}
      data-testid={`task-initiative-${task.id}`}
    >
      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span
              className="inline-block px-1.5 py-0.5 rounded-sm text-[9.5px] uppercase tracking-wider border bg-slate-50 text-slate-700 border-slate-200"
              data-testid={`task-card-category-${task.id}`}
            >
              {catLabel}
            </span>
            <h3 className="text-[14.5px] text-[var(--ink)] font-medium truncate">{task.title}</h3>
            <span
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-wider border ${status.tone}`}
              data-testid={`task-card-status-${task.id}`}
            >
              {(task.status === "on_track" || task.status === "achieved") && <CheckCircle2 className="w-2.5 h-2.5" />}
              {(task.status === "at_risk" || task.status === "off_track") && <AlertTriangle className="w-2.5 h-2.5" />}
              {status.label}
            </span>
          </div>
          {task.body && (
            <p className="text-[12.5px] text-[var(--deep)] line-clamp-2 mb-1.5">{task.body}</p>
          )}
        </div>

        <div className="flex items-center gap-6 shrink-0">
          <ScoreBar
            label="Performance"
            value={task.performance_score}
            barClass={statusBarClass(task.status)}
            testId={`task-card-perf-bar-${task.id}`}
          />
          <ScoreBar
            label="Probability"
            value={task.probability_score}
            barClass={probabilityBarClass(task.probability_score)}
            testId={`task-card-prob-bar-${task.id}`}
          />
        </div>
      </div>

      <div className="flex items-center gap-4 mt-1.5 flex-wrap text-[11.5px] text-[var(--deep)]">
        {task.owner_role && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onOwnerClick && onOwnerClick(task.owner_role); }}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm bg-[var(--cream-deep)]/60 border border-[var(--rule)] font-medium hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors cursor-pointer"
            data-testid={`task-card-owner-${task.id}`}
            title={`Filter by ${task.owner_role}`}
          >
            {task.owner_role}
          </button>
        )}
        {/* AA-slice-1 indexes `(context_id, parent_objective_id)` so
            counting child tasks is cheap. For now we surface only
            the parent linkage badge (the count rollup is a future
            refinement once parent_objective_id is populated by
            extraction or the Akki commit pipe). */}
        {task.parent_objective_id && (
          <span className="inline-flex items-center gap-1 text-[var(--muted)]" data-testid={`task-card-parent-${task.id}`}>
            <Layers className="w-3 h-3" /> Linked to a strategic goal
          </span>
        )}
        {lastRel && (
          <span className="inline-flex items-center gap-1 text-[var(--muted)]" data-testid={`task-card-last-reassessed-${task.id}`}>
            <span>Reassessed:</span> {lastRel}
          </span>
        )}
      </div>

      <ProvenanceChip task={task} sourceDoc={sourceDoc} />
    </div>
  );
}


export default function TasksInitiativesPanel({ contextId, onCountChange }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusTab, setStatusTab] = useState("all");
  // AA-slice-4 (2026-05-27 redispatch) — owner-role capsule filter.
  // `null` = "All owners" (no filter). String = exact owner_role
  // value. `"__unassigned__"` = rows with `owner_role IS NULL`
  // (Sonnet couldn't infer the owner from the source doc).
  const [ownerFilter, setOwnerFilter] = useState(null);
  // Map of source_document_id → document doc (for provenance chip).
  const [docsById, setDocsById] = useState({});
  // Distinct owner_role values present across the FULL listing — the
  // capsule row needs this *before* statusTab narrows the rows.
  const [allOwners, setAllOwners] = useState([]);
  const [hasUnassigned, setHasUnassigned] = useState(false);

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoading(true);
    try {
      // 1. Fetch the unfiltered listing for the owner capsule row.
      //    Needs to happen first so the capsules are stable even when
      //    a narrow status/owner filter is active.
      const unfiltered = await api.get(
        `/contexts/${contextId}/tasks-initiatives`,
        { params: { page_size: 200 } },
      );
      const allRows = unfiltered.data.rows || [];
      const distinct = Array.from(new Set(
        allRows.filter((r) => r.owner_role).map((r) => r.owner_role),
      )).sort();
      setAllOwners(distinct);
      setHasUnassigned(allRows.some((r) => !r.owner_role));
      // Capsule-tab badge reflects the full total (not the filtered).
      onCountChange && onCountChange(unfiltered.data.total || 0);

      // 2. Fetch the filtered listing for the card rows.
      const params = { page_size: 200 };
      if (statusTab !== "all") params.status = statusTab;
      if (ownerFilter === "__unassigned__") params.owner = "null";
      else if (ownerFilter) params.owner = ownerFilter;
      const { data } = await api.get(
        `/contexts/${contextId}/tasks-initiatives`, { params },
      );
      setRows(data.rows || []);
      setTotal(data.total || 0);

      // 3. Resolve source-doc names for the provenance chip.
      const docIds = Array.from(new Set(
        (data.rows || [])
          .filter((r) => r.extracted_by === "llm" && r.source_document_id)
          .map((r) => r.source_document_id),
      ));
      if (docIds.length) {
        try {
          const fetched = await Promise.all(docIds.map((did) =>
            api.get(`/contexts/${contextId}/documents/${did}`)
              .then((r) => r.data).catch(() => null),
          ));
          const map = {};
          fetched.forEach((d) => { if (d?.id) map[d.id] = d; });
          setDocsById(map);
        } catch {
          setDocsById({});
        }
      } else {
        setDocsById({});
      }
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [contextId, statusTab, ownerFilter, onCountChange]);
  useEffect(() => { load(); }, [load]);

  const counts = useMemo(() => {
    const c = { all: total };
    for (const t of STATUS_FILTER_TABS) {
      if (t.key === "all") continue;
      c[t.key] = rows.filter((r) => r.status === t.key).length;
    }
    return c;
  }, [rows, total]);

  const handleOwnerClick = useCallback((role) => {
    setOwnerFilter((prev) => (prev === role ? null : role));
  }, []);

  return (
    <section data-testid="tasks-initiatives-panel">
      {/* AA-slice-4 redispatch (2026-05-27) — owner-role capsule row.
          Sits ABOVE the status pills, BELOW the Monitor capsule tabs.
          Single-select; clicking the active capsule deselects (back
          to "All owners"). "Unassigned" capsule surfaces when the
          listing carries any owner_role=null rows (LLM didn't infer
          an owner). flex-nowrap + overflow-x-auto so the row never
          breaks into a second line on narrow viewports
          (Recurrence #4 lock). */}
      {(allOwners.length > 0 || hasUnassigned) && (
        <div
          className="flex items-center gap-2 mb-3 flex-nowrap overflow-x-auto"
          data-testid="tasks-owner-capsules"
        >
          <button
            type="button"
            onClick={() => setOwnerFilter(null)}
            className={`px-3 py-1 rounded-full text-[11.5px] uppercase tracking-wider border transition-colors whitespace-nowrap ${
              ownerFilter === null
                ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                : "text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)] hover:bg-[var(--cream-deep)]/40"
            }`}
            data-testid="tasks-owner-capsule-all"
          >
            All owners
          </button>
          {allOwners.map((role) => (
            <button
              key={role}
              type="button"
              onClick={() => handleOwnerClick(role)}
              className={`px-3 py-1 rounded-full text-[11.5px] uppercase tracking-wider border transition-colors whitespace-nowrap ${
                ownerFilter === role
                  ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                  : "text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)] hover:bg-[var(--cream-deep)]/40"
              }`}
              data-testid={`tasks-owner-capsule-${role}`}
            >
              {role}
            </button>
          ))}
          {hasUnassigned && (
            <button
              type="button"
              onClick={() => setOwnerFilter(
                (prev) => (prev === "__unassigned__" ? null : "__unassigned__"),
              )}
              className={`px-3 py-1 rounded-full text-[11.5px] uppercase tracking-wider border transition-colors whitespace-nowrap italic ${
                ownerFilter === "__unassigned__"
                  ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                  : "text-[var(--muted)] border-[var(--rule)] hover:border-[var(--accent)] hover:bg-[var(--cream-deep)]/40"
              }`}
              data-testid="tasks-owner-capsule-unassigned"
            >
              Unassigned
            </button>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 mb-4 flex-nowrap overflow-x-auto" data-testid="tasks-status-filters">
        {STATUS_FILTER_TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setStatusTab(t.key)}
            className={`px-3 py-1.5 rounded-full text-[12px] uppercase tracking-wider border transition-colors whitespace-nowrap ${
              statusTab === t.key
                ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                : "text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)] hover:bg-[var(--cream-deep)]/40"
            }`}
            data-testid={`tasks-status-tab-${t.key}`}
          >
            <span>{t.label}</span>
            <span
              className="ml-1.5 text-[10px] opacity-80"
              data-testid={`tasks-status-tab-${t.key}-count`}
            >
              {counts[t.key] ?? 0}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div
          className="bg-white border border-[var(--rule)] rounded-md p-12 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]"
          data-testid="tasks-loading"
        >
          <Loader2 className="w-4 h-4 inline animate-spin mr-1" /> Reading the work…
        </div>
      ) : rows.length === 0 ? (
        <div
          className="bg-white border border-[var(--rule)] rounded-md p-10 text-center"
          data-testid="tasks-empty"
        >
          <FileText className="w-5 h-5 text-[var(--muted)] mx-auto mb-2" />
          <p
            className="text-[14px] text-[var(--ink)] mb-1"
            data-testid="tasks-empty-headline"
          >
            No tasks yet
          </p>
          <p
            className="text-[12.5px] text-[var(--muted)] italic mb-4"
            data-testid="tasks-empty-helper"
          >
            Upload a document with extraction enabled to populate this view.
          </p>
          {/* AA-slice-4 redispatch — disabled `+ Add` placeholder.
              Real wiring lands in a later slice; tooltip surfaces the
              expected ship phase so the user isn't confused by the
              dead button. */}
          <button
            type="button"
            disabled
            title="Coming in AA-slice-5"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-sm text-[12.5px] text-[var(--muted)] border border-[var(--rule)] bg-white opacity-60 cursor-not-allowed"
            data-testid="tasks-empty-add-btn"
          >
            <Plus className="w-3 h-3" /> Add
          </button>
        </div>
      ) : (
        <div className="bg-white border border-[var(--rule)] rounded-md overflow-hidden" data-testid="tasks-listing">
          {rows.map((r, i) => (
            <TaskCard
              key={r.id}
              task={r}
              sourceDoc={docsById[r.source_document_id]}
              isLast={i === rows.length - 1}
              onOwnerClick={handleOwnerClick}
            />
          ))}
        </div>
      )}
    </section>
  );
}
