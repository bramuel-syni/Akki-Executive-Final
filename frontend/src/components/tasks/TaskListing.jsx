/**
 * TaskListing — Phase F.2 (2026-05-26) · F.3 patched 2026-05-26.
 *
 * Renders the list of task cards for the active sort tab. Calls
 * `GET /api/tasks?state=<tab>`. Each card shows: title · objective
 * (truncated) · readiness score · contributor avatars · due date ·
 * status pill.
 *
 * F.3: clicking a task card now sets `?task_id=<id>` on the URL —
 * the <TaskDrawer> mounted on TaskManager opens automatically.
 */
import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Loader2, Calendar, Users, FileText, Inbox } from "lucide-react";
import { toast } from "sonner";


function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}


function StatusPill({ state }) {
  const map = {
    active: { label: "Active", cls: "text-[var(--ink)] bg-[var(--cream-deep)]" },
    draft:  { label: "Draft",  cls: "text-[var(--oxblood)] bg-[rgba(122,46,46,0.10)]" },
    closed: { label: "Closed", cls: "text-[var(--muted)] bg-[var(--parchment)]" },
  };
  const m = map[state] || map.active;
  return (
    <span
      className={`px-1.5 py-0.5 rounded-sm text-[10px] uppercase tracking-[0.14em] font-mono ${m.cls}`}
      data-testid={`task-card-status-${state}`}
    >
      {m.label}
    </span>
  );
}


function ContributorAvatars({ team }) {
  const first = (team || []).slice(0, 4);
  const extra = Math.max(0, (team || []).length - first.length);
  if (first.length === 0) {
    return <span className="text-[11px] italic text-[var(--muted)]">No team</span>;
  }
  return (
    <div className="flex -space-x-1.5">
      {first.map((m, i) => (
        <span
          key={i}
          title={m.name || m.email}
          className="w-6 h-6 rounded-full bg-[var(--cream-deep)] border border-white text-[10px] font-mono flex items-center justify-center text-[var(--ink)]"
        >
          {(m.name || m.email || "?").slice(0, 1).toUpperCase()}
        </span>
      ))}
      {extra > 0 && (
        <span className="w-6 h-6 rounded-full bg-[var(--parchment)] border border-white text-[10px] font-mono flex items-center justify-center text-[var(--muted)]">
          +{extra}
        </span>
      )}
    </div>
  );
}


