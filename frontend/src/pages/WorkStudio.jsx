/**
 * WorkStudio — Patch 2B.1 (six-tab expansion).
 *
 * Top-of-page chrome:
 *   1. Title + subtitle (verbatim copy locked in SYSTEM_STATE §2.3)
 *   2. Six-tab line — `Board Packs | Minutes | Committee Packs | Decks | Reports | Briefing`
 *      No "Cycle" prefix. Underlying API kinds are unchanged
 *      (cycle_board_pack / cycle_minutes / cycle_committee_pack / deck / report / briefing).
 *
 * Per-tab body:
 *   • Contextual action row at the top (per-tab CTAs — see ACTIONS map)
 *   • Search input + sort dropdown (the universal status filter strip
 *     is REMOVED in this patch)
 *   • ListingShell-wrapped row list, with the drawer pattern preserved
 *
 * Universal action bar (the "QUICK ACTION" header strip) is REMOVED.
 *
 * Read endpoints unchanged:
 *   GET /api/contexts/{cid}/briefings/aggregates?kind=…
 *   GET /api/contexts/{cid}/briefings/aggregates/{aid}
 *
 * v7 palette only. No hex literals.
 */
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { Link, useSearchParams, useNavigate, useParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import ValidatedBadge from "@/components/trust/ValidatedBadge";
import { toast } from "sonner";
import DocumentOverlay from "@/components/work_studio/overlay/DocumentOverlay";
import DocumentCardsSection from "@/components/work_studio/DocumentCardsSection";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import ExportModal from "@/components/studio/ExportModal";
import EnhanceModal from "@/components/studio/EnhanceModal";
import PerArtefactSynisenseBadge from "@/components/studio/PerArtefactSynisenseBadge";
import WorkStudioMasterTabs from "@/components/work_studio/WorkStudioMasterTabs";
import CreateArtefactModal from "@/components/work_studio/CreateArtefactModal";
import CompilationRail from "@/components/work_studio/CompilationRail";
// Wave 3 (2026-05-27) — Right-rail Document Journal panel.
import DocumentJournalRail from "@/components/work_studio/DocumentJournalRail";
// Phase E.3 (2026-05-26) — Universal Document Drawer + objective capture.
import DocumentDrawer from "@/components/documents/DocumentDrawer";
import ObjectiveCaptureModal from "@/components/documents/ObjectiveCaptureModal";
import CompilationWizard from "@/components/work_studio/CompilationWizard";
// Phase Z (2026-05-27, Z-slice-3) — Unified RIGHT sidebar replacing
// the legacy `<CompilationRail>` + `<DocumentJournalRail>` twin
// layout with the locked vertical card stack.
import WorkStudioSidebar from "@/components/work_studio/WorkStudioSidebar";
import {
  FileText, Presentation, ScrollText, Loader2, ArrowRight, AlertCircle,
  Layers, FolderOpen, FileDown, Wand2, Calendar, Users, Files,
  Sparkles, X as XIcon, Plus, BookOpen,
} from "lucide-react";
import WorkspaceEntryGate from "@/components/transitions/WorkspaceEntryGate";
import ListingShell from "@/components/common/ListingShell";
// Phase Z (2026-05-27, Z-slice-2) — origin display map (single source
// of truth; mirror of `backend/services/documents/origin_display.py`).
import { displayOrigin, displayCategory, displayCategoryChip } from "@/lib/origins";

// =============================================================================
// Helpers
// =============================================================================
function formatMeetingDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch { return "—"; }
}

function formatPeriod(period_start, period_end, fallback) {
  if (period_start && period_end) {
    try {
      const a = new Date(period_start);
      const b = new Date(period_end);
      const monthA = a.toLocaleDateString(undefined, { month: "short" });
      const monthB = b.toLocaleDateString(undefined, { month: "short" });
      return `${monthA}–${monthB} ${b.getFullYear()}`;
    } catch { /* fall through */ }
  }
  return fallback || "—";
}

// =============================================================================
// Six-tab listing
// Phase Z (2026-05-27, Z-slice-2) — Each tab now maps to a canonical
// `category` value on the `documents` collection. The active tab's
// listing surfaces ALL documents in that category, across all 3
// origins (akki_generated / upload / email_receipt), with the origin
// badge shown on each row.
//
// Tab → category mapping (locked by user dispatch):
//   cycle_main_and_committee_pack → board_pack
//   cycle_minutes                 → minutes
//   drafts                        → draft
//   deck                          → deck
//   report                        → report
//   briefing                      → briefing
//
// Pre-Z behavior (now retired): tabs sourced from
// /briefings/aggregates (board pack + minutes + decks + reports +
// briefings) and /documents/drafts. The new unified `GET
// /api/contexts/{cid}/documents?category=X` endpoint (shipped in
// Z-slice-1) replaces all four fetcher branches with one call.
//
// Phase E.1 (2026-05-26) — tab cleanup:
//   • "Board Packs" + "Committee Packs" merged into
//     "Main Board & Committee Packs". The new tab id is
//     `cycle_main_and_committee_pack`; the listing fetches both
//     legacy kinds in parallel and unions the rows (dedup by id).
//   • New "Drafts" tab inserted between Minutes and Decks. Sources
//     documents where `state == "draft"` from the documents
//     collection (NOT briefings/aggregates).
//   • Tab order is now:
//     Main Board & Committee Packs · Minutes · Drafts · Decks · Reports · Briefing
//   • Phase M-revision (2026-05-27) — Briefing restored INLINE as the
//     6th tab in the main horizontal strip. The original Phase M
//     shipped Briefing on a 2nd-line pill because the orchestrator
//     misread a user bug report ("brief is on the 2nd line") as a
//     layout spec. Corrected: Briefing is peer-level with the other
//     5 tabs.
// =============================================================================
const KIND_TABS = [
  {
    id: "cycle_main_and_committee_pack",
    label: "Main Board & Committee Packs",
    short: "main board & committee packs",
    icon: ScrollText,
    empty: "No board or committee packs yet.",
    // Phase Z (2026-05-27) — canonical category for this tab. Both
    // Main Board AND Committee packs roll up under `board_pack`
    // (the underlying `work_studio_exports.kind` keeps the
    // sub-distinction for compile-template selection only).
    category: "board_pack",
  },
  { id: "cycle_minutes",        label: "Minutes",  short: "minutes",  icon: FileText,     empty: "No documents in this category yet.", category: "minutes" },
  // Drafts + Briefs merge (2026-02 fork-resume) — collapsed two
  // tabs (Drafts / Briefing) into one combined tab. Per-tile chip
  // distinguishes DRAFT vs BRIEF at the row level. Data model
  // untouched: the `draft` and `briefing` categories remain orthogonal
  // in the API; this is UI grouping only. The fetcher uses array form
  // `category` to fire 2 parallel GETs and merge results.
  { id: "drafts_briefs",        label: "Drafts & Briefs", short: "drafts-briefs", icon: FileText, empty: "No drafts or briefs yet.", category: ["draft", "briefing"] },
  { id: "deck",                 label: "Decks",    short: "decks",    icon: Presentation, empty: "No documents in this category yet.", category: "deck" },
  { id: "report",               label: "Reports",  short: "reports",  icon: FileText,     empty: "No documents in this category yet.", category: "report" },
];


