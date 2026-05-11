/**
 * WorkStudio — Phase C.1 rewire (memo Item 2).
 *
 * The Workspace surface is reorganised around the memo's three
 * aggregate types — Cycle Board Pack, Cycle Minutes, Cycle Board
 * Committee Packs — listed under a single tabbed control. Clicking a
 * row opens a side drawer (~50% page width) showing the topline strip
 * (doc count, contributor count, period) and notes classified by
 * topic, with citations to source documents. The drawer pattern is
 * the same one Phase E will adopt for the Document Journal.
 *
 * A horizontal action bar sits above the listing with five buttons —
 * Export a Brief, Export a Summary Deck, Export a Report, Enhance my
 * Deck, Enhance my Report. In C.1 they are visible but inert; they
 * raise a toast saying the action will work in the next phase. The
 * actual export and enhance logic ships in C.2 and C.3.
 *
 * The existing Decks and Reports tabs remain below the briefs listing
 * (frozen until C.2 redesigns the output to production quality). Each
 * tab now carries a one-line "About" caption in restraint voice.
 *
 * Read endpoints (Phase C.1 — added to backend/routers/briefings.py):
 *   GET /api/contexts/{cid}/briefings/aggregates?kind=…    listing
 *   GET /api/contexts/{cid}/briefings/aggregates/{aid}     drawer detail
 *
 * Frozen surfaces NOT touched by this rewire:
 *   /app/workspace (Document Journal — Phase E),
 *   /app/contexts, Solva, Pulse, Cycle Manager, Chat, AppShell nav.
 */
