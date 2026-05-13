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
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import ValidatedBadge from "@/components/trust/ValidatedBadge";
import { toast } from "sonner";
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
import CreateArtefactModal from "@/components/work_studio/CreateArtefactModal";
import CompilationRail from "@/components/work_studio/CompilationRail";
import CompilationWizard from "@/components/work_studio/CompilationWizard";
import {
  FileText, Presentation, ScrollText, Loader2, ArrowRight, AlertCircle,
  Layers, FolderOpen, FileDown, Wand2, Calendar, Users, Files,
  Sparkles, X as XIcon, Plus, BookOpen,
} from "lucide-react";
import WorkspaceEntryGate from "@/components/transitions/WorkspaceEntryGate";
import ListingShell from "@/components/common/ListingShell";

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
// =============================================================================
const KIND_TABS = [
  { id: "cycle_board_pack",     label: "Board Packs",     short: "board packs",     icon: ScrollText,     empty: "No board packs yet." },
  { id: "cycle_minutes",        label: "Minutes",         short: "minutes",         icon: FileText,       empty: "No minutes filed yet." },
  { id: "cycle_committee_pack", label: "Committee Packs", short: "committee packs", icon: FolderOpen,     empty: "No committee packs yet." },
  { id: "deck",                 label: "Decks",           short: "decks",           icon: Presentation,   empty: "No decks in flight." },
  { id: "report",               label: "Reports",         short: "reports",         icon: FileText,       empty: "No reports yet." },
  { id: "briefing",             label: "Briefing",        short: "briefings",       icon: BookOpen,       empty: "No briefs yet." },
];