// Per-tab contextual action rows. Spec-locked.
function ContextActions({ kind, onExport, onEnhance, onCompile, onCreate }) {
  const ACTIONS = {
    // Phase E.1 (2026-05-26) — merged tab carries BOTH legacy
    // compile actions (the union of `compile_board_pack` +
    // `compile_committee_pack`). Either button still routes to the
    // wizard with the correct artefact-type pre-selected.
    cycle_main_and_committee_pack: [
      { id: "compile_board_pack",     label: "Compile Board Pack",     icon: Files, onClick: () => onCompile("board_pack") },
      { id: "compile_committee_pack", label: "Compile Committee Pack", icon: Files, onClick: () => onCompile("committee_pack") },
    ],
    cycle_minutes: [
      { id: "compile_minutes",    label: "Compile Minutes",    icon: Files,    onClick: () => onCompile("minutes") },
      // Chunk 3 (WS-R06) — Enhance Minutes now passes `kind="minutes"`
      // (was `"report"`). The backend has a dedicated `minutes` kind
      // registered as of Chunk 3 (same renderer as Report, but the
      // resulting artefact is filed under Minutes rather than Reports).
      { id: "enhance_minutes",    label: "Enhance Minutes",    icon: Wand2,    onClick: () => onEnhance("minutes") },
    ],
    // Phase E.1 — Drafts tab carries a single CTA today; future
    // passes can add per-draft actions (objective edit, finalize, etc.)
    drafts: [
      { id: "create_draft",       label: "+ New draft",        icon: Plus,    onClick: () => onCreate("draft") },
    ],
    // Drafts+Briefs merge (2026-02 fork-resume) — combined tab keeps
    // BOTH `+ New draft` (creates a draft document) and `Create a Brief`
    // (the briefing-export CTA), since each maps to a different
    // category-orthogonal action. Phase Z orthogonality holds: the
    // create path still files under `draft`, the brief path still
    // files under `briefing`.
    drafts_briefs: [
      { id: "create_draft",       label: "+ New draft",        icon: Plus,     onClick: () => onCreate("draft") },
      { id: "create_a_brief",     label: "Create a Brief",     icon: FileDown, onClick: () => onExport("brief") },
    ],
    deck: [
      { id: "create_summary_deck", label: "Create Summary Deck", icon: Plus,   onClick: () => onCreate("deck") },
      { id: "enhance_deck",        label: "Enhance my Deck",     icon: Wand2,  onClick: () => onEnhance("deck") },
    ],
    report: [
      { id: "create_report",       label: "Create Report",       icon: Plus,   onClick: () => onCreate("report") },
      { id: "enhance_report",      label: "Enhance my Report",   icon: Wand2,  onClick: () => onEnhance("report") },
    ],
    briefing: [
      { id: "create_a_brief",      label: "Create a Brief",      icon: FileDown, onClick: () => onExport("brief") },
    ],
  };
  const acts = ACTIONS[kind] || [];
  if (acts.length === 0) return null;
  return (
    <div
      className="flex flex-wrap items-center gap-2 mb-4"
      data-testid={`work-studio-context-actions-${kind}`}
      role="toolbar"
      aria-label="Tab actions"
    >
      {acts.map((a) => {
        const Icon = a.icon;
        return (
          <Button
            key={a.id}
            type="button"
            variant="outline"
            size="sm"
            onClick={a.onClick}
            className="rounded-sm border-[var(--rule)] text-[12.5px] hover:border-[var(--ink)] hover:bg-white"
            data-testid={`work-studio-context-action-${a.id}`}
          >
            <Icon className="w-3.5 h-3.5 mr-1.5" strokeWidth={1.7} /> {a.label}
          </Button>
        );
      })}
    </div>
  );
}


function BriefRow({ row, onOpen }) {
  // Phase M-revision (2026-05-27) — Briefing is back in KIND_TABS as
  // the 6th tab, so the icon lookup is uniform across all kinds.
  const Icon = (KIND_TABS.find((k) => k.id === row.kind) || KIND_TABS[0]).icon;
  // Chunk 5 (2026-05-13) — Patch 28D parity: show a 1-line description
  // under the title, prioritised as `description` (set by Work Studio
  // create flows) → null (no placeholder; we hide the line entirely
  // when there's nothing to show, since these rows already carry
  // structured meeting/doc/contributor metadata below the title).
  const description = (row.description || "").trim();
  return (
    <button
      type="button"
      onClick={() => onOpen(row)}
      className="w-full text-left border border-[var(--rule)] rounded-md bg-white px-4 py-3 flex items-start sm:items-center gap-3 flex-col sm:flex-row hover:border-[var(--ink)] hover:bg-[var(--parchment)] transition-colors"
      data-testid="work-studio-brief-row"
    >
      <Icon className="w-4 h-4 text-[var(--ink)] shrink-0 mt-1 sm:mt-0" strokeWidth={1.7} />
      <div className="min-w-0 flex-1">
        <p className="text-[14px] text-[var(--ink)] truncate" data-testid="work-studio-brief-row-name">
          {row.name || "Untitled"}
        </p>
        {description && (
          <p
            className="text-[12px] text-[var(--muted)] mt-0.5 line-clamp-1"
            data-testid={`work-studio-brief-row-description-${row.id}`}
          >
            {description}
          </p>
        )}
        <div className="flex items-center gap-3 mt-1 flex-wrap text-[11.5px] text-[var(--muted)]">
          <span className="inline-flex items-center gap-1" data-testid="work-studio-brief-row-meeting">
            <Calendar className="w-3 h-3" strokeWidth={1.7} />
            {formatMeetingDate(row.meeting_date)}
          </span>
          <span className="inline-flex items-center gap-1" data-testid="work-studio-brief-row-docs">
            <Files className="w-3 h-3" strokeWidth={1.7} />
            {row.document_count} {row.document_count === 1 ? "document" : "documents"}
          </span>
          <span className="inline-flex items-center gap-1" data-testid="work-studio-brief-row-contribs">
            <Users className="w-3 h-3" strokeWidth={1.7} />
            {row.contributor_count} {row.contributor_count === 1 ? "contributor" : "contributors"}
          </span>
          {row.cycle_label && (
            <span className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]">
              {row.cycle_label}
            </span>
          )}
        </div>
      </div>
      <ArrowRight className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" />
    </button>
  );
}


