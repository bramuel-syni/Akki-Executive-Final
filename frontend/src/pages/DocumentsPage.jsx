/**
 * Phase Z (2026-05-27, Z-slice-4) — Documents Journal page.
 *
 * Canonical `/app/documents` surface — surfaces every document that
 * crosses the user's desk, organized by `origin` via 3 capsule tabs:
 *   • Akki-generated  (origin == "akki_generated")  → default active
 *   • Uploaded        (origin == "upload")
 *   • Emailed         (origin == "email_receipt")   → "Coming soon"
 *                                                     placeholder
 *                                                     until Email-to-
 *                                                     Akki ingestion
 *                                                     ships (Z.followup.3)
 *
 * Each row carries a category badge (the orthogonal axis — answers
 * "what kind of artefact is it?") + last-modified + click → opens
 * the canonical document drawer via the `?doc_id=` URL contract.
 *
 * Top-right `+ Add a document` button — same toast stub as the
 * Work Studio sidebar; Z-slice-5 replaces both with the real upload
 * modal.
 *
 * The orthogonal classification contract:
 *   - Work Studio tabs filter by `category` (board pack / minutes /
 *     etc).
 *   - This page filters by `origin` (akki_generated / upload /
 *     email_receipt).
 *   - A document has BOTH. An uploaded report surfaces under
 *     "Reports" in Work Studio AND under "Uploaded" here. The
 *     Z-slice-1 critical orthogonality test guards this institution-
 *     ally; Z-slice-6 will add the live-DOM E2E equivalent.
 */
import React, { useEffect, useMemo, useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Plus, Search, FileText, Calendar, ArrowRight, AlertCircle,
  Loader2, Mail,
} from "lucide-react";

import AppShell from "@/components/layout/AppShell";
import DocumentDrawer from "@/components/documents/DocumentDrawer";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import {
  ORIGIN_VALUES, displayOrigin, displayCategory,
} from "@/lib/origins";


// ─────────────────────────────────────────────────────────────────────
// Capsule tab order (top-to-bottom of the locked spec):
//   1. Akki-generated  (default active)
//   2. Uploaded
//   3. Emailed         (Coming soon placeholder until ingestion lands)
// ─────────────────────────────────────────────────────────────────────
const TAB_ORDER = ["akki_generated", "upload", "email_receipt"];


function fmtModified(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric", month: "short", day: "numeric",
    });
  } catch (_e) {
    return "—";
  }
}


function DocumentJournalRow({ doc, onOpen }) {
  const ts = doc.updated_at || doc.committed_at || doc.created_at;
  return (
    <button
      type="button"
      onClick={() => onOpen(doc)}
      className="w-full text-left border border-[var(--rule)] rounded-md bg-white px-4 py-3 flex items-start sm:items-center gap-3 flex-col sm:flex-row hover:border-[var(--ink)] hover:bg-[var(--parchment)] transition-colors"
      data-testid="documents-journal-row"
      data-origin={doc.origin || "unknown"}
      data-category={doc.category || "uncategorized"}
      data-doc-id={doc.id}
    >
      <FileText className="w-4 h-4 text-[var(--ink)] shrink-0 mt-1 sm:mt-0" strokeWidth={1.7} />
      <div className="min-w-0 flex-1">
        <p
          className="text-[14px] text-[var(--ink)] truncate"
          data-testid="documents-journal-row-name"
        >
          {doc.name || doc.original_filename || "Untitled"}
        </p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <span
            className="inline-flex items-center px-2 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider bg-[var(--parchment)] text-[var(--muted)] border border-[var(--rule)]"
            data-testid="documents-journal-row-category-badge"
          >
            {displayCategory(doc.category)}
          </span>
          <span
            className="inline-flex items-center gap-1 text-[11.5px] text-[var(--muted)]"
            data-testid="documents-journal-row-modified"
          >
            <Calendar className="w-3 h-3" strokeWidth={1.7} />
            {fmtModified(ts)}
          </span>
        </div>
      </div>
      <ArrowRight className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" />
    </button>
  );
}


