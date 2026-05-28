/**
 * Phase Z (2026-05-27, Z-slice-3) — Work Studio RIGHT sidebar.
 *
 * Replaces the prior `<CompilationRail>` + `<DocumentJournalRail>`
 * twin-rail layout with the locked vertical stack of 5 cards
 * (per user-locked spec, 6th pass on this surface):
 *
 *   1. `+ Add a document`    — NEW. Top of stack. Opens the upload
 *                              modal. Z-slice-3 ships a toast stub;
 *                              the real modal lands in Z-slice-5.
 *   2. Generate Report       — existing primary CTA, relocated from
 *                              CompilationRail. Italic subtext
 *                              "from multiple documents" preserved.
 *   3. Recent Drafts         — preview deck (top N rows); "View more"
 *                              routes to /app/work-studio?kind=drafts.
 *   4. Recent Activity       — preview deck; "View more" routes to
 *                              /app/work-studio/activity.
 *   5. Document Journal      — preview deck of recent documents;
 *                              "View more →" routes to /app/documents
 *                              (the canonical Documents Journal page,
 *                              landing in Z-slice-4 — until then the
 *                              link will 404 visually; the wire is
 *                              correct so Z-slice-4 ships as a no-op
 *                              on this surface).
 *
 * Recurrence #3 closure preserved: smoke-upload rows are filtered
 * from the Document Journal preview (same `!d?.smoke_upload` rule
 * the legacy DocumentJournalRail used).
 *
 * Multi-viewport behavior: same `hidden xl:block` gating as the
 * legacy rails (collapses on narrow viewports so the main column
 * gets the full width).
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Sparkles, Plus, FileText, RefreshCw, BookOpen, Loader2,
  ArrowRight, AlertCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";


const RECENT_DOCS_LIMIT = 5;
const DECK_BODY_HEIGHT_5ROW = 5 * 28 + 24;  // matches legacy rail height


function fmtRelDays(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "";
  const days = Math.max(0, Math.floor((Date.now() - then) / (1000 * 60 * 60 * 24)));
  if (days === 0)  return "today";
  if (days === 1)  return "1d";
  return `${days}d`;
}


function timeAgoShort(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "";
  const sec = Math.max(1, Math.floor((Date.now() - then) / 1000));
  if (sec < 60)        return `${sec}s ago`;
  if (sec < 3600)      return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400)     return `${Math.floor(sec / 3600)}h ago`;
  if (sec < 86400 * 7) return `${Math.floor(sec / 86400)}d ago`;
  return new Date(iso).toLocaleDateString();
}


export default function WorkStudioSidebar({
  contextId, onOpenWizard, onOpenUpload, refreshKey = 0,
}) {
  const navigate = useNavigate();
  const [err, setErr] = useState(null);

  // ── Card 3: Recent Drafts ────────────────────────────────────
  const [recentDrafts, setRecentDrafts] = useState([]);
  const [recentDraftsLoading, setRecentDraftsLoading] = useState(true);

  // ── Card 4: Recent Activity ──────────────────────────────────
  const [recentActivity, setRecentActivity] = useState([]);
  const [recentActivityLoading, setRecentActivityLoading] = useState(true);

  // ── Card 5: Document Journal preview ─────────────────────────
  const [recentDocs, setRecentDocs] = useState([]);
  const [recentDocsLoading, setRecentDocsLoading] = useState(true);

  // Recent Drafts feed (documents where state == "draft").
  useEffect(() => {
    if (!contextId) return undefined;
    let dead = false;
    setRecentDraftsLoading(true);
    api
      .get(`/contexts/${contextId}/documents/drafts`, { params: { limit: RECENT_DOCS_LIMIT } })
      .then(({ data }) => { if (!dead) setRecentDrafts(Array.isArray(data) ? data : []); })
      .catch(() => { if (!dead) setRecentDrafts([]); })
      .finally(() => { if (!dead) setRecentDraftsLoading(false); });
    return () => { dead = true; };
  }, [contextId, refreshKey]);

  // Recent Activity feed (audit + feature_events stream).
  useEffect(() => {
    if (!contextId) return undefined;
    let dead = false;
    setRecentActivityLoading(true);
    api
      .get(`/contexts/${contextId}/activity/recent`, { params: { limit: RECENT_DOCS_LIMIT } })
      .then(({ data }) => { if (!dead) setRecentActivity(Array.isArray(data) ? data : []); })
      .catch(() => { if (!dead) setRecentActivity([]); })
      .finally(() => { if (!dead) setRecentActivityLoading(false); });
    return () => { dead = true; };
  }, [contextId, refreshKey]);

  // Document Journal preview (recent documents across all categories).
  // Recurrence #3 — filter out smoke_upload rows so the preview
  // stays editorial.
  useEffect(() => {
    if (!contextId) return undefined;
    let dead = false;
    setRecentDocsLoading(true);
    api
      .get(`/contexts/${contextId}/documents`, { params: { limit: 20 } })
      .then(({ data }) => {
        if (dead) return;
        const list = Array.isArray(data) ? data : (data?.items || []);
        setRecentDocs(list.filter((d) => !d?.smoke_upload).slice(0, RECENT_DOCS_LIMIT));
      })
      .catch((e) => {
        if (!dead) {
          setRecentDocs([]);
          setErr(e?.response?.data?.detail || "Could not load documents.");
        }
      })
      .finally(() => { if (!dead) setRecentDocsLoading(false); });
    return () => { dead = true; };
  }, [contextId, refreshKey]);

  // ── + Add a document handler ─────────────────────────────────
  const handleAddDocument = () => {
    if (typeof onOpenUpload === "function") {
      // Z-slice-5 will hand us the modal opener. Until then the
      // parent wires the toast stub below.
      onOpenUpload();
      return;
    }
    toast.info("Upload modal — coming in Z-slice-5.");
  };

  return (
    <aside
      className="hidden xl:block w-[340px] shrink-0"
      data-testid="work-studio-sidebar"
    >
      <div
        className="sticky top-24 space-y-5"
        data-testid="work-studio-sidebar-sticky"
      >
        {/* ─────────────────────────────────────────────────────────
            Card 1 — `+ Add a document`. NEW per Z-slice-3 spec.
            Top of the stack; primary entry point for uploads.
            ───────────────────────────────────────────────────────── */}
        <div data-testid="work-studio-sidebar-add-document-card">
          <Button
            type="button"
            onClick={handleAddDocument}
            variant="outline"
            className="w-full bg-white border-2 border-[var(--ned-purple)] hover:bg-[var(--ned-purple)]/10 text-[var(--ned-purple)] rounded-sm font-medium tracking-wide"
            data-testid="work-studio-sidebar-add-document-btn"
          >
            <Plus className="w-4 h-4 mr-1.5" strokeWidth={2.2} /> Add a document
          </Button>
          <p
            className="text-[11.5px] italic text-[var(--muted)] mt-1.5 text-center"
            data-testid="work-studio-sidebar-add-document-subtext"
          >
            upload a file, label its category
          </p>
        </div>

        {/* ─────────────────────────────────────────────────────────
            Card 2 — Generate Report (relocated from CompilationRail).
            Primary CTA for the multi-document compilation wizard.
            ───────────────────────────────────────────────────────── */}
        <div data-testid="work-studio-sidebar-generate-report-card">
          <Button
            type="button"
            onClick={() => onOpenWizard && onOpenWizard()}
            className="w-full bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
            data-testid="work-studio-sidebar-generate-report-btn"
          >
            <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Generate Report
          </Button>
          <p
            className="text-[11.5px] italic text-[var(--muted)] mt-1.5 text-center"
            data-testid="work-studio-sidebar-generate-report-subtext"
          >
            from multiple documents
          </p>
        </div>

        {/* ─────────────────────────────────────────────────────────
            Card 3 — Recent Drafts (relocated from CompilationRail).
            ───────────────────────────────────────────────────────── */}
        <section
          className="border border-[var(--rule)] bg-white rounded-sm"
          data-testid="work-studio-sidebar-recent-drafts-card"
        >
          <header className="px-3 py-2 border-b border-[var(--rule)] flex items-center gap-1.5">
            <FileText className="w-3 h-3 text-[var(--deep)]" strokeWidth={1.7} />
            <p className="akki-overline text-[10.5px] tracking-[0.16em] text-[var(--ink)]">Recent drafts</p>
            {recentDraftsLoading && <Loader2 className="w-3 h-3 animate-spin text-[var(--muted)] ml-auto" />}
          </header>
          <div
            className="p-2.5 overflow-hidden"
            style={{ minHeight: DECK_BODY_HEIGHT_5ROW, maxHeight: DECK_BODY_HEIGHT_5ROW }}
          >
            {recentDraftsLoading ? null : recentDrafts.length === 0 ? (
              <p className="text-[12px] text-[var(--muted)] italic px-1" data-testid="work-studio-sidebar-recent-drafts-empty">
                No drafts yet.
              </p>
            ) : (
              <ul className="space-y-1.5" data-testid="work-studio-sidebar-recent-drafts-list">
                {recentDrafts.slice(0, RECENT_DOCS_LIMIT).map((d) => (
                  <li key={d.id} className="text-[12.5px]">
                    <button
                      type="button"
                      onClick={() => navigate(`/app/work-studio?kind=drafts&doc_id=${d.id}`)}
                      className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] flex items-center gap-2"
                      data-testid={`work-studio-sidebar-recent-drafts-row-${d.id}`}
                    >
                      <span className="flex-1 min-w-0 truncate text-[var(--ink)]">
                        {d.name || d.original_filename || "Untitled draft"}
                      </span>
                      <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[color:var(--oxblood)] shrink-0">
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
              data-testid="work-studio-sidebar-recent-drafts-view-more"
            >
              View more <ArrowRight className="w-3 h-3" strokeWidth={1.7} />
            </button>
          </footer>
        </section>

        {/* ─────────────────────────────────────────────────────────
            Card 4 — Recent Activity (relocated from CompilationRail).
            ───────────────────────────────────────────────────────── */}
        <section
          className="border border-[var(--rule)] bg-white rounded-sm"
          data-testid="work-studio-sidebar-recent-activity-card"
        >
          <header className="px-3 py-2 border-b border-[var(--rule)] flex items-center gap-1.5">
            <RefreshCw className="w-3 h-3 text-[var(--deep)]" strokeWidth={1.7} />
            <p className="akki-overline text-[10.5px] tracking-[0.16em] text-[var(--ink)]">Recent activity</p>
            {recentActivityLoading && <Loader2 className="w-3 h-3 animate-spin text-[var(--muted)] ml-auto" />}
          </header>
          <div
            className="p-2.5 overflow-hidden"
            style={{ minHeight: DECK_BODY_HEIGHT_5ROW, maxHeight: DECK_BODY_HEIGHT_5ROW }}
          >
            {recentActivityLoading ? null : recentActivity.length === 0 ? (
              <p className="text-[12px] text-[var(--muted)] italic px-1" data-testid="work-studio-sidebar-recent-activity-empty">
                No activity yet.
              </p>
            ) : (
              <ul className="space-y-1.5" data-testid="work-studio-sidebar-recent-activity-list">
                {recentActivity.slice(0, RECENT_DOCS_LIMIT).map((a) => (
                  <li key={a.id} className="text-[12px]">
                    <button
                      type="button"
                      onClick={() => a.doc_id && navigate(`/app/work-studio?doc_id=${a.doc_id}`)}
                      disabled={!a.doc_id}
                      className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] flex items-center gap-2 disabled:opacity-70 disabled:cursor-default"
                      data-testid={`work-studio-sidebar-recent-activity-row-${a.id}`}
                    >
                      <span className="flex-1 min-w-0 truncate text-[var(--ink)]">
                        {a.doc_title || a.action || "—"}
                      </span>
                      <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] shrink-0">
                        {(a.action || "").split(".").pop() || "event"}
                      </span>
                      <span className="font-mono text-[11px] text-[var(--muted)] shrink-0 w-8 text-right">
                        {fmtRelDays(a.created_at)}
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
              onClick={() => navigate("/app/work-studio/activity")}
              className="text-[11.5px] text-[var(--deep)] hover:text-[var(--ink)] inline-flex items-center gap-1 transition-colors"
              data-testid="work-studio-sidebar-recent-activity-view-more"
            >
              View more <ArrowRight className="w-3 h-3" strokeWidth={1.7} />
            </button>
          </footer>
        </section>

        {/* ─────────────────────────────────────────────────────────
            Card 5 — Document Journal preview.
            "View more →" routes to /app/documents (Z-slice-4 lands
            the page; until then the link 404s visually — the wire is
            CORRECT so Z-slice-4 ships as a drop-in).
            Recurrence #3 closure preserved (smoke-upload filter).
            ───────────────────────────────────────────────────────── */}
        <section
          className="border border-[var(--rule)] bg-white rounded-sm"
          data-testid="work-studio-sidebar-document-journal-card"
        >
          <header className="px-3 py-2 border-b border-[var(--rule)] flex items-center gap-1.5">
            <BookOpen className="w-3 h-3 text-[var(--deep)]" strokeWidth={1.7} />
            <p className="akki-overline text-[10.5px] tracking-[0.16em] text-[var(--ink)]">Document Journal</p>
            {recentDocsLoading && <Loader2 className="w-3 h-3 animate-spin text-[var(--muted)] ml-auto" />}
          </header>
          <div
            className="p-2.5 overflow-hidden"
            style={{ minHeight: DECK_BODY_HEIGHT_5ROW, maxHeight: DECK_BODY_HEIGHT_5ROW }}
          >
            {recentDocsLoading ? null : recentDocs.length === 0 ? (
              <p className="text-[12px] text-[var(--muted)] italic px-1" data-testid="work-studio-sidebar-document-journal-empty">
                No documents yet.
              </p>
            ) : (
              <ul className="space-y-1.5" data-testid="work-studio-sidebar-document-journal-list">
                {recentDocs.map((d) => (
                  <li key={d.id} className="text-[12.5px]">
                    <button
                      type="button"
                      onClick={() => {
                        // Reuse the canonical `?doc_id=` URL contract.
                        const sp = new URLSearchParams(window.location.search);
                        sp.set("doc_id", d.id);
                        navigate(`/app/work-studio?${sp.toString()}`);
                      }}
                      className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] flex items-center gap-2"
                      data-testid={`work-studio-sidebar-document-journal-row-${d.id}`}
                    >
                      <span className="flex-1 min-w-0 truncate text-[var(--ink)]">
                        {d.name || d.original_filename || "Untitled"}
                      </span>
                      <span className="font-mono text-[11px] text-[var(--muted)] shrink-0">
                        {timeAgoShort(d.updated_at || d.created_at)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <footer className="px-3 py-2 border-t border-[var(--rule)] bg-[var(--cream-deep)]/40">
            <a
              href="/app/documents"
              onClick={(e) => { e.preventDefault(); navigate("/app/documents"); }}
              className="text-[11.5px] text-[var(--deep)] hover:text-[var(--ink)] inline-flex items-center gap-1 transition-colors"
              data-testid="work-studio-sidebar-document-journal-view-more"
            >
              View more <ArrowRight className="w-3 h-3" strokeWidth={1.7} />
            </a>
          </footer>
        </section>

        {err && (
          <p
            className="text-[11.5px] text-amber-900 inline-flex items-center gap-1.5"
            data-testid="work-studio-sidebar-error"
          >
            <AlertCircle className="w-3 h-3" /> {err}
          </p>
        )}
      </div>
    </aside>
  );
}