// =============================================================================
// Phase Z (2026-05-27, Z-slice-2) — DocumentRow
//
// Active-tab row component for the Work Studio LEFT column listing.
// Renders ONE document — sourced from the new unified
// `GET /api/contexts/{cid}/documents?category=X` endpoint — with:
//
//   - Doc name
//   - Category badge (redundant on the active tab BUT reinforces the
//     orthogonal classification model + visually equates the row
//     with rows on `/app/documents`)
//   - Origin badge (Akki-generated / Uploaded / Emailed via the
//     display map — single source of truth)
//   - Last-modified timestamp
//   - Click → opens the document drawer (board pack / committee pack
//     keep their dedicated full-page route; everything else opens via
//     the canonical `?doc_id=` URL contract picked up by the
//     <DocumentDrawer> mounted at the page root)
//
// Per the locked Z-slice-2 spec: origin badge is the primary visual
// affordance — user must instantly see "where this doc came from".
// =============================================================================
function DocumentRow({ row, onOpen }) {
  const origin = row.origin || null;
  const category = row.category || null;
  // Last-modified prefers `updated_at` → `committed_at` → `created_at`.
  const ts = row.updated_at || row.committed_at || row.created_at;
  let modifiedLabel = "—";
  if (ts) {
    try {
      const d = new Date(ts);
      modifiedLabel = d.toLocaleDateString(undefined, {
        year: "numeric", month: "short", day: "numeric",
      });
    } catch (_e) { /* keep fallback */ }
  }
  return (
    <button
      type="button"
      onClick={() => onOpen(row)}
      className="w-full text-left border border-[var(--rule)] rounded-md bg-white px-4 py-3 flex items-start sm:items-center gap-3 flex-col sm:flex-row hover:border-[var(--ink)] hover:bg-[var(--parchment)] transition-colors"
      data-testid="work-studio-document-row"
      data-origin={origin || "unknown"}
      data-category={category || "uncategorized"}
    >
      <Files className="w-4 h-4 text-[var(--ink)] shrink-0 mt-1 sm:mt-0" strokeWidth={1.7} />
      <div className="min-w-0 flex-1">
        <p className="text-[14px] text-[var(--ink)] truncate" data-testid="work-studio-document-row-name">
          {row.name || row.original_filename || "Untitled"}
        </p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          {/* Origin badge — primary affordance per Z-slice-2 spec. */}
          <span
            className="inline-flex items-center px-2 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider bg-ned-purple/10 text-[var(--ned-purple)] border border-ned-purple/20"
            data-testid="work-studio-document-row-origin-badge"
          >
            {displayOrigin(origin)}
          </span>
          {/* Category badge — reinforces orthogonality model.
              Drafts+Briefs merge (2026-02 fork-resume) — chip now uses
              brand-purple ned-purple/N (Tailwind-config short name so
              opacity composites correctly, see Wave 4.2.followup.2)
              and the shorter singular label form (DRAFT / BRIEF / etc).
              On the merged tab this is the per-tile DRAFT vs BRIEF
              discriminator the user requested. */}
          {category && (
            <span
              className="inline-flex items-center px-2 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider bg-ned-purple/10 text-ned-purple border border-ned-purple/20"
              data-testid="work-studio-document-row-category-badge"
              data-category={category}
            >
              {displayCategoryChip(category)}
            </span>
          )}
          <span
            className="inline-flex items-center gap-1 text-[11.5px] text-[var(--muted)]"
            data-testid="work-studio-document-row-modified"
          >
            <Calendar className="w-3 h-3" strokeWidth={1.7} />
            {modifiedLabel}
          </span>
        </div>
      </div>
      <ArrowRight className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" />
    </button>
  );
}




