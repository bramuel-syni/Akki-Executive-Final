/**
 * DocumentCardsSection — Work Studio Document Cards listing.
 *
 * Chunk 16 (QA-2026-05-16-037/-038/-039/-040, 2026-05-21) — surfaces
 * the existing Chunk-8 `work_studio_exports` rows as cards with:
 *
 *   • Status badge (QA-037) — Draft / In Review / Committed
 *   • Lock icon overlay (QA-038) — ONLY when lifecycle_state==="committed"
 *   • Confidence chip (QA-039) — "Confidence X%" with RAG colour
 *     (uses Chunk-8 `confidence_band` from the backend listing endpoint
 *     — 80/50 thresholds; QA-039 verbatim 75/50 documented as divergence
 *     in CHUNK_16_STATE.md §3)
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
import { Download, Lock, FileText, Loader2 } from "lucide-react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";


// QA-2026-05-16-037 (Chunk 16) — verbatim badge taxonomy per the
// dispatch's locked decision: draft → Draft (neutral) · in_review →
// In Review (amber) · committed → Committed (dark filled). The
// chip uses palette tokens identical to other Chunk-9/10/11 chips so
// the surface looks native against the existing Work Studio rows.
const BADGES = {
  draft: {
    label: "Draft",
    className: "bg-[var(--ned-purple)]/10 text-[var(--ink)] border-[var(--ned-purple)]/25",
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

// QA-2026-05-16-039 (Chunk 16) — confidence chip palette. Mirrors the
// `rag_band` helper from `services/work_studio_overlay.py` (80/50
// thresholds, Chunk 8 decision). The QA-039 verbatim spec uses 75/50
// — divergence documented in CHUNK_16_STATE.md §3.
const CONFIDENCE_CHIP_PALETTE = {
  green:   "bg-emerald-50 text-emerald-800 border-emerald-200",
  amber:   "bg-amber-50 text-amber-800 border-amber-200",
  red:     "bg-rose-50 text-rose-800 border-rose-200",
  unrated: "bg-[var(--ned-purple)]/6 text-[var(--ink)] border-[var(--ned-purple)]/18",
};


export default function DocumentCardsSection({ contextId, onOpenDocument }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloading, setDownloading] = useState(null);

  useEffect(() => {
    if (!contextId) return undefined;
    let cancelled = false;
    setLoading(true); setError(null);
    api.get(`/contexts/${contextId}/work-studio/documents?limit=20`)
      .then((r) => { if (!cancelled) setItems(r.data?.items || []); })
      .catch((e) => { if (!cancelled) setError(apiErrorMessage(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
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
      const apiBase = process.env.REACT_APP_BACKEND_URL || "";
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
            downloading={downloading === it.id}
          />
        ))}
      </ul>
    </section>
  );
}


function DocumentCardRow({ item, onOpen, onDownload, downloading }) {
  const ls = (item.lifecycle_state || "draft").toLowerCase();
  const badge = BADGES[ls] || BADGES.draft;
  const isCommitted = ls === "committed";
  const intel = item.intelligence_report || {};
  const conf = typeof intel.confidence_pct === "number" ? intel.confidence_pct : null;
  const band = item.confidence_band || "unrated";
  const confClassName = CONFIDENCE_CHIP_PALETTE[band] || CONFIDENCE_CHIP_PALETTE.unrated;

  return (
    <li
      data-testid={`ws-document-card-${item.id}`}
      data-lifecycle={ls}
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

      {/* Body — name + meta row + (optional) confidence row */}
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
    </li>
  );
}
