/**
 * ARCHIVED 2026-05-26 — Legacy Workspace JournalDrawer.
 *
 * This was the inline drawer originally defined in `pages/Workspace.jsx`
 * (lines 44-198). It rendered "Topline / From AKKI / Body excerpt"
 * sections with 5 CTAs (Open full reader / Ask in Chat / Add to Cycle
 * / Add to Work Studio / Take into Solva) and was the surface a user
 * saw when they clicked a doc row on `/app/workspace`.
 *
 * Phase E.3 (2026-05-26) replaced this with the universal
 * `<DocumentDrawer>` (5 tabs: Document / Intelligence / Summary &
 * Notes / Signals / Related + 5 canonical-URL CTAs: Use in Solva /
 * Use in Chat / Generate brief / Test hypothesis / Share document).
 * The runtime drawer regression on Workspace was fixed here:
 * /app/memory/sprints/HOME_CLEANUP_LOG.md §"E.3 — runtime drawer
 * regression fix".
 *
 * The wire test that originally passed by JSX-import inspection was
 * replaced with a runtime-DOM assertion test
 * (`test_home_cleanup_phase_e3_runtime_drawer.py`).
 *
 * Kept here for git-history continuity only. NOT imported anywhere.
 */
import React from "react";
import { Link } from "react-router-dom";
import { FileText, X, Eye, Loader2, ArrowRight } from "lucide-react";
import DocumentRoutingActions from "@/components/documents/DocumentRoutingActions";

function formatDate() { return ""; }
function formatBytes() { return ""; }

export function JournalDrawer({ doc, loading, onClose, onOpenStructuralDetail, contextId }) {
  if (!doc && !loading) return null;
  return (
    <div
      className="fixed inset-0 z-40 flex"
      role="dialog"
      aria-modal="true"
      aria-label="Document detail"
      data-testid="journal-drawer"
    >
      <div className="flex-1 bg-black/30 transition-opacity" onClick={onClose} aria-hidden="true" />
      <aside className="w-full sm:w-[640px] md:w-[760px] lg:w-[820px] max-w-[92vw] bg-[var(--paper)] border-l border-[var(--rule)] h-full overflow-y-auto shadow-xl flex flex-col" data-testid="journal-drawer-panel">
        <header className="px-5 py-4 border-b border-[var(--rule)] bg-white sticky top-0 z-10 flex items-start gap-3">
          <FileText className="w-4 h-4 text-[var(--accent)] mt-1 shrink-0" strokeWidth={1.7} />
          <div className="flex-1 min-w-0">
            {loading ? <p className="akki-meta">Loading…</p> : (
              <>
                <h2 className="akki-serif text-[18px] text-[var(--ink)] leading-snug truncate" data-testid="journal-drawer-title">
                  {doc?.name || "(untitled)"}
                </h2>
                <p className="akki-meta mt-0.5 text-[11.5px] text-[var(--muted)]">
                  {[formatDate(doc?.created_at), formatBytes(doc?.size_bytes), doc?.doc_kind].filter(Boolean).join(" · ")}
                </p>
              </>
            )}
          </div>
          <button type="button" onClick={onClose} className="p-1 hover:bg-[var(--cream-deep)] rounded-sm shrink-0" aria-label="Close drawer" data-testid="journal-drawer-close">
            <X className="w-4 h-4 text-[var(--muted)]" />
          </button>
        </header>
        <div className="flex-1 px-5 py-4 space-y-5">
          {loading && <div className="py-12 text-center"><Loader2 className="w-4 h-4 mx-auto animate-spin text-[var(--accent)]" /></div>}
          {!loading && doc && (
            <>
              <div className="border border-[var(--rule)] bg-[var(--cream-deep)]/40 rounded-sm px-4 py-3" data-testid="journal-drawer-topline">
                <p className="akki-overline text-[var(--muted)] mb-1">Topline</p>
                <p className="akki-serif text-[14.5px] text-[var(--ink)] leading-[1.55]">{doc.preview || "—"}</p>
              </div>
              <div data-testid="journal-drawer-commentary">
                <p className="akki-overline text-[var(--muted)] mb-2">From AKKI</p>
                {doc.journal_commentary ? <p className="akki-serif text-[14px] text-[var(--ink)] leading-[1.7] whitespace-pre-wrap">{doc.journal_commentary}</p> : <p className="text-[13px] text-[var(--muted)] italic">Notes pending.</p>}
              </div>
              <div data-testid="journal-drawer-body-excerpt">
                <div className="flex items-center justify-between mb-2">
                  <p className="akki-overline text-[var(--muted)]">Body excerpt</p>
                  <button type="button" onClick={onOpenStructuralDetail} className="text-[11.5px] text-[var(--accent)] hover:underline inline-flex items-center gap-1" data-testid="journal-drawer-open-structural"><Eye className="w-3 h-3" /> Structural detail</button>
                </div>
                <p className="text-[13px] text-[var(--ink)] leading-[1.7] whitespace-pre-wrap">{(doc.extracted_text || "—").slice(0, 1800)}</p>
              </div>
              <div className="border-t border-[var(--rule)] pt-4 flex flex-wrap gap-2">
                <Link to={`/app/documents/${doc.id}`} className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm text-[var(--ink)] hover:border-[var(--accent)] no-underline inline-flex items-center gap-1" data-testid="journal-drawer-open-reader">
                  Open full reader <ArrowRight className="w-3 h-3" />
                </Link>
                <Link to={`/app/chat?ctx_type=document&ctx_id=${doc.id}`} className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm text-[var(--ink)] hover:border-[var(--accent)] no-underline inline-flex items-center gap-1" data-testid="journal-drawer-continue-chat">Ask in Chat</Link>
                <DocumentRoutingActions contextId={contextId} doc={doc} onActionDone={onClose} />
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
