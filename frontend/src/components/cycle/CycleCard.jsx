/**
 * CycleCard — one row in the cycle list.
 *
 * Visual hierarchy per Cycle v2 brief:
 *   Active    — ink text on parchment, full saturation
 *   Draft     — graphite border, muted
 *   Completed — quiet greyscale; archived feel
 *
 * All colours via CSS tokens; no hex literals.
 */
import React from "react";
import { Link } from "react-router-dom";
import CycleStatusBadge from "./CycleStatusBadge";


function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric", month: "short", day: "numeric",
    });
  } catch { return iso; }
}


const STATUS_TONE = {
  active:    "bg-[var(--parchment)] border-[var(--rule)] hover:border-[color:var(--oxblood)] text-[var(--ink)]",
  draft:     "bg-white border-[var(--graphite,var(--rule))]/30 hover:border-[var(--ink)] text-[var(--ink)]",
  completed: "bg-[var(--parchment-soft,var(--parchment))] border-[var(--rule)] hover:border-[var(--muted)] text-[var(--muted)]",
};


export default function CycleCard({ cycle, contextId }) {
  const status = (cycle.status || "draft").toLowerCase();
  const tone = STATUS_TONE[status] || STATUS_TONE.draft;
  const isCompleted = status === "completed";
  const isDraft = status === "draft";

  const readinessNode = isDraft && (cycle.readiness_score === null || cycle.readiness_score === undefined)
    ? <span className="text-[var(--muted)] italic">Not yet scored</span>
    : cycle.readiness_score !== null && cycle.readiness_score !== undefined
      ? <span className="font-mono">{cycle.readiness_score}%</span>
      : <span className="text-[var(--muted)] italic">—</span>;

  return (
    <Link
      to={`/app/cycle/${cycle.id}?tab=agenda`}
      data-testid={`cycle-card-${cycle.id}`}
      title={isCompleted
        ? "Compilation document can be re-generated from the Compilation tab."
        : undefined}
      className={[
        "block border rounded-sm p-4 transition-colors",
        tone,
        isCompleted ? "opacity-90" : "",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3
          className={`akki-serif ${isCompleted ? "text-[16px]" : "text-[17.5px]"} leading-tight flex-1`}
          data-testid={`cycle-card-title-${cycle.id}`}
        >
          {cycle.title}
        </h3>
        <CycleStatusBadge status={status} testId={`cycle-card-status-${cycle.id}`} />
      </div>
      <p className="akki-meta text-[11.5px] font-mono">
        Created {fmtDate(cycle.created_at)}
      </p>
      <div className="grid grid-cols-3 gap-3 mt-3 pt-3 border-t border-[var(--rule)]">
        <div>
          <p className="akki-meta text-[10.5px] uppercase tracking-[0.12em]">Readiness</p>
          <p className="text-[14px] mt-0.5" data-testid={`cycle-card-readiness-${cycle.id}`}>
            {readinessNode}
          </p>
        </div>
        <div>
          <p className="akki-meta text-[10.5px] uppercase tracking-[0.12em]">Agenda</p>
          <p className="text-[14px] mt-0.5 font-mono" data-testid={`cycle-card-agenda-count-${cycle.id}`}>
            {cycle.agenda_count ?? 0}
          </p>
        </div>
        <div>
          <p className="akki-meta text-[10.5px] uppercase tracking-[0.12em]">Contributors</p>
          <p className="text-[14px] mt-0.5 font-mono" data-testid={`cycle-card-contrib-count-${cycle.id}`}>
            {cycle.contributor_count ?? 0}
          </p>
        </div>
      </div>
    </Link>
  );
}
