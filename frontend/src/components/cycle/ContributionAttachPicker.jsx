/**
 * ContributionAttachPicker — Chunk 9 (QA-2026-05-16-017).
 *
 * Inlined locally per Chunk-9 dispatch decision #2 (YAGNI vs shared
 * `DocumentAttachPicker`). The Solva flow has its own
 * `AttachDocumentModal.jsx` with session-attach semantics; deduping
 * is queued for after Chunk 12 when the second consumer is stable.
 *
 * Two tabs:
 *   - "From Document Journal" — searchable list of docs in this
 *     context. Selection attaches the doc id.
 *   - "Upload External" — device file picker → multipart upload to
 *     the existing `/api/contexts/{cid}/documents` endpoint → attaches
 *     the resulting doc id.
 *
 * On attach the parent receives `{id, name}` so it can render the
 * chip and auto-populate the contribution Title.
 */
import React, { useEffect, useRef, useState } from "react";
import { Loader2, Upload, FileText, FolderOpen, Search } from "lucide-react";

import { api, apiErrorMessage } from "@/lib/api";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";


// Mirror the Solva attach modal's accept set so users get the same
// extensions regardless of which surface they attach from.
const ACCEPT_EXTENSIONS = [
  ".pdf", ".docx", ".pptx", ".txt", ".md", ".rtf",
  ".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif",
  ".csv", ".xlsx",
];


export default function ContributionAttachPicker({
  open, onClose, contextId, onAttached,
}) {
  const [tab, setTab] = useState("journal");
  const [docs, setDocs] = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  // Reset modal state on every open so closing+re-opening yields a
  // clean slate (matches Solva attach modal idiom).
  useEffect(() => {
    if (open) {
      setTab("journal"); setSearch(""); setFile(null);
      setError(null); setDocs([]);
    }
  }, [open]);

  // Fetch documents when the journal tab activates.
  useEffect(() => {
    if (!open || tab !== "journal" || !contextId) return;
    let cancelled = false;
    (async () => {
      setDocsLoading(true); setError(null);
      try {
        const { data } = await api.get(`/contexts/${contextId}/documents?limit=100`);
        // The documents endpoint historically returns either a bare
        // list (older callers) or `{items: [...]}` (newer ones). Handle both.
        const rows = Array.isArray(data) ? data : (data?.items || []);
        if (!cancelled) setDocs(rows);
      } catch (e) {
        if (!cancelled) setError(apiErrorMessage(e, "Couldn't load documents."));
      } finally {
        if (!cancelled) setDocsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [open, tab, contextId]);

  const filtered = search.trim()
    ? docs.filter((d) => {
        const hay = `${d.name || ""} ${d.original_filename || ""}`.toLowerCase();
        return hay.includes(search.trim().toLowerCase());
      })
    : docs;

  const handleSelectJournalDoc = (doc) => {
    onAttached({
      id: doc.id,
      name: doc.name || doc.original_filename || "Document",
    });
    onClose();
  };

  const handleUploadExternal = async () => {
    if (!file) return;
    setBusy(true); setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post(
        `/contexts/${contextId}/documents`,
        form,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      // The upload endpoint emits the newly created doc. Mirror the
      // journal-tab attach shape so the parent doesn't branch.
      const doc = data?.document || data;
      onAttached({
        id: doc.id,
        name: doc.name || doc.original_filename || file.name,
      });
      onClose();
    } catch (e) {
      setError(apiErrorMessage(e, "Upload failed."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && !busy && onClose && onClose()}>
      <DialogContent
        className="bg-[var(--parchment)] max-w-[640px]"
        data-testid="contribution-attach-picker"
      >
        <DialogHeader>
          <DialogTitle className="akki-serif text-[18px] text-[var(--ink)]">
            Attach a document
          </DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)]">
            Pull from your Document Journal or upload a new file.
          </DialogDescription>
        </DialogHeader>

        {/* Tabs */}
        <div className="flex border-b border-[var(--rule)]">
          <button
            type="button"
            onClick={() => setTab("journal")}
            className={[
              "px-3 py-2 text-[12px] flex items-center gap-1.5 border-b-2 -mb-px",
              tab === "journal"
                ? "border-[var(--ink)] text-[var(--ink)]"
                : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]",
            ].join(" ")}
            data-testid="contribution-attach-tab-journal"
          >
            <FolderOpen className="w-3.5 h-3.5" /> From Document Journal
          </button>
          <button
            type="button"
            onClick={() => setTab("upload")}
            className={[
              "px-3 py-2 text-[12px] flex items-center gap-1.5 border-b-2 -mb-px",
              tab === "upload"
                ? "border-[var(--ink)] text-[var(--ink)]"
                : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]",
            ].join(" ")}
            data-testid="contribution-attach-tab-upload"
          >
            <Upload className="w-3.5 h-3.5" /> Upload External
          </button>
        </div>

        {/* Journal tab */}
        {tab === "journal" && (
          <div className="space-y-2 mt-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-[var(--muted)]" />
              <Input
                autoFocus
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search documents…"
                className="pl-8 rounded-sm text-[13px]"
                data-testid="contribution-attach-search"
              />
            </div>
            <div className="max-h-[280px] overflow-y-auto border border-[var(--rule)] rounded-sm bg-white">
              {docsLoading ? (
                <p className="px-3 py-3 text-[12.5px] text-[var(--muted)] italic">Loading…</p>
              ) : filtered.length === 0 ? (
                <p
                  className="px-3 py-3 text-[12.5px] text-[var(--muted)] italic"
                  data-testid="contribution-attach-empty"
                >
                  {search.trim() ? "No documents match that search." : "No documents in this context yet."}
                </p>
              ) : (
                <ul>
                  {filtered.map((d) => (
                    <li key={d.id}>
                      <button
                        type="button"
                        onClick={() => handleSelectJournalDoc(d)}
                        className="w-full text-left px-3 py-2 hover:bg-[var(--cream-deep)]/40 text-[13px] flex items-center gap-2 border-b border-[var(--rule)] last:border-b-0"
                        data-testid={`contribution-attach-row-${d.id}`}
                      >
                        <FileText className="w-3.5 h-3.5 text-[var(--muted)]" />
                        <span className="flex-1 truncate">
                          {d.name || d.original_filename || "Document"}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {/* Upload tab */}
        {tab === "upload" && (
          <div className="space-y-3 mt-2">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT_EXTENSIONS.join(",")}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="hidden"
              data-testid="contribution-attach-file-input"
            />
            <Button
              type="button"
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              className="rounded-sm w-full text-[12.5px] border-dashed py-8"
              data-testid="contribution-attach-pick-file"
            >
              <Upload className="w-3.5 h-3.5 mr-1.5" />
              {file ? file.name : "Choose a file from your device"}
            </Button>
            <p className="text-[11.5px] text-[var(--muted)]">
              Accepted: {ACCEPT_EXTENSIONS.join(" · ")}
            </p>
            <Button
              type="button"
              onClick={handleUploadExternal}
              disabled={!file || busy}
              className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm w-full"
              data-testid="contribution-attach-upload-submit"
            >
              {busy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : null}
              {busy ? "Uploading…" : "Upload & attach"}
            </Button>
          </div>
        )}

        {error && (
          <p
            className="text-[11.5px] text-rose-700 mt-2"
            data-testid="contribution-attach-error"
          >
            {error}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
