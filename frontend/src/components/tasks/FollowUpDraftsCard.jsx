/**
 * FollowUpDraftsCard — Phase F.2 (2026-05-26).
 *
 * Right-rail card on Task Manager that surfaces draft documents
 * (`state === "draft"`) the current user owns or contributes to.
 * Source: `GET /api/contexts/{cid}/documents/drafts` (Phase E.2
 * endpoint). 5-listing + "View more" pattern matches the other
 * right-rail cards.
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { FileText, Loader2 } from "lucide-react";


export default function FollowUpDraftsCard({ contextId, refreshKey }) {
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!contextId) { setDrafts([]); setLoading(false); return; }
    let dead = false;
    setLoading(true);
    api.get(`/contexts/${contextId}/documents/drafts`)
      .then(({ data }) => { if (!dead) setDrafts(Array.isArray(data) ? data : []); })
      .catch(() => { if (!dead) setDrafts([]); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [contextId, refreshKey]);

  const visible = expanded ? drafts : drafts.slice(0, 5);

  return (
    <section
      className="border border-[var(--rule)] bg-white rounded-sm p-4"
      data-testid="follow-up-drafts-card"
    >
      <header className="flex items-center justify-between mb-3">
        <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
          Follow Up Drafts for You
        </p>
        <span className="text-[10.5px] font-mono text-[var(--muted)]" data-testid="follow-up-drafts-count">
          {drafts.length}
        </span>
      </header>
      {loading ? (
        <p className="text-[11.5px] text-[var(--muted)] inline-flex items-center gap-1.5">
          <Loader2 className="w-3 h-3 animate-spin" /> Loading…
        </p>
      ) : drafts.length === 0 ? (
        <p className="text-[11.5px] italic text-[var(--muted)]" data-testid="follow-up-drafts-empty">
          No drafts to follow up on.
        </p>
      ) : (
        <>
          <ul className="space-y-1" data-testid="follow-up-drafts-list">
            {visible.map((d) => (
              <li key={d.id}>
                <button
                  type="button"
                  onClick={() => navigate(`/app/work-studio?doc_id=${d.id}`)}
                  className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] text-[12px] text-[var(--ink)] inline-flex items-center gap-1.5"
                  data-testid={`follow-up-drafts-row-${d.id}`}
                >
                  <FileText className="w-3 h-3 text-[var(--muted)] shrink-0" />
                  <span className="truncate">{d.name || d.original_filename || d.id}</span>
                </button>
              </li>
            ))}
          </ul>
          {drafts.length > 5 && (
            <button
              type="button"
              onClick={() => setExpanded((x) => !x)}
              className="text-[11px] font-mono text-[var(--ink)] mt-2 hover:underline"
              data-testid="follow-up-drafts-view-more"
            >
              {expanded ? "View less" : `View more (${drafts.length - 5})`}
            </button>
          )}
        </>
      )}
    </section>
  );
}
