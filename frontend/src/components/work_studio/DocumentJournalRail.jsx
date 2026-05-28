/**
 * Wave 3 (2026-05-27) — Work Studio Document Journal rail.
 *
 * Right-rail panel that surfaces the canonical document listing for
 * the active context inside Work Studio. The full Workspace
 * page (`/app/workspace`) stays the dedicated document journal
 * surface; this rail mirrors its READ path so users don't have to
 * leave Work Studio to find a doc.
 *
 * Brief (Wave 3):
 *   - Tabs in WorkStudio surface ONLY the artefacts marked to each
 *     category (unchanged — they already do).
 *   - The full document listing moves to the Document Journal
 *     (right rail) — this component.
 *   - Listing starts under the search bar; no large hero spacing.
 *   - Respects Recurrence #3 smoke-upload filter (`smoke_upload === true`
 *     rows are hidden from the journal — same filter Workspace.jsx uses).
 *
 * Click a row → set `?doc_id={id}` in the URL → the existing
 * `<DocumentDrawer>` in WorkStudio opens via deep-link.
 */
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, FileText, BookOpen } from "lucide-react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const now  = Date.now();
  const sec  = Math.max(1, Math.floor((now - then) / 1000));
  if (sec < 60)        return `${sec}s ago`;
  if (sec < 3600)      return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400)     return `${Math.floor(sec / 3600)}h ago`;
  if (sec < 86400 * 7) return `${Math.floor(sec / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function DocumentJournalRail({ contextId, refreshKey = 0 }) {
  const [docs, setDocs]      = useState([]);
  const [loading, setLoad]   = useState(false);
  const [query, setQuery]    = useState("");
  const [, setSearchParams]  = useSearchParams();

  const load = useCallback(async () => {
    if (!contextId) return;
    setLoad(true);
    try {
      const { data } = await api.get(`/contexts/${contextId}/documents`);
      const list = Array.isArray(data) ? data : (data?.items || []);
      // Recurrence #3 — hide smoke-upload rows so the journal stays
      // editorial. Workspace.jsx applies the same filter.
      setDocs(list.filter((d) => !d?.smoke_upload));
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setLoad(false);
    }
  }, [contextId]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return docs;
    return docs.filter((d) => {
      const name = (d?.name || d?.title || "").toLowerCase();
      return name.includes(q);
    });
  }, [docs, query]);

  const openDoc = useCallback((docId) => {
    const sp = new URLSearchParams(window.location.search);
    sp.set("doc_id", docId);
    setSearchParams(sp, { replace: false });
  }, [setSearchParams]);

  return (
    <aside
      className="hidden xl:block xl:w-[280px] xl:flex-shrink-0"
      data-testid="document-journal-rail"
    >
      <div className="sticky top-6">
        <p className="akki-overline mb-3 flex items-center gap-2">
          <BookOpen className="w-3 h-3 text-[var(--accent)]" /> Document Journal
        </p>

        {/* Listing starts UNDER the search bar — no large hero spacing
            eating real estate (Wave 3 spec). */}
        <div className="relative mb-3">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)]" strokeWidth={1.7} />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search documents…"
            className="w-full pl-8 pr-3 py-2 text-[12.5px] bg-white border border-[var(--rule)] rounded-sm focus:outline-none focus:border-[var(--accent)] placeholder:text-[var(--muted)]"
            data-testid="document-journal-rail-search"
          />
        </div>

        {loading && (
          <p className="text-[12px] text-[var(--muted)] py-4" data-testid="document-journal-rail-loading">
            Loading documents…
          </p>
        )}

        {!loading && filtered.length === 0 && (
          <p
            className="text-[12px] text-[var(--muted)] py-4 px-1"
            data-testid="document-journal-rail-empty"
          >
            {query
              ? "No documents match this search."
              : "No documents in this context yet."}
          </p>
        )}

        {!loading && filtered.length > 0 && (
          <ul
            className="space-y-1.5 max-h-[60vh] overflow-y-auto pr-1"
            data-testid="document-journal-rail-list"
          >
            {filtered.map((d) => (
              <li key={d.id}>
                <button
                  type="button"
                  onClick={() => openDoc(d.id)}
                  className="w-full text-left p-2.5 border border-[var(--rule)] hover:border-[var(--accent)] hover:bg-[var(--cream-deep)] rounded-sm bg-white transition-colors"
                  data-testid={`document-journal-rail-row-${d.id}`}
                >
                  <div className="flex items-start gap-2">
                    <FileText className="w-3.5 h-3.5 text-[var(--muted)] mt-0.5 flex-shrink-0" strokeWidth={1.7} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[12.5px] text-[var(--ink)] truncate font-medium">
                        {d.name || d.title || "Untitled"}
                      </p>
                      <p className="text-[10.5px] text-[var(--muted)] mt-0.5">
                        {timeAgo(d.uploaded_at || d.created_at)}
                      </p>
                    </div>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
