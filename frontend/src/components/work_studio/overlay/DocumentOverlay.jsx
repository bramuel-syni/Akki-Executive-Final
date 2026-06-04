/**
 * Document Overlay — Chunk 8 (QA-2026-05-16-029…-036)
 *
 * Self-contained overlay component that covers all 8 IDs:
 *   -029  shell (3 vertical layers, dimmed page, close returns to list)
 *   -030  toolbar (Draft/InReview vs Committed variants)
 *   -031  intelligence card (collapsed, RAG-coloured accent border)
 *   -032  intelligence modal (full report, source map, audit trail)
 *   -033  document surface (read mode by default; Edit toggle per Divergence #1)
 *   -034  AI revision side panel (Shield-routed, source-doc allowlist)
 *   -035  version history modal (chronological, preview, restore)
 *   -036  commit confirmation modal (summary, confidence, lock warning)
 *
 * All child surfaces inlined to keep the file co-locatable and the diff
 * reviewable in one place — pattern matches ObjectivesProjectsPanel.jsx.
 */
import React, {
  useCallback, useEffect, useMemo, useRef, useState,
} from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  ArrowLeft, History, Download, Lock, Save, X, Wand2, FileText,
  ChevronDown, ChevronUp, ShieldCheck, Eye, Pencil, Undo2, Redo2,
  Check,
} from "lucide-react";

import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

// ─────────────────────────────────────────────────────────────────────
// RAG band helper (Phase 5 2026-06-04 — flipped from the Chunk 8
// 80/50 thresholds to the QA-doc-mandated 75/50. Mirrors backend
// `services.work_studio_overlay.rag_band`.)
// ≥75 green · 50-74 amber · <50 red · null → unrated.
// ─────────────────────────────────────────────────────────────────────
export function ragBand(pct) {
  if (pct === null || pct === undefined) return "unrated";
  if (pct >= 75) return "green";
  if (pct >= 50) return "amber";
  return "red";
}

const RAG_BORDER = {
  green: "border-emerald-500",
  amber: "border-amber-500",
  red: "border-[color:var(--oxblood)]",
  unrated: "border-[var(--rule)]",
};

const RAG_TEXT = {
  green: "text-emerald-700",
  amber: "text-amber-700",
  red: "text-[color:var(--oxblood)]",
  unrated: "text-[var(--muted)]",
};

const LIFECYCLE_LABEL = {
  draft: "Draft",
  in_review: "In Review",
  committed: "Committed",
};

const LIFECYCLE_DOT = {
  draft: "bg-amber-500",
  in_review: "bg-sky-600",
  committed: "bg-emerald-600",
};

