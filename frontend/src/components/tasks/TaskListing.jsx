/**
 * TaskListing — Phase F.2 (2026-05-26).
 *
 * Renders the list of task cards for the active sort tab. Calls
 * `GET /api/tasks?state=<tab>`. Each card shows: title · objective
 * (truncated) · readiness score · contributor avatars · due date ·
 * status pill.
 *
 * F.3 deferred: clicking a task card opens a placeholder "Task drawer
 * coming soon" sheet. The drawer surface ships in F.3.
 */
import React, { useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Sheet, SheetContent } from "@/components/ui/sheet";
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


export default function TaskListing({ contextId, state, refreshKey, activeTaskId }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openTask, setOpenTask] = useState(null);

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

  // Open the drawer placeholder if a `task_id` URL param is set.
  useEffect(() => {
    if (!activeTaskId || tasks.length === 0) return;
    const found = tasks.find((t) => t.id === activeTaskId);
    if (found) setOpenTask(found);
  }, [activeTaskId, tasks]);

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
        {tasks.map((t) => (
          <li key={t.id}>
            <button
              type="button"
              onClick={() => setOpenTask(t)}
              className="w-full text-left p-4 border border-[var(--rule)] bg-white rounded-sm hover:border-[var(--ink)] transition-colors"
              data-testid={`task-card-${t.id}`}
            >
              <div className="flex items-start justify-between gap-3 mb-2">
                <p className="akki-serif text-[15px] text-[var(--ink)] leading-tight">
                  {t.name || "Untitled task"}
                </p>
                <StatusPill state={t.state} />
              </div>
              {t.objective && (
                <p className="text-[12.5px] text-[var(--deep)] line-clamp-2 mb-3">
                  {t.objective}
                </p>
              )}
              <div className="flex items-center gap-4 text-[11.5px] text-[var(--muted)]">
                <span className="inline-flex items-center gap-1" data-testid={`task-card-readiness-${t.id}`}>
                  <span className="font-mono text-[var(--ink)]">{t.readiness_score ?? 0}</span>
                  <span>readiness</span>
                </span>
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
            </button>
          </li>
        ))}
      </ul>

      {/* F.3 — Task Drawer is the next sub-phase. Placeholder for now. */}
      <Sheet open={!!openTask} onOpenChange={(o) => !o && setOpenTask(null)}>
        <SheetContent
          side="right"
          className="w-full sm:max-w-[60vw] p-0 flex flex-col"
          data-testid="task-drawer-placeholder"
        >
          <div className="px-6 py-5 border-b border-[var(--rule)] flex items-start justify-between">
            <div>
              <p className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)]">
                Task
              </p>
              <h2 className="akki-serif text-[20px] text-[var(--ink)] mt-0.5">
                {openTask?.name || "—"}
              </h2>
            </div>
            <StatusPill state={openTask?.state} />
          </div>
          <div className="p-6 space-y-4 flex-1 overflow-y-auto">
            {openTask?.objective && (
              <section>
                <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Objective</p>
                <p className="text-[13px] text-[var(--ink)] leading-relaxed">{openTask.objective}</p>
              </section>
            )}
            {openTask?.success_criteria && (
              <section>
                <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Success criteria</p>
                <p className="text-[13px] text-[var(--ink)] leading-relaxed">{openTask.success_criteria}</p>
              </section>
            )}
            <section className="border-t border-[var(--rule)] pt-4 mt-2">
              <p
                className="text-[12.5px] italic text-[var(--muted)]"
                data-testid="task-drawer-coming-soon"
              >
                Task drawer with full intelligence, compile flow, and contributor activity is the next sub-phase (F.3). For now this drawer shows the captured spec.
              </p>
            </section>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
