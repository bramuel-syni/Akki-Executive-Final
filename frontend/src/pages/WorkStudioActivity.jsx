/**
 * WorkStudioActivity — Phase E.2 (2026-05-26).
 *
 * Full-page view of the unified Recent Activity feed surfaced as the
 * right-rail card on /app/work-studio. Same data source
 * (GET /api/contexts/{cid}/activity/recent) but with a higher row
 * limit and a fuller layout.
 *
 * Renders one row per audit event:
 *   <timestamp> · <doc title or action label> · <action verb> · <actor>
 *
 * Empty state when no rows. Click on a row with a `doc_id` navigates
 * back to Work Studio with `?doc_id=…` (drawer-deep-link contract
 * landing in E.3).
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import WorkspaceEntryGate from "@/components/transitions/WorkspaceEntryGate";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { RefreshCw, ChevronLeft, Loader2 } from "lucide-react";


function fmtAbs(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  } catch { return "—"; }
}


function ActivityRowItem({ row, onOpen }) {
  return (
    <button
      type="button"
      onClick={() => row.doc_id && onOpen(row.doc_id)}
      disabled={!row.doc_id}
      className="w-full text-left px-3 py-2.5 border border-[var(--rule)] rounded-sm bg-white hover:border-[var(--ink)] hover:bg-[var(--parchment)] transition-colors flex items-center gap-3 disabled:opacity-70 disabled:cursor-default"
      data-testid="work-studio-activity-row"
    >
      <RefreshCw className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" strokeWidth={1.7} />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] text-[var(--ink)] truncate">
          {row.doc_title || row.action || "—"}
        </p>
        <div className="text-[11px] text-[var(--muted)] mt-0.5 flex items-center gap-2 flex-wrap">
          <span className="font-mono uppercase tracking-[0.12em]" data-testid="work-studio-activity-row-action">
            {(row.action || "").split(".").slice(-2).join(".")}
          </span>
          <span>·</span>
          <span data-testid="work-studio-activity-row-actor">{row.actor_id || "system"}</span>
          <span>·</span>
          <span className="font-mono" data-testid="work-studio-activity-row-time">{fmtAbs(row.created_at)}</span>
        </div>
      </div>
    </button>
  );
}


function WorkStudioActivityInner() {
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const cid = activeContext?.id || null;
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!cid) return;
    let dead = false;
    setLoading(true);
    api
      .get(`/contexts/${cid}/activity/recent`, { params: { limit: 100 } })
      .then(({ data }) => { if (!dead) setRows(Array.isArray(data) ? data : []); })
      .catch(() => { if (!dead) setRows([]); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [cid]);

  return (
    <div className="akki-w-medium akki-vmedium" data-testid="work-studio-activity-page">
      <div className="pt-6">
        <button
          type="button"
          onClick={() => navigate("/app/work-studio")}
          className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1.5 mb-4"
          data-testid="work-studio-activity-back"
        >
          <ChevronLeft className="w-3.5 h-3.5" strokeWidth={1.7} /> Work Studio
        </button>
        <h1 className="text-[20px] text-[var(--ink)] mb-1" data-testid="work-studio-activity-title">
          Recent activity
        </h1>
        <p className="text-[12.5px] text-[var(--muted)] mb-4">
          Every audit event scoped to this workspace.
        </p>
        {loading ? (
          <p className="text-[12px] text-[var(--muted)] inline-flex items-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin" /> Loading…
          </p>
        ) : rows.length === 0 ? (
          <p className="text-[12.5px] text-[var(--muted)] italic" data-testid="work-studio-activity-empty">
            No activity yet.
          </p>
        ) : (
          <ul className="space-y-2" data-testid="work-studio-activity-list">
            {rows.map((r) => (
              <li key={r.id}>
                <ActivityRowItem
                  row={r}
                  onOpen={(docId) => navigate(`/app/work-studio?doc_id=${docId}`)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}


export default function WorkStudioActivity() {
  return (
    <AppShell>
      <WorkspaceEntryGate>
        <WorkStudioActivityInner />
      </WorkspaceEntryGate>
    </AppShell>
  );
}