// ─────────────────────────────────────────────────────────────────────
// Main overlay component (QA-2026-05-16-029 — shell)
// Props:
//   contextId, artefactId — opens this overlay's data load.
//   open: bool, onClose: () => void
// ─────────────────────────────────────────────────────────────────────
export default function DocumentOverlay({ contextId, artefactId, open, onClose }) {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [revising, setRevising] = useState(false);
  // Modals
  const [intelOpen, setIntelOpen] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [commitOpen, setCommitOpen] = useState(false);

  // Load + reload helper
  const loadDoc = useCallback(async () => {
    if (!contextId || !artefactId) return;
    setLoading(true); setLoadError("");
    try {
      const { data } = await api.get(`/contexts/${contextId}/work-studio/documents/${artefactId}`);
      setDoc(data);
    } catch (e) {
      setLoadError(apiErrorMessage(e, "Could not open document."));
    } finally {
      setLoading(false);
    }
  }, [contextId, artefactId]);

  useEffect(() => {
    if (open) loadDoc();
    else { setDoc(null); setEditMode(false); setRevising(false); }
  }, [open, loadDoc]);

  // Whenever lifecycle flips back to committed, force-exit edit mode.
  useEffect(() => {
    if (doc?.lifecycle_state === "committed") setEditMode(false);
  }, [doc?.lifecycle_state]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-center bg-black/35 backdrop-blur-[2px]"
      data-testid="document-overlay-root"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Overlay container — near-full-screen but not edge-to-edge, so the
          dim of the page-behind reads (per QA-029). */}
      <div
        className="relative bg-[var(--parchment)] my-4 mx-4 w-full max-w-[1280px] rounded-md shadow-2xl flex flex-col overflow-hidden border border-[var(--rule)]"
        data-testid="document-overlay-shell"
      >
        {loading && (
          <div className="p-10 text-center text-[var(--muted)] text-[13px] italic">
            Loading document…
          </div>
        )}
        {loadError && (
          <div className="p-10 text-center text-rose-700 text-[13px]">
            {loadError}
            <button
              className="block mx-auto mt-3 text-[12px] underline text-[var(--accent)]"
              onClick={onClose}
              data-testid="document-overlay-error-close"
            >
              Close
            </button>
          </div>
        )}
        {doc && !loading && !loadError && (
          <>
            <Toolbar
              doc={doc}
              editMode={editMode}
              onClose={onClose}
              onToggleEdit={() => setEditMode((v) => !v)}
              onShowVersions={() => setVersionsOpen(true)}
              onCommit={() => setCommitOpen(true)}
              onMoveToReview={async () => {
                try {
                  await api.post(`/contexts/${contextId}/work-studio/documents/${artefactId}/move-to-review`);
                  toast.success("Document moved to In Review.");
                  await loadDoc();
                } catch (e) {
                  toast.error(apiErrorMessage(e, "Couldn't move to review."));
                }
              }}
              onCreateNewVersion={async () => {
                try {
                  const r = await api.post(`/contexts/${contextId}/work-studio/documents/${artefactId}/create-new-version`);
                  toast.success("New draft version created.");
                  // Open the new draft in place.
                  onClose();
                  // Pass the new id to the parent via location event;
                  // simplest implementation: navigate via window.dispatchEvent.
                  window.dispatchEvent(new CustomEvent(
                    "akki:open-document-overlay",
                    { detail: { contextId, artefactId: r.data.id } },
                  ));
                } catch (e) {
                  toast.error(apiErrorMessage(e, "Couldn't create new version."));
                }
              }}
              onTitleChange={async (newTitle) => {
                try {
                  const { data } = await api.patch(`/contexts/${contextId}/work-studio/documents/${artefactId}`, { title: newTitle });
                  setDoc(data);
                } catch (e) {
                  toast.error(apiErrorMessage(e, "Couldn't update title."));
                }
              }}
              onDownload={async (fmt) => {
                /* T4.1 (2026-05-25) — G6 ratified server-produced
                 * downloads in DOCX / PDF / PPTX. Hits the on-the-fly
                 * render endpoint and triggers a browser download via
                 * a blob URL. We use the same axios `api` client so
                 * the auth header is attached automatically; using
                 * `window.open` directly would lose the bearer token
                 * for cross-origin previews. */
                const format = (fmt || "docx").toLowerCase();
                try {
                  const resp = await api.get(
                    `/contexts/${contextId}/work-studio/documents/${artefactId}/render`,
                    { params: { format }, responseType: "blob" },
                  );
                  const blob = new Blob([resp.data], {
                    type: resp.headers["content-type"] || "application/octet-stream",
                  });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  // Filename comes from Content-Disposition; fall back
                  // to a synthetic name if the header isn't set.
                  const cd = resp.headers["content-disposition"] || "";
                  const match = cd.match(/filename="?([^";]+)"?/);
                  a.download = match ? match[1] : `${doc.title || "document"}.${format}`;
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  URL.revokeObjectURL(url);
                } catch (e) {
                  const status = e?.response?.status;
                  if (status === 409) {
                    toast.error("This artefact has no compiled content yet.");
                  } else {
                    toast.error(
                      apiErrorMessage(e, `Couldn't download ${format.toUpperCase()} file.`),
                    );
                  }
                }
              }}
            />
            {/* Layer 2 — Intelligence card */}
            <IntelligenceCard
              report={doc.intelligence_report}
              confidenceBand={doc.confidence_band}
              onOpenFullReport={() => setIntelOpen(true)}
            />
            {/* Layer 3 — Document Surface (-033) */}
            <DocumentSurface
              key={`${artefactId}-${doc.lifecycle_state}`}
              doc={doc}
              editMode={editMode}
              setEditMode={setEditMode}
              contextId={contextId}
              artefactId={artefactId}
              onSaved={(updatedDoc) => setDoc(updatedDoc)}
              onOpenRevise={() => setRevising(true)}
            />

            {/* AI Revision side panel — slides in alongside (-034) */}
            {revising && (
              <AIRevisionPanel
                contextId={contextId}
                artefactId={artefactId}
                doc={doc}
                onClose={() => setRevising(false)}
                onApplied={(updatedDoc) => {
                  setDoc(updatedDoc);
                  setRevising(false);
                  toast.success("AI revisions applied.");
                }}
              />
            )}

            {/* Modals (-032, -035, -036) */}
            <IntelligenceModal
              open={intelOpen}
              onClose={() => setIntelOpen(false)}
              report={doc.intelligence_report}
            />
            <VersionHistoryModal
              open={versionsOpen}
              onClose={() => setVersionsOpen(false)}
              contextId={contextId}
              artefactId={artefactId}
              lifecycleState={doc.lifecycle_state}
              onRestored={async () => {
                setVersionsOpen(false);
                await loadDoc();
                toast.success("Restored from version.");
              }}
            />
            <CommitConfirmationModal
              open={commitOpen}
              onClose={() => setCommitOpen(false)}
              doc={doc}
              contextId={contextId}
              artefactId={artefactId}
              onCommitted={async () => {
                setCommitOpen(false);
                await loadDoc();
                toast.success("Document committed and locked.");
              }}
            />
          </>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Toolbar — QA-2026-05-16-030
// Two variants: Draft/InReview (editable affordances) vs Committed (read-only).
// ─────────────────────────────────────────────────────────────────────
function Toolbar({
  doc, editMode, onClose, onToggleEdit, onShowVersions, onCommit,
  onMoveToReview, onCreateNewVersion, onTitleChange, onDownload,
}) {
  const isCommitted = doc.lifecycle_state === "committed";
  const isDraft = doc.lifecycle_state === "draft";
  const isInReview = doc.lifecycle_state === "in_review";
  const [titleDraft, setTitleDraft] = useState(doc.title || "");
  useEffect(() => { setTitleDraft(doc.title || ""); }, [doc.title]);

  return (
    <div
      className="flex items-center gap-3 px-5 py-3 border-b border-[var(--rule)] bg-white"
      data-testid="document-overlay-toolbar"
    >
      <button
        type="button"
        onClick={onClose}
        className="flex items-center gap-1 text-[12px] text-[var(--muted)] hover:text-[var(--ink)]"
        data-testid="document-overlay-back"
        aria-label="Back to list"
      >
        <ArrowLeft className="w-4 h-4" strokeWidth={1.6} />
        Back to list
      </button>

      <div className="flex-1 min-w-0 mx-4">
        {isCommitted ? (
          <h2
            className="akki-serif text-[18px] text-[var(--ink)] truncate"
            data-testid="document-overlay-title-readonly"
          >
            {doc.title || "Untitled document"}
          </h2>
        ) : (
          <input
            type="text"
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={() => {
              if (titleDraft.trim() && titleDraft.trim() !== (doc.title || "").trim()) {
                onTitleChange(titleDraft.trim());
              }
            }}
            className="w-full akki-serif text-[18px] bg-transparent border-b border-transparent hover:border-[var(--rule)] focus:border-[var(--ink)] focus:outline-none px-1 text-[var(--ink)]"
            data-testid="document-overlay-title-editable"
            placeholder="Untitled document"
          />
        )}
      </div>

      <span
        className="flex items-center gap-1.5 text-[11.5px] font-mono uppercase tracking-[0.14em] text-[var(--muted)]"
        data-testid="document-overlay-status-badge"
      >
        <span className={`w-2 h-2 rounded-full ${LIFECYCLE_DOT[doc.lifecycle_state] || "bg-slate-400"}`} />
        {LIFECYCLE_LABEL[doc.lifecycle_state] || "Unknown"}
      </span>

      <div className="flex items-center gap-1.5">
        {/* Common to all states */}
        <button
          type="button"
          onClick={onShowVersions}
          className="p-1.5 text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)]/30 rounded"
          aria-label="Version history"
          data-testid="document-overlay-history-btn"
          title="Version history"
        >
          <History className="w-4 h-4" strokeWidth={1.6} />
        </button>
        {/* T4.1 (2026-05-25) — G6 ratified: 3 server-produced download
            formats (DOCX / PDF / PPTX). Each button hits the on-the-fly
            render endpoint `/work-studio/documents/{aid}/render?format=...`
            and streams the binary back. All three buttons emit DOM
            unconditionally (T2.3 rule); they're disabled only when no
            artefactId is available (the toolbar root won't render
            without a doc anyway, but the prop guard keeps test data
            clean). The pre-T4 single "Download" icon (which routed to
            the legacy export-job pipeline) is removed; that pipeline
            is still reachable from the Compile wizard's commission
            flow and isn't a Compiled Document toolbar affordance. */}
        <button
          type="button"
          onClick={() => onDownload("docx")}
          className="px-2.5 py-1 text-[11.5px] uppercase tracking-[0.14em] font-mono text-[var(--ink)] hover:bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-sm"
          aria-label="Download DOCX"
          data-testid="document-overlay-download-docx-btn"
          title="Download as DOCX"
        >
          DOCX
        </button>
        <button
          type="button"
          onClick={() => onDownload("pdf")}
          className="px-2.5 py-1 text-[11.5px] uppercase tracking-[0.14em] font-mono text-[var(--ink)] hover:bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-sm"
          aria-label="Download PDF"
          data-testid="document-overlay-download-pdf-btn"
          title="Download as PDF"
        >
          PDF
        </button>
        <button
          type="button"
          onClick={() => onDownload("pptx")}
          className="px-2.5 py-1 text-[11.5px] uppercase tracking-[0.14em] font-mono text-[var(--ink)] hover:bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-sm"
          aria-label="Download PPTX"
          data-testid="document-overlay-download-pptx-btn"
          title="Download as PPTX"
        >
          PPTX
        </button>

        {/* Draft / In Review affordances */}
        {!isCommitted && (
          <>
            {isDraft && doc.is_owner && (
              <Button
                size="sm"
                variant="outline"
                onClick={onMoveToReview}
                className="rounded-sm text-[12px] border-[var(--rule)] hover:border-[var(--ink)]"
                data-testid="document-overlay-move-to-review-btn"
              >
                Move to review
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={onToggleEdit}
              disabled
              data-phase6="true"
              className="rounded-sm text-[12px] border-[var(--rule)] hover:border-[var(--ink)] opacity-60 cursor-not-allowed"
              data-testid="document-overlay-edit-toggle"
              title="Inline edit ships in Phase 6"
            >
              {editMode ? (<><Eye className="w-3.5 h-3.5 mr-1" /> Read mode</>) : (<><Pencil className="w-3.5 h-3.5 mr-1" /> Edit</>)}
            </Button>
            <Button
              size="sm"
              onClick={onCommit}
              className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm text-[12px]"
              data-testid="document-overlay-commit-btn"
            >
              <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Commit
            </Button>
          </>
        )}

        {/* Committed variant */}
        {isCommitted && (
          <Button
            size="sm"
            onClick={onCreateNewVersion}
            className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm text-[12px]"
            data-testid="document-overlay-create-new-version-btn"
          >
            <Pencil className="w-3.5 h-3.5 mr-1" /> Create new version
          </Button>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Intelligence card (-031) — collapsed strip with RAG accent border
// ─────────────────────────────────────────────────────────────────────
function IntelligenceCard({ report, confidenceBand, onOpenFullReport }) {
  const hasReport = report && typeof report === "object";
  const conf = hasReport ? report.confidence_pct : null;
  const band = confidenceBand || ragBand(conf);
  return (
    <div
      className={`mx-5 my-3 px-4 py-3 rounded-md bg-white border-l-[3px] ${RAG_BORDER[band]} border-y border-r border-y-[var(--rule)] border-r-[var(--rule)] flex items-center gap-3`}
      data-testid="document-overlay-intelligence-card"
      data-confidence-band={band}
    >
      <FileText className="w-4 h-4 text-[var(--muted)]" strokeWidth={1.6} />
      <div className="flex-1 min-w-0 text-[12px] text-[var(--ink)]">
        {hasReport ? (
          <span data-testid="document-overlay-intelligence-summary">
            Synthesised from{" "}
            <strong>{report.sources_count ?? 0}</strong>{" "}
            source{(report.sources_count ?? 0) === 1 ? "" : "s"}
            {report.period && (<> · period {report.period}</>)}
            {report.framing && (<> · framing {report.framing}</>)}
            {(report.pending_recommendations ?? 0) > 0 && (
              <> · <strong>{report.pending_recommendations}</strong> recommendation{report.pending_recommendations === 1 ? "" : "s"}</>
            )}
          </span>
        ) : (
          <span
            className="italic text-[var(--muted)]"
            data-testid="document-overlay-intelligence-empty"
          >
            Intelligence report not captured for this document.
          </span>
        )}
      </div>
      <span
        className={`text-[12px] font-mono ${RAG_TEXT[band]}`}
        data-testid="document-overlay-intelligence-confidence"
      >
        {conf !== null && conf !== undefined ? `${conf}%` : "—"}
      </span>
      <button
        type="button"
        onClick={onOpenFullReport}
        className="text-[11.5px] text-[var(--accent)] hover:underline underline-offset-2"
        data-testid="document-overlay-intelligence-open"
        disabled={!hasReport}
      >
        View full report →
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Intelligence modal (-032)
// ─────────────────────────────────────────────────────────────────────
function IntelligenceModal({ open, onClose, report }) {
  if (!open) return null;
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent
        className="bg-[var(--parchment)] max-w-[1024px] max-h-[85vh] overflow-y-auto"
        data-testid="document-overlay-intelligence-modal"
      >
        <DialogHeader>
          <DialogTitle className="akki-serif text-[18px] text-[var(--ink)]">
            Document Intelligence Report
          </DialogTitle>
        </DialogHeader>
        {!report ? (
          <p
            className="text-[13px] text-[var(--muted)] italic"
            data-testid="document-overlay-intelligence-modal-empty"
          >
            No intelligence report has been captured for this document.
          </p>
        ) : (
          <div className="space-y-4 text-[13px] text-[var(--ink)]">
            <section>
              <h3 className="akki-overline text-[10.5px] tracking-[0.18em] text-[var(--muted)] mb-1">
                Source map
              </h3>
              <ul className="list-disc list-outside ml-5 space-y-0.5">
                {(report.sources || []).map((s, i) => (
                  <li key={i} data-testid={`document-overlay-intelligence-source-${i}`}>
                    {s.name || s.doc_id} {s.period && <span className="text-[var(--muted)]">· {s.period}</span>}
                  </li>
                ))}
                {(!report.sources || report.sources.length === 0) && (
                  <li className="text-[var(--muted)] italic list-none">
                    {report.sources_count ?? 0} source documents (names not captured).
                  </li>
                )}
              </ul>
            </section>
            <section>
              <h3 className="akki-overline text-[10.5px] tracking-[0.18em] text-[var(--muted)] mb-1">
                Per-section confidence
              </h3>
              {Array.isArray(report.sections) && report.sections.length > 0 ? (
                <ul className="space-y-1.5">
                  {report.sections.map((s, i) => {
                    const band = ragBand(s.confidence_pct);
                    return (
                      <li
                        key={i}
                        className={`flex items-center gap-3 border-l-[3px] ${RAG_BORDER[band]} pl-3`}
                        data-testid={`document-overlay-intelligence-section-${i}`}
                      >
                        <span className="flex-1">{s.heading || `Section ${i + 1}`}</span>
                        <span className={`font-mono text-[12px] ${RAG_TEXT[band]}`}>
                          {s.confidence_pct ?? "—"}%
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-[var(--muted)] italic">No per-section breakdown.</p>
              )}
            </section>
            {report.framing_analysis && (
              <section>
                <h3 className="akki-overline text-[10.5px] tracking-[0.18em] text-[var(--muted)] mb-1">Framing</h3>
                <p>{report.framing_analysis}</p>
              </section>
            )}
            {Array.isArray(report.gaps) && report.gaps.length > 0 && (
              <section>
                <h3 className="akki-overline text-[10.5px] tracking-[0.18em] text-[var(--muted)] mb-1">Gaps</h3>
                <ul className="list-disc list-outside ml-5 space-y-0.5">
                  {report.gaps.map((g, i) => <li key={i}>{g}</li>)}
                </ul>
              </section>
            )}
            {Array.isArray(report.recommendations) && report.recommendations.length > 0 && (
              <section>
                <h3 className="akki-overline text-[10.5px] tracking-[0.18em] text-[var(--muted)] mb-1">Recommendations</h3>
                <ul className="list-disc list-outside ml-5 space-y-0.5">
                  {report.recommendations.map((r, i) => (
                    <li key={i}>{r.text || r} {r.addressed && <span className="text-emerald-700">✓</span>}</li>
                  ))}
                </ul>
              </section>
            )}
            {report.audit && (
              <section className="text-[11.5px] text-[var(--muted)] font-mono pt-2 border-t border-[var(--rule)]">
                <p>Generated at {report.audit.generated_at}</p>
                {report.audit.model_version && <p>Model: {report.audit.model_version}</p>}
                {report.audit.source_document_ids?.length > 0 && (
                  <p>Source ids: {report.audit.source_document_ids.join(", ")}</p>
                )}
              </section>
            )}
          </div>
        )}
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={onClose}
            data-testid="document-overlay-intelligence-modal-close"
          >
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Document surface (-033)
// Tiptap editor; READ MODE by default per Divergence #1.
// 30s autosave when in edit mode (Draft/InReview only).
// ─────────────────────────────────────────────────────────────────────
function DocumentSurface({
  doc, editMode, setEditMode, contextId, artefactId, onSaved, onOpenRevise,
}) {
  const isCommitted = doc.lifecycle_state === "committed";
  const isLegacyReadOnly = isCommitted || doc.legacy;
  const sections = doc.structured_content?.sections || [];

  // Build the tiptap-compatible HTML body from the section/paragraph tree.
  const initialHtml = useMemo(() => {
    if (!sections.length) {
      // Legacy doc with no structured content. Render whatever string field
      // we can find.
      const fallback = doc.legacy
        ? "<p><em>This is a legacy document. Structured editing is not available — use Download or Create New Version to make changes.</em></p>"
        : "<p><em>This document is empty. Switch on Edit mode to add content.</em></p>";
      return fallback;
    }
    return sections.map((s, i) => {
      const heading = (s.heading || "").trim();
      const paras = (s.paragraphs || []).map((p) => `<p>${escapeHtml(p)}</p>`).join("");
      return heading
        ? `<h2>${escapeHtml(heading)}</h2>${paras}`
        : paras || `<p data-empty="section-${i}"></p>`;
    }).join("");
  }, [sections, doc.legacy]);

  const editor = useEditor({
    extensions: [StarterKit],
    content: initialHtml,
    // Track A Phase 5 (2026-06-04) — locked to read-only for the
    // Document Review Side Drawer surface; inline edit re-enables
    // in Phase 6. The toolbar's Edit button is disabled (data-phase6=
    // true) and the secondary-toolbar "Inline edit on" indicator is
    // a stub. Phase 5 = read-only render of DOCX/PPTX HTML; PDFs
    // use an iframe instead (rendered outside this surface).
    editable: false,
    editorProps: {
      attributes: {
        class: "akki-serif text-[14.5px] leading-[1.65] text-[var(--ink)] focus:outline-none",
        "data-testid": "document-overlay-surface-editor",
      },
    },
  });

  // Track A Phase 5 (2026-06-04) — editor stays in read-only mode
  // regardless of the editMode flag (the toolbar button is disabled).
  // Phase 6 will restore: `editor.setEditable(editMode && !isLegacyReadOnly);`.
  useEffect(() => {
    if (editor) editor.setEditable(false);
  }, [editor, editMode, isLegacyReadOnly]);

  // Reload content when the doc identity changes (Create New Version, etc.)
  useEffect(() => {
    if (editor) editor.commands.setContent(initialHtml, false);
  }, [editor, initialHtml]);

  // 30s autosave (only in edit mode, draft/in_review).
  const autosaveTimer = useRef(null);
  useEffect(() => {
    if (!editor || !editMode || isLegacyReadOnly) {
      if (autosaveTimer.current) {
        clearInterval(autosaveTimer.current);
        autosaveTimer.current = null;
      }
      return undefined;
    }
    autosaveTimer.current = setInterval(async () => {
      try {
        const structured = htmlToStructuredContent(editor.getHTML());
        await api.patch(
          `/contexts/${contextId}/work-studio/documents/${artefactId}`,
          { structured_content: structured },
        );
        await api.post(
          `/contexts/${contextId}/work-studio/documents/${artefactId}/save`,
          { label: "Auto-save" },
        );
      } catch (e) {
        // Silent autosave failure — visible save errors surface on
        // explicit Save click.
        // eslint-disable-next-line no-console
        console.warn("autosave failed:", e?.message);
      }
    }, 30000);
    return () => clearInterval(autosaveTimer.current);
  }, [editor, editMode, isLegacyReadOnly, contextId, artefactId]);

  const handleSaveNow = useCallback(async () => {
    if (!editor || isLegacyReadOnly) return;
    try {
      const structured = htmlToStructuredContent(editor.getHTML());
      const { data } = await api.patch(
        `/contexts/${contextId}/work-studio/documents/${artefactId}`,
        { structured_content: structured },
      );
      await api.post(
        `/contexts/${contextId}/work-studio/documents/${artefactId}/save`,
        { label: null },
      );
      toast.success("Saved.");
      onSaved && onSaved(data);
    } catch (e) {
      toast.error(apiErrorMessage(e, "Couldn't save."));
    }
  }, [editor, isLegacyReadOnly, contextId, artefactId, onSaved]);

  return (
    <div className="flex-1 overflow-y-auto bg-white">
      {/* Subdued toolbar above the document body (per Q5 divergence) */}
      <div
        className="sticky top-0 z-10 flex items-center gap-2 px-6 py-2 border-b border-[var(--rule)] bg-[var(--cream-deep)]/60 text-[11.5px] text-[var(--muted)]"
        data-testid="document-overlay-surface-toolbar"
      >
        {isCommitted ? (
          <span className="flex items-center gap-1.5 text-[var(--muted)]" data-testid="document-overlay-surface-locked">
            <Lock className="w-3.5 h-3.5" strokeWidth={1.6} />
            This document is committed. Use “Create new version” to make changes.
          </span>
        ) : (
          <>
            <span
              data-testid="document-overlay-surface-mode-indicator"
              data-phase6="true"
              className="text-[var(--muted)] italic"
              title="Inline edit ships in Phase 6"
            >
              Inline edit on — Phase 6
            </span>
            <div className="ml-auto flex items-center gap-1.5">
              {editor && editMode && (
                <>
                  <button
                    type="button"
                    onClick={() => editor.chain().focus().undo().run()}
                    disabled={!editor.can().undo()}
                    className="p-1.5 hover:bg-[var(--cream-deep)] rounded disabled:opacity-40"
                    aria-label="Undo"
                    data-testid="document-overlay-surface-undo"
                  >
                    <Undo2 className="w-3.5 h-3.5" strokeWidth={1.6} />
                  </button>
                  <button
                    type="button"
                    onClick={() => editor.chain().focus().redo().run()}
                    disabled={!editor.can().redo()}
                    className="p-1.5 hover:bg-[var(--cream-deep)] rounded disabled:opacity-40"
                    aria-label="Redo"
                    data-testid="document-overlay-surface-redo"
                  >
                    <Redo2 className="w-3.5 h-3.5" strokeWidth={1.6} />
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveNow}
                    className="flex items-center gap-1 px-2 py-1 hover:bg-[var(--cream-deep)] rounded"
                    data-testid="document-overlay-surface-save-now"
                  >
                    <Save className="w-3.5 h-3.5" strokeWidth={1.6} />
                    Save
                  </button>
                </>
              )}
              {/* Track A Phase 5 (2026-06-04) — Revise-with-AI is
                  stubbed in Phase 5 (re-enables in Phase 6 with the
                  diff-view panel). HIDDEN entirely for PDF
                  output_format per QA spec; DISABLED everywhere
                  else with the Phase 6 tooltip. */}
              {doc.output_format !== "pdf" && (
                <button
                  type="button"
                  onClick={() => {}}
                  disabled
                  data-phase6="true"
                  title="Revise with AI ships in Phase 6"
                  className="flex items-center gap-1 px-2 py-1 hover:bg-[var(--cream-deep)] rounded opacity-40 cursor-not-allowed"
                  data-testid="document-overlay-surface-revise-btn"
                >
                  <Wand2 className="w-3.5 h-3.5" strokeWidth={1.6} />
                  Revise with AI
                </button>
              )}
            </div>
          </>
        )}
      </div>
      <div className="px-10 py-8 max-w-[820px] mx-auto" data-testid="document-overlay-surface">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}

// HTML ↔ structured_content helpers
function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function htmlToStructuredContent(html) {
  // Parse tiptap's HTML output into the {sections:[{heading,paragraphs[]}]} shape.
  // tiptap emits <h2>, <p>, <h3>, etc. — we treat any h-tag as a new section
  // boundary; runs of <p> attach to the most recent section.
  if (!html) return { sections: [] };
  const container = document.createElement("div");
  container.innerHTML = html;
  const sections = [];
  let current = null;
  for (const node of Array.from(container.childNodes)) {
    if (node.nodeType !== 1) continue;
    const tag = node.tagName.toLowerCase();
    if (/^h[1-6]$/.test(tag)) {
      if (current) sections.push(current);
      current = { heading: node.textContent.trim(), paragraphs: [] };
    } else if (tag === "p") {
      if (!current) current = { heading: "", paragraphs: [] };
      const text = node.textContent.trim();
      if (text) current.paragraphs.push(text);
    } else {
      if (!current) current = { heading: "", paragraphs: [] };
      const text = node.textContent.trim();
      if (text) current.paragraphs.push(text);
    }
  }
  if (current) sections.push(current);
  return { sections };
}

// ─────────────────────────────────────────────────────────────────────
// AI Revision panel (-034) — slide-in side panel (not popup).
// ─────────────────────────────────────────────────────────────────────
function AIRevisionPanel({ contextId, artefactId, doc, onClose, onApplied }) {
  const [instruction, setInstruction] = useState("");
  const [scope, setScope] = useState("entire");
  const [tone, setTone] = useState("formal");
  const [submitting, setSubmitting] = useState(false);
  const [diff, setDiff] = useState(null);
  const [error, setError] = useState("");
  const [accepted, setAccepted] = useState({}); // section_index → bool

  const submit = async () => {
    setSubmitting(true); setError(""); setDiff(null);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/work-studio/documents/${artefactId}/revise`,
        { instruction, scope, tone },
      );
      setDiff(data.diff);
      // Default-accept all modified or added sections; unchanged stay as-is.
      const initial = {};
      for (const sd of (data.diff?.section_diffs || [])) {
        if (sd.change_type !== "unchanged") initial[sd.section_index] = true;
      }
      setAccepted(initial);
    } catch (e) {
      // T4.2 (2026-05-25) — G7 ratified failure copy verbatim.
      // The recommendation/state (instruction, scope, tone, last
      // diff if any) is left untouched in the inline error block so
      // the user can hit Refine again without re-typing. We only
      // clear the in-flight diff that hasn't been computed yet —
      // the diff state is set to null at the START of `submit()`
      // above, so this catch path doesn't accidentally clear an
      // already-displayed diff (there isn't one to clear here).
      setError("We couldn't apply that refinement. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const apply = async () => {
    if (!diff) return;
    // Build a new structured_content from the diff: take revised paragraphs
    // for accepted sections, original paragraphs for rejected ones.
    const sections = (diff.section_diffs || []).map((sd) => {
      const useRevised = accepted[sd.section_index] !== false && sd.change_type !== "unchanged";
      if (sd.change_type === "section_removed" && !useRevised) {
        return { heading: sd.heading, paragraphs: sd.original_paragraphs || [] };
      }
      if (sd.change_type === "section_removed" && useRevised) {
        return null; // accepting a removal drops the section
      }
      return {
        heading: sd.heading,
        paragraphs: useRevised ? (sd.revised_paragraphs || []) : (sd.original_paragraphs || []),
      };
    }).filter(Boolean);
    try {
      const { data } = await api.patch(
        `/contexts/${contextId}/work-studio/documents/${artefactId}`,
        { structured_content: { sections } },
      );
      await api.post(
        `/contexts/${contextId}/work-studio/documents/${artefactId}/save`,
        { label: "Applied AI revision" },
      );
      onApplied(data);
    } catch (e) {
      toast.error(apiErrorMessage(e, "Couldn't apply revisions."));
    }
  };

  return (
    <div
      className="absolute right-0 top-[64px] bottom-0 w-[420px] bg-[var(--parchment)] border-l border-[var(--rule)] flex flex-col overflow-hidden shadow-xl"
      data-testid="document-overlay-revise-panel"
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--rule)]">
        <h3 className="akki-serif text-[15px] text-[var(--ink)]">Revise with AI</h3>
        <button
          type="button"
          onClick={onClose}
          className="text-[var(--muted)] hover:text-[var(--ink)]"
          aria-label="Close revise panel"
          data-testid="document-overlay-revise-close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {!diff && (
          <>
            <p className="text-[11.5px] text-[var(--muted)]">
              Revisions draw only from the original source documents — no
              external knowledge is introduced.
            </p>
            <label className="block">
              <span className="text-[11.5px] text-[var(--muted)] mb-1 block">Instruction</span>
              <textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                rows={4}
                className="w-full text-[13px] bg-white border border-[var(--rule)] rounded-sm px-2 py-1.5"
                placeholder="e.g. Tighten the executive summary; flag the capital adequacy concern as a priority risk."
                data-testid="document-overlay-revise-instruction"
              />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-[11.5px] text-[var(--muted)] mb-1 block">Scope</span>
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                  className="w-full text-[13px] bg-white border border-[var(--rule)] rounded-sm px-2 py-1.5"
                  data-testid="document-overlay-revise-scope"
                >
                  <option value="entire">Entire document</option>
                  <option value="section">Specific section</option>
                  <option value="pages">Specific pages</option>
                </select>
              </label>
              <label className="block">
                <span className="text-[11.5px] text-[var(--muted)] mb-1 block">Tone</span>
                <select
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  className="w-full text-[13px] bg-white border border-[var(--rule)] rounded-sm px-2 py-1.5"
                  data-testid="document-overlay-revise-tone"
                >
                  <option value="formal">Formal</option>
                  <option value="concise">Concise</option>
                  <option value="detailed">Detailed</option>
                </select>
              </label>
            </div>
            <Button
              size="sm"
              onClick={submit}
              disabled={submitting || !instruction.trim() || (doc.source_document_ids || []).length === 0}
              className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] w-full rounded-sm"
              data-testid="document-overlay-revise-submit"
            >
              {submitting ? "Generating revisions…" : "Generate revisions"}
            </Button>
            {(doc.source_document_ids || []).length === 0 && (
              <p
                className="text-[11.5px] text-rose-700 italic"
                data-testid="document-overlay-revise-no-sources"
              >
                This document has no source documents recorded — AI revision is not available.
                Re-compile from sources to enable.
              </p>
            )}
            {error && (
              <p className="text-[11.5px] text-rose-700" data-testid="document-overlay-revise-error">{error}</p>
            )}
          </>
        )}
        {diff && (
          <>
            <p className="text-[11.5px] text-[var(--muted)]" data-testid="document-overlay-revise-diff-summary">
              {(diff.change_notes || []).length} change{(diff.change_notes || []).length === 1 ? "" : "s"} proposed
            </p>
            {(diff.change_notes || []).length > 0 && (
              <ul className="text-[12px] space-y-0.5 list-disc list-outside ml-4 text-[var(--ink)]">
                {(diff.change_notes || []).map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            )}
            <div className="space-y-2" data-testid="document-overlay-revise-section-list">
              {(diff.section_diffs || []).map((sd) => (
                <div
                  key={sd.section_index}
                  className={`border-l-[3px] pl-3 py-1.5 text-[12.5px] ${
                    sd.change_type === "modified" || sd.change_type === "section_added"
                      ? "border-amber-500"
                      : sd.change_type === "section_removed"
                        ? "border-rose-600"
                        : "border-[var(--rule)]"
                  }`}
                  data-testid={`document-overlay-revise-section-${sd.section_index}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{sd.heading || `Section ${sd.section_index + 1}`}</span>
                    <span className="text-[10.5px] uppercase tracking-[0.12em] font-mono text-[var(--muted)]">
                      {sd.change_type.replace("_", " ")}
                    </span>
                  </div>
                  {sd.change_type !== "unchanged" && (
                    <label className="flex items-center gap-1.5 mt-1 text-[11.5px] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={accepted[sd.section_index] !== false}
                        onChange={(e) => setAccepted((p) => ({ ...p, [sd.section_index]: e.target.checked }))}
                        data-testid={`document-overlay-revise-accept-${sd.section_index}`}
                      />
                      Accept this change
                    </label>
                  )}
                </div>
              ))}
            </div>
            <div className="pt-2 flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => { setDiff(null); setAccepted({}); }}
                className="rounded-sm text-[12px]"
                data-testid="document-overlay-revise-discard"
              >
                Discard
              </Button>
              <Button
                size="sm"
                onClick={apply}
                className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm text-[12px] flex-1"
                data-testid="document-overlay-revise-apply"
              >
                <Check className="w-3.5 h-3.5 mr-1" /> Apply selected revisions
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Version History modal (-035)
// ─────────────────────────────────────────────────────────────────────
function VersionHistoryModal({
  open, onClose, contextId, artefactId, lifecycleState, onRestored,
}) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [restoring, setRestoring] = useState(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    api.get(`/contexts/${contextId}/work-studio/documents/${artefactId}/versions`)
      .then(({ data }) => { if (!cancelled) setVersions(data.items || []); })
      .catch(() => { if (!cancelled) setVersions([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, contextId, artefactId]);

  const canRestore = lifecycleState !== "committed";

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent
        className="bg-[var(--parchment)] max-w-[720px] max-h-[80vh] overflow-y-auto"
        data-testid="document-overlay-version-history-modal"
      >
        <DialogHeader>
          <DialogTitle className="akki-serif text-[18px] text-[var(--ink)]">Version history</DialogTitle>
        </DialogHeader>
        {loading && <p className="text-[13px] text-[var(--muted)] italic">Loading versions…</p>}
        {!loading && versions.length === 0 && (
          <p className="text-[13px] text-[var(--muted)] italic" data-testid="document-overlay-version-history-empty">
            No saved versions yet.
          </p>
        )}
        {!loading && versions.length > 0 && (
          <ul className="space-y-2">
            {versions.map((v) => (
              <li
                key={v.id}
                className="flex items-center justify-between gap-3 border border-[var(--rule)] rounded-sm bg-white px-3 py-2"
                data-testid={`document-overlay-version-row-${v.id}`}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] text-[var(--ink)]">
                    {v.label || "Save point"}
                    {v.pre_commit && (
                      <span
                        className="ml-2 text-[10.5px] uppercase tracking-[0.12em] font-mono text-emerald-700"
                        data-testid={`document-overlay-version-pre-commit-${v.id}`}
                      >
                        Pre-commit
                      </span>
                    )}
                  </p>
                  <p className="text-[11.5px] text-[var(--muted)] font-mono">
                    {v.saved_at} · {v.section_count} section{v.section_count === 1 ? "" : "s"}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!canRestore || restoring === v.id}
                  onClick={async () => {
                    setRestoring(v.id);
                    try {
                      await api.post(`/contexts/${contextId}/work-studio/documents/${artefactId}/versions/${v.id}/restore`);
                      onRestored && onRestored();
                    } catch (e) {
                      toast.error(apiErrorMessage(e, "Couldn't restore version."));
                    } finally {
                      setRestoring(null);
                    }
                  }}
                  className="rounded-sm text-[12px]"
                  data-testid={`document-overlay-version-restore-${v.id}`}
                >
                  {restoring === v.id ? "Restoring…" : (canRestore ? "Restore" : "Read-only")}
                </Button>
              </li>
            ))}
          </ul>
        )}
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={onClose}
            data-testid="document-overlay-version-history-close"
          >Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─────────────────────────────────────────────────────────────────────
// Commit Confirmation modal (-036)
// ─────────────────────────────────────────────────────────────────────
function CommitConfirmationModal({ open, onClose, doc, contextId, artefactId, onCommitted }) {
  const [busy, setBusy] = useState(false);
  const intel = doc?.intelligence_report;
  const conf = intel?.confidence_pct;
  const band = ragBand(conf);
  const unaddressed = (intel?.recommendations || []).filter((r) => !r.addressed);

  return (
    <Dialog open={open} onOpenChange={(v) => !v && !busy && onClose()}>
      <DialogContent
        className="bg-[var(--parchment)] max-w-[560px]"
        data-testid="document-overlay-commit-modal"
      >
        <DialogHeader>
          <DialogTitle className="akki-serif text-[18px] text-[var(--ink)]">
            Commit document
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 text-[13px] text-[var(--ink)]">
          <p data-testid="document-overlay-commit-summary">
            Committing locks the document. No more edits are possible — to make
            further changes you’ll need to create a new version.
          </p>
          {conf !== undefined && conf !== null && (
            <p>
              Confidence: <span className={`font-mono ${RAG_TEXT[band]}`}>{conf}%</span>
            </p>
          )}
          {unaddressed.length > 0 && (
            <div
              className="border-l-[3px] border-amber-500 pl-3 py-1.5 bg-amber-50 text-[12.5px]"
              data-testid="document-overlay-commit-unaddressed-recs"
            >
              <p className="font-medium mb-1">
                {unaddressed.length} unaddressed recommendation{unaddressed.length === 1 ? "" : "s"}:
              </p>
              <ul className="list-disc list-outside ml-4 space-y-0.5">
                {unaddressed.slice(0, 4).map((r, i) => <li key={i}>{r.text || r}</li>)}
              </ul>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={busy}
            data-testid="document-overlay-commit-cancel"
          >
            Cancel
          </Button>
          <Button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api.post(`/contexts/${contextId}/work-studio/documents/${artefactId}/commit`);
                onCommitted && onCommitted();
              } catch (e) {
                toast.error(apiErrorMessage(e, "Couldn't commit document."));
              } finally {
                setBusy(false);
              }
            }}
            className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
            data-testid="document-overlay-commit-confirm"
          >
            {busy ? "Committing…" : "Commit & lock"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
