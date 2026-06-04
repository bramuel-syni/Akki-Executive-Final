/**
 * DocumentCardsSection — Work Studio Document Cards listing.
 *
 * Chunk 16 (QA-2026-05-16-037/-038/-039/-040, 2026-05-21) — surfaces
 * the existing Chunk-8 `work_studio_exports` rows as cards with:
 *
 *   • Status badge (QA-037) — Draft / In Review / Committed
 *   • Lock icon overlay (QA-038) — ONLY when lifecycle_state==="committed"
 *   • Confidence chip (QA-039) — "Confidence X%" with RAG colour
 *     (uses `confidence_band` from the backend listing endpoint —
 *     Phase 5 (2026-06-04) flipped to the QA-doc 75/50 thresholds.
 *     The Chunk 16 80/50 divergence callout previously documented in
 *     CHUNK_16_STATE.md §3 is now resolved by the threshold flip.)
 *   • Persistent download icon (QA-040) — visible on every card.
 *
 * Reads from `GET /api/contexts/{cid}/work-studio/documents` (the
 * Chunk-8 listing endpoint, extended this chunk to include
 * `confidence_band`). Clicking the card body opens the existing
 * DocumentOverlay (Chunk 8) so the read-only consumer pattern holds.
 *
 * Scope guards honoured:
 *   - NO new backend endpoint (just augmented an existing one).
 *   - NO migration of `lifecycle_state` field.
 *   - NO modification of the Chunk-8 overlay state machine — we just
 *     READ `lifecycle_state` here.
 *   - NO new third-party libraries.
 */
import React, { useEffect, useState, useCallback } from "react";
import { Download, Lock, FileText, Loader2, MoreHorizontal, Share2, Trash2 } from "lucide-react";
import { api, apiErrorMessage, resolveBackendOrigin } from "@/lib/api";
import { toast } from "sonner";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// QA-2026-05-16-037 (Chunk 16) — verbatim badge taxonomy per the
// dispatch's locked decision: draft → Draft (neutral) · in_review →
// In Review (amber) · committed → Committed (dark filled). The
// chip uses palette tokens identical to other Chunk-9/10/11 chips so
// the surface looks native against the existing Work Studio rows.
const BADGES = {
  draft: {
    label: "Draft",
    className: "bg-ned-purple/10 text-[var(--ink)] border-ned-purple/25",
  },
  in_review: {
    label: "In Review",
    className: "bg-amber-50 text-amber-800 border-amber-200",
  },
  committed: {
    label: "Committed",
    // "Dark filled pill" per QA-037 verbatim spec — distinct from the
    // amber In Review chip; signals terminal state.
    className: "bg-slate-900 text-white border-slate-900",
  },
};

// QA-2026-05-16-039 (Chunk 16) — confidence chip palette. Phase 5
// (2026-06-04) flipped both backend `services/work_studio_overlay.py`
// and frontend `overlay/DocumentOverlay.jsx` from 80/50 to the
// QA-doc-verbatim 75/50 thresholds. The chip palette below is
// band-keyed so no numeric change needed here — the backend now
// emits the correct band on each row.
const CONFIDENCE_CHIP_PALETTE = {
  green:   "bg-emerald-50 text-emerald-800 border-emerald-200",
  amber:   "bg-amber-50 text-amber-800 border-amber-200",
  red:     "bg-rose-50 text-rose-800 border-rose-200",
  unrated: "bg-ned-purple/10 text-[var(--ink)] border-ned-purple/20",
};


