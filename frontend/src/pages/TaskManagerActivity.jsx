/**
 * TaskManagerActivity — Phase F.6 (2026-05-26).
 *
 * Full-page account-scoped task activity feed. Mirrors the
 * Work Studio Activity surface pattern. Mounted at
 * `/app/task-manager/activity`.
 *
 * Source: `GET /api/accounts/{account_id}/task-activity/recent?limit=200`.
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Loader2, Inbox, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";


function fmtTime(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}


function actionLabel(action) {
  if (!action) return "event";
  return action.replace(/^task\./, "").replace(/\./g, " · ").replace(/_/g, " ");
}


export default function TaskManagerActivity() {
  const navigate = useNavigate();
  const { account } = useAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!account?.id) return;
    let dead = false;
    setLoading(true);
    api.get(`/accounts/${account.id}/task-activity/recent`, { params: { limit: 200 } })
      .then(({ data }) => { if (!dead) setRows(Array.isArray(data) ? data : []); })
      .catch(() => { if (!dead) setRows([]); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [account?.id]);

  return (
    <AppShell>
      <main className="akki-w-medium py-8" data-testid="task-manager-activity-page">
        <Button
          variant="ghost" size="sm"
          onClick={() => navigate("/app/task-manager")}
          className="mb-4"
          data-testid="task-manager-activity-back"
        >
          <ArrowLeft className="w-3 h-3 mr-1.5" /> Back to Task Manager
        </Button>
        <header className="mb-6">
          <p className="text-[11px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] mb-1.5">
            Task Manager · Activity
          </p>
          <h1 className="akki-serif text-[24px] text-[var(--ink)] leading-tight">
            All task events
          </h1>
        </header>
        {loading ? (
          <p className="text-[12px] text-[var(--muted)] inline-flex items-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin" /> Loading…
          </p>
        ) : rows.length === 0 ? (
          <div className="text-center py-12" data-testid="task-manager-activity-empty">
            <Inbox className="w-6 h-6 text-[var(--muted)] mx-auto mb-2" strokeWidth={1.5} />
            <p className="text-[12.5px] italic text-[var(--muted)]">
              No task activity yet.
            </p>
          </div>
        ) : (
          <ul
            className="border border-[var(--rule)] bg-white rounded-sm divide-y divide-[var(--rule)]"
            data-testid="task-manager-activity-list"
          >
            {rows.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => r.task_id && navigate(`/app/task-manager?task_id=${r.task_id}`)}
                  disabled={!r.task_id}
                  className="w-full text-left px-4 py-3 hover:bg-[var(--parchment)] disabled:opacity-60"
                  data-testid={`task-manager-activity-row-${r.id}`}
                >
                  <div className="flex items-center gap-3">
                    <span className="text-[13px] text-[var(--ink)] flex-1 min-w-0 truncate">
                      {r.task_name}
                    </span>
                    <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] shrink-0">
                      {actionLabel(r.action)}
                    </span>
                    <span className="font-mono text-[11px] text-[var(--muted)] shrink-0">
                      {fmtTime(r.created_at)}
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </main>
    </AppShell>
  );
}
