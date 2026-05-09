/**
 * DocumentBodyModal — Phase M.2 in-app overlay for the Document Journal.
 *
 * Replaces the row-level "Download original" anchor (which used to open
 * the file in a new browser tab) with a Dialog overlay that renders the
 * document body inline. The journal listing stays mounted behind the
 * dialog (Radix `<Dialog>` is a portal-based overlay, not a route
 * change), and closing the modal returns the user to the same scroll
 * position they were at.
 *
 * Lighter-weight implementation: we hit the existing
 * `GET /api/contexts/{cid}/documents/{did}` endpoint which returns
 * `extracted_text` (truncated to MAX_EXTRACT_CHARS_OUT) plus the
 * paragraph-anchored body when available. We render a basic typographic
 * read; full Reading Viewer features (citations, commentary drawer,
 * scroll-sync) live at /app/documents/:id and are only one click away
 * via the "Open in Reading Viewer" link inside the modal.
 *
 * A "Download" link is preserved as a secondary action so users who
 * actually want the file still can.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api, apiErrorMessage, API_BASE } from "@/lib/api";
import { Download, ExternalLink, FileText, Loader2, X, AlertTriangle } from "lucide-react";

export default function DocumentBodyModal({
  open,
  onClose,
  contextId,
  docId,
  docName,
}) {
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!open || !contextId || !docId) return undefined;
    let dead = false;
    setLoading(true);
    setError(null);
    setDoc(null);
    api
      .get(`/contexts/${contextId}/documents/${docId}`)
      .then(({ data }) => {
        if (!dead) setDoc(data || null);
      })
      .catch((e) => {
        if (!dead) setError(apiErrorMessage(e));
      })
      .finally(() => {
        if (!dead) setLoading(false);
      });
    return () => {
      dead = true;
    };
  }, [open, contextId, docId]);

  // Reset on close so re-opening a different doc doesn't flash the
  // previous body for a frame.
  useEffect(() => {
    if (open) return;
    setDoc(null);
    setError(null);
    setLoading(false);
  }, [open]);

  const body = (doc?.extracted_text || "").trim();
  const paragraphs = body
    ? body.split(/\n\s*\n+/).map((p) => p.trim()).filter(Boolean)
    : [];

  // API_BASE already ends with `/api` (see frontend/src/lib/api.js:4),
  // so the path here MUST NOT re-add `/api` — doing so 404s. Same
  // regression family as UploadModal.jsx.
  const downloadHref =
    contextId && docId
      ? `${API_BASE}/contexts/${contextId}/documents/${docId}/download`
      : "#";

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent
        className="max-w-[820px] max-h-[88vh] overflow-hidden flex flex-col bg-[var(--cream)] border-[var(--rule)] p-0"
        data-testid="document-body-modal"
      >
        <DialogTitle className="sr-only">
          {docName || doc?.name || "Document"}
        </DialogTitle>
        <DialogDescription className="sr-only">
          The body of the document, rendered inline. Use the close button or press Escape to return to the journal.
        </DialogDescription>

        {/* Header — title + close */}
        <div className="px-7 py-4 border-b border-[var(--rule)] bg-white flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="akki-overline mb-1 flex items-center gap-1.5">
              <FileText className="w-3 h-3 text-[var(--accent)]" /> Document body
            </p>
            <h2 className="akki-serif text-[20px] font-normal text-[var(--ink)] leading-snug truncate">
              {docName || doc?.name || "Document"}
            </h2>
            {doc?.original_filename && (
              <p className="text-[10.5px] text-[var(--muted)] font-mono mt-1 truncate">
                {doc.original_filename}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1 text-[var(--muted)] hover:text-[var(--ink)] shrink-0"
            aria-label="Close"
            data-testid="document-body-modal-close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-8 py-6 bg-white">
          {loading && (
            <div className="flex items-center gap-2 text-[12.5px] text-[var(--muted)]" data-testid="document-body-modal-loading">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Loading the body…
            </div>
          )}

          {!loading && error && (
            <div
              className="flex items-start gap-2 p-4 bg-red-50 border border-red-200 rounded-sm text-[12.5px] text-red-800"
              data-testid="document-body-modal-error"
            >
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <div>
                <p className="font-medium mb-1">Couldn't load the document body.</p>
                <p>{error}</p>
              </div>
            </div>
          )}

          {!loading && !error && paragraphs.length === 0 && (
            <div
              className="text-[13px] text-[var(--muted)] italic"
              data-testid="document-body-modal-empty"
            >
              AKKI hasn't extracted any text from this file yet — the
              source file is still the only readable copy. Use Download
              below or open it in the Reading Viewer once extraction
              finishes.
            </div>
          )}

          {!loading && !error && paragraphs.length > 0 && (
            <article
              className="akki-serif text-[15px] leading-[1.7] text-[var(--deep)] max-w-[68ch] mx-auto"
              data-testid="document-body-modal-body"
            >
              {paragraphs.map((p, i) => (
                <p key={i} className="mb-4 whitespace-pre-wrap">{p}</p>
              ))}
            </article>
          )}
        </div>

        {/* Footer — secondary actions */}
        <div className="px-7 py-3 border-t border-[var(--rule)] bg-white flex items-center justify-between gap-3">
          <p className="text-[11px] text-[var(--muted)]">
            {doc?.akki_summary
              ? "AKKI's summary is on the journal row."
              : "Body is shielded — Synisense masks PII before any LLM read."}
          </p>
          <div className="flex items-center gap-2">
            <a
              href={downloadHref}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 text-[12.5px] text-[var(--muted)] hover:text-[var(--ink)] px-3 py-1.5 rounded-sm hover:bg-[var(--cream-deep)] transition-colors"
              data-testid="document-body-modal-download"
              title="Download the original file"
            >
              <Download className="w-3.5 h-3.5" /> Download
            </a>
            {contextId && docId && (
              <Link
                to={`/app/documents/${docId}`}
                onClick={onClose}
                className="inline-flex items-center gap-1.5 text-[12.5px] text-[var(--accent)] hover:underline px-3 py-1.5"
                data-testid="document-body-modal-open-reader"
              >
                Open in Reading Viewer <ExternalLink className="w-3.5 h-3.5" />
              </Link>
            )}
            <Button
              onClick={onClose}
              variant="ghost"
              className="rounded-sm h-9 text-[12.5px]"
              data-testid="document-body-modal-close-btn"
            >
              Close
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
