/**
 * FollowUpDraftsCard — Phase F.2 (2026-05-26) · F.6 visual harmonization 2026-05-26.
 *
 * Right-rail card on Task Manager. Surfaces draft documents
 * (`state === "draft"`) the current user owns or contributes to.
 * Source: `GET /api/contexts/{cid}/documents/drafts` (E.2 endpoint).
 *
 * F.6 — restyled to match the canonical Home 2 / CompilationRail card
 * pattern: bordered section + icon-label header + 5-row clipped body
 * + "View more →" footer. Same chrome as Recent Drafts / Recent
 * Activity.
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { FileText, Loader2, ArrowRight } from "lucide-react";


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


const ROW_LIMIT = 5;
const BODY_MIN_HEIGHT = 144;  // matches CompilationRail's 5-row clip


export default function FollowUpDraftsCard({ contextId, refreshKey }) {
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState([]);
  const [loading, setLoading] = useState(true);

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

  const visible = drafts.slice(0, ROW_LIMIT);

  return (
    <section
      className="border border-[var(--rule)] bg-white rounded-sm"
      data-testid="follow-up-drafts-card"
    >
      <header className="px-3 py-2 border-b border-[var(--rule)] flex items-center gap-1.5">
        <FileText className="w-3 h-3 text-[var(--deep)]" strokeWidth={1.7} />
        <p className="akki-overline text-[10.5px] tracking-[0.16em] text-[var(--ink)]">
          Follow up drafts for you
        </p>
        <span
          className="ml-auto text-[10.5px] font-mono text-[var(--muted)]"
          data-testid="follow-up-drafts-count"
        >
          {drafts.length}
        </span>
        {loading && <Loader2 className="w-3 h-3 animate-spin text-[var(--muted)]" />}
      </header>
      <div
        className="p-2.5 overflow-hidden"
        style={{ minHeight: BODY_MIN_HEIGHT, maxHeight: BODY_MIN_HEIGHT }}
      >
        {loading ? null : drafts.length === 0 ? (
          <p
            className="text-[12px] text-[var(--muted)] italic px-1"
            data-testid="follow-up-drafts-empty"
          >
            No drafts to follow up on.
          </p>
        ) : (
          <ul className="space-y-1.5" data-testid="follow-up-drafts-list">
            {visible.map((d) => (
              <li key={d.id} className="text-[12.5px]">
                <button
                  type="button"
                  onClick={() => navigate(`/app/work-studio?doc_id=${d.id}`)}
                  className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] flex items-center gap-2"
                  data-testid={`follow-up-drafts-row-${d.id}`}
                  data-card-kind="follow-up-draft"
                >
                  <span className="flex-1 min-w-0 truncate text-[var(--ink)]">
                    {d.name || d.original_filename || d.id}
                  </span>
                  <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--oxblood)] shrink-0">
                    DRAFT
                  </span>
                  <span className="font-mono text-[11px] text-[var(--muted)] shrink-0 w-8 text-right">
                    {fmtRelDays(d.updated_at || d.created_at)}
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
          onClick={() => navigate("/app/work-studio?kind=drafts")}
          className="text-[11.5px] text-[var(--deep)] hover:text-[var(--ink)] inline-flex items-center gap-1 transition-colors"
          data-testid="follow-up-drafts-view-more"
        >
          View more <ArrowRight className="w-3 h-3" strokeWidth={1.7} />
        </button>
      </footer>
    </section>
  );
}
