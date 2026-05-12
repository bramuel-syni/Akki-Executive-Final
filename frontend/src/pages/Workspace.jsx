/**
 * Workspace.jsx — Phase E rewrite (MEMO Item 1).
 *
 * Documents Journal listing with:
 *   • Indexed full-text + notes + metadata search across active
 *     context (BM25 via the new /api/contexts/{cid}/document-journal
 *     /search endpoint).
 *   • Single-drawer-on-row-click pattern (no navigation away from the
 *     listing — replaces the legacy three-column /app/documents/:id
 *     detail, which still works as a deep-link fallback).
 *   • Title-bar Upload + Camera actions, replacing inline +Add CTAs.
 *   • Phase H width token `akki-w-medium` for the page frame.
 *
 * Restraint copy throughout — banned-word grep clean.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Link } from "react-router-dom";
import { Sparkles, Search, Upload, Camera, FileText, X, Eye, Loader2, ArrowRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import DocumentRoutingActions from "@/components/documents/DocumentRoutingActions";

/* ------------------------------------------------------------------ */
/* Helpers                                                            */
/* ------------------------------------------------------------------ */
function formatBytes(n) {
  if (n == null || isNaN(n)) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
function formatDate(s) {
  if (!s) return "";
  try { return new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }); }
  catch { return s; }
}