export default function DocumentCardsSection({ contextId, onOpenDocument }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null);

  useEffect(() => {
    if (!contextId) return undefined;
    let cancelled = false;
    const refetch = () => {
      setLoading(true); setError(null);
      api.get(`/contexts/${contextId}/work-studio/documents?limit=20`)
        .then((r) => { if (!cancelled) setItems(r.data?.items || []); })
        .catch((e) => { if (!cancelled) setError(apiErrorMessage(e)); })
        .finally(() => { if (!cancelled) setLoading(false); });
    };
    refetch();
    // Track A Phase 5 (2026-06-04, W2 + W4) — listen for the
    // `akki:document-card-pulse` event so newly-compiled / enhanced /
    // composed docs auto-appear at the top without a page reload.
    // The event is dispatched from CompilationWizard's completion
    // handler, ExportModal's success modal, and the Drafting Drawer's
    // Save handler.
    const onPulse = () => refetch();
    if (typeof window !== "undefined") {
      window.addEventListener("akki:document-card-pulse", onPulse);
    }
    return () => {
      cancelled = true;
      if (typeof window !== "undefined") {
        window.removeEventListener("akki:document-card-pulse", onPulse);
      }
    };
  }, [contextId]);

  const onShare = useCallback((item) => {
    // Track A Phase 5 — emit the Share modal open event handled by the
    // existing share-document Sheet at page level. The G7 dispatch's
    // `recipient_emails` payload schema is preserved.
    if (typeof window === "undefined") return;
    window.dispatchEvent(new CustomEvent("akki:open-share-modal", {
      detail: { artefactId: item.id, kind: item.export_kind || "document",
                title: item.title || "Untitled document" },
    }));
  }, []);

  const onDelete = useCallback(async (item) => {
    // Phase 5 — Draft-only. Hard delete via the existing
    // `/work-studio/documents/{aid}/discard-draft` endpoint
    // (work_studio_overlay.py — discard returns the row to no-op
    // state). If the endpoint isn't reachable, surface the error.
    if (!window.confirm(`Delete the draft "${item.title || "Untitled draft"}"?`)) return;
    try {
      await api.delete(`/contexts/${contextId}/work-studio/documents/${item.id}`);
      setItems((xs) => xs.filter((x) => x.id !== item.id));
      toast.success("Draft deleted.");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }, [contextId]);

  const onDownload = useCallback(async (item) => {
    // QA-2026-05-16-040 — 2-step token-minted download flow.
    //   1) GET /api/contexts/{cid}/work-studio/exports/{eid} returns a
    //      single-use `download_token` for export rows with status="complete".
    //   2) Open `…/{eid}/download?token=…` in a new tab — the server streams
    //      the file with the original Content-Disposition + source MIME.
    if (downloading === item.id) return;
    setDownloading(item.id);
    try {
      const { data } = await api.get(
        `/contexts/${contextId}/work-studio/exports/${item.id}`,
      );
      const token = data?.download_token;
      if (!token) {
        toast.info(
          "This document doesn't have a downloadable export yet. "
          + "Compile the underlying source artefact first.",
        );
        return;
      }
      // Open in a new tab to preserve the current Work Studio state.
      // Using window.open keeps the auth cookie + token query param
      // self-contained on the server stream.
      const apiBase = resolveBackendOrigin();
      const url = `${apiBase}/api/contexts/${contextId}/work-studio/exports/${item.id}/download?token=${encodeURIComponent(token)}`;
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setDownloading(null);
    }
  }, [contextId, downloading]);

  if (loading) {
    return (
      <div
        className="mb-6 rounded-md border border-[var(--rule)] bg-white p-6 text-[12.5px] text-[var(--muted)] flex items-center gap-2"
        data-testid="work-studio-document-cards-loading"
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading document cards…
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="mb-6 rounded-md border border-amber-200 bg-amber-50 p-3 text-[12px] text-amber-900"
        data-testid="work-studio-document-cards-error"
      >
        {error}
      </div>
    );
  }

  if (!items.length) {
    // Empty state — keep concise; the rest of the Work Studio page is
    // still rendering the aggregates listing below.
    return null;
  }

  return (
    <section
      className="mb-6"
      data-testid="work-studio-document-cards-section"
      aria-label="Document Cards"
    >
      {/* Phase E.1 (2026-05-26) — "Document Cards" h2 label removed
          per user spec; the listing itself stays. */}
      <ul className="space-y-2" data-testid="work-studio-document-cards-list">
        {items.map((it) => (
          <DocumentCardRow
            key={it.id}
            item={it}
            onOpen={() => onOpenDocument && onOpenDocument(it.id, it.export_kind)}
            onDownload={() => onDownload(it)}
            onShare={() => onShare(it)}
            onDelete={() => onDelete(it)}
            downloading={downloading === it.id}
          />
        ))}
      </ul>
    </section>
  );
}


