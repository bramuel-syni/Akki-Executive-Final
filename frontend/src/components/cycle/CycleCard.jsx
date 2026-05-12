/**
 * CycleCard — Cycle Manager Feel pass (Patch 2 of 4).
 *
 * Visual contract (top → bottom):
 *   1. Title (prominent)
 *   2. Status badge (Active / Draft / Completed)
 *   3. Readiness % — "Not yet scored" for empty drafts
 *   4. Date created
 *   5. Intel row — Monitor-style metadata strip:
 *        Agenda · N · Team · N · Last activity · {rel} · Next · {hint}
 *
 * Visual hierarchy per v2 brief:
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

function fmtRelative(iso) {
  if (!iso) return "—";
  try {
    const then = new Date(iso).getTime();
    const now = Date.now();
    const diff = Math.max(0, now - then);
    const min = Math.floor(diff / 60000);
    if (min < 1) return "just now";
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    const day = Math.floor(hr / 24);
    if (day === 1) return "1 day ago";
    if (day < 30) return `${day} days ago`;
    const mo = Math.floor(day / 30);
    if (mo === 1) return "1 month ago";
    if (mo < 12) return `${mo} months ago`;
    const yr = Math.floor(mo / 12);
    return yr === 1 ? "1 year ago" : `${yr} years ago`;
  } catch { return "—"; }
}


const STATUS_TONE = {
  active:    "bg-[var(--parchment)] border-[var(--rule)] hover:border-[color:var(--oxblood)] text-[var(--ink)]",
  draft:     "bg-white border-[var(--graphite,var(--rule))]/30 hover:border-[var(--ink)] text-[var(--ink)]",
  completed: "bg-[var(--parchment-soft,var(--parchment))] border-[var(--rule)] hover:border-[var(--muted)] text-[var(--muted)]",
};


export default function CycleCard({ cycle }) {
  const status = (cycle.status || "draft").toLowerCase();
  const tone = STATUS_TONE[status] || STATUS_TONE.draft;
  const isCompleted = status === "completed";

  const agendaCount = cycle.agenda_count ?? 0;
  const teamCount = cycle.team_count ?? cycle.contributor_count ?? 0;
  // Readiness — backend-computed; null/undefined → "Not yet scored".
  const readiness = (typeof cycle.readiness_pct === "number") ? cycle.readiness_pct : null;
  const hasAgenda = agendaCount > 0;
  const readinessNode = (!hasAgenda)
    ? <span className="text-[var(--muted)] italic">Not yet scored</span>
    : <span className="font-mono">{readiness ?? 0}%</span>;

  return (
    <Link
      to={`/app/cycle/${cycle.id}?tab=agenda`}
      data-testid={`cycle-card-${cycle.id}`}
      title={isCompleted
        ? "Compilation document can be re-generated from the Compilation tab."
        : undefined}
      className={[
        "block border rounded-sm px-4 py-3.5",
        "transition-colors duration-150",
        tone,
        isCompleted ? "opacity-90" : "",
      ].join(" ")}
    >
      {/* Title + Status */}
      <div className="flex items-start justify-between gap-3 mb-2">
        <h3
          className={`akki-serif ${isCompleted ? "text-[15.5px]" : "text-[17px]"} leading-tight flex-1`}
          data-testid={`cycle-card-title-${cycle.id}`}
        >
          {cycle.title}
        </h3>
        <CycleStatusBadge status={status} testId={`cycle-card-status-${cycle.id}`} />
      </div>

      {/* Readiness % */}
      <p
        className="text-[13px] mb-1"
        data-testid={`cycle-card-readiness-${cycle.id}`}
      >
        <span className="akki-meta text-[10.5px] uppercase tracking-[0.12em] mr-2">Readiness</span>
        {readinessNode}
      </p>

      {/* Date created */}
      <p className="akki-meta text-[11.5px] font-mono mb-3">
        Created {fmtDate(cycle.created_at)}
      </p>

      {/* Intel row — Monitor-style */}
      <p
        className="border-t border-[var(--rule)] pt-2 text-[11.5px] text-[var(--muted)] font-mono leading-relaxed"
        data-testid={`cycle-card-intel-${cycle.id}`}
      >
        <span data-testid={`cycle-card-intel-agenda-${cycle.id}`}>Agenda · {agendaCount}</span>
        <span className="mx-1.5 opacity-50">·</span>
        <span data-testid={`cycle-card-intel-team-${cycle.id}`}>Team · {teamCount}</span>
        <span className="mx-1.5 opacity-50">·</span>
        <span data-testid={`cycle-card-intel-last-${cycle.id}`}>
          Last activity · {fmtRelative(cycle.last_activity_at || cycle.updated_at || cycle.created_at)}
        </span>
        <span className="mx-1.5 opacity-50">·</span>
        <span
          className="text-[var(--ink)]"
          data-testid={`cycle-card-intel-next-${cycle.id}`}
        >
          Next · {cycle.next_action_hint || "—"}
        </span>
      </p>
    </Link>
  );
}