export default function TaskListing({ contextId, state, refreshKey }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [, setParams] = useSearchParams();
  const { account } = useAuth();
  const myEmail = (account?.email || "").toLowerCase();

  useEffect(() => {
    let dead = false;
    setLoading(true);
    const params = { state };
    if (contextId) params.context_id = contextId;
    api.get("/tasks", { params })
      .then(({ data }) => { if (!dead) setTasks(Array.isArray(data) ? data : []); })
      .catch((e) => {
        if (!dead) { setTasks([]); toast.error(apiErrorMessage(e)); }
      })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [contextId, state, refreshKey]);

  // F.3: card click opens the drawer via `?task_id=<id>`.
  const openTask = (taskId) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("task_id", taskId);
      return next;
    }, { replace: false });
  };

  if (loading) {
    return (
      <div
        className="text-[12px] text-[var(--muted)] inline-flex items-center gap-1.5"
        data-testid="task-listing-loading"
      >
        <Loader2 className="w-3 h-3 animate-spin" /> Loading…
      </div>
    );
  }
  if (tasks.length === 0) {
    return (
      <div className="text-center py-12" data-testid={`task-listing-empty-${state}`}>
        <Inbox className="w-6 h-6 text-[var(--muted)] mx-auto mb-2" strokeWidth={1.5} />
        <p className="text-[12.5px] italic text-[var(--muted)]">
          {state === "active" && "No active tasks. Click \u201CSet up new task\u201D to get started."}
          {state === "draft" && "No draft tasks. Drafts you save without commissioning land here."}
          {state === "closed" && "No closed tasks yet."}
        </p>
      </div>
    );
  }

  return (
    <>
      <ul className="space-y-3" data-testid="task-listing-list">
        {tasks.map((t) => {
          // Wave 4.1 (2026-05-27) — compute the "attention pill" the
          // user-facing card surfaces in the top-right. Currently only
          // "Needs your input" qualifies; future signals (overdue,
          // blocked, etc.) hang off the same slot.
          const me = myEmail
            ? (t.team || []).find((m) => (m.email || "").toLowerCase() === myEmail)
            : null;
          const needsInput = me && ["not_started", "in_progress"].includes(me.status || "not_started");
          // Active rows take the brand-purple highlight (token from
          // index.css `--ned-purple`, Phase A Role-chip purple — not a
          // new colour).
          const isActiveRow = t.state === "active";
          return (
          <li key={t.id}>
            <button
              type="button"
              onClick={() => openTask(t.id)}
              className={[
                "w-full text-left p-4 border bg-white rounded-sm transition-colors",
                isActiveRow
                  ? "border-[color:var(--ned-purple)]/40 hover:border-[color:var(--ned-purple)] hover:bg-[color:var(--ned-purple)]/5"
                  : "border-[var(--rule)] hover:border-[var(--ink)]",
              ].join(" ")}
              data-testid={`task-card-${t.id}`}
              data-card-kind="task"
              data-active-highlight={isActiveRow ? "true" : "false"}
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="flex-1 min-w-0">
                  <p className="akki-serif text-[15px] text-[var(--ink)] leading-tight">
                    {t.name || "Untitled task"}
                  </p>
                </div>
                {/* Wave 4.1 (2026-05-27) — Top-right cluster:
                    [attention pill | Active pill]  with readiness sitting
                    immediately under the Active pill. The attention pill
                    is positioned LEFT of the state pill per the spec. */}
                <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                  <div className="flex items-center gap-1.5">
                    {needsInput && (
                      <span
                        className="inline-flex items-center gap-1.5 text-[10.5px] font-mono uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-sm bg-amber-50 text-amber-800"
                        data-testid={`task-card-needs-your-input-${t.id}`}
                      >
                        Needs your input
                      </span>
                    )}
                    <StatusPill state={t.state} />
                  </div>
                  <span
                    className="inline-flex items-center gap-1 text-[11px] text-[var(--muted)]"
                    data-testid={`task-card-readiness-${t.id}`}
                  >
                    <span className="font-mono text-[var(--ink)]">{t.readiness_score ?? 0}%</span>
                    <span>readiness</span>
                  </span>
                </div>
              </div>
              {t.objective && (
                <p className="text-[12.5px] text-[var(--deep)] line-clamp-2 mb-3">
                  {t.objective}
                </p>
              )}
              <div className="flex items-center gap-4 text-[11.5px] text-[var(--muted)]">
                <span className="inline-flex items-center gap-1">
                  <Users className="w-3 h-3" strokeWidth={1.7} />
                  <ContributorAvatars team={t.team} />
                </span>
                {t.due_date && (
                  <span className="inline-flex items-center gap-1 ml-auto">
                    <Calendar className="w-3 h-3" strokeWidth={1.7} />
                    {fmtDate(t.due_date)}
                  </span>
                )}
              </div>
              {/* Phase F.4 enhancement — Compile session pill on the card */}
              {t.compile_session?.active && t.compile_session?.current_stage && (
                <div
                  className="mt-2 inline-flex items-center gap-1.5 text-[10.5px] font-mono uppercase tracking-[0.14em] px-1.5 py-0.5 rounded-sm bg-[rgba(122,46,46,0.08)] text-[var(--oxblood)]"
                  data-testid={`task-card-compile-pill-${t.id}`}
                >
                  <span>Compile · {(t.compile_session.current_stage || "").replace(/_/g, " ")}</span>
                </div>
              )}
            </button>
          </li>
          );
        })}
      </ul>
    </>
  );
}
