/**
 * RecentTaskActivityCard — Phase F.6 (2026-05-26).
 *
 * Account-scoped task activity feed on the Task Manager right rail.
 * Fixes the gap surfaced after F.5: task audit rows without
 * `context_id` weren't appearing in the context-scoped activity feed.
 *
 * Source: `GET /api/accounts/{account_id}/task-activity/recent`.
 *
 * Visual harmonization — same chrome as FollowUpDraftsCard +
 * CompilationRail's Recent Drafts/Activity decks (Phase B/E.2
 * canonical pattern).
 */
import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { Activity, Loader2, ArrowRight } from "lucide-react";


function fmtRelDays(iso) {
  if (!iso) return "—";
  try {
    const ms = new Date(iso).getTime();
    if (Number.isNaN(ms)) return "—";
    const d = Math.floor((Date.now() - ms) / (1000 * 60 * 60 * 24));
    if (d < 1) return "today";
    if (d < 30) return `${d}d`;
    if (d < 365) return `${Math.floor(d / 30)}mo`;
    return `${Math.floor(d / 365)}y`;
  } catch { return "—"; }
}


function actionVerb(action) {
  // Map "task.compile.commit.completed" → "committed", etc.
  if (!action) return "event";
  const segs = action.split(".");
  return segs[segs.length - 1] || segs[segs.length - 2] || "event";
}


const ROW_LIMIT = 5;
const BODY_MIN_HEIGHT = 144;


export default function RecentTaskActivityCard({ refreshKey }) {
  const navigate = useNavigate();
  const [, setParams] = useSearchParams();
  const { account } = useAuth();
  const aid = account?.id;
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!aid) { setRows([]); setLoading(false); return; }
    let dead = false;
    setLoading(true);
    api.get(`/accounts/${aid}/task-activity/recent`, { params: { limit: 25 } })
      .then(({ data }) => { if (!dead) setRows(Array.isArray(data) ? data : []); })
      .catch(() => { if (!dead) setRows([]); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [aid, refreshKey]);

  const visible = rows.slice(0, ROW_LIMIT);

  const openTask = (tid) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("task_id", tid);
      return next;
    }, { replace: false });
  };

  return (
    <section
      className="border border-[var(--rule)] bg-white rounded-sm"
      data-testid="recent-task-activity-card"
    >
      <header className="px-3 py-2 border-b border-[var(--rule)] flex items-center gap-1.5">
        <Activity className="w-3 h-3 text-[var(--deep)]" strokeWidth={1.7} />
        <p className="akki-overline text-[10.5px] tracking-[0.16em] text-[var(--ink)]">
          Recent task activity
        </p>
        <span
          className="ml-auto text-[10.5px] font-mono text-[var(--muted)]"
          data-testid="recent-task-activity-count"
        >
          {rows.length}
        </span>
        {loading && <Loader2 className="w-3 h-3 animate-spin text-[var(--muted)]" />}
      </header>
      <div
        className="p-2.5 overflow-hidden"
        style={{ minHeight: BODY_MIN_HEIGHT, maxHeight: BODY_MIN_HEIGHT }}
      >
        {loading ? null : rows.length === 0 ? (
          <p
            className="text-[12px] text-[var(--muted)] italic px-1"
            data-testid="recent-task-activity-empty"
          >
            No task activity yet.
          </p>
        ) : (
          <ul className="space-y-1.5" data-testid="recent-task-activity-list">
            {visible.map((r) => (
              <li key={r.id} className="text-[12px]">
                <button
                  type="button"
                  onClick={() => openTask(r.task_id)}
                  className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] flex items-center gap-2"
                  data-testid={`recent-task-activity-row-${r.id}`}
                >
                  <span className="flex-1 min-w-0 truncate text-[var(--ink)]">
                    {r.task_name}
                  </span>
                  <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] shrink-0">
                    {actionVerb(r.action)}
                  </span>
                  <span className="font-mono text-[11px] text-[var(--muted)] shrink-0 w-8 text-right">
                    {fmtRelDays(r.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <footer className="px-3 py-2 border-t border-[var(--rule)] bg-[var(--cream-deep)]/40">
        <button
          type="button"
          onClick={() => navigate("/app/task-manager/activity")}
          className="text-[11.5px] text-[var(--deep)] hover:text-[var(--ink)] inline-flex items-center gap-1 transition-colors"
          data-testid="recent-task-activity-view-more"
        >
          View more <ArrowRight className="w-3 h-3" strokeWidth={1.7} />
        </button>
      </footer>
    </section>
  );
}
