/**
 * CycleCard — Patch 2B.1 full-width row.
 *
 * Layout (desktop, single horizontal line):
 *   [ Title (prominent) ]  [ Status badge ]  [ READINESS % ]  [ Created date ]
 *   [ Intel strip: Agenda · N · Team · N · Last activity · X ago · Next · hint ]
 *   [ Chevron → ]
 *
 * Narrow (<768px) viewports: title row on top, then status/readiness/date
 * stack under title, intel strip wraps. Same row rhythm as Work Studio rows.
 *
 * Visual hierarchy:
 *   Active    — ink text on parchment
 *   Draft     — muted border, ink
 *   Completed — quiet greyscale; archived feel
 *
 * All colours via CSS tokens. No hex literals.
 */
import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
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
  active:    "bg-white border-[var(--rule)] hover:border-[color:var(--oxblood)] text-[var(--ink)]",
  draft:     "bg-white border-[var(--rule)] hover:border-[var(--ink)] text-[var(--ink)]",
  completed: "bg-[var(--parchment)] border-[var(--rule)] hover:border-[var(--muted)] text-[var(--muted)]",
};


export default function CycleCard({ cycle, highlight = false }) {
  const status = (cycle.status || "draft").toLowerCase();
  const tone = STATUS_TONE[status] || STATUS_TONE.draft;
  const isCompleted = status === "completed";

  const agendaCount = cycle.agenda_count ?? 0;
  const teamCount = cycle.team_count ?? cycle.contributor_count ?? 0;
  const readiness = (typeof cycle.readiness_pct === "number") ? cycle.readiness_pct : null;
  const hasAgenda = agendaCount > 0;

  return (
    <Link
      to={`/app/cycle/${cycle.id}?tab=agenda`}
      data-testid={`cycle-card-${cycle.id}`}
      data-pulse={highlight ? "true" : undefined}
      title={isCompleted
        ? "Compilation document can be re-generated from the Compilation tab."
        : undefined}
      className={[
        "group block border rounded-sm px-5 py-4 w-full",
        "transition-colors duration-150",
        tone,
        isCompleted ? "opacity-90" : "",
        /* T1.6 (2026-05-25) — D6 step 5: pulse the just-attached card
           in the platform accent colour for ~1.5 s before settling. The
           `.cycle-card-pulse` keyframe lives in index.css. */
        highlight ? "cycle-card-pulse" : "",
      ].join(" ")}
    >
      {/* Top line: title (flex-grow) + status badge + readiness + created date + chevron */}
      <div className="flex items-start md:items-center gap-3 md:gap-5 flex-col md:flex-row">
        {/* Title — prominent, flex-grow */}
        <h3
          className={`akki-serif ${isCompleted ? "text-[16px]" : "text-[17px]"} leading-tight flex-1 min-w-0 md:truncate`}
          data-testid={`cycle-card-title-${cycle.id}`}
        >
          {cycle.title}
          {/* P5.20.1 (2026-02) — default-inbox badge on list rows.
              Parity with the cycle detail page badge from P5.20. The
              `is_default_inbox_cycle` flag flows straight through
              `_hydrate_cycle` so no serializer change was needed. */}
          {cycle.is_default_inbox_cycle && (
            <span
              className="ml-2 inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded-sm border bg-amber-50 text-amber-800 border-amber-300 align-middle"
              data-testid="cycle-default-inbox-badge"
              title="Auto-scaffolded cycle for inbound email routing."
            >
              <span aria-hidden>✉</span> default inbox
            </span>
          )}
        </h3>

        {/* Status badge — fixed slot */}
        <div className="shrink-0">
          <CycleStatusBadge status={status} testId={`cycle-card-status-${cycle.id}`} />
        </div>

        {/* Readiness % — JetBrains Mono numeral + small READINESS label */}
        <div
          className="shrink-0 inline-flex items-baseline gap-1.5"
          data-testid={`cycle-card-readiness-${cycle.id}`}
        >
          {hasAgenda ? (
            <span className="font-mono text-[14px] text-[var(--ink)] tabular-nums">
              {readiness ?? 0}%
            </span>
          ) : (
            <span className="text-[12px] text-[var(--muted)] italic">Not yet scored</span>
          )}
          <span className="text-[9.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
            Readiness
          </span>
        </div>

        {/* Created date — fixed slot */}
        <p
          className="shrink-0 akki-meta text-[11.5px] font-mono text-[var(--muted)]"
          data-testid={`cycle-card-created-${cycle.id}`}
        >
          Created {fmtDate(cycle.created_at)}
        </p>

        {/* Chevron */}
        <ArrowRight
          className="shrink-0 w-3.5 h-3.5 text-[var(--muted)] group-hover:text-[var(--ink)] transition-colors hidden md:inline-block"
          strokeWidth={1.7}
          aria-hidden="true"
        />
      </div>

      {/* Intel strip — monitor-style metadata under the top line */}
      <p
        className="mt-2.5 pt-2.5 border-t border-[var(--rule)] text-[11.5px] text-[var(--muted)] font-mono leading-relaxed"
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