import React, { useEffect, useMemo, useState, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
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
import {
  FileText, Presentation, ScrollText, Plus, Loader2, ArrowRight, AlertCircle,
  Layers, FolderOpen, FileDown, Wand2, Calendar, Users, Files,
  Sparkles, Inbox, X as XIcon,
} from "lucide-react";
import WorkspaceEntryGate from "@/components/transitions/WorkspaceEntryGate";

// =============================================================================
// Helpers
// =============================================================================
function shortAge(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const ms = Date.now() - d.getTime();
    const mins = Math.floor(ms / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch { return "—"; }
}

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

function SensitivityChip({ s }) {
  if (!s || !s.label) return null;
  const cls = {
    Public: "bg-emerald-50 text-emerald-700 border-emerald-100",
    Internal: "bg-sky-50 text-sky-700 border-sky-100",
    Confidential: "bg-amber-50 text-amber-800 border-amber-100",
    Restricted: "bg-rose-50 text-rose-700 border-rose-100",
  }[s.label] || "bg-[var(--cream-deep)] text-[var(--deep)] border-[var(--rule)]";
  return (
    <span className={`inline-flex items-center text-[10.5px] uppercase tracking-[0.14em] font-medium border rounded-sm px-1.5 py-[2px] ${cls}`}>
      {s.label}
    </span>
  );
}

// =============================================================================
// Three-aggregate-type briefs listing (Phase C.1 core)
// =============================================================================
const KIND_TABS = [
  {
    id: "cycle_board_pack",
    label: "Cycle Board Pack",
    short: "Board Pack",
    icon: ScrollText,
    empty: "No board packs prepared for this period yet.",
  },
  {
    id: "cycle_minutes",
    label: "Cycle Minutes",
    short: "Minutes",
    icon: FileText,
    empty: "No minutes uploaded for this period.",
  },
  {
    id: "cycle_committee_pack",
    label: "Cycle Board Committee Packs",
    short: "Committee Packs",
    icon: FolderOpen,
    empty: "No committee packs filed yet.",
  },
];

function BriefRow({ row, onOpen }) {
  const Icon = (KIND_TABS.find((k) => k.id === row.kind) || KIND_TABS[0]).icon;
  return (
    <button
      type="button"
      onClick={() => onOpen(row)}
      className="w-full text-left border border-[var(--rule)] rounded-md bg-white px-4 py-3 flex items-start sm:items-center gap-3 flex-col sm:flex-row hover:border-[var(--accent)] hover:bg-[var(--cream-deep)]/40 transition-colors"
      data-testid="work-studio-brief-row"
    >
      <Icon className="w-4 h-4 text-[var(--deep)] shrink-0 mt-1 sm:mt-0" strokeWidth={1.7} />
      <div className="min-w-0 flex-1">
        <p className="text-[14px] text-[var(--ink)] truncate" data-testid="work-studio-brief-row-name">
          {row.name || "Untitled"}
        </p>
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

// Reusable side drawer — same shape Phase E will use for the Document
// Journal. Keeps the page mounted underneath; user can dismiss with
// the close button or the overlay click.
function BriefDrawer({ open, onClose, aid, contextId }) {
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState(null);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!open || !aid || !contextId) return;
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
                Brief detail · close with Esc or the X
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
              {/* STUDIO sprint (2026-05-12) — per-artefact Synisense
                  badge + storyline. Sits at the very top of the drawer
                  body so the trust posture is visible before the
                  validation / topline / sections. */}
              <PerArtefactSynisenseBadge kind={detail.kind || "briefing"} artefactId={detail.id || detail.brief_id} />
              {/* Phase F.1 — Validation header. Provenance + confidence
                  sits AT THE TOP of the drawer so the executive sees
                  what's vouched for before reading the body. Block is
                  honest-render: each line only appears when its
                  underlying field is present. The whole block stays
                  hidden when the aggregate has no validation metadata
                  AND no topline information at all. */}
              {(detail.validation ||
                (detail.topline?.doc_count ?? 0) > 0 ||
                (detail.topline?.contributor_count ?? 0) > 0 ||
                !!detail.topline?.period ||
                !!detail.period_start || !!detail.period_end) && (
                <div
                  className="mb-5 border border-[var(--rule)] rounded-md bg-[var(--cream-deep)]/30 px-4 py-3 space-y-2"
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
                  {(detail.topline?.doc_count ?? 0) > 0 ? (
                    <p
                      className="text-[12px] text-[var(--muted)] leading-[1.55]"
                      data-testid="work-studio-brief-drawer-provenance"
                    >
                      Synthesised from <strong className="text-[var(--ink)] font-medium">{detail.topline.doc_count}</strong>{" "}
                      source document{detail.topline.doc_count === 1 ? "" : "s"}
                      {(detail.topline?.contributor_count ?? 0) > 0 && (
                        <> · <strong className="text-[var(--ink)] font-medium">{detail.topline.contributor_count}</strong> contributor{detail.topline.contributor_count === 1 ? "" : "s"}</>
                      )}
                      {detail.topline?.period && <> · {detail.topline.period}</>}
                    </p>
                  ) : (
                    <p
                      className="text-[12px] text-[var(--muted)] leading-[1.55]"
                      data-testid="work-studio-brief-drawer-provenance"
                    >
                      Provenance · period <strong className="text-[var(--ink)] font-medium">{detail.topline?.period || formatPeriod(detail.period_start, detail.period_end, "—")}</strong>
                      {(detail.topline?.contributor_count ?? 0) > 0 && (
                        <> · <strong className="text-[var(--ink)] font-medium">{detail.topline.contributor_count}</strong> contributor{detail.topline.contributor_count === 1 ? "" : "s"}</>
                      )}
                      {!detail.validation && (
                        <span className="ml-1 text-[var(--muted)] italic"> · awaiting validator pass</span>
                      )}
                    </p>
                  )}
                </div>
              )}

              {/* Topline strip — memo: doc count, contributors, period */}
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

              {/* Notes — classified by topic with citations */}
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
                          {n.citations.map((c, j) => (
                            <Link
                              key={`${c.doc_id}-${j}`}
                              to={`/app/documents/${c.doc_id}`}
                              className="inline-flex items-center gap-1 text-[11px] text-[var(--accent)] hover:text-[var(--accent-dark)] border border-[var(--rule)] rounded-sm px-1.5 py-[2px] bg-[var(--cream-deep)]/40"
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

// Six-button action bar — three Create buttons (Phase C.2 / F.4 relabel),
// two Enhance buttons (Phase C.3), plus a Compile-a-Report CTA (F.6)
// that reuses the legacy upload-and-enhance path for external docs.
function ActionBar({ onExportClick, onEnhanceClick, onCompileClick }) {
  const ACTIONS = [
    { id: "export_brief",    label: "Create a Brief",         icon: FileDown,  kind: "brief",  flow: "export"  },
    { id: "export_deck",     label: "Create a Summary Deck",  icon: FileDown,  kind: "deck",   flow: "export"  },
    { id: "export_report",   label: "Create a Report",        icon: FileDown,  kind: "report", flow: "export"  },
    { id: "enhance_deck",    label: "Enhance my Deck",        icon: Wand2,     kind: "deck",   flow: "enhance" },
    { id: "enhance_report",  label: "Enhance my Report",      icon: Wand2,     kind: "report", flow: "enhance" },
  ];
  return (
    <div
      className="flex justify-between items-center gap-3 mb-4 px-3 py-2 border border-[var(--rule)] bg-white rounded-md"
      data-testid="work-studio-action-bar"
      role="toolbar"
      aria-label="Work Studio actions"
    >
      {/* Phase F.2.B — left-anchored "Quick Action" editorial label.
          Not a button. Oxblood double-rule on top + bottom marks the
          section without competing with the clustered CTAs on the
          right. Plain <span>; no hover, no click handler. */}
      <span
        className="inline-block py-1 text-[11px] font-medium tracking-[0.18em] uppercase text-[var(--accent)] border-y border-[var(--accent)] select-none"
        data-testid="work-studio-quick-action-label"
        aria-hidden="false"
      >
        Quick Action
      </span>
      <div className="flex flex-wrap items-center gap-2 justify-end" data-testid="work-studio-action-cluster">
        {ACTIONS.map((a) => {
          const Icon = a.icon;
          return (
            <Button
              key={a.id}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => a.flow === "export" ? onExportClick(a.kind) : onEnhanceClick(a.kind)}
              className="rounded-sm border-[var(--rule)] text-[12.5px] hover:border-[var(--accent)]"
              data-testid={`work-studio-action-${a.id}`}
            >
              <Icon className="w-3.5 h-3.5 mr-1.5" strokeWidth={1.7} /> {a.label}
            </Button>
          );
        })}
        {/* Phase F.6 — Compile Report. Reuses EnhanceModal's Path A
            (legacy upload-and-enhance, POST /work-studio/enhance/report)
            but with copy that names the use case: pulling together
            external emails / attachments / PDFs into one structured
            report. Phase F.2.C — relabelled "Compile a Report" → "Compile Report". */}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => onCompileClick && onCompileClick("report")}
          className="rounded-sm border-[var(--rule)] text-[12.5px] hover:border-[var(--accent)]"
          data-testid="work-studio-action-compile_report"
        >
          <Files className="w-3.5 h-3.5 mr-1.5" strokeWidth={1.7} /> Compile Report
        </Button>
      </div>
    </div>
  );
}

// =============================================================================
// Decks + Reports — preserved Phase 13.3 listing (frozen until C.2)
// =============================================================================
function ArtefactRow({ kind, item, onRefine }) {
  const href = item.href || "#";
  const updated = item.updated_at || item.modified_at || item.created_at;
  const Icon = kind === "briefing" ? ScrollText : kind === "deck" ? Presentation : FileText;
  const hasBrief = !!item.brief_id;
  return (
    <li className="border border-[var(--rule)] rounded-md bg-white px-4 py-3 flex items-start sm:items-center gap-3 flex-col sm:flex-row" data-testid="work-studio-row">
      <Icon className="w-4 h-4 text-[var(--deep)] shrink-0 mt-1 sm:mt-0" strokeWidth={1.7} />
      <div className="min-w-0 flex-1">
        <p className="text-[14px] text-[var(--ink)] truncate">{item.title || "Untitled"}</p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <span className="text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
            {kind} · {item.status || "draft"}
          </span>
          <SensitivityChip s={item.sensitivity} />
          {item.synisense_version >= 1 && (
            <span className="text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--accent)]">shielded</span>
          )}
          {hasBrief && (
            <span
              className="text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--accent-dark)] border border-[var(--accent)] rounded-sm px-1.5 py-[1px]"
              title="This artefact has a persisted Brief — refine via two-pass enhance."
              data-testid="work-studio-row-brief-chip"
            >
              brief
            </span>
          )}
          {item.validation && <ValidatedBadge size="compact" validation={item.validation} />}
        </div>
      </div>
      <span className="text-[11.5px] text-[var(--muted)] shrink-0 sm:ml-2" title={updated || ""}>
        {shortAge(updated)}
      </span>
      {hasBrief && (
        <Button
          variant="ghost" size="sm"
          onClick={() => onRefine?.({ kind, brief_id: item.brief_id, title: item.title })}
          className="shrink-0 text-[12.5px] text-[var(--accent-dark)] hover:bg-[var(--accent-soft)]"
          data-testid="work-studio-row-refine"
        >
          <Sparkles className="w-3.5 h-3.5 mr-1" /> Refine
        </Button>
      )}
      <Link to={href} className="shrink-0">
        <Button variant="ghost" size="sm" className="text-[12.5px] text-[var(--accent)] hover:bg-[var(--accent-soft)]">
          Open <ArrowRight className="w-3.5 h-3.5 ml-1" />
        </Button>
      </Link>
    </li>
  );
}

async function loadDecksReports(cid) {
  // Existing Phase 13.3 sources, retained for the lower section.
  const out = { decks: [], reports: [], briefings: [], errors: [] };
  try {
    const { data } = await api.get(`/contexts/${cid}/decks`);
    const raw = Array.isArray(data) ? data : (data?.items || data?.decks || []);
    const items = raw.filter((d) => (d.status || "draft") !== "sent");
    out.decks = items.map((d) => ({ ...d, href: `/app/decks/${d.id}` }));
  } catch (e) { out.errors.push(["decks", apiErrorMessage(e)]); }
  try {
    const { data } = await api.get(`/reports/inbox`);
    const items = (data?.reports || data?.items || []).filter((r) => {
      if (r.context_id && r.context_id !== cid) return false;
      const s = (r.status || "draft").toLowerCase();
      return s !== "sent" && s !== "finalised" && s !== "finalized" && s !== "complete" && s !== "archived";
    });
    out.reports = items.map((r) => ({ ...r, href: `/app/cycle?tab=overview&report=${r.id}` }));
  } catch {
    out.reports = [];
  }
  return out;
}

// =============================================================================
// Main
// =============================================================================
export default function WorkStudio() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [searchParams, setSearchParams] = useSearchParams();

  // Top tabs for the three aggregate kinds.
  const initialKind = (() => {
    const k = (searchParams.get("kind") || "cycle_board_pack").toLowerCase();
    return KIND_TABS.find((t) => t.id === k) ? k : "cycle_board_pack";
  })();
  const [kind, setKind] = useState(initialKind);
  const [aggLoading, setAggLoading] = useState(true);
  const [aggItems, setAggItems] = useState([]);
  const [aggErr, setAggErr] = useState(null);

  // Drawer state.
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerAid, setDrawerAid] = useState(null);

  // Phase C.2 — export modal state.
  const [exportOpen, setExportOpen] = useState(false);
  const [exportKind, setExportKind] = useState("brief");

  // Phase C.3 — enhance modal state.
  const [enhanceOpen, setEnhanceOpen] = useState(false);
  const [enhanceKind, setEnhanceKind] = useState("deck");
  const [enhanceBriefId, setEnhanceBriefId] = useState(null);
  // Phase F.6 — when true, EnhanceModal renders Compile-a-Report copy
  // for its existing Path A (upload + enhance) flow.
  const [enhanceMode, setEnhanceMode] = useState("default");

  // Phase C.3 — listing of Solva-/chat-originated briefings (kind=briefing)
  // pulled from db.boardpacks via the existing aggregates listing route,
  // filtered to rows that carry a top-level brief_id.
  const [seedRows, setSeedRows] = useState([]);

  // Decks + reports (lower section).
  const [drData, setDrData] = useState({ decks: [], reports: [], errors: [] });
  const [drLoading, setDrLoading] = useState(true);
  // Inner tab for decks/reports section.
  const initialView = (() => {
    const v = (searchParams.get("view") || "decks").toLowerCase();
    return ["decks", "reports"].includes(v) ? v : "decks";
  })();
  const [view, setView] = useState(initialView);

  const fetchAggregates = useCallback(async () => {
    if (!cid) return;
    setAggLoading(true);
    setAggErr(null);
    try {
      const { data } = await api.get(`/contexts/${cid}/briefings/aggregates`, { params: { kind } });
      setAggItems(data?.items || []);
    } catch (e) {
      setAggErr(apiErrorMessage(e));
      setAggItems([]);
    } finally {
      setAggLoading(false);
    }
  }, [cid, kind]);

  useEffect(() => { fetchAggregates(); }, [fetchAggregates]);

  useEffect(() => {
    if (!cid) return;
    let cancelled = false;
    setDrLoading(true);
    loadDecksReports(cid).then((res) => {
      if (cancelled) return;
      setDrData(res);
      setDrLoading(false);
      res.errors.forEach(([k, msg]) => toast.error(`Could not load ${k}: ${msg}`));
    });
    return () => { cancelled = true; };
  }, [cid]);

  const onKind = (next) => {
    setKind(next);
    const sp = new URLSearchParams(searchParams);
    if (next === "cycle_board_pack") sp.delete("kind"); else sp.set("kind", next);
    setSearchParams(sp, { replace: true });
  };

  const onView = (next) => {
    setView(next);
    const sp = new URLSearchParams(searchParams);
    if (next === "decks") sp.delete("view"); else sp.set("view", next);
    setSearchParams(sp, { replace: true });
  };

  const onActionInProgress = (label) => {
    toast(`${label} — this will work in the next phase.`, {
      description: "Action queued for C.3.",
      duration: 3500,
    });
  };

  const onExportClick = (kind) => {
    setExportKind(kind);
    setExportOpen(true);
  };

  const onEnhanceClick = (kind) => {
    setEnhanceKind(kind);
    setEnhanceBriefId(null);
    setEnhanceMode("default");
    setEnhanceOpen(true);
  };

  // Phase F.6 — Compile-a-Report. Reuses Path A of EnhanceModal
  // (legacy /work-studio/enhance/{kind} upload+enhance), with copy
  // that frames the use case as combining external docs (emails,
  // attachments, PDFs received outside Akki) into a single report.
  const onCompileClick = (kind) => {
    setEnhanceKind(kind || "report");
    setEnhanceBriefId(null);
    setEnhanceMode("compile");
    setEnhanceOpen(true);
  };

  const onOpenBrief = (row) => {
    setDrawerAid(row.id);
    setDrawerOpen(true);
  };
  const onCloseDrawer = () => {
    setDrawerOpen(false);
    // Keep the aid so the drawer-content state isn't immediately blanked
    // during the close transition. Reset on next open.
  };

  // Sorted derived lists for the lower Decks/Reports section. Computed
  // BEFORE the !cid early return so hook count stays constant across
  // renders (rules-of-hooks).
  const visibleDecks = useMemo(
    () => [...(drData.decks || [])].sort(
      (a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0),
    ),
    [drData],
  );
  const visibleReports = useMemo(
    () => [...(drData.reports || [])].sort(
      (a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0),
    ),
    [drData],
  );

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
      <div className="akki-w-medium px-8 py-10" data-testid="work-studio">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Work Studio · {activeContext.name}
        </p>
        <h1 className="akki-greeting mb-2">Check or review your work.</h1>
        <p className="akki-meta max-w-2xl">
          Cycle aggregates for <strong className="text-[var(--ink)]">{activeContext.name}</strong> — board packs, minutes, and committee packs. Click any row for the topline and notes.
        </p>

        {/* C.4 — action bar sits directly after the intro copy and BEFORE the kind tabs */}
        <div className="mt-6">
          <ActionBar
            onExportClick={onExportClick}
            onEnhanceClick={onEnhanceClick}
            onCompileClick={onCompileClick}
          />
        </div>

        {/* F.7 — section heading: "Board Artefacts" (was "Cycle Board
            Pack, Briefs and Reports") above the kind tabs */}
        <h2
          className="akki-serif text-[18px] text-[var(--ink)] font-medium mt-6 mb-2"
          data-testid="work-studio-section-heading"
        >
          Board Artefacts
        </h2>

        {/* Three-tab kind selector */}
        <div className="border-b border-[var(--rule)] flex items-stretch gap-0 mb-4 flex-wrap" data-testid="work-studio-kind-tabs">
          {KIND_TABS.map((t) => {
            const Icon = t.icon;
            const active = kind === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => onKind(t.id)}
                className={`px-5 py-3 text-[14px] inline-flex items-center gap-2 border-b-2 -mb-px transition-colors ${
                  active
                    ? "border-[var(--accent)] text-[var(--ink)] font-medium"
                    : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
                }`}
                data-testid={`work-studio-kind-tab-${t.id}${active ? "-active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                <Icon className="w-3.5 h-3.5" strokeWidth={1.7} />
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Aggregate listing */}
        {aggLoading ? (
          <div className="p-12 text-center text-[var(--muted)] text-sm flex items-center justify-center gap-2" data-testid="work-studio-agg-loading">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading {KIND_TABS.find((t) => t.id === kind).short.toLowerCase()}…
          </div>
        ) : aggErr ? (
          <div className="p-4 bg-amber-50 border border-amber-100 rounded-md text-[12px] text-amber-900 flex items-center gap-2" data-testid="work-studio-agg-err">
            <AlertCircle className="w-3.5 h-3.5" /> {aggErr}
          </div>
        ) : aggItems.length === 0 ? (
          <div className="p-12 text-center border border-[var(--rule)] rounded-md bg-white" data-testid="work-studio-agg-empty">
            <Layers className="w-6 h-6 text-[var(--muted)] mx-auto mb-3" />
            <p className="text-[14px] text-[var(--ink)] font-medium">{KIND_TABS.find((t) => t.id === kind).empty}</p>
            <p className="text-[12.5px] text-[var(--muted)] mt-1 max-w-md mx-auto">
              When the cycle has data for this aggregate, rows will appear here.
            </p>
          </div>
        ) : (
          <ul className="space-y-2" data-testid="work-studio-agg-list">
            {aggItems.map((row) => (
              <BriefRow key={row.id} row={row} onOpen={onOpenBrief} />
            ))}
          </ul>
        )}

        {/* Existing Decks / Reports section — preserved, with About lines */}
        <div className="mt-12">
          <div className="border-b border-[var(--rule)] flex items-stretch gap-0 mb-3 flex-wrap" data-testid="work-studio-dr-tabs">
            <button
              type="button"
              onClick={() => onView("decks")}
              className={`px-5 py-3 text-[14px] inline-flex items-center gap-2 border-b-2 -mb-px transition-colors ${
                view === "decks"
                  ? "border-[var(--accent)] text-[var(--ink)] font-medium"
                  : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
              data-testid={`work-studio-dr-tab-decks${view === "decks" ? "-active" : ""}`}
            >
              <Presentation className="w-3.5 h-3.5" strokeWidth={1.7} />
              Decks
              <span className="text-[11px] text-[var(--muted)] font-mono">· {visibleDecks.length}</span>
            </button>
            <button
              type="button"
              onClick={() => onView("reports")}
              className={`px-5 py-3 text-[14px] inline-flex items-center gap-2 border-b-2 -mb-px transition-colors ${
                view === "reports"
                  ? "border-[var(--accent)] text-[var(--ink)] font-medium"
                  : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
              data-testid={`work-studio-dr-tab-reports${view === "reports" ? "-active" : ""}`}
            >
              <FileText className="w-3.5 h-3.5" strokeWidth={1.7} />
              Reports
              <span className="text-[11px] text-[var(--muted)] font-mono">· {visibleReports.length}</span>
            </button>
          </div>

          {/* About line — restraint voice. */}
          <p className="text-[12.5px] text-[var(--muted)] mb-4 max-w-2xl" data-testid="work-studio-dr-about">
            {view === "decks"
              ? "Decks gather slides for board read-outs and committee briefings. Lifecycle stays draft → review → approve → send."
              : "Reports collect cycle responses ready for review and send. The reviewer queue routes them through compose, polish, and send-up."}
          </p>

          {drLoading ? (
            <div className="p-12 text-center text-[var(--muted)] text-sm flex items-center justify-center gap-2" data-testid="work-studio-dr-loading">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading {view}…
            </div>
          ) : view === "decks" ? (
            visibleDecks.length === 0 ? (
              <div className="p-10 text-center border border-[var(--rule)] rounded-md bg-white" data-testid="work-studio-dr-empty">
                <Presentation className="w-6 h-6 text-[var(--muted)] mx-auto mb-3" />
                <p className="text-[14px] text-[var(--ink)] font-medium">No decks in flight.</p>
                <p className="text-[12.5px] text-[var(--muted)] mt-1 max-w-md mx-auto">
                  Drafts you save will land here. Use the Decks builder to start a new one.
                </p>
                <Link to="/app/decks" className="mt-4 inline-block">
                  <Button variant="outline" size="sm" className="rounded-sm border-[var(--rule)] text-[12.5px]">
                    <Plus className="w-3.5 h-3.5 mr-1.5" /> Open the deck builder
                  </Button>
                </Link>
              </div>
            ) : (
              <ul className="space-y-2" data-testid="work-studio-dr-decks">
                {visibleDecks.map((d) => (
                  <ArtefactRow
                    key={`dck-${d.id}`}
                    kind="deck"
                    item={d}
                    onRefine={({ brief_id }) => {
                      setEnhanceKind("deck");
                      setEnhanceBriefId(brief_id);
                      setEnhanceOpen(true);
                    }}
                  />
                ))}
              </ul>
            )
          ) : (
            visibleReports.length === 0 ? (
              <div className="p-10 text-center border border-[var(--rule)] rounded-md bg-white" data-testid="work-studio-dr-empty-reports">
                <FileText className="w-6 h-6 text-[var(--muted)] mx-auto mb-3" />
                <p className="text-[14px] text-[var(--ink)] font-medium">No reports in your reviewer queue.</p>
                <p className="text-[12.5px] text-[var(--muted)] mt-1 max-w-md mx-auto">
                  Reports waiting on your review will appear here.
                </p>
                <Link to="/app/cycle?tab=overview" className="mt-4 inline-block">
                  <Button variant="outline" size="sm" className="rounded-sm border-[var(--rule)] text-[12.5px]">
                    <Inbox className="w-3.5 h-3.5 mr-1.5" /> Open Cycle Manager
                  </Button>
                </Link>
              </div>
            ) : (
              <ul className="space-y-2" data-testid="work-studio-dr-reports">
                {visibleReports.map((r) => (
                  <ArtefactRow
                    key={`rpt-${r.id}`}
                    kind="report"
                    item={r}
                    onRefine={({ brief_id }) => {
                      setEnhanceKind("report");
                      setEnhanceBriefId(brief_id);
                      setEnhanceOpen(true);
                    }}
                  />
                ))}
              </ul>
            )
          )}

          {drData.errors.length > 0 && (
            <div className="mt-4 p-4 bg-amber-50 border border-amber-100 rounded-md text-[12px] text-amber-900 flex items-center gap-2" data-testid="work-studio-partial-banner">
              <AlertCircle className="w-3.5 h-3.5" />
              Some lower-section data did not load — refresh to retry.
            </div>
          )}
        </div>
      </div>

      <BriefDrawer
        open={drawerOpen}
        onClose={onCloseDrawer}
        aid={drawerAid}
        contextId={cid}
      />

      {/* Phase C.2 — Export modal (wired to the three Export buttons) */}
      <ExportModal
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        kind={exportKind}
        contextId={cid}
        contextName={activeContext?.name}
      />

      {/* Phase C.3 — Enhance modal (Path A: upload; Path B: C.2 brief refine)
          Phase F.6 — also serves the Compile-a-Report mode via the `mode` prop. */}
      <EnhanceModal
        open={enhanceOpen}
        onClose={() => { setEnhanceOpen(false); setEnhanceBriefId(null); setEnhanceMode("default"); }}
        kind={enhanceKind}
        contextId={cid}
        briefId={enhanceBriefId}
        mode={enhanceMode}
      />
      </WorkspaceEntryGate>
    </AppShell>
  );
}
