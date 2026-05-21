/**
 * AttachDocumentModal — mid-Solva-session document anchor.
 *
 * Phase F.1 (2026-05-16). Two tabs:
 *   - "Upload new"            — drop-zone + file picker, multipart upload
 *                               via POST .../attach-document (file field).
 *   - "From Document Journal" — searchable list of existing docs scoped
 *                               to the active context, JSON POST with
 *                               {document_id}.
 *
 * On success the parent receives the resolved anchor + the updated
 * session row. Caller is responsible for refreshing the session and
 * surfacing the inline confirmation.
 */
import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Upload, FileText, FolderOpen } from "lucide-react";
import { api } from "@/lib/api";


const ACCEPT_EXTENSIONS = [
  ".pdf", ".docx", ".pptx", ".txt", ".md", ".rtf",
  ".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif",
  ".csv", ".xlsx",
];


export default function AttachDocumentModal({ open, onClose, contextId, sessionId, onAttached }) {
  const [tab, setTab] = useState("upload");
  const [file, setFile] = useState(null);
  const [docs, setDocs] = useState([]);
  const [docsLoading, setDocsLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // QA-2026-05-16-010 (Chunk 15) — ref so we can auto-focus the search
  // input the instant the journal tab activates. `autoFocus` alone is
  // only honored at first mount; we need an effect-driven focus call
  // for the tab switch case (user opens modal on Upload, then clicks
  // Journal — `autoFocus` doesn't re-fire).
  const journalSearchRef = useRef(null);

  // Reset modal state on every open so closing+re-opening yields a
  // clean slate.
  useEffect(() => {
    if (open) {
      setTab("upload"); setFile(null); setSearch("");
      setError(null); setDocs([]);
    }
  }, [open]);

  // Fetch existing docs when the "From Document Journal" tab activates.
  useEffect(() => {
    if (!open || tab !== "journal" || !contextId) return;
    let cancelled = false;
    (async () => {
      setDocsLoading(true); setError(null);
      try {
        const { data } = await api.get(`/contexts/${contextId}/documents?limit=50`);
        if (!cancelled) setDocs(data?.items || []);
      } catch (e) {
        if (!cancelled) setError(`${e?.name || "Error"}: ${(e?.message || "").slice(0, 200)}`);
      } finally {
        if (!cancelled) setDocsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [open, tab, contextId]);

  // QA-2026-05-16-010 (Chunk 15) — auto-focus the search input when the
  // journal tab activates (covers the upload→journal switch where
  // `autoFocus` on the Input doesn't re-fire). One frame delay so the
  // input has mounted by the time we call .focus().
  useEffect(() => {
    if (!open || tab !== "journal") return undefined;
    const t = setTimeout(() => { journalSearchRef.current?.focus(); }, 40);
    return () => clearTimeout(t);
  }, [open, tab]);


  const handleUpload = async () => {
    if (!file) return;
    setBusy(true); setError(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(
        `/contexts/${contextId}/solva/v2/sessions/${sessionId}/attach-document`,
        fd,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      if (onAttached) onAttached(data);
      onClose && onClose();
    } catch (e) {
      const detail = e?.response?.data?.detail || e?.message || "";
      setError(`${e?.name || "Error"}: ${String(detail).slice(0, 200)}`);
    } finally { setBusy(false); }
  };

  const handleLink = async (docId) => {
    setBusy(true); setError(null);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/solva/v2/sessions/${sessionId}/attach-document`,
        { document_id: docId },
      );
      if (onAttached) onAttached(data);
      onClose && onClose();
    } catch (e) {
      const detail = e?.response?.data?.detail || e?.message || "";
      setError(`${e?.name || "Error"}: ${String(detail).slice(0, 200)}`);
    } finally { setBusy(false); }
  };

  const filteredDocs = docs.filter((d) => {
    if (!search) return true;
    const hay = `${d.name || ""} ${d.original_filename || ""}`.toLowerCase();
    return hay.includes(search.toLowerCase());
  });

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose && onClose()}>
      <DialogContent className="sm:max-w-[520px]" data-testid="solva-attach-modal">
        <DialogHeader>
          <DialogTitle>Attach a document</DialogTitle>
          <DialogDescription className="text-xs">
            Akki will read the document and reason with it for the rest of this session.
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-2 border-b border-slate-200 pb-1.5">
          <Button
            variant={tab === "upload" ? "default" : "ghost"}
            size="sm"
            onClick={() => setTab("upload")}
            data-testid="solva-attach-tab-upload"
          >
            <Upload className="mr-1.5 h-3.5 w-3.5" /> Upload new
          </Button>
          <Button
            variant={tab === "journal" ? "default" : "ghost"}
            size="sm"
            onClick={() => setTab("journal")}
            data-testid="solva-attach-tab-journal"
          >
            <FolderOpen className="mr-1.5 h-3.5 w-3.5" /> From Document Journal
          </Button>
        </div>

        {error && (
          <div
            className="rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700"
            data-testid="solva-attach-error"
          >{error}</div>
        )}

        {tab === "upload" && (
          <div className="space-y-3" data-testid="solva-attach-upload-panel">
            <label
              className="flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 px-3 py-6 hover:border-emerald-500 hover:bg-emerald-50/30"
              data-testid="solva-attach-dropzone"
            >
              <Upload className="mb-1.5 h-5 w-5 text-slate-500" />
              <p className="text-sm text-slate-700">
                {file ? file.name : "Click to choose a file"}
              </p>
              <p className="mt-1 text-[11px] text-slate-500">
                PDF, DOCX, PPTX, XLSX, CSV, TXT, PNG, JPG, HEIC — up to 25 MB
              </p>
              <input
                type="file"
                accept={ACCEPT_EXTENSIONS.join(",")}
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="hidden"
                data-testid="solva-attach-file-input"
              />
            </label>
            <Button
              onClick={handleUpload}
              disabled={!file || busy}
              data-testid="solva-attach-upload-btn"
              className="w-full"
            >
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Upload and attach
            </Button>
          </div>
        )}

        {tab === "journal" && (
          <div className="space-y-3" data-testid="solva-attach-journal-panel">
            {/* QA-2026-05-16-010 (Chunk 15, 2026-05-21) — search bar is the
                first thing inside the open panel, carries a magnifying-glass
                icon, and auto-focuses when the journal tab activates so the
                user can start typing immediately without clicking. Real-time
                filter (case-insensitive substring on name + original_filename)
                already drives `filteredDocs` below. */}
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" aria-hidden />
              <Input
                ref={journalSearchRef}
                placeholder="Search by name or filename…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                data-testid="solva-attach-journal-search"
                autoFocus
                className="pl-8"
              />
            </div>
            <div className="max-h-72 overflow-y-auto rounded border border-slate-200">
              {docsLoading && (
                <p className="px-3 py-4 text-xs text-slate-500">Loading…</p>
              )}
              {!docsLoading && filteredDocs.length === 0 && (
                <p className="px-3 py-4 text-xs text-slate-500" data-testid="solva-attach-journal-empty">
                  No documents found in this context.
                </p>
              )}
              {filteredDocs.map((d) => (
                <button
                  key={d.id}
                  type="button"
                  onClick={() => handleLink(d.id)}
                  disabled={busy}
                  className="flex w-full items-start gap-2 border-b border-slate-100 px-3 py-2 text-left text-sm last:border-b-0 hover:bg-slate-50 disabled:opacity-60"
                  data-testid={`solva-attach-journal-row-${d.id}`}
                >
                  <FileText className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-slate-800">
                      {d.name || d.original_filename || d.id}
                    </span>
                    <span className="block truncate text-[11px] text-slate-500">
                      {d.original_filename || ""} · {d.extracted_chars ?? 0} chars
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