export default function DocumentsPage() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id || null;
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // ── Active tab (URL-driven; defaults to akki_generated) ─────────
  const tabFromUrl = searchParams.get("tab");
  const activeTab = TAB_ORDER.includes(tabFromUrl) ? tabFromUrl : "akki_generated";

  // ── Search query (URL-driven so deep-links carry the filter) ────
  const queryFromUrl = searchParams.get("q") || "";
  const [searchInput, setSearchInput] = useState(queryFromUrl);

  // ── Counts (one fetch per origin so the badges populate) ────────
  const [counts, setCounts] = useState({ akki_generated: 0, upload: 0, email_receipt: 0 });
  // ── Listing for the active tab ──────────────────────────────────
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  // Debounced search (250ms) — keeps the URL clean while typing.
  useEffect(() => {
    const handle = setTimeout(() => {
      const sp = new URLSearchParams(searchParams);
      if (searchInput.trim()) sp.set("q", searchInput.trim()); else sp.delete("q");
      setSearchParams(sp, { replace: true });
    }, 250);
    return () => clearTimeout(handle);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchInput]);

  // Fetch counts for all 3 tabs in parallel — one round-trip per origin.
  useEffect(() => {
    if (!cid) return undefined;
    let dead = false;
    (async () => {
      try {
        const results = await Promise.all(ORIGIN_VALUES.map(
          (o) => api.get(`/contexts/${cid}/documents`, {
            params: { origin: o, limit: 500 },
          }).then((res) => Array.isArray(res.data) ? res.data.length : 0)
            .catch(() => 0),
        ));
        if (dead) return;
        setCounts({
          akki_generated: results[0],
          upload:         results[1],
          email_receipt:  results[2],
        });
      } catch {
        if (!dead) setCounts({ akki_generated: 0, upload: 0, email_receipt: 0 });
      }
    })();
    return () => { dead = true; };
  }, [cid]);

  // Fetch the active-tab listing whenever tab or query changes.
  const fetchActiveTab = useCallback(async () => {
    if (!cid) return;
    setLoading(true);
    setErr(null);
    try {
      const { data } = await api.get(`/contexts/${cid}/documents`, {
        params: {
          origin: activeTab,
          search: queryFromUrl || undefined,
          limit:  500,
        },
      });
      const list = Array.isArray(data) ? data : (data?.items || []);
      // Recurrence #3 closure — strip smoke-upload rows here too.
      setDocs(list.filter((d) => !d?.smoke_upload));
    } catch (e) {
      setDocs([]);
      setErr(apiErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [cid, activeTab, queryFromUrl]);

  useEffect(() => { fetchActiveTab(); }, [fetchActiveTab]);

  // Open the document drawer via the canonical `?doc_id=` URL contract.
  // Keep tab + query intact so closing the drawer returns the user
  // to their browsing state.
  const onOpenDoc = useCallback((doc) => {
    if (!doc?.id) return;
    const sp = new URLSearchParams(searchParams);
    sp.set("doc_id", doc.id);
    setSearchParams(sp, { replace: false });
  }, [searchParams, setSearchParams]);

  // ── + Add a document — toast stub (Z-slice-5 replaces with modal) ──
  const handleAddDocument = () => {
    toast.info("Upload modal — coming in Z-slice-5.");
  };

  // ── Tab click ─────────────────────────────────────────────────────
  const switchTab = (next) => {
    const sp = new URLSearchParams(searchParams);
    sp.set("tab", next);
    // Reset doc_id so the drawer doesn't survive a tab switch.
    sp.delete("doc_id");
    setSearchParams(sp, { replace: false });
  };

  const showEmailedPlaceholder = useMemo(
    () => activeTab === "email_receipt" && docs.length === 0 && !loading && !err,
    [activeTab, docs.length, loading, err],
  );

  return (
    <AppShell>
      <div
        className="max-w-6xl mx-auto px-4 sm:px-6 py-8"
        data-testid="documents-page"
      >
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-4 flex-wrap mb-6">
          <div>
            <h1
              className="text-[28px] sm:text-[32px] font-georgia text-[var(--ink)]"
              data-testid="documents-page-h1"
            >
              Documents
            </h1>
            <p
              className="text-[13.5px] text-[var(--muted)] mt-1.5"
              data-testid="documents-page-subtext"
            >
              Everything that crosses your desk — organized by where it came from.
            </p>
            {/* Wave 8.3 (2026-05-27) — H1 subtext audit sentinel.
                Mirrors the visible documents-page-subtext text into
                the universal page-subtext testid for the Recurrence #5
                CI guard. Preserves Z-slice-4's locked testids. */}
            <span
              data-testid="page-subtext"
              className="sr-only"
              aria-hidden="true"
            >
              Everything that crosses your desk — organized by where it came from.
            </span>
          </div>
          <Button
            type="button"
            onClick={handleAddDocument}
            variant="outline"
            className="bg-white border-2 border-[var(--ned-purple)] hover:bg-[var(--ned-purple)]/10 text-[var(--ned-purple)] rounded-sm font-medium tracking-wide shrink-0"
            data-testid="documents-page-add-document-btn"
          >
            <Plus className="w-4 h-4 mr-1.5" strokeWidth={2.2} />
            Add a document
          </Button>
        </div>

        {/* ── 3 capsule tabs ──────────────────────────────────────── */}
        <nav
          className="flex items-center gap-2 flex-wrap mb-5"
          data-testid="documents-tabs"
          role="tablist"
        >
          {TAB_ORDER.map((origin) => {
            const isActive = origin === activeTab;
            const count = counts[origin] ?? 0;
            return (
              <button
                key={origin}
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => switchTab(origin)}
                className={
                  "inline-flex items-center gap-2 px-4 py-2 rounded-full text-[12.5px] font-medium tracking-wide transition-colors border " +
                  (isActive
                    ? "bg-[var(--ink)] text-[var(--parchment)] border-[var(--ink)]"
                    : "bg-white text-[var(--ink)] border-[var(--rule)] hover:border-[var(--ink)]")
                }
                data-testid={`documents-tab-${origin}`}
                data-active={isActive ? "true" : "false"}
              >
                <span>{displayOrigin(origin)}</span>
                <span
                  className={
                    "inline-flex items-center justify-center min-w-[20px] px-1.5 py-0.5 rounded-full text-[10.5px] font-mono " +
                    (isActive
                      ? "bg-[var(--parchment)]/20 text-[var(--parchment)]"
                      : "bg-[var(--parchment)] text-[var(--muted)]")
                  }
                  data-testid={`documents-tab-${origin}-count`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </nav>

        {/* ── Search bar (filters active tab) ─────────────────────── */}
        <div className="relative mb-5" data-testid="documents-search">
          <Search
            className="w-4 h-4 text-[var(--muted)] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
            strokeWidth={1.7}
          />
          <Input
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder={`Search ${displayOrigin(activeTab).toLowerCase()} documents by name…`}
            className="pl-9 bg-white border-[var(--rule)] focus:border-[var(--ink)] rounded-sm"
            data-testid="documents-search-input"
          />
        </div>

        {/* ── Listing ─────────────────────────────────────────────── */}
        <div data-testid={`documents-listing-${activeTab}`}>
          {err ? (
            <div
              className="p-4 bg-amber-50 border border-amber-100 rounded-md text-[12.5px] text-amber-900 flex items-center gap-2"
              data-testid="documents-error"
            >
              <AlertCircle className="w-3.5 h-3.5" /> {err}
            </div>
          ) : loading ? (
            <div
              className="border border-dashed border-[var(--rule)] rounded-sm bg-[var(--parchment)] px-6 py-10 text-center"
              data-testid="documents-loading"
            >
              <Loader2 className="w-5 h-5 text-[var(--muted)] animate-spin mx-auto mb-3" />
              <p className="text-[13px] text-[var(--muted)]">Loading…</p>
            </div>
          ) : showEmailedPlaceholder ? (
            <div
              className="border border-dashed border-[var(--rule)] rounded-sm bg-[var(--parchment)] px-6 py-10 text-center"
              data-testid="documents-emailed-placeholder"
            >
              <Mail className="w-6 h-6 text-[var(--muted)] mx-auto mb-3" strokeWidth={1.7} />
              <p className="text-[14px] text-[var(--ink)] font-medium">
                Coming soon.
              </p>
              <p className="text-[12.5px] text-[var(--muted)] mt-1 max-w-md mx-auto">
                Email-to-Akki ingestion isn't wired yet. Drop files into the Uploaded tab or generate via Akki for now.
              </p>
            </div>
          ) : docs.length === 0 ? (
            <div
              className="border border-dashed border-[var(--rule)] rounded-sm bg-[var(--parchment)] px-6 py-10 text-center"
              data-testid="documents-empty"
            >
              <FileText className="w-6 h-6 text-[var(--muted)] mx-auto mb-3" />
              <p className="text-[14px] text-[var(--ink)] font-medium">
                {queryFromUrl ? "No documents match this search." : "No documents in this tab yet."}
              </p>
              <p className="text-[12.5px] text-[var(--muted)] mt-1 max-w-md mx-auto">
                {queryFromUrl
                  ? "Try clearing the search."
                  : "Upload one via Add a document above, or generate via Akki."}
              </p>
            </div>
          ) : (
            <ul className="space-y-2" data-testid="documents-list">
              {docs.map((d) => (
                <DocumentJournalRow key={d.id} doc={d} onOpen={onOpenDoc} />
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Universal document drawer — picks up `?doc_id=` from the URL. */}
      <DocumentDrawer contextId={cid} />
    </AppShell>
  );
}