// Reusable side drawer — same shape as the legacy briefs drawer.
function BriefDrawer({ open, onClose, aid, contextId }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!open || !aid || !contextId) return undefined;
    let cancelled = false;
    setLoading(true);
    setErr(null);
    setDetail(null);
    api.get(`/contexts/${contextId}/briefings/aggregates/${encodeURIComponent(aid)}`)
      .then(({ data }) => { if (!cancelled) setDetail(data); })
      .catch((e) => { if (!cancelled) setErr(apiErrorMessage(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, aid, contextId]);

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[50vw] sm:w-[50vw] overflow-y-auto bg-[var(--paper)] p-0"
        data-testid="work-studio-brief-drawer"
      >
        <div className="px-6 py-5 border-b border-[var(--rule)] flex items-start gap-3 sticky top-0 bg-[var(--paper)] z-10">
          <div className="min-w-0 flex-1">
            <SheetHeader className="text-left">
              <SheetTitle className="akki-serif text-[20px] text-[var(--ink)] leading-snug" data-testid="work-studio-brief-drawer-title">
                {detail?.name || "Loading…"}
              </SheetTitle>
              <SheetDescription className="text-[12px] text-[var(--muted)]">
                Detail · close with Esc or the X
              </SheetDescription>
            </SheetHeader>
          </div>
          <button
            onClick={onClose}
            type="button"
            className="text-[var(--muted)] hover:text-[var(--ink)] p-1"
            aria-label="Close drawer"
            data-testid="work-studio-brief-drawer-close"
          >
            <XIcon className="w-4 h-4" />
          </button>
        </div>

        <div className="px-6 py-5">
          {loading && (
            <div className="text-[var(--muted)] text-sm flex items-center gap-2" data-testid="work-studio-brief-drawer-loading">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading detail…
            </div>
          )}
          {err && (
            <div className="text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-3 py-2 text-[12.5px] flex items-center gap-2" data-testid="work-studio-brief-drawer-err">
              <AlertCircle className="w-3.5 h-3.5" /> {err}
            </div>
          )}
          {detail && !loading && !err && (
            <>
              <PerArtefactSynisenseBadge kind={detail.kind || "briefing"} artefactId={detail.id || detail.brief_id} />

              {/* Chunk 8 (2026-05-18, QA-2026-05-16-029) — Open Document
                  Overlay CTA. Per Divergence #2 (qa_reports/...), the
                  overlay is reached via the drawer rather than directly
                  from the row click, so the heavily-tested drawer
                  preview surface stays intact. */}
              <div className="mb-5 pb-4 border-b border-[var(--rule)]" data-testid="work-studio-brief-drawer-overlay-row">
                <Button
                  type="button"
                  onClick={() => {
                    const aid = detail.id || detail.brief_id;
                    onClose();
                    window.dispatchEvent(new CustomEvent(
                      "akki:open-document-overlay",
                      { detail: { contextId, artefactId: aid } },
                    ));
                  }}
                  variant="outline"
                  className="rounded-sm border-[var(--rule)] hover:border-[var(--ink)]"
                  data-testid="work-studio-brief-drawer-open-overlay"
                >
                  Open Document Overlay
                  <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                </Button>
                <p className="text-[11.5px] text-[var(--muted)] mt-1.5">
                  Read · revise with AI · commit. Per QA-2026-05-16-029.
                </p>
              </div>

              {/* Chunk 6 (2026-05-13, WS-R01): primary CTA to open the
                  artefact in the block composer. The backend now emits
                  `composer_url` on every detail response; we route via
                  useNavigate so the SPA doesn't full-reload. */}
              {detail.composer_url && (
                <div className="mb-5 pb-4 border-b border-[var(--rule)]" data-testid="work-studio-brief-drawer-cta-row">
                  <Button
                    type="button"
                    onClick={() => {
                      onClose();
                      navigate(detail.composer_url);
                    }}
                    className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
                    data-testid="work-studio-brief-drawer-open-composer"
                  >
                    Open in composer
                    <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                  </Button>
                  <p className="text-[11.5px] text-[var(--muted)] mt-1.5">
                    Edit blocks, attach citations, and export when ready.
                  </p>
                </div>
              )}
              {(detail.validation ||
                (detail.topline?.doc_count ?? 0) > 0 ||
                (detail.topline?.contributor_count ?? 0) > 0 ||
                !!detail.topline?.period ||
                !!detail.period_start || !!detail.period_end) && (
                <div
                  className="mb-5 border border-[var(--rule)] rounded-md bg-[var(--parchment)] px-4 py-3 space-y-2"
                  data-testid="work-studio-brief-drawer-validation"
                >
                  {detail.validation && (
                    <div className="flex items-start gap-3 flex-wrap">
                      <ValidatedBadge
                        size="compact"
                        validation={detail.validation}
                        data-testid="work-studio-brief-drawer-validation-badge"
                      />
                      {detail.validation.validator_model && (
                        <span className="text-[11.5px] font-mono text-[var(--muted)]">
                          validator · {detail.validation.validator_model}
                        </span>
                      )}
                      {typeof detail.validation.confidence === "number" && (
                        <span className="text-[11.5px] font-mono text-[var(--muted)]">
                          confidence · {detail.validation.confidence}
                        </span>
                      )}
                    </div>
                  )}
                  <p
                    className="text-[12px] text-[var(--muted)] leading-[1.55]"
                    data-testid="work-studio-brief-drawer-provenance"
                  >
                    Synthesised from <strong className="text-[var(--ink)] font-medium">{detail.topline?.doc_count ?? 0}</strong>{" "}
                    source document{(detail.topline?.doc_count ?? 0) === 1 ? "" : "s"}
                    {(detail.topline?.contributor_count ?? 0) > 0 && (
                      <> · <strong className="text-[var(--ink)] font-medium">{detail.topline.contributor_count}</strong> contributor{detail.topline.contributor_count === 1 ? "" : "s"}</>
                    )}
                    {detail.topline?.period && <> · {detail.topline.period}</>}
                  </p>
                </div>
              )}

              <div
                className="grid grid-cols-3 gap-3 mb-6 border border-[var(--rule)] rounded-md bg-white px-3 py-3"
                data-testid="work-studio-brief-drawer-topline"
              >
                <div>
                  <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Documents</p>
                  <p className="text-[18px] akki-serif text-[var(--ink)]">{detail.topline?.doc_count ?? 0}</p>
                </div>
                <div>
                  <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Contributors</p>
                  <p className="text-[18px] akki-serif text-[var(--ink)]">{detail.topline?.contributor_count ?? 0}</p>
                </div>
                <div>
                  <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">Period</p>
                  <p className="text-[14px] akki-serif text-[var(--ink)] truncate" title={detail.topline?.period}>
                    {formatPeriod(detail.period_start, detail.period_end, detail.topline?.period)}
                  </p>
                </div>
              </div>

              <h3 className="akki-serif text-[15px] text-[var(--ink)] mb-3">Notes</h3>
              {(!detail.notes || detail.notes.length === 0) ? (
                <p className="text-[12.5px] text-[var(--muted)] italic" data-testid="work-studio-brief-drawer-no-notes">
                  No notes yet for this aggregate.
                </p>
              ) : (
                <ul className="space-y-4" data-testid="work-studio-brief-drawer-notes">
                  {detail.notes.map((n, i) => (
                    <li key={i} className="border border-[var(--rule)] rounded-md bg-white px-4 py-3" data-testid="work-studio-brief-drawer-note">
                      <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1">{n.topic || "Note"}</p>
                      <p className="akki-serif text-[14px] text-[var(--ink)] leading-[1.6] whitespace-pre-wrap">{n.body || "—"}</p>
                      {n.citations && n.citations.length > 0 && (
                        <div className="mt-3 pt-2 border-t border-[var(--rule)] flex flex-wrap gap-2" data-testid="work-studio-brief-drawer-citations">
                          {n.citations.filter((c) => c && c.doc_id).map((c, j) => (
                            <Link
                              key={`${c.doc_id}-${j}`}
                              to={`/app/documents/${c.doc_id}`}
                              className="inline-flex items-center gap-1 text-[11px] text-[var(--ink)] hover:underline border border-[var(--rule)] rounded-sm px-1.5 py-[2px] bg-[var(--parchment)]"
                              title={c.doc_name}
                            >
                              <FileText className="w-3 h-3" strokeWidth={1.7} />
                              <span className="truncate max-w-[180px]">{c.doc_name || c.doc_id}</span>
                            </Link>
                          ))}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}


// =============================================================================
// Main
// =============================================================================
export default function WorkStudio() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [searchParams, setSearchParams] = useSearchParams();
  // T3.3 G8 ratified routing — Board/Committee Pack cards navigate to
  // the dedicated `/app/work-studio/document/{aid}` page. Hardening
  // Step 2 Phase B (2026-05-25, B3 false-green fix) — the `navigate`
  // hook was previously missing from this component scope, so the
  // call site at line 669 (`navigate(\`/app/work-studio/document/${aid}\`)`)
  // would throw `ReferenceError` at runtime. Caught by the new
  // `no-undef` ESLint rule (Step 2 Phase C).
  const navigate = useNavigate();

  // Tab state — URL-backed. Phase E.1 (2026-05-26) — default tab is
  // now the merged `cycle_main_and_committee_pack`.
  const initialKind = (() => {
    const k = (searchParams.get("kind") || "cycle_main_and_committee_pack").toLowerCase();
    // Phase E.1 — legacy kind ids redirect to the merged tab.
    if (k === "cycle_board_pack" || k === "cycle_committee_pack") {
      return "cycle_main_and_committee_pack";
    }
    // Drafts+Briefs merge (2026-02 fork-resume) — legacy `drafts` and
    // `briefing` URL params redirect to the merged tab id. Preserves
    // ALL existing deep links (FollowUpDraftsCard, WorkStudioSidebar,
    // CompilationRail, etc) without touching their navigation strings.
    if (k === "drafts" || k === "briefing") {
      return "drafts_briefs";
    }
    return KIND_TABS.find((t) => t.id === k) ? k : "cycle_main_and_committee_pack";
  })();
  const [kind, setKind] = useState(initialKind);

  const [aggLoading, setAggLoading] = useState(true);
  const [aggItems, setAggItems] = useState([]);
  const [aggErr, setAggErr] = useState(null);
  const [aggTotal, setAggTotal] = useState(0);

  const aggQ = searchParams.get("q") || "";
  const aggSort = searchParams.get("sort") || "recent";
  const aggPage = parseInt(searchParams.get("page") || "1", 10) || 1;
  const aggPageSize = 5;

  const setListingParam = (k, v, opts = {}) => {
    const sp = new URLSearchParams(searchParams);
    if (v === "" || v === null || v === undefined || v === "recent" || v === 1) {
      sp.delete(k);
    } else {
      sp.set(k, String(v));
    }
    if (k !== "page" && !opts.preservePage) sp.delete("page");
    setSearchParams(sp, { replace: true });
  };

  // Drawer state.
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerAid, setDrawerAid] = useState(null);
  // Chunk 8 (2026-05-18) — Document Overlay state.
  const routeParams = useParams();
  const [overlayOpen, setOverlayOpen] = useState(false);
  const [overlayAid, setOverlayAid] = useState(null);
  // Auto-open the overlay when the route carries `:artefactId`.
  useEffect(() => {
    const routeAid = routeParams?.artefactId;
    if (routeAid) {
      setOverlayAid(routeAid);
      setOverlayOpen(true);
    }
  }, [routeParams?.artefactId]);
  useEffect(() => {
    const onOpenOverlay = (e) => {
      const aid = e?.detail?.artefactId;
      if (!aid) return;
      // Phase O (2026-05-27) — belt-and-suspenders redirect: even if a
      // legacy code path fires `akki:open-document-overlay`, the request
      // is routed through the canonical `?doc_id=` URL contract instead
      // of mounting the legacy DocumentOverlay. Keeps every nested-doc
      // navigation flowing through the universal <DocumentDrawer>.
      setSearchParams({ doc_id: aid, kind, context_id: cid || "" }, { replace: false });
    };
    window.addEventListener("akki:open-document-overlay", onOpenOverlay);
    return () => window.removeEventListener("akki:open-document-overlay", onOpenOverlay);
  }, [setSearchParams, kind, cid]);

  // Modal state — Export / Enhance / Compile / Create.
  const [exportOpen, setExportOpen] = useState(false);
  const [exportKind, setExportKind] = useState("brief");

  const [enhanceOpen, setEnhanceOpen] = useState(false);
  const [enhanceKind, setEnhanceKind] = useState("deck");
  const [enhanceBriefId, setEnhanceBriefId] = useState(null);
  const [enhanceMode, setEnhanceMode] = useState("default");

  const [createOpen, setCreateOpen] = useState(false);
  const [createKind, setCreateKind] = useState("deck");
  // Phase E.3 (2026-05-26) — objective capture modal for new drafts.
  const [objectiveModalOpen, setObjectiveModalOpen] = useState(false);

  // Patch 2B.2 — Compilation Wizard state.
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardPreselectType, setWizardPreselectType] = useState(null);
  const [wizardPreselectSourceId, setWizardPreselectSourceId] = useState(null);
  const [railRefreshKey, setRailRefreshKey] = useState(0);

  const fetchAggregates = useCallback(async () => {
    if (!cid) return;
    setAggLoading(true);
    setAggErr(null);
    try {
      // Phase Z (2026-05-27, Z-slice-2) — Unified document listing.
      // Every tab now fetches via `GET /api/contexts/{cid}/documents`
      // filtered by the tab's canonical `category` (mapped on the
      // KIND_TABS row). All 3 origins surface together with the
      // origin badge on each row.
      //
      // Replaces the prior 3-branch fetcher (briefings/aggregates
      // union for board pack, /documents/drafts for Drafts,
      // briefings/aggregates for everything else). The aggregate
      // endpoint remains available for legacy callers; we just don't
      // hit it from this surface anymore.
      const tab = KIND_TABS.find((t) => t.id === kind);
      const cat = tab?.category;
      if (!cat) {
        // Should never happen with the locked KIND_TABS; defensive
        // bail-out so a future tab-row regression surfaces visibly.
        setAggItems([]);
        setAggTotal(0);
        return;
      }
      // Drafts+Briefs merge (2026-02 fork-resume) — `category` may be
      // a string (single category tab) OR an array (merged tab). For
      // arrays, fire one GET per category in parallel and merge the
      // results. Backend `?category=` filter remains single-valued —
      // the data-model orthogonality lock (Phase Z-slice-6) holds.
      let all;
      if (Array.isArray(cat)) {
        const responses = await Promise.all(
          cat.map((c) =>
            api.get(`/contexts/${cid}/documents`, {
              params: { category: c, search: aggQ || undefined, limit: 500 },
            })
          )
        );
        all = responses.flatMap((r) => (Array.isArray(r.data) ? r.data : []));
      } else {
        const { data } = await api.get(`/contexts/${cid}/documents`, {
          params: {
            category: cat,
            search:   aggQ || undefined,
            limit:    500,
          },
        });
        all = Array.isArray(data) ? data : [];
      }
      // Client-side sort + paginate (the backend already returns
      // newest-first by created_at; we re-sort here to honour the
      // user's choice from the ListingShell sort dropdown).
      let sorted = all.slice();
      if (aggSort === "oldest") {
        sorted.sort((a, b) => String(a.created_at || "").localeCompare(String(b.created_at || "")));
      } else if (aggSort === "alpha") {
        sorted.sort((a, b) => String(a.name || a.original_filename || "")
          .localeCompare(String(b.name || b.original_filename || "")));
      } else {
        // "recent" is the default — newest first.
        sorted.sort((a, b) => String(b.updated_at || b.created_at || "")
          .localeCompare(String(a.updated_at || a.created_at || "")));
      }
      const total = sorted.length;
      const start = (aggPage - 1) * aggPageSize;
      const paged = sorted.slice(start, start + aggPageSize);
      setAggItems(paged);
      setAggTotal(total);
    } catch (e) {
      setAggErr(apiErrorMessage(e));
      setAggItems([]);
      setAggTotal(0);
    } finally {
      setAggLoading(false);
    }
  }, [cid, kind, aggQ, aggSort, aggPage]);

  useEffect(() => { fetchAggregates(); }, [fetchAggregates]);

  const onKind = (next) => {
    setKind(next);
    const sp = new URLSearchParams(searchParams);
    // Phase E.1 (2026-05-26) — default tab is the merged main-pack tab,
    // so we drop the param when landing there. Other tabs persist.
    if (next === "cycle_main_and_committee_pack") sp.delete("kind");
    else sp.set("kind", next);
    // Switching tabs resets pagination + search to keep listings honest.
    sp.delete("page");
    setSearchParams(sp, { replace: true });
  };

  const onExportClick = (k) => { setExportKind(k); setExportOpen(true); };
  const onEnhanceClick = (k) => {
    setEnhanceKind(k);
    setEnhanceBriefId(null);
    setEnhanceMode("default");
    setEnhanceOpen(true);
  };
  const onCompileClick = (k) => {
    // Chunk 4 (2026-05-13, WS-R02/R04/R05/R07/R08) — the Compile-XXX
    // buttons now pass their REAL artefact-type key (board_pack /
    // minutes / committee_pack / deck / report), and this map routes
    // all six wizard-eligible types to the wizard. Pre-Chunk-4 only
    // `report` and `deck` were mapped, so Board Pack / Minutes /
    // Committee Pack fell into the legacy enhance-compile fallback
    // path AND every Compile-XXX button literally passed `"report"`
    // (ContextActions, see above), making the wizard land as a
    // Report compilation regardless of which button was clicked.
    //
    // Patch 2B.2's `preselectArtefactType` prop is still used — but
    // the wizard itself now ALWAYS opens at Step 1 (see
    // `CompilationWizard.jsx` post-Chunk-4) so the user explicitly
    // confirms the radio default before continuing.
    const map = {
      board_pack:     "board_pack",
      minutes:        "minutes",
      committee_pack: "committee_pack",
      deck:           "deck",
      report:         "report",
      briefing:       "briefing",
    };
    const preset = map[k] || null;
    if (preset) {
      setWizardPreselectType(preset);
      setWizardPreselectSourceId(null);
      setWizardOpen(true);
      return;
    }
    // Fallback to the legacy enhance-compile mode if no mapping.
    setEnhanceKind(k || "report");
    setEnhanceBriefId(null);
    setEnhanceMode("compile");
    setEnhanceOpen(true);
  };
  const onCreateClick = (k) => {
    // Phase E.3 (2026-05-26) — when creating a new draft, fire the
    // Objective Capture modal first. The modal's onSave handler
    // creates the document with the objective payload and deep-links
    // into the drawer. Other artefact kinds (deck/report) keep the
    // existing CreateArtefactModal flow.
    if (k === "draft") {
      setObjectiveModalOpen(true);
      return;
    }
    setCreateKind(k);
    setCreateOpen(true);
  };

  // Phase O (2026-05-27) — Universal Document Drawer discipline. Every
  // doc-open trigger MUST route through the canonical `?doc_id=` URL
  // contract per Phase E.3 spec. The legacy `BriefDrawer` + `DocumentOverlay`
  // mounts below stay in place (open=false unreachable; dead via redirect)
  // to avoid breaking any tests that reference their mount points; their
  // open-state setters are no longer called by ANY entry point.
  // Phase Z (2026-05-27, Z-slice-2) — Row click handler.
  // Board pack / committee pack rows keep their dedicated full-page
  // route (`/app/work-studio/document/{id}`); everything else opens
  // the universal DocumentDrawer via the canonical `?doc_id=` URL
  // contract.
  //
  // 2026-02 fork-resume P0 fix — only docs that ORIGINATED via Work
  // Studio compile (i.e. have a matching row in `work_studio_exports`)
  // can use the dedicated full-page route, because that route's
  // backend (`GET /api/contexts/{cid}/work-studio/documents/{aid}`)
  // looks the artefact up in `work_studio_exports`, NOT in
  // `documents`. Auto-generated `cycle_compilation` docs live ONLY
  // in `documents`, so the full-page route 404s for them. Route them
  // through the universal `?doc_id=` drawer like every other category.
  //
  // Heuristic for "originated via Work Studio compile":
  //   - row.work_studio_export_id is present (canonical signal), OR
  //   - row.source_channel === "work_studio" (legacy fallback)
  // Anything else — cycle_compilation, uploaded PDFs, ai_generated
  // artefacts that bypassed compile — drops to the universal drawer.
  const onOpenBrief = (row) => {
    if (!row?.id) return;
    const cat = (row.category || "").toLowerCase();
    const hasWorkStudioExport = !!row.work_studio_export_id;
    const isWorkStudioOrigin = (row.source_channel || "").toLowerCase() === "work_studio";
    if (cat === "board_pack" && (hasWorkStudioExport || isWorkStudioOrigin)) {
      navigate(`/app/work-studio/document/${row.work_studio_export_id || row.id}`);
      return;
    }
    setSearchParams({ doc_id: row.id, kind, context_id: cid || "" }, { replace: false });
  };
  const onCloseDrawer = () => { setDrawerOpen(false); };

  const activeTab = useMemo(
    () => (KIND_TABS.find((t) => t.id === kind) || KIND_TABS[0]),
    [kind],
  );

  if (!cid) {
    // Phase P5.14 — even without an active context, the user
    // should still be able to navigate to the Analyze tab (which
    // is account-scoped, not context-scoped). Render the master
    // pill-tab strip on the no-context stub so the navigation
    // is reachable at every viewport.
    return (
      <AppShell>
        <div className="akki-w-medium px-8 pt-6">
          <WorkStudioMasterTabs />
        </div>
        <div className="p-12 text-center text-[var(--muted)] text-sm">No company selected.</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <WorkspaceEntryGate workspace="work_studio">
        {/* Phase P5.14 — master pill tabs above the existing surface.
            Sits inside akki-w-medium so it lines up with the listing
            column at every viewport; sits OUTSIDE the lg:flex two-
            column container so it doesn't disturb the existing
            listing/rail layout. */}
        <div className="akki-w-medium px-8 pt-6" data-testid="work-studio-master-tabs-wrap">
          <WorkStudioMasterTabs />
        </div>
        <div className="akki-w-medium px-8 py-10 lg:flex lg:items-start lg:gap-10 flex-1 relative" data-testid="work-studio">
          {/* Left column. The vertical hairline divider is rendered as
              an absolute-positioned <div> at the column boundary so it
              touches the top + bottom horizontal rules (sign-in spec). */}
          <div className="flex-1 min-w-0 lg:pr-10"
               data-testid="work-studio-listing-column"
               data-divider-id="work-studio-vertical-divider">
          <p className="akki-overline mb-2 flex items-center gap-2">
            <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Work Studio · {activeContext.name}
          </p>
          <h1
            className="akki-greeting mb-2"
            data-testid="page-h1"
          >
            Check or review your work.
          </h1>
          <p
            className="text-[13.5px] text-[var(--muted)] mt-1 mb-4"
            data-testid="page-subtext"
          >
            Compile and review the work that goes to the room.
          </p>

          {/* Six-tab line — spec-locked label order. Phase M-revision
              (2026-05-27): Briefing restored INLINE as the 6th tab
              (was on a 2nd-line pill in original Phase M close-out,
              which the user clarified was a misread of a bug report).
              Recurrence #4 (2026-05-27): replaced `flex-wrap` with
              `overflow-x-auto` so the row never wraps at narrow
              viewports (Samsung Tab A 600px portrait was wrapping
              Decks/Reports/Briefing onto a 2nd line). Tabs now scroll
              horizontally when the row exceeds viewport width. Per-
              tab `flex-shrink-0` + `whitespace-nowrap` is the
              companion piece that prevents content-driven shrinking
              + label wrapping. */}
          <div className="mt-7 border-b border-[var(--rule)]" data-testid="work-studio-tabs">
            <div className="flex items-stretch gap-0 overflow-x-auto -mb-px no-scrollbar">
              {KIND_TABS.map((t) => {
                const Icon = t.icon;
                const active = kind === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => onKind(t.id)}
                    className={`flex-shrink-0 whitespace-nowrap px-5 py-3 text-[13px] inline-flex items-center gap-2 border-b-2 -mb-px transition-colors ${
                      active
                        ? "border-[color:var(--oxblood)] text-[var(--ink)] font-medium"
                        : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
                    }`}
                    data-testid={`work-studio-tab-${t.id}${active ? "-active" : ""}`}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon className="w-3.5 h-3.5" strokeWidth={1.7} />
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Per-tab body — Phase Z (2026-05-27, Z-slice-2) rewrite.
              Active tab surfaces ALL documents in that tab's
              `category` (akki_generated + upload + email_receipt) via
              the unified GET /api/contexts/{cid}/documents endpoint.
              Each row carries an origin badge so the user knows
              instantly where the doc came from.

              Layout order per locked Z-slice-2 spec:
                1. Document listing (ListingShell + DocumentRow)
                2. ContextActions (compile / enhance / create CTAs)

              The legacy `DocumentCardsSection` (work_studio_exports
              confidence-chip grid) is REMOVED — the unified documents
              listing now subsumes Akki-generated artefacts. Confidence
              chips remain available via the document drawer. */}
          {/* Drafts+Briefs merge (2026-02 fork-resume) — when the
              active tab carries a category ARRAY (merged tab), expose
              the testid for BOTH categories on the same body so legacy
              Z-slice-6 wire-tests (which iterate `ws-tab-content-${cat}`
              per single category) still resolve to the correct wrapper.
              For single-category tabs the testid is the singular string. */}
          <div
            className="mt-5"
            data-testid={
              Array.isArray(activeTab.category)
                ? `ws-tab-content-${activeTab.category[0]}`
                : `ws-tab-content-${activeTab.category}`
            }
            data-testid-alt={
              Array.isArray(activeTab.category)
                ? activeTab.category.slice(1).map((c) => `ws-tab-content-${c}`).join(" ")
                : undefined
            }
            data-active-category={
              Array.isArray(activeTab.category)
                ? activeTab.category.join(",")
                : activeTab.category
            }
          >
            {/* Phantom testid anchors for merged-tab compat — each
                array category gets a 0×0 child carrying its solo
                `ws-tab-content-${cat}` testid so Playwright locators
                from Phase Z-slice-6 (which iterate per-category) keep
                resolving to a DOM element inside the merged body. */}
            {Array.isArray(activeTab.category) && activeTab.category.slice(1).map((c) => (
              <span
                key={c}
                className="sr-only"
                data-testid={`ws-tab-content-${c}`}
                aria-hidden="true"
              />
            ))}
            <ListingShell
              testId="work-studio-listing"
              searchValue={aggQ}
              onSearchChange={(v) => setListingParam("q", v)}
              searchPlaceholder={`Search ${activeTab.short} by name…`}
              sortOptions={[
                { key: "recent", label: "Most recent" },
                { key: "oldest", label: "Oldest" },
                { key: "alpha",  label: "A → Z" },
              ]}
              activeSortKey={aggSort}
              onSortChange={(k) => setListingParam("sort", k)}
              pageSize={aggPageSize}
              page={aggPage}
              totalCount={aggTotal}
              onPageChange={(n) => setListingParam("page", n, { preservePage: true })}
              isLoading={aggLoading}
              emptyState={
                <div
                  className="border border-dashed border-[var(--rule)] rounded-sm bg-[var(--parchment)] px-6 py-10 text-center"
                  data-testid="work-studio-agg-empty"
                >
                  <Layers className="w-6 h-6 text-[var(--muted)] mx-auto mb-3" />
                  <p className="text-[14px] text-[var(--ink)] font-medium">
                    {aggQ ? "No documents match this search." : "No documents in this category yet."}
                  </p>
                  <p className="text-[12.5px] text-[var(--muted)] mt-1 max-w-md mx-auto">
                    {aggQ
                      ? "Try clearing the search."
                      : "Upload one via the sidebar, or compile something using the actions below."}
                  </p>
                </div>
              }
              data-testid={
                Array.isArray(activeTab.category)
                  ? `ws-tab-content-${activeTab.category[0]}-shell`
                  : `ws-tab-content-${activeTab.category}-shell`
              }
              preBody={
                <div data-testid="ws-tab-compile-actions">
                  <ContextActions
                    kind={kind}
                    onExport={onExportClick}
                    onEnhance={onEnhanceClick}
                    onCompile={onCompileClick}
                    onCreate={onCreateClick}
                  />
                </div>
              }
            >
              <div data-active-category={activeTab.category}>
                {aggErr ? (
                  <div className="p-4 bg-amber-50 border border-amber-100 rounded-md text-[12px] text-amber-900 flex items-center gap-2" data-testid="work-studio-agg-err">
                    <AlertCircle className="w-3.5 h-3.5" /> {aggErr}
                  </div>
                ) : (
                  <ul className="space-y-2" data-testid="work-studio-agg-list">
                    {aggItems.map((row) => (
                      <DocumentRow key={row.id} row={row} onOpen={onOpenBrief} />
                    ))}
                  </ul>
                )}
              </div>
            </ListingShell>

            {/* Phase Z Wave 8.1 (2026-05-27) — Compile actions
                relocated from below the listing to the `preBody` slot
                of <ListingShell> above. The legacy ContextActions
                mount below is REMOVED — keeping it would duplicate
                the buttons. */}
          </div>
          </div>

          {/* Vertical hairline handle — the real border lives on the
              listing column above; this is the testable testid. */}
          <div
            data-testid="work-studio-vertical-divider"
            data-divider-attached-to="work-studio-listing-column"
            className="hidden lg:block absolute top-0 bottom-0 w-px bg-[var(--rule)] pointer-events-none"
            style={{ right: 'calc(340px + 40px + 32px)' }}
            aria-hidden="true"
          />

          {/* Phase Z (2026-05-27, Z-slice-3) — RIGHT sidebar.
              Replaces the prior `<CompilationRail>` + `<DocumentJournalRail>`
              twin layout with the locked vertical card stack:
                1. + Add a document (NEW, top)
                2. Generate Report
                3. Recent Drafts
                4. Recent Activity
                5. Document Journal preview + "View more →" to
                   /app/documents (Z-slice-4 builds that page).
              The upload entry point is wired via a toast stub until
              Z-slice-5 lands the real modal — pass `onOpenUpload`
              once the modal exists. */}
          <WorkStudioSidebar
            contextId={cid}
            onOpenWizard={(opts) => {
              setWizardPreselectType(opts?.artefactType || null);
              setWizardPreselectSourceId(opts?.sourceId || null);
              setWizardOpen(true);
            }}
            refreshKey={railRefreshKey}
          />
        </div>

        <BriefDrawer
          open={drawerOpen}
          onClose={onCloseDrawer}
          aid={drawerAid}
          contextId={cid}
        />

        {/* Chunk 8 (2026-05-18) — Document Overlay (QA-2026-05-16-029…-036). */}
        <DocumentOverlay
          open={overlayOpen}
          onClose={() => setOverlayOpen(false)}
          contextId={cid}
          artefactId={overlayAid}
        />

        <ExportModal
          open={exportOpen}
          onClose={() => setExportOpen(false)}
          kind={exportKind}
          contextId={cid}
          contextName={activeContext?.name}
        />

        <EnhanceModal
          open={enhanceOpen}
          onClose={() => { setEnhanceOpen(false); setEnhanceBriefId(null); setEnhanceMode("default"); }}
          kind={enhanceKind}
          contextId={cid}
          briefId={enhanceBriefId}
          mode={enhanceMode}
        />

        <CreateArtefactModal
          open={createOpen}
          onClose={() => setCreateOpen(false)}
          kind={createKind}
          contextId={cid}
          onCreated={() => { fetchAggregates(); setRailRefreshKey((k) => k + 1); }}
        />

        <CompilationWizard
          open={wizardOpen}
          onClose={() => {
            setWizardOpen(false);
            setWizardPreselectType(null);
            setWizardPreselectSourceId(null);
          }}
          contextId={cid}
          preselectArtefactType={wizardPreselectType}
          preselectSourceId={wizardPreselectSourceId}
          onCreated={() => setRailRefreshKey((k) => k + 1)}
        />

        {/* Phase E.3 (2026-05-26) — Universal Document Drawer.
            Opens automatically when the URL carries `?doc_id=`. */}
        <DocumentDrawer contextId={cid} />

        {/* Phase E.3 — Objective capture modal. Fires from the
            Drafts tab's "+ New draft" CTA; persists `draft.objective`
            on the freshly-created document and opens the drawer. */}
        <ObjectiveCaptureModal
          open={objectiveModalOpen}
          onOpenChange={setObjectiveModalOpen}
          onSave={async (obj) => {
            try {
              const { data: newDoc } = await api.post(`/contexts/${cid}/documents/manual-create`, {
                name: "Untitled draft",
                body: "",
                state: "draft",
                origin: "akki_generated",
                objective: { ...obj, set_at: new Date().toISOString() },
              });
              fetchAggregates();
              // Open the new draft in the drawer via deep-link.
              const sp = new URLSearchParams(searchParams);
              sp.set("doc_id", newDoc?.id);
              setSearchParams(sp, { replace: true });
            } catch (e) {
              toast.error(apiErrorMessage(e));
            }
          }}
        />
      </WorkspaceEntryGate>
    </AppShell>
  );
}