// Per-tab contextual action rows. Spec-locked.
function ContextActions({ kind, onExport, onEnhance, onCompile, onCreate }) {
  const ACTIONS = {
    cycle_board_pack: [
      // Chunk 4 (2026-05-13, WS-R02/R04/R05/R07/R08) — pass the *real*
      // artefact-type key so the wizard opens with the right radio
      // pre-selected AND queries the right source kind on Step 2.
      // Pre-fix all three Compile-XXX buttons literally passed
      // `"report"`, which made every flow land as a Report
      // compilation regardless of which button was clicked.
      { id: "compile_board_pack", label: "Compile Board Pack", icon: Files,    onClick: () => onCompile("board_pack") },
    ],
    cycle_minutes: [
      { id: "compile_minutes",    label: "Compile Minutes",    icon: Files,    onClick: () => onCompile("minutes") },
      // Chunk 3 (WS-R06) — Enhance Minutes now passes `kind="minutes"`
      // (was `"report"`). The backend has a dedicated `minutes` kind
      // registered as of Chunk 3 (same renderer as Report, but the
      // resulting artefact is filed under Minutes rather than Reports).
      { id: "enhance_minutes",    label: "Enhance Minutes",    icon: Wand2,    onClick: () => onEnhance("minutes") },
    ],
    cycle_committee_pack: [
      { id: "compile_committee_pack", label: "Compile Committee Pack", icon: Files, onClick: () => onCompile("committee_pack") },
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

  // Tab state — URL-backed.
  const initialKind = (() => {
    const k = (searchParams.get("kind") || "cycle_board_pack").toLowerCase();
    return KIND_TABS.find((t) => t.id === k) ? k : "cycle_board_pack";
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

  // Modal state — Export / Enhance / Compile / Create.
  const [exportOpen, setExportOpen] = useState(false);
  const [exportKind, setExportKind] = useState("brief");

  const [enhanceOpen, setEnhanceOpen] = useState(false);
  const [enhanceKind, setEnhanceKind] = useState("deck");
  const [enhanceBriefId, setEnhanceBriefId] = useState(null);
  const [enhanceMode, setEnhanceMode] = useState("default");

  const [createOpen, setCreateOpen] = useState(false);
  const [createKind, setCreateKind] = useState("deck");

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
      // Patch 2B.1 — Status filter strip removed from UI. We send a
      // benign `status=all` here so the backend keeps the param shape
      // (no /api/docs change), but the result is unfiltered.
      const { data } = await api.get(`/contexts/${cid}/briefings/aggregates`, {
        params: {
          kind,
          q: aggQ || undefined,
          sort: aggSort,
          page: aggPage,
          page_size: aggPageSize,
        },
      });
      setAggItems(data?.items || []);
      setAggTotal(data?.total ?? (data?.items || []).length);
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
    if (next === "cycle_board_pack") sp.delete("kind"); else sp.set("kind", next);
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
  const onCreateClick = (k) => { setCreateKind(k); setCreateOpen(true); };

  const onOpenBrief = (row) => { setDrawerAid(row.id); setDrawerOpen(true); };
  const onCloseDrawer = () => { setDrawerOpen(false); };

  const activeTab = useMemo(() => KIND_TABS.find((t) => t.id === kind) || KIND_TABS[0], [kind]);

  if (!cid) {
    return (
      <AppShell>
        <div className="p-12 text-center text-[var(--muted)] text-sm">No company selected.</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <WorkspaceEntryGate workspace="work_studio">
        <div className="akki-w-medium px-8 py-10 xl:flex xl:items-start xl:gap-10" data-testid="work-studio">
          <div className="flex-1 min-w-0">
          <p className="akki-overline mb-2 flex items-center gap-2">
            <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Work Studio · {activeContext.name}
          </p>
          <h1 className="akki-greeting mb-2">Check or review your work.</h1>
          <p className="akki-meta max-w-2xl" data-testid="work-studio-subtitle">
            Shape board packs, decks, reports, and briefings. Agent Cycle compiles your work to executive cadence.
          </p>

          {/* Six-tab line — spec-locked label order, no "Cycle" prefix. */}
          <div className="mt-7 border-b border-[var(--rule)]" data-testid="work-studio-tabs">
            <div className="flex items-stretch gap-0 flex-wrap -mb-px">
              {KIND_TABS.map((t) => {
                const Icon = t.icon;
                const active = kind === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => onKind(t.id)}
                    className={`px-5 py-3 text-[13px] inline-flex items-center gap-2 border-b-2 -mb-px transition-colors ${
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

          {/* Per-tab body */}
          <div className="mt-5">
            <ContextActions
              kind={kind}
              onExport={onExportClick}
              onEnhance={onEnhanceClick}
              onCompile={onCompileClick}
              onCreate={onCreateClick}
            />

            <ListingShell
              testId="work-studio-listing"
              searchValue={aggQ}
              onSearchChange={(v) => setListingParam("q", v)}
              searchPlaceholder={`Search ${activeTab.short} by name…`}
              sortOptions={[
                { key: "recent", label: "Most recent" },
                { key: "oldest", label: "Oldest" },
                { key: "alpha",  label: "A → Z" },
                { key: "type",   label: "By type" },
              ]}
              activeSortKey={aggSort}
              onSortChange={(k) => setListingParam("sort", k)}
              pageSize={aggPageSize}
              page={aggPage}
              totalCount={aggTotal}
              onPageChange={(n) => setListingParam("page", n, { preservePage: true })}
              isLoading={aggLoading}
              emptyState={
                <div className="border border-dashed border-[var(--rule)] rounded-sm bg-[var(--parchment)] px-6 py-10 text-center" data-testid="work-studio-agg-empty">
                  <Layers className="w-6 h-6 text-[var(--muted)] mx-auto mb-3" />
                  <p className="text-[14px] text-[var(--ink)] font-medium">
                    {aggQ ? "No artefacts match this search." : activeTab.empty}
                  </p>
                  <p className="text-[12.5px] text-[var(--muted)] mt-1 max-w-md mx-auto">
                    {aggQ
                      ? "Try clearing the search."
                      : "When the cycle has data for this aggregate, rows will appear here."}
                  </p>
                </div>
              }
            >
              {aggErr ? (
                <div className="p-4 bg-amber-50 border border-amber-100 rounded-md text-[12px] text-amber-900 flex items-center gap-2" data-testid="work-studio-agg-err">
                  <AlertCircle className="w-3.5 h-3.5" /> {aggErr}
                </div>
              ) : (
                <ul className="space-y-2" data-testid="work-studio-agg-list">
                  {aggItems.map((row) => (
                    <BriefRow key={row.id} row={row} onOpen={onOpenBrief} />
                  ))}
                </ul>
              )}
            </ListingShell>
          </div>
          </div>
          <CompilationRail
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
      </WorkspaceEntryGate>
    </AppShell>
  );
}