/* ------------------------------------------------------------------ */
/* JournalDrawer — side drawer for a single document                  */
/* Pattern mirrors WorkStudio.BriefDrawer (Phase C.1).                */
/* ------------------------------------------------------------------ */
function JournalDrawer({ doc, loading, onClose, onOpenStructuralDetail, contextId }) {
  if (!doc && !loading) return null;
  return (
    <div
      className="fixed inset-0 z-40 flex"
      role="dialog"
      aria-modal="true"
      aria-label="Document detail"
      data-testid="journal-drawer"
    >
      {/* Backdrop */}
      <div
        className="flex-1 bg-black/30 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Panel */}
      <aside
        className="
          w-full sm:w-[640px] md:w-[760px] lg:w-[820px] max-w-[92vw]
          bg-[var(--paper)] border-l border-[var(--rule)]
          h-full overflow-y-auto shadow-xl flex flex-col
        "
        data-testid="journal-drawer-panel"
      >
        {/* Title bar */}
        <header className="px-5 py-4 border-b border-[var(--rule)] bg-white sticky top-0 z-10 flex items-start gap-3">
          <FileText className="w-4 h-4 text-[var(--accent)] mt-1 shrink-0" strokeWidth={1.7} />
          <div className="flex-1 min-w-0">
            {loading ? (
              <p className="akki-meta">Loading…</p>
            ) : (
              <>
                <h2 className="akki-serif text-[18px] text-[var(--ink)] leading-snug truncate" data-testid="journal-drawer-title">
                  {doc?.name || "(untitled)"}
                </h2>
                <p className="akki-meta mt-0.5 text-[11.5px] text-[var(--muted)]">
                  {[
                    formatDate(doc?.created_at),
                    formatBytes(doc?.size_bytes),
                    doc?.doc_kind,
                    (doc?.sensitivity_band || "").toLowerCase(),
                  ].filter(Boolean).join(" · ")}
                </p>
              </>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-[var(--cream-deep)] rounded-sm shrink-0"
            aria-label="Close drawer"
            data-testid="journal-drawer-close"
          >
            <X className="w-4 h-4 text-[var(--muted)]" />
          </button>
        </header>

        {/* Body */}
        <div className="flex-1 px-5 py-4 space-y-5">
          {loading && (
            <div className="py-12 text-center">
              <Loader2 className="w-4 h-4 mx-auto animate-spin text-[var(--accent)]" />
            </div>
          )}

          {!loading && doc && (
            <>
              {/* Topline strip */}
              <div className="border border-[var(--rule)] bg-[var(--cream-deep)]/40 rounded-sm px-4 py-3" data-testid="journal-drawer-topline">
                <p className="akki-overline text-[var(--muted)] mb-1">Topline</p>
                <p className="akki-serif text-[14.5px] text-[var(--ink)] leading-[1.55]">
                  {doc.preview ||
                    (doc.extracted_text || "").slice(0, 240).replace(/\s+/g, " ").trim() ||
                    "—"}
                </p>
              </div>

              {/* Akki notes (journal commentary) */}
              <div data-testid="journal-drawer-commentary">
                <p className="akki-overline text-[var(--muted)] mb-2">From AKKI</p>
                {doc.journal_commentary ? (
                  <p className="akki-serif text-[14px] text-[var(--ink)] leading-[1.7] whitespace-pre-wrap">
                    {doc.journal_commentary}
                  </p>
                ) : (
                  <p className="text-[13px] text-[var(--muted)] italic">
                    Notes are still being prepared. They appear automatically once the document finishes processing.
                  </p>
                )}
              </div>

              {/* Body excerpt */}
              <div data-testid="journal-drawer-body-excerpt">
                <div className="flex items-center justify-between mb-2">
                  <p className="akki-overline text-[var(--muted)]">Body excerpt</p>
                  <button
                    type="button"
                    onClick={onOpenStructuralDetail}
                    className="text-[11.5px] text-[var(--accent)] hover:underline inline-flex items-center gap-1"
                    data-testid="journal-drawer-open-structural"
                  >
                    <Eye className="w-3 h-3" /> Structural detail
                  </button>
                </div>
                <p className="text-[13px] text-[var(--ink)] leading-[1.7] whitespace-pre-wrap">
                  {(doc.extracted_text || "—").slice(0, 1800)}
                  {((doc.extracted_text || "").length > 1800) && "…"}
                </p>
              </div>

              {/* Actions */}
              <div className="border-t border-[var(--rule)] pt-4 flex flex-wrap gap-2">
                <Link
                  to={`/app/documents/${doc.id}`}
                  className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm text-[var(--ink)] hover:border-[var(--accent)] no-underline inline-flex items-center gap-1"
                  data-testid="journal-drawer-open-reader"
                >
                  Open full reader <ArrowRight className="w-3 h-3" />
                </Link>
                <Link
                  to={`/app/chat?doc=${doc.id}`}
                  className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm text-[var(--ink)] hover:border-[var(--accent)] no-underline inline-flex items-center gap-1"
                  data-testid="journal-drawer-continue-chat"
                >
                  Ask in Chat
                </Link>
                {/* Phase H2 (2026-05-11) — three new routing CTAs. */}
                <DocumentRoutingActions
                  contextId={contextId}
                  doc={doc}
                  onActionDone={onClose}
                />
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Workspace page                                                     */
/* ------------------------------------------------------------------ */
export default function Workspace() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;

  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [q, setQ] = useState("");
  const [searchHits, setSearchHits] = useState(null); // null = no search ran
  const [searching, setSearching] = useState(false);

  const [drawerDoc, setDrawerDoc] = useState(null);
  const [drawerLoading, setDrawerLoading] = useState(false);

  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  // Phase H1 (2026-05-11) — drag-and-drop on the library landing.
  const [dragOver, setDragOver] = useState(false);

  /* Initial listing */
  useEffect(() => {
    if (!cid) return;
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const { data } = await api.get(`/contexts/${cid}/documents`, { params: { limit: 500 } });
        if (cancelled) return;
        // Newest first
        const sorted = [...(data || [])].sort((a, b) =>
          (b.created_at || "").localeCompare(a.created_at || "")
        );
        setDocs(sorted);
        setError(null);
      } catch (e) {
        if (!cancelled) setError(apiErrorMessage(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [cid]);

  /* Search-as-you-type (300 ms debounce) */
  useEffect(() => {
    if (!cid) return;
    if (!q.trim()) {
      setSearchHits(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const t = setTimeout(async () => {
      try {
        const { data } = await api.get(`/contexts/${cid}/document-journal/search`, {
          params: { q: q.trim(), limit: 20 },
        });
        setSearchHits(data?.hits || []);
      } catch (e) {
        setSearchHits([]);
        toast.error(apiErrorMessage(e));
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q, cid]);

  /* Upload (title-bar) */
  const onUploadFile = async (file) => {
    if (!file || !cid) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      // Workstream B.8 — let the browser set the multipart boundary.
      const { data } = await api.post(`/contexts/${cid}/documents`, fd);
      setDocs((prev) => [data, ...prev]);
      toast.success(`Added · ${data.name || file.name}`);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (cameraInputRef.current) cameraInputRef.current.value = "";
    }
  };

  /* Drawer open */
  const openDrawer = async (docId) => {
    if (!cid || !docId) return;
    setDrawerDoc({ id: docId, name: "" });
    setDrawerLoading(true);
    try {
      const { data } = await api.get(`/contexts/${cid}/documents/${docId}`);
      setDrawerDoc(data);
    } catch (e) {
      toast.error(apiErrorMessage(e));
      setDrawerDoc(null);
    } finally {
      setDrawerLoading(false);
    }
  };

  /* Listing rows: search hits OR all docs */
  const listingRows = useMemo(() => {
    if (searchHits !== null) {
      return searchHits.map((h) => ({
        id: h.doc_id,
        name: h.doc_name,
        created_at: h.created_at,
        doc_kind: h.doc_kind,
        sensitivity_band: h.sensitivity_band,
        size_bytes: h.size_bytes,
        snippet: h.snippet,
        score: h.score,
      }));
    }
    return docs.map((d) => ({
      id: d.id,
      name: d.name || "(untitled)",
      created_at: d.created_at,
      doc_kind: d.doc_kind,
      sensitivity_band: d.sensitivity_band,
      size_bytes: d.size_bytes,
      snippet: null,
      score: null,
    }));
  }, [searchHits, docs]);

  if (!cid) {
    return (
      <AppShell>
        <div className="akki-w-medium px-8 py-12 text-[var(--muted)]">
          Pick a workspace to see its documents.
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      {/* Phase H1 (2026-05-11) — page-level drag-and-drop. Drop a
          file anywhere on the workspace and it uploads via the same
          handler as the Upload button. dragOverlay flips on
          dragenter; visual cue stays subtle (calm-fast). */}
      <div
        className="akki-w-medium px-8 py-10"
        data-testid="workspace-journal"
        onDragOver={(e) => { e.preventDefault(); if (!dragOver) setDragOver(true); }}
        onDragLeave={(e) => {
          // Only deactivate when leaving the wrapper, not entering a child.
          if (e.currentTarget === e.target) setDragOver(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          const f = e.dataTransfer?.files?.[0];
          if (f) onUploadFile(f);
        }}
      >
        {dragOver && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--accent)]/8 pointer-events-none border-4 border-dashed border-[var(--accent)]/40"
            data-testid="workspace-drop-overlay"
          >
            <p className="text-2xl akki-serif text-[var(--accent)] bg-[var(--cream)] px-6 py-3 rounded-sm shadow-lg">
              Drop to add to {activeContext.name}
            </p>
          </div>
        )}
        {/* Title bar */}
        <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
          <div>
            <p className="akki-overline mb-2 flex items-center gap-2">
              <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Documents Journal · {activeContext.name}
            </p>
            <h1 className="akki-greeting mb-1">Your documents.</h1>
            <p className="akki-meta">
              Everything uploaded into <strong className="text-[var(--ink)]">{activeContext.name}</strong>. Click a row to open the side drawer.
            </p>
          </div>
          <div className="flex items-center gap-2" data-testid="workspace-titlebar-actions">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.pptx,.txt,.md,.csv,.xlsx,.png,.jpg,.jpeg,.webp,.heic,.heif,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,text/markdown,text/csv,image/*"
              className="hidden"
              onChange={(e) => onUploadFile(e.target.files?.[0])}
              data-testid="workspace-upload-input"
            />
            <input
              ref={cameraInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(e) => onUploadFile(e.target.files?.[0])}
              data-testid="workspace-camera-input"
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={uploading}
              onClick={() => fileInputRef.current?.click()}
              className="rounded-sm border-[var(--rule)] hover:border-[var(--accent)] text-[12.5px]"
              data-testid="workspace-upload-btn"
            >
              <Upload className="w-3.5 h-3.5 mr-1.5" strokeWidth={1.7} /> Upload
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={uploading}
              onClick={() => cameraInputRef.current?.click()}
              className="rounded-sm border-[var(--rule)] hover:border-[var(--accent)] text-[12.5px]"
              data-testid="workspace-camera-btn"
            >
              <Camera className="w-3.5 h-3.5 mr-1.5" strokeWidth={1.7} /> Camera
            </Button>
          </div>
        </div>

        {/* Search box */}
        <div className="relative mb-5" data-testid="workspace-search">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)]" />
          <Input
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search documents — body, AKKI notes, file name."
            className="pl-9 rounded-sm border-[var(--rule)] focus-visible:border-[var(--accent)]"
            data-testid="workspace-search-input"
            aria-label="Search documents"
          />
          {searching && (
            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--muted)] animate-spin" />
          )}
        </div>

        {/* Listing */}
        {error && (
          <p className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-3 py-2 mb-3">{error}</p>
        )}
        {loading && (
          <div className="py-16 text-center">
            <Loader2 className="w-4 h-4 mx-auto animate-spin text-[var(--accent)]" />
          </div>
        )}
        {!loading && listingRows.length === 0 && searchHits === null && (
          <div className="py-16 text-center" data-testid="workspace-empty">
            <p className="akki-serif text-[18px] text-[var(--ink)] mb-1">No documents yet.</p>
            <p className="akki-meta text-[var(--muted)]">Use Upload or Camera in the title bar to add one.</p>
          </div>
        )}
        {!loading && listingRows.length === 0 && searchHits !== null && (
          <div className="py-12 text-center text-[var(--muted)] text-[13px]" data-testid="workspace-no-search-hits">
            No documents match <span className="font-mono">{JSON.stringify(q)}</span> in this workspace.
          </div>
        )}
        {!loading && listingRows.length > 0 && (
          <ul className="border border-[var(--rule)] divide-y divide-[var(--rule)] rounded-md bg-white" data-testid="workspace-list">
            {listingRows.map((row) => (
              <li key={row.id}>
                <button
                  type="button"
                  onClick={() => openDrawer(row.id)}
                  className="w-full text-left px-4 py-3 hover:bg-[var(--cream-deep)]/30 transition-colors block"
                  data-testid={`workspace-row-${row.id}`}
                >
                  <div className="flex items-baseline justify-between gap-3 flex-wrap">
                    <p className="akki-serif text-[14.5px] text-[var(--ink)] truncate">
                      {row.name}
                    </p>
                    <p className="akki-meta text-[11px] text-[var(--muted)] font-mono shrink-0">
                      {[formatDate(row.created_at), formatBytes(row.size_bytes), row.doc_kind, (row.sensitivity_band || "").toLowerCase()].filter(Boolean).join(" · ")}
                    </p>
                  </div>
                  {/* Patch 28D — Document Journal description line.
                      Uses the snippet (derived from doc.summary or
                      first 240 chars of extracted text — see ll. 117-120
                      above) when present; muted placeholder when not.
                      Two-line clamp keeps rows readable. */}
                  <p
                    className={
                      "text-[12.5px] mt-1 leading-[1.55] line-clamp-2 " +
                      (row.snippet
                        ? "text-[var(--muted)]"
                        : "text-[var(--muted)] italic opacity-70")
                    }
                    data-testid={`workspace-row-snippet-${row.id}`}
                  >
                    {row.snippet || "No summary available yet."}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {(drawerDoc || drawerLoading) && (
        <JournalDrawer
          doc={drawerDoc}
          loading={drawerLoading}
          contextId={cid}
          onClose={() => { setDrawerDoc(null); setDrawerLoading(false); }}
          onOpenStructuralDetail={() => {
            // The legacy three-column reader (ReadingView.jsx) is the
            // structural-detail view for now. Keep route working as
            // documented in the C.3 brief.
            if (drawerDoc?.id) {
              window.open(`/app/documents/${drawerDoc.id}`, "_self");
            }
          }}
        />
      )}
    </AppShell>
  );
}