function DocumentCardRow({ item, onOpen, onDownload, onShare, onDelete, downloading }) {
  const ls = (item.lifecycle_state || "draft").toLowerCase();
  const badge = BADGES[ls] || BADGES.draft;
  const isCommitted = ls === "committed";
  const intel = item.intelligence_report || {};
  const conf = typeof intel.confidence_pct === "number" ? intel.confidence_pct : null;
  const band = item.confidence_band || "unrated";
  const confClassName = CONFIDENCE_CHIP_PALETTE[band] || CONFIDENCE_CHIP_PALETTE.unrated;
  // Track A Phase 5 (2026-06-04, fig 53 row 2) — additive fields.
  const sourceCount = typeof item.source_count === "number" ? item.source_count : null;
  const contribCount = typeof item.contributor_count === "number" ? item.contributor_count : null;
  const akkiGenerated = item.akki_generated === true;
  // Phase 5 (fig 53) — only Draft cards expose a Delete action.
  const canDelete = ls === "draft";

  return (
    <li
      data-testid={`ws-document-card-${item.id}`}
      data-lifecycle={ls}
      data-akki-generated={akkiGenerated}
      className="group relative flex items-center gap-3 border border-[var(--rule)] bg-white px-3 py-3 rounded-sm hover:border-slate-300 transition-colors"
    >
      {/* Document icon + QA-038 lock overlay */}
      <div className="relative shrink-0">
        <FileText className="h-9 w-9 text-slate-500" strokeWidth={1.4} />
        {isCommitted && (
          <span
            data-testid={`ws-document-card-lock-${item.id}`}
            className="absolute -bottom-1 -right-1 rounded-full bg-slate-900 p-0.5 ring-2 ring-white"
            aria-label="Committed — locked"
            title="Committed"
          >
            <Lock className="h-2.5 w-2.5 text-white" strokeWidth={2.5} />
          </span>
        )}
      </div>

      {/* Body — name + meta row 1 (date/conf) + (Phase 5) meta row 2 */}
      <button
        type="button"
        onClick={onOpen}
        data-testid={`ws-document-card-open-${item.id}`}
        className="flex-1 text-left min-w-0 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-400 rounded-sm"
      >
        <div className="flex items-center justify-between gap-3">
          <p className="text-[13px] font-medium text-slate-900 truncate">
            {item.title || item.export_kind || "Untitled document"}
          </p>
          {/* QA-037 status badge */}
          <span
            data-testid={`ws-document-card-status-${item.id}`}
            data-status={ls}
            className={`shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-full border text-[10px] uppercase tracking-[0.08em] font-semibold ${badge.className}`}
          >
            {badge.label}
          </span>
        </div>
        <div className="flex items-center gap-2 mt-1 text-[11.5px] text-[var(--muted)]">
          <span>{item.export_kind || "—"}</span>
          {item.updated_at && (
            <>
              <span>·</span>
              <span>{new Date(item.updated_at).toLocaleDateString(undefined, { dateStyle: "medium" })}</span>
            </>
          )}
          {/* QA-039 confidence chip — only renders when a numeric
              confidence_pct is present on the row. */}
          {conf !== null && (
            <>
              <span>·</span>
              <span
                data-testid={`ws-document-card-confidence-${item.id}`}
                data-confidence-band={band}
                className={`inline-flex items-center px-1.5 py-0.5 rounded-full border text-[10px] font-medium ${confClassName}`}
              >
                Confidence {conf}%
              </span>
            </>
          )}
        </div>
        {/* Track A Phase 5 (2026-06-04, fig 53 row 2) — sources count,
            contributors count, Akki Generated badge. Hidden entirely
            for cards that lack any of the additive fields (legacy
            rows). */}
        {(sourceCount !== null || contribCount !== null || akkiGenerated) && (
          <div
            data-testid={`ws-document-card-meta-row2-${item.id}`}
            className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5 text-[10.5px] text-[var(--muted)] font-mono uppercase tracking-[0.08em]"
          >
            {sourceCount !== null && (
              <span data-testid={`ws-document-card-sources-${item.id}`}>
                {sourceCount} source{sourceCount === 1 ? "" : "s"}
              </span>
            )}
            {contribCount !== null && (
              <>
                {sourceCount !== null && <span>·</span>}
                <span data-testid={`ws-document-card-contribs-${item.id}`}>
                  {contribCount} contributor{contribCount === 1 ? "" : "s"}
                </span>
              </>
            )}
            {akkiGenerated && (
              <>
                {(sourceCount !== null || contribCount !== null) && <span>·</span>}
                <span
                  data-testid={`ws-document-card-akki-generated-${item.id}`}
                  className="inline-flex items-center rounded-sm bg-ned-purple/10 text-ned-purple px-1 py-0.5 text-[9.5px] not-italic"
                >
                  Akki Generated
                </span>
              </>
            )}
          </div>
        )}
      </button>

      {/* QA-040 — persistent download icon, visible regardless of lifecycle_state */}
      <button
        type="button"
        onClick={onDownload}
        disabled={downloading}
        data-testid={`ws-document-card-download-${item.id}`}
        className="shrink-0 inline-flex items-center justify-center h-8 w-8 rounded-sm hover:bg-slate-100 disabled:opacity-50 transition-colors"
        aria-label={`Download ${item.title || "document"}`}
        title="Download source format"
      >
        {downloading
          ? <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-500" />
          : <Download className="h-3.5 w-3.5 text-slate-500" />}
      </button>

      {/* Track A Phase 5 (2026-06-04, fig 53) — kebab menu.
          Download / Share / (if Draft) Delete. */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            data-testid={`ws-document-card-kebab-${item.id}`}
            className="shrink-0 inline-flex items-center justify-center h-8 w-8 rounded-sm hover:bg-slate-100 transition-colors"
            aria-label="More actions"
          >
            <MoreHorizontal className="h-3.5 w-3.5 text-slate-500" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="w-[180px] text-[12.5px]"
          data-testid={`ws-document-card-kebab-menu-${item.id}`}
        >
          <DropdownMenuItem
            onClick={onDownload}
            disabled={downloading}
            data-testid={`ws-document-card-kebab-download-${item.id}`}
          >
            <Download className="h-3.5 w-3.5 mr-2" />Download
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={onShare}
            data-testid={`ws-document-card-kebab-share-${item.id}`}
          >
            <Share2 className="h-3.5 w-3.5 mr-2" />Share
          </DropdownMenuItem>
          {canDelete && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={onDelete}
                className="text-red-600 focus:text-red-700"
                data-testid={`ws-document-card-kebab-delete-${item.id}`}
              >
                <Trash2 className="h-3.5 w-3.5 mr-2" />Delete draft
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    </li>
  );
}
