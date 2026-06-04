/**
 * DocumentDrawer — Phase E.3 (2026-05-26).
 *
 * The Universal Document Drawer. Opens from every doc-listing surface
 * via the canonical `?doc_id=<uuid>` URL contract. Two render modes
 * based on `doc.state`:
 *
 *   CREATION (state === "draft" AND origin === "akki_generated"):
 *     editable body + DRAFT watermark overlay + Creation intelligence.
 *   REFERENCE (everything else, incl. committed + uploaded + email):
 *     read-only preview + Reference intelligence.
 *
 * 5 tabs: Document · Intelligence · Your Notes · Signals · Related Documents.
 * 5 footer CTAs: Use in Solva · Use in Chat · Generate brief · Test
 *                hypothesis · Share document.
 * All CTAs emit `?ctx_type=document&ctx_id=<id>` URLs (Phase D.3 contract).
 *
 * Sheet at 60% viewport width, slides from right. Esc + backdrop close.
 * Stack pattern: nested doc opens push onto an internal stack; close
 * pops back to the parent drawer.
 *
 * Reuse: existing Shadcn Sheet primitive (`components/ui/sheet.jsx`).
 * No new overlay components.
 */
import React, { useEffect, useMemo, useState, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  FileText, MessageSquare, Sparkles, Brain, Signal, Link2, Share2,
  Pencil, Save, Loader2, RefreshCw, ChevronLeft, Wand2, X, Trash2,
} from "lucide-react";
import DocumentDrawerWatermark from "./DocumentDrawerWatermark";
import ShareDocumentModal from "./ShareDocumentModal";
import { useTrackRecentView } from "@/lib/recentViews";


// Helpers -----------------------------------------------------------------
function isCreationMode(doc) {
  return doc?.state === "draft" && doc?.origin === "akki_generated";
}

// Z2.7 (2026-02) — artefact categories that surface a Sources section
// in the drawer's Intelligence tab. Mirrors `_CATEGORY_ENUM` in
// backend/routers/documents.py plus `committee_pack` which is a
// post-compile category not enforced in the docs router enum.
const _ARTEFACT_CATEGORIES = [
  "board_pack", "minutes", "draft", "deck", "report", "briefing", "committee_pack",
];

function fmtRel(iso) {
  if (!iso) return "—";
  try {
    const ms = Date.now() - new Date(iso).getTime();
    const d = Math.floor(ms / (1000 * 60 * 60 * 24));
    if (d < 1) return "today";
    if (d < 7) return `${d}d ago`;
    if (d < 30) return `${Math.floor(d / 7)}w ago`;
    return new Date(iso).toLocaleDateString();
  } catch { return iso; }
}


// Intelligence tab content -------------------------------------------------
function IntelligenceTab({ doc, contextId, mode, navigate }) {
  const [intel, setIntel] = useState(null);
  const [status, setStatus] = useState("loading");  // loading | pending | ready

  const fetchIntel = useCallback(async () => {
    if (!doc?.id) return;
    setStatus("loading");
    try {
      const { data } = await api.get(`/contexts/${contextId}/documents/${doc.id}/intelligence`);
      if (data?.status === "ready") {
        setIntel(data);
        setStatus("ready");
      } else {
        setIntel(null);
        setStatus("pending");
        // Kick off async extraction.
        await api.post(`/contexts/${contextId}/documents/${doc.id}/intelligence/regenerate`);
        // Poll every 4s up to ~40s.
        let tries = 10;
        const poll = async () => {
          if (tries-- <= 0) return;
          await new Promise((r) => setTimeout(r, 4000));
          const { data: pd } = await api.get(`/contexts/${contextId}/documents/${doc.id}/intelligence`);
          if (pd?.status === "ready") { setIntel(pd); setStatus("ready"); }
          else poll();
        };
        poll();
      }
    } catch (e) {
      setStatus("ready");
      setIntel(null);
    }
  }, [doc?.id, contextId]);

  useEffect(() => { fetchIntel(); }, [fetchIntel]);

  const onRegenerate = async () => {
    try {
      await api.post(`/contexts/${contextId}/documents/${doc.id}/intelligence/regenerate`);
      // Clear cached then refetch loop.
      setIntel(null);
      setStatus("pending");
      fetchIntel();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const onOpenQuestionToSolva = (qText) => {
    const url = `/app/solva/session/new?ctx_type=document&ctx_id=${encodeURIComponent(doc.id)}&starter=${encodeURIComponent(qText)}`;
    navigate(url);
  };

  return (
    <div className="space-y-5" data-testid="drawer-intelligence-tab">
      <div className="flex items-center justify-between">
        <p className="text-[12px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
          {mode === "creation" ? "Creation intelligence" : "Reference intelligence"}
        </p>
        <button
          type="button"
          onClick={onRegenerate}
          className="text-[11px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1"
          data-testid="drawer-intelligence-regenerate"
        >
          <RefreshCw className="w-3 h-3" /> Regenerate
        </button>
      </div>

      {status === "pending" && (
        <div className="border border-[var(--rule)] rounded-sm p-4 bg-[var(--cream-deep)]/30" data-testid="drawer-intelligence-skeleton">
          <p className="text-[12px] text-[var(--muted)] inline-flex items-center gap-2">
            <Loader2 className="w-3 h-3 animate-spin" /> Generating intelligence…
          </p>
          <p className="text-[11px] text-[var(--muted)] mt-2">This usually takes 10-30 seconds. You can keep editing the document; intelligence will refresh once ready.</p>
        </div>
      )}

      {/* Reference-mode: 2-sentence summary */}
      {mode === "reference" && intel?.summary && (
        <section data-testid="drawer-intel-summary">
          <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">What this is</p>
          <p className="text-[13.5px] text-[var(--ink)] leading-relaxed">{intel.summary}</p>
        </section>
      )}

      {/* Creation-mode: objective adherence */}
      {mode === "creation" && (
        <section data-testid="drawer-intel-objective">
          <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Objective adherence</p>
          {doc.objective?.goal ? (
            <div className="flex items-start gap-3">
              <div className="flex-1">
                <p className="text-[13px] text-[var(--ink)]">{doc.objective.goal}</p>
                {doc.objective.context && (
                  <p className="text-[11.5px] text-[var(--muted)] mt-1">{doc.objective.context}</p>
                )}
              </div>
              {typeof intel?.objective_score === "number" && (
                <div className="text-right shrink-0" data-testid="drawer-intel-objective-score">
                  <p className="font-mono text-[24px] tabular-nums text-[var(--ink)]">{intel.objective_score}</p>
                  <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]">/ 100</p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-[12px] italic text-[var(--muted)]">No objective set for this draft.</p>
          )}
        </section>
      )}

      {/* Creation-mode: completeness gaps */}
      {mode === "creation" && intel?.completeness_gaps?.length > 0 && (
        <section data-testid="drawer-intel-completeness">
          <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Completeness check</p>
          <ul className="space-y-1">
            {intel.completeness_gaps.map((g, i) => (
              <li key={i} className="text-[12.5px] text-[var(--ink)] flex items-start gap-1.5">
                <span className="text-[color:var(--oxblood)]">•</span>
                <span>{g}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Clarity signals (heuristic; both modes) */}
      {intel?.clarity_signals && (
        <section data-testid="drawer-intel-clarity">
          <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Clarity signals</p>
          <div className="grid grid-cols-3 gap-2 text-[12px]">
            <div className="border border-[var(--rule)] rounded-sm p-2">
              <p className="text-[10px] text-[var(--muted)]">Words</p>
              <p className="font-mono text-[15px] text-[var(--ink)] tabular-nums">{intel.clarity_signals.word_count}</p>
            </div>
            <div className="border border-[var(--rule)] rounded-sm p-2">
              <p className="text-[10px] text-[var(--muted)]">Avg sentence</p>
              <p className="font-mono text-[15px] text-[var(--ink)] tabular-nums">{intel.clarity_signals.avg_sentence_length}</p>
            </div>
            <div className="border border-[var(--rule)] rounded-sm p-2">
              <p className="text-[10px] text-[var(--muted)]">Jargon density</p>
              <p className="font-mono text-[15px] text-[var(--ink)] tabular-nums">{Math.round((intel.clarity_signals.jargon_density || 0) * 100)}%</p>
            </div>
          </div>
        </section>
      )}

      {/* Audience fit (Creation mode) */}
      {mode === "creation" && intel?.audience_fit && (
        <section data-testid="drawer-intel-audience">
          <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Audience fit · {intel.audience_fit.expected}</p>
          <p className="text-[12.5px] text-[var(--ink)]">Score: <span className="font-mono">{intel.audience_fit.score} / 100</span></p>
          {(intel.audience_fit.gaps || []).map((g, i) => (
            <p key={i} className="text-[11.5px] text-[var(--muted)] mt-1">{g}</p>
          ))}
        </section>
      )}

      {/* Creation-mode: suggested improvements */}
      {mode === "creation" && intel?.suggested_improvements?.length > 0 && (
        <section data-testid="drawer-intel-suggestions">
          <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Suggested improvements</p>
          <ul className="space-y-2">
            {intel.suggested_improvements.map((s, i) => (
              <li key={i} className="border border-[var(--rule)] rounded-sm p-2.5">
                <p className="text-[12.5px] text-[var(--ink)] font-medium">{s.title}</p>
                {s.body && <p className="text-[11.5px] text-[var(--muted)] mt-0.5">{s.body}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Reference-mode: open questions */}
      {mode === "reference" && intel?.open_questions?.length > 0 && (
        <section data-testid="drawer-intel-open-questions">
          <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Open questions</p>
          <ul className="space-y-1.5">
            {intel.open_questions.map((q, i) => (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => onOpenQuestionToSolva(q)}
                  className="w-full text-left text-[12.5px] text-[var(--ink)] hover:text-[var(--accent)] hover:underline underline-offset-2"
                  data-testid="drawer-intel-open-question-btn"
                  title="Open this question in Solva"
                >
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Provenance (Reference mode) */}
      {mode === "reference" && (
        <section data-testid="drawer-intel-provenance">
          <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Provenance</p>
          <p className="text-[12.5px] text-[var(--ink)]">
            Origin: <span className="font-mono">{doc.origin || "upload"}</span>
          </p>
          {doc.source_channel && (
            <p className="text-[11.5px] text-[var(--muted)]">Source: {doc.source_channel}</p>
          )}
        </section>
      )}

      {/* Z2.7 (2026-02) — Sources block for every artefact category.
          Renders unconditionally (either populated or fallback) when
          the doc's category is on the artefact whitelist — never
          silently hidden. */}
      {_ARTEFACT_CATEGORIES.includes((doc?.category || "").toLowerCase()) && (
        <section data-testid="drawer-intel-sources" className="mt-4 pt-4 border-t border-[var(--rule)]">
          <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Sources</p>
          {(doc.source_doc_ids && doc.source_doc_ids.length > 0) ? (
            <ul className="space-y-1" data-testid="drawer-intel-sources-list">
              {doc.source_doc_ids.map((sid, i) => (
                <li key={`${sid}-${i}`} data-testid="drawer-intel-sources-item" className="text-[12.5px] text-[var(--ink)] font-mono break-all">
                  · {sid}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[12px] italic text-[var(--muted)]" data-testid="drawer-intel-sources-fallback">
              Sources: not applicable for this artefact type.
            </p>
          )}
        </section>
      )}
    </div>
  );
}


// Signals tab --------------------------------------------------------------
function SignalsTab({ doc, contextId }) {
  const [intel, setIntel] = useState(null);
  useEffect(() => {
    if (!doc?.id) return;
    api.get(`/contexts/${contextId}/documents/${doc.id}/intelligence`)
      .then(({ data }) => { if (data?.status === "ready") setIntel(data); })
      .catch(() => {});
  }, [doc?.id, contextId]);
  const signals = intel?.key_signals || [];
  return (
    <div data-testid="drawer-signals-tab">
      <p className="text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-3">
        Extracted signals
      </p>
      {signals.length === 0 ? (
        <p className="text-[12px] italic text-[var(--muted)]" data-testid="drawer-signals-empty">
          No signals extracted yet. Try regenerating intelligence.
        </p>
      ) : (
        <ul className="space-y-2">
          {signals.map((s, i) => (
            <li key={i} className="border border-[var(--rule)] rounded-sm p-2.5">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] uppercase tracking-[0.14em] font-mono text-[color:var(--oxblood)]">{s.type}</span>
                {typeof s.confidence === "number" && (
                  <span className="text-[10px] text-[var(--muted)] font-mono ml-auto">{Math.round(s.confidence * 100)}%</span>
                )}
              </div>
              <p className="text-[12.5px] text-[var(--ink)]">{s.value}</p>
              {s.source_span && (
                <p className="text-[10.5px] text-[var(--muted)] italic mt-1 line-clamp-2">"{s.source_span}"</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}


// Notes tab ----------------------------------------------------------------
//
// Track B Phase B5 G6 (2026-06-04) — autosave rewrite. Replaces the
// Sprint Z1.2 manual "Save notes" button with debounced autosave +
// "Last updated: <date>" indicator + delete-with-confirm. QA spec
// (verbatim figure 26):
//   • "automatically saved in the background as the user enters or
//      modifies content"
//   • "display the date and time the note was last updated eg. Last
//      updated: 2 June 2026, 10:45 AM"
//   • "any changes made during editing should continue to be auto-saved"
//   • "Users should be able to delete a note and a confirmation
//      prompt should be displayed before deletion"
//
// Debounce: 1.0s after last keystroke. In-flight race coalescing via
// `inflightRef` — drops intermediate keystrokes during a flight, queues
// ONE re-save if the user typed during the flight. Force-flush on
// (a) `beforeunload` (browser tab close) via `fetch(keepalive: true)`
// because `navigator.sendBeacon` is POST-only and our endpoint is
// PATCH, and (b) component unmount via `useEffect` cleanup (drawer
// close, doc switch).
//
// Delete: `window.confirm` rather than a styled modal — spec-meeting
// minimum honouring credit-discipline. Upgrade to a styled modal
// can be a future polish pass.
const _AUTOSAVE_DEBOUNCE_MS = 1000;

function _formatNotesUpdated(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    // Spec example: "2 June 2026, 10:45 AM"
    const dayMonth = d.toLocaleDateString("en-GB", {
      day: "numeric", month: "long", year: "numeric",
    });
    const time = d.toLocaleTimeString("en-US", {
      hour: "numeric", minute: "2-digit", hour12: true,
    });
    return `${dayMonth}, ${time}`;
  } catch {
    return "";
  }
}

function NotesTab({ doc, contextId }) {
  const [notes, setNotes] = useState(doc?.notes || "");
  const [savedSnapshot, setSavedSnapshot] = useState(doc?.notes || "");
  const [notesUpdatedAt, setNotesUpdatedAt] = useState(doc?.notes_updated_at || null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Refs for the debounce + in-flight coalescer. Refs (not state)
  // because we need the LATEST value inside async callbacks without
  // re-binding the timer / event listener on every keystroke.
  const debounceTimerRef = useRef(null);
  const inflightRef = useRef(false);
  const queuedRef = useRef(false);
  const notesRef = useRef(notes);
  const savedRef = useRef(savedSnapshot);
  const dirtyRef = useRef(false);
  useEffect(() => { notesRef.current = notes; }, [notes]);
  useEffect(() => { savedRef.current = savedSnapshot; }, [savedSnapshot]);
  useEffect(() => { dirtyRef.current = (notes || "") !== (savedSnapshot || ""); }, [notes, savedSnapshot]);

  // Re-hydrate when the user switches to a different doc.
  useEffect(() => {
    setNotes(doc?.notes || "");
    setSavedSnapshot(doc?.notes || "");
    setNotesUpdatedAt(doc?.notes_updated_at || null);
  }, [doc?.id, doc?.notes, doc?.notes_updated_at]);

  // Core save — single async path used by debounce, force-flush,
  // delete-confirm. `nextNotes` is the value to send (current
  // typed value for autosave; empty string for delete).
  const performSave = useCallback(async (nextNotes) => {
    if (inflightRef.current) {
      // Coalesce — drop the intermediate, mark one queued. The
      // current flight will re-check `notesRef` on completion and
      // fire one more save if dirty.
      queuedRef.current = true;
      return;
    }
    inflightRef.current = true;
    setSaving(true);
    try {
      const resp = await api.patch(
        `/contexts/${contextId}/documents/${doc.id}`,
        { notes: nextNotes },
      );
      setSavedSnapshot(nextNotes);
      // Backend returns the sanitised doc with `notes_updated_at`
      // populated. Use the server timestamp as the source of truth.
      const serverTs = resp?.data?.notes_updated_at;
      setNotesUpdatedAt(serverTs || new Date().toISOString());
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      inflightRef.current = false;
      setSaving(false);
      // Coalesced re-save if the user typed during the flight.
      if (queuedRef.current) {
        queuedRef.current = false;
        const latest = notesRef.current || "";
        if (latest !== savedRef.current) {
          // Re-enter performSave; inflightRef is now false so it
          // will fire (not coalesce again).
          performSave(latest);
        }
      }
    }
  }, [contextId, doc?.id]);

  // Debounced autosave on textarea change.
  const onTextChange = (e) => {
    const next = e.target.value;
    setNotes(next);
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      debounceTimerRef.current = null;
      const current = notesRef.current || "";
      if (current !== savedRef.current) {
        performSave(current);
      }
    }, _AUTOSAVE_DEBOUNCE_MS);
  };

  // Force-flush on browser tab close. `fetch(keepalive: true)` is
  // the spec-compliant way to fire a PATCH that survives unload
  // (sendBeacon is POST-only). Bypass the `api` axios helper so we
  // can set `keepalive`; reuse the same withCredentials + JSON
  // shape. CSRF: documents PATCH does not require X-CSRF-Token
  // (see require_context_membership wiring); cookie auth alone is
  // sufficient.
  useEffect(() => {
    if (!contextId || !doc?.id) return;
    const onBeforeUnload = () => {
      if (!dirtyRef.current) return;
      try {
        const apiBase = process.env.REACT_APP_BACKEND_URL || "";
        // eslint-disable-next-line no-restricted-syntax -- axios/api helper does not support fetch's `keepalive: true`, which is required for a beforeunload PATCH to survive page unload. This is the documented escape-hatch case from /app/memory/sprints/LINT_API_CLIENT_RULE.md (Patch 24B). Fire-and-forget; no response handling.
        fetch(
          `${apiBase}/api/contexts/${contextId}/documents/${doc.id}`,
          {
            method: "PATCH",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ notes: notesRef.current || "" }),
            keepalive: true,
          },
        );
      } catch {
        /* swallow — best-effort */
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [contextId, doc?.id]);

  // Force-flush on unmount (drawer close / doc switch). Fire and
  // forget — `useEffect` cleanup runs synchronously, so we don't
  // `await` the in-page PATCH. The component is already unmounting,
  // but the request lives on in the network stack.
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
      if (dirtyRef.current && contextId && doc?.id) {
        const latest = notesRef.current || "";
        api.patch(
          `/contexts/${contextId}/documents/${doc.id}`,
          { notes: latest },
        ).catch(() => { /* swallow — unmount, no user surface */ });
      }
    };
  }, [contextId, doc?.id]);

  const onDelete = async () => {
    if (!window.confirm("Delete this note? This cannot be undone.")) return;
    // Cancel any pending debounce so we don't race the delete.
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }
    setDeleting(true);
    try {
      const resp = await api.patch(
        `/contexts/${contextId}/documents/${doc.id}`,
        { notes: "" },
      );
      setNotes("");
      setSavedSnapshot("");
      const serverTs = resp?.data?.notes_updated_at;
      setNotesUpdatedAt(serverTs || new Date().toISOString());
      toast.success("Note deleted.");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setDeleting(false);
    }
  };

  const dirty = (notes || "") !== (savedSnapshot || "");
  const lastUpdatedLabel = notesUpdatedAt
    ? `Last updated: ${_formatNotesUpdated(notesUpdatedAt)}`
    : "";
  const showDelete = !!savedSnapshot && !deleting && !dirty;

  return (
    <div data-testid="drawer-notes-tab">
      <p className="text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-3">Your notes</p>
      <textarea
        value={notes}
        onChange={onTextChange}
        placeholder="Your notes about this document… (autosaves as you type)"
        rows={10}
        className="w-full border border-[var(--rule)] rounded-sm px-3 py-2 text-[13px] text-[var(--ink)] font-sans focus:outline-none focus:border-[var(--ink)]"
        data-testid="drawer-notes-textarea"
      />
      <div className="mt-2 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-h-[20px]">
          {saving && (
            <span
              className="text-[11px] font-mono uppercase tracking-[0.14em] text-[var(--muted)] inline-flex items-center gap-1.5"
              data-testid="drawer-notes-saving-indicator"
            >
              <Loader2 className="w-3 h-3 animate-spin" />
              Saving…
            </span>
          )}
          {!saving && lastUpdatedLabel && (
            <span
              className="text-[11px] font-mono uppercase tracking-[0.14em] text-[var(--ned-purple)]"
              data-testid="drawer-notes-last-updated"
            >
              {lastUpdatedLabel}
            </span>
          )}
        </div>
        {showDelete && (
          <button
            type="button"
            onClick={onDelete}
            className="text-[11px] font-mono uppercase tracking-[0.14em] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1.5"
            data-testid="drawer-notes-delete"
          >
            <Trash2 className="w-3 h-3" />
            Delete note
          </button>
        )}
      </div>
    </div>
  );
}


// Related tab --------------------------------------------------------------
//
// E.3 scope-compliance: surfaces 4 typed groups from
//   GET /contexts/{cid}/documents/{did}/related
//
//   • metadata_match      (same context + same doc_type)
//   • explicit_attachment (Debt W3 — `document_attachments` collection)
//   • canonical_lineage   (Debt W3 — `documents.parent_doc_id` walk)
//   • content_similarity  (gap — deferred to Phase G, embedding infra)
//
// Gap buckets render in muted style with the server's `gap_reason`.
function RelatedTab({ doc, contextId, onOpenDoc }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  // Debt W3 (2026-05-26) — attach affordance state.
  const [attachOpen, setAttachOpen] = useState(false);
  const [attachTarget, setAttachTarget] = useState("");
  const [attachNote, setAttachNote] = useState("");
  const [attachBusy, setAttachBusy] = useState(false);
  const [attachError, setAttachError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const refetch = () => {
    if (!doc?.id) return;
    setLoading(true);
    api.get(`/contexts/${contextId}/documents/${doc.id}/related`)
      .then(({ data }) => setData(data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!doc?.id) { setData(null); return; }
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doc?.id, contextId, refreshKey]);

  const onCreateAttachment = async () => {
    const tgt = attachTarget.trim();
    if (!tgt) {
      setAttachError("Target document id is required.");
      return;
    }
    setAttachBusy(true);
    setAttachError("");
    try {
      await api.post(`/documents/${doc.id}/attachments`, {
        target_doc_id: tgt,
        note: attachNote.trim() || null,
      });
      setAttachOpen(false);
      setAttachTarget("");
      setAttachNote("");
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setAttachError(e?.response?.data?.detail || "Failed to attach.");
    } finally {
      setAttachBusy(false);
    }
  };

  const onDeleteAttachment = async (attId) => {
    try {
      await api.delete(`/documents/${doc.id}/attachments/${attId}`);
      setRefreshKey((k) => k + 1);
    } catch {
      // best-effort
    }
  };

  const groupOrder = [
    "metadata_match", "explicit_attachment",
    "canonical_lineage", "content_similarity",
  ];
  return (
    <div data-testid="drawer-related-tab" className="space-y-4">
      <p className="text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">Related documents</p>
      {loading && (
        <p className="text-[12px] text-[var(--muted)] inline-flex items-center gap-1.5">
          <Loader2 className="w-3 h-3 animate-spin" /> Loading…
        </p>
      )}
      {!loading && data && groupOrder.map((gk) => {
        const grp = data.groups?.[gk];
        if (!grp) return null;
        const items = grp.items || [];
        const isAttach = gk === "explicit_attachment";
        return (
          <div key={gk} data-testid={`drawer-related-group-${gk}`} className="border-t border-[var(--rule)] pt-3 first:border-t-0 first:pt-0">
            <div className="flex items-center justify-between mb-2">
              <p className="text-[11.5px] font-medium text-[var(--ink)]">{grp.label}</p>
              {!grp.available && (
                <span className="text-[10px] uppercase tracking-[0.12em] font-mono text-[var(--muted)]" data-testid={`drawer-related-gap-${gk}`}>
                  Not available
                </span>
              )}
            </div>
            {!grp.available ? (
              <p className="text-[11.5px] italic text-[var(--muted)]" data-testid={`drawer-related-gap-reason-${gk}`}>
                {grp.gap_reason || "Data infrastructure not wired."}
              </p>
            ) : items.length === 0 ? (
              <p className="text-[11.5px] italic text-[var(--muted)]" data-testid={`drawer-related-empty-${gk}`}>
                No matches.
              </p>
            ) : (
              <ul className="space-y-1" data-testid={`drawer-related-list-${gk}`}>
                {items.map((r) => (
                  <li key={r.id || r.attachment_id} className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => onOpenDoc(r.id)}
                      className="flex-1 text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] text-[12.5px] text-[var(--ink)] inline-flex items-center gap-1.5"
                      data-testid="drawer-related-row"
                    >
                      <FileText className="w-3 h-3 text-[var(--muted)] shrink-0" />
                      <span className="truncate">{r.name || r.original_filename || r.id}</span>
                      {r.lineage && (
                        <span className="ml-auto text-[10px] uppercase tracking-[0.12em] font-mono text-[var(--oxblood)]">
                          {r.lineage}{r.depth ? ` · d${r.depth}` : ""}
                        </span>
                      )}
                      {r.direction && !r.lineage && (
                        <span className="ml-auto text-[10px] uppercase tracking-[0.12em] font-mono text-[var(--muted)]">
                          {r.direction}
                        </span>
                      )}
                      {typeof r.score === "number" && (
                        <span className="ml-auto text-[10px] font-mono text-[var(--muted)]">{r.score.toFixed(2)}</span>
                      )}
                    </button>
                    {isAttach && r.attachment_id && (
                      <button
                        type="button"
                        onClick={() => onDeleteAttachment(r.attachment_id)}
                        className="text-[10px] text-[var(--muted)] hover:text-[var(--oxblood)] px-1.5"
                        data-testid={`drawer-related-attachment-detach-${r.attachment_id}`}
                        title="Detach"
                      >
                        ×
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {isAttach && grp.available && (
              <div className="mt-2">
                {!attachOpen ? (
                  <button
                    type="button"
                    onClick={() => setAttachOpen(true)}
                    className="text-[11.5px] text-[var(--oxblood)] hover:text-[var(--ink)] inline-flex items-center gap-1"
                    data-testid="drawer-related-attach-open"
                  >
                    + Attach related document
                  </button>
                ) : (
                  <div className="border border-[var(--rule)] rounded-sm p-2 bg-[var(--cream-deep)]/30 space-y-1.5">
                    <input
                      type="text"
                      value={attachTarget}
                      onChange={(e) => setAttachTarget(e.target.value)}
                      placeholder="Target document id"
                      className="w-full px-2 py-1 text-[12px] border border-[var(--rule)] rounded-sm bg-white"
                      data-testid="drawer-related-attach-target-input"
                    />
                    <input
                      type="text"
                      value={attachNote}
                      onChange={(e) => setAttachNote(e.target.value)}
                      placeholder="Note (optional)"
                      className="w-full px-2 py-1 text-[12px] border border-[var(--rule)] rounded-sm bg-white"
                      data-testid="drawer-related-attach-note-input"
                    />
                    {attachError && (
                      <p className="text-[11px] text-[var(--oxblood)]" data-testid="drawer-related-attach-error">{attachError}</p>
                    )}
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={onCreateAttachment}
                        disabled={attachBusy}
                        className="text-[11.5px] px-2 py-1 bg-[var(--ink)] text-white rounded-sm disabled:opacity-50"
                        data-testid="drawer-related-attach-submit"
                      >
                        {attachBusy ? "Attaching…" : "Attach"}
                      </button>
                      <button
                        type="button"
                        onClick={() => { setAttachOpen(false); setAttachError(""); }}
                        className="text-[11.5px] px-2 py-1 text-[var(--muted)] hover:text-[var(--ink)]"
                        data-testid="drawer-related-attach-cancel"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
      {!loading && !data && (
        <p className="text-[12px] italic text-[var(--muted)]" data-testid="drawer-related-error">Could not load related documents.</p>
      )}
    </div>
  );
}


// Document tab content -----------------------------------------------------
//
// E.3 scope-compliance: the prompt-based-edit composer now calls
//   POST /api/documents/{id}/prompted-edit
// which returns `{ new_body, current_body, prompt_hash, diff_size }`.
// We render a side-by-side preview using a simple word-level diff and
// expose Apply (PATCH the draft body) / Discard (drop the proposal).
function _wordDiff(oldText, newText) {
  // Lightweight LCS-based word diff. Returns [{op:"keep"|"add"|"del", word}].
  const a = (oldText || "").split(/(\s+)/);
  const b = (newText || "").split(/(\s+)/);
  const m = a.length;
  const n = b.length;
  // Cap for huge diffs — fall back to plain replace.
  if (m * n > 600000) {
    return [{ op: "del", word: oldText }, { op: "add", word: newText }];
  }
  const dp = Array.from({ length: m + 1 }, () => new Uint16Array(n + 1));
  for (let i = 1; i <= m; i += 1) {
    for (let j = 1; j <= n; j += 1) {
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1]);
    }
  }
  const out = [];
  let i = m, j = n;
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) { out.push({ op: "keep", word: a[i - 1] }); i--; j--; }
    else if (dp[i - 1][j] >= dp[i][j - 1]) { out.push({ op: "del", word: a[i - 1] }); i--; }
    else { out.push({ op: "add", word: b[j - 1] }); j--; }
  }
  while (i > 0) { out.push({ op: "del", word: a[i - 1] }); i--; }
  while (j > 0) { out.push({ op: "add", word: b[j - 1] }); j--; }
  return out.reverse();
}

function DocumentTab({ doc, contextId, mode, onPatched }) {
  const [body, setBody] = useState(doc?.extracted_text || "");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [composer, setComposer] = useState("");
  const [proposal, setProposal] = useState(null); // {current_body, new_body, prompt_hash, diff_size}
  const [proposing, setProposing] = useState(false);
  const [applying, setApplying] = useState(false);
  useEffect(() => { setBody(doc?.extracted_text || ""); }, [doc?.id, doc?.extracted_text]);

  const onSave = async () => {
    setSaving(true);
    try {
      await api.patch(`/contexts/${contextId}/documents/${doc.id}`, { body });
      toast.success("Saved.");
      setEditing(false);
      onPatched?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSaving(false); }
  };

  const onPromptEdit = async () => {
    if (!composer.trim() || proposing) return;
    setProposing(true);
    try {
      const { data } = await api.post(`/documents/${doc.id}/prompted-edit`, {
        prompt: composer.trim(),
      });
      setProposal(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setProposing(false); }
  };

  const onApplyProposal = async () => {
    if (!proposal?.new_body || applying) return;
    setApplying(true);
    try {
      await api.patch(`/contexts/${contextId}/documents/${doc.id}`, {
        body: proposal.new_body,
      });
      setBody(proposal.new_body);
      setProposal(null);
      setComposer("");
      toast.success("Edit applied.");
      onPatched?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setApplying(false); }
  };

  const onDiscardProposal = () => { setProposal(null); };

  const diff = proposal ? _wordDiff(proposal.current_body || body, proposal.new_body) : null;

  return (
    <div className="space-y-3" data-testid="drawer-document-tab">
      {mode === "creation" ? (
        <>
          {editing ? (
            <>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={20}
                className="w-full border border-[var(--rule)] rounded-sm px-3 py-2 text-[13px] text-[var(--ink)] focus:outline-none focus:border-[var(--ink)]"
                data-testid="drawer-document-textarea"
              />
              <div className="flex gap-2">
                <Button onClick={onSave} disabled={saving} size="sm" data-testid="drawer-document-save">
                  {saving ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : <Save className="w-3 h-3 mr-1.5" />}
                  Save
                </Button>
                <Button onClick={() => { setBody(doc.extracted_text || ""); setEditing(false); }} variant="outline" size="sm" data-testid="drawer-document-cancel">
                  Cancel
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="relative">
                <pre className="whitespace-pre-wrap text-[13px] text-[var(--ink)] font-sans" data-testid="drawer-document-body-display">{body || "(empty)"}</pre>
                <Button onClick={() => setEditing(true)} variant="ghost" size="sm" className="absolute top-0 right-0" data-testid="drawer-document-edit-toggle">
                  <Pencil className="w-3 h-3 mr-1" /> Edit
                </Button>
              </div>
              {proposal && (
                <div className="border border-[var(--oxblood)] rounded-sm p-3 bg-[var(--parchment)]" data-testid="drawer-document-prompt-diff">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--oxblood)]">Proposed rewrite</p>
                    <span className="text-[10px] font-mono text-[var(--muted)]" data-testid="drawer-document-prompt-diff-size">
                      diff {proposal.diff_size} chars
                    </span>
                  </div>
                  <div className="text-[12.5px] leading-relaxed max-h-72 overflow-y-auto whitespace-pre-wrap" data-testid="drawer-document-prompt-diff-body">
                    {diff?.map((seg, i) => seg.op === "keep" ? (
                      <span key={i}>{seg.word}</span>
                    ) : seg.op === "del" ? (
                      <span key={i} className="line-through text-[var(--oxblood)] bg-[rgba(122,46,46,0.08)]" data-testid="drawer-document-prompt-diff-del">{seg.word}</span>
                    ) : (
                      <span key={i} className="underline decoration-[var(--oxblood)] decoration-2 underline-offset-2 text-[var(--ink)] bg-[rgba(122,46,46,0.04)]" data-testid="drawer-document-prompt-diff-add">{seg.word}</span>
                    ))}
                  </div>
                  <div className="flex gap-2 mt-3">
                    <Button onClick={onApplyProposal} disabled={applying} size="sm" data-testid="drawer-document-prompt-apply-confirm">
                      {applying ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : <Save className="w-3 h-3 mr-1.5" />}
                      Apply
                    </Button>
                    <Button onClick={onDiscardProposal} variant="outline" size="sm" data-testid="drawer-document-prompt-discard">
                      Discard
                    </Button>
                  </div>
                </div>
              )}
              <div className="border-t border-[var(--rule)] pt-3 mt-3">
                <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-2">Prompt-based edit</p>
                <div className="flex gap-2">
                  <input
                    value={composer}
                    onChange={(e) => setComposer(e.target.value)}
                    placeholder='e.g. "rewrite section 2 to be sharper"'
                    className="flex-1 border border-[var(--rule)] rounded-sm px-2 py-1.5 text-[12.5px] focus:outline-none focus:border-[var(--ink)]"
                    data-testid="drawer-document-prompt-composer"
                  />
                  <Button onClick={onPromptEdit} disabled={proposing || !composer.trim()} size="sm" data-testid="drawer-document-prompt-apply">
                    {proposing ? <Loader2 className="w-3 h-3 animate-spin mr-1" /> : <Wand2 className="w-3 h-3 mr-1" />}
                    {proposing ? "Drafting…" : "Apply"}
                  </Button>
                </div>
              </div>
            </>
          )}
        </>
      ) : (
        <pre className="whitespace-pre-wrap text-[13px] text-[var(--ink)] font-sans" data-testid="drawer-document-body-readonly">
          {body || "(no body extracted)"}
        </pre>
      )}
    </div>
  );
}


// Main drawer --------------------------------------------------------------
export default function DocumentDrawer({
  contextId,
  // When deep-linked via `?doc_id=`, the host page provides this prop;
  // closing the drawer strips the param.
}) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const docId = searchParams.get("doc_id");
  // Stack of doc ids — the topmost is the active drawer.
  const [stack, setStack] = useState([]);
  useEffect(() => {
    if (docId && !stack.includes(docId)) {
      setStack([docId]);
    } else if (!docId) {
      setStack([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docId]);

  const activeId = stack[stack.length - 1];
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("document");
  const [shareOpen, setShareOpen] = useState(false);
  const [fetchErr, setFetchErr] = useState(null);

  useEffect(() => {
    if (!activeId || !contextId) return;
    setLoading(true);
    setFetchErr(null);
    api.get(`/contexts/${contextId}/documents/${activeId}`)
      .then(({ data }) => setDoc(data))
      .catch((e) => {
        setDoc(null);
        setFetchErr(apiErrorMessage(e));
      })
      .finally(() => setLoading(false));
  }, [activeId, contextId]);

  // Phase H.4.1 (2026-05-27) — Track recent view so the Portfolio
  // Landing "Where you left off" resume card can deep-link back to
  // this document. Tracking happens once `doc` is loaded.
  useTrackRecentView({
    surfacePath: activeId ? `?doc_id=${activeId}` : null,
    label: doc?.title || doc?.original_filename || null,
    contextId,
    artefactId: activeId || null,
    artefactKind: "document",
    deepLink: activeId
      ? `/app/work-studio?doc_id=${activeId}`
      : null,
    enabled: !!activeId && !!contextId && !!doc,
  });

  const mode = isCreationMode(doc) ? "creation" : "reference";

  const onClose = () => {
    if (stack.length > 1) {
      setStack(stack.slice(0, -1));
      return;
    }
    const sp = new URLSearchParams(searchParams);
    sp.delete("doc_id");
    setSearchParams(sp, { replace: true });
    setStack([]);
    setDoc(null);
  };

  const pushDoc = (newId) => setStack([...stack, newId]);

  // CTA URL builders — Phase D.3 canonical contract.
  // Note: prefixed with `build*` not `use*` to avoid React Rules-of-Hooks
  // confusion (`use*` triggers the hook linter even though these are
  // pure functions).
  const buildSolvaUrl       = () => `/app/solva?ctx_type=document&ctx_id=${encodeURIComponent(doc.id)}`;
  const buildChatUrl        = () => `/app/chat?ctx_type=document&ctx_id=${encodeURIComponent(doc.id)}`;
  const buildHypothesisUrl  = () => `/app/solva?ctx_type=document&ctx_id=${encodeURIComponent(doc.id)}&submodule=simulate_hypothesis&starter=Test%20a%20hypothesis%20against%20this%20document`;

  // Sprint Z1.5 (2026-05-29) — Generate brief now generates a brief
  // (not navigates to Solva). The drawer queues a `briefing.create`
  // job scoped to this document, polls for completion, and on success
  // routes the founder to the Briefings tab with the new id
  // highlighted.
  const [briefing, setBriefing] = useState(false);
  const onGenerateBrief = async () => {
    if (briefing) return;
    setBriefing(true);
    const toastId = toast.loading("Generating brief from this document…", {
      duration: 60000,
    });
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/documents/${doc.id}/briefings/generate`,
      );
      const jobId = data?.job_id;
      if (!jobId) throw new Error("No job_id returned");
      // Poll the job for up to 90s (45 × 2s) — same cadence the
      // briefings page uses for its long-poll loop.
      let briefingId = null;
      for (let i = 0; i < 45; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          const { data: jd } = await api.get(`/jobs/${jobId}`);
          if (jd?.status === "completed") {
            briefingId = jd?.result?.id || jd?.result?.briefing_id || null;
            break;
          }
          if (jd?.status === "failed") {
            throw new Error(jd?.error || "Briefing job failed");
          }
        } catch (poll_err) {
          if (i >= 5) throw poll_err;
        }
      }
      toast.dismiss(toastId);
      if (briefingId) {
        toast.success("Brief ready.");
        navigate(
          `/app/work-studio?tab=briefings&context_id=${encodeURIComponent(contextId)}&highlight=${encodeURIComponent(briefingId)}`,
        );
      } else {
        toast.error("Brief is still generating. Check the Briefings tab in a moment.");
        navigate(
          `/app/work-studio?tab=briefings&context_id=${encodeURIComponent(contextId)}`,
        );
      }
    } catch (e) {
      toast.dismiss(toastId);
      toast.error(apiErrorMessage(e));
    } finally {
      setBriefing(false);
    }
  };

  const open = !!activeId;

  return (
    <>
      <Sheet open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
        <SheetContent
          side="right"
          className="!w-[60vw] !max-w-[60vw] p-0 flex flex-col"
          data-testid="document-drawer"
          data-mode={mode}
          data-doc-id={activeId || ""}
        >
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 className="w-5 h-5 animate-spin text-[var(--muted)]" />
            </div>
          ) : !doc ? (
            <div className="flex-1 flex items-center justify-center px-6">
              <div className="text-center" data-testid="drawer-load-error">
                <p className="text-[13px] text-[var(--ink)]">Could not load this document.</p>
                {fetchErr && <p className="text-[11.5px] text-[var(--muted)] mt-1">{fetchErr}</p>}
                <Button onClick={onClose} size="sm" variant="outline" className="mt-3">Close</Button>
              </div>
            </div>
          ) : (
            <>
              {/* Header */}
              <header className="border-b border-[var(--rule)] px-6 py-4 flex items-start gap-3" data-testid="drawer-header">
                {stack.length > 1 && (
                  <button
                    type="button"
                    onClick={onClose}
                    className="text-[var(--muted)] hover:text-[var(--ink)] mt-1"
                    aria-label="Back"
                    data-testid="drawer-back-btn"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span
                      className={`text-[10px] uppercase tracking-[0.16em] font-mono px-2 py-0.5 rounded-sm ${mode === "creation" ? "bg-[color:var(--oxblood)] text-white" : "bg-emerald-700 text-white"}`}
                      data-testid="drawer-state-badge"
                    >
                      {mode === "creation" ? "DRAFT" : "COMMITTED"}
                    </span>
                    <span className="text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--muted)]" data-testid="drawer-origin-chip">
                      {doc.origin === "akki_generated" ? "Akki generated"
                        : doc.origin === "email_receipt" ? "Email receipt"
                        : "Uploaded"}
                    </span>
                  </div>
                  <h2 className="text-[18px] text-[var(--ink)] truncate" data-testid="drawer-title">
                    {doc.name || doc.original_filename || "Untitled"}
                  </h2>
                  <p className="text-[11px] text-[var(--muted)] mt-0.5">
                    Created {fmtRel(doc.created_at)} · Edited {fmtRel(doc.updated_at)}
                    {doc.committed_at && <> · Committed {fmtRel(doc.committed_at)}</>}
                  </p>
                </div>
                <button onClick={onClose} aria-label="Close" className="text-[var(--muted)] hover:text-[var(--ink)]" data-testid="drawer-close-btn">
                  <X className="w-4 h-4" />
                </button>
              </header>

              {/* Tab nav + body
                  Z2.2 (2026-05-29) — `min-h-0` on each flex-1 child
                  is load-bearing for scroll. Without it, flexbox's
                  default `min-height: auto` lets the body expand past
                  the SheetContent's viewport height; `overflow-y-auto`
                  never engages and the Related Documents tab (or any
                  long tab content) silently exceeds the visible area.
                  See https://css-tricks.com/min-content-min-height-flexbox/. */}
              <div className="flex-1 overflow-hidden flex flex-col min-h-0">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col min-h-0">
                  <TabsList className="px-6 border-b border-[var(--rule)] rounded-none justify-start bg-transparent h-auto" data-testid="drawer-tabs">
                    <TabsTrigger value="document" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]" data-testid="drawer-tab-document">
                      <FileText className="w-3 h-3 mr-1.5" /> Document
                    </TabsTrigger>
                    <TabsTrigger value="intelligence" data-testid="drawer-tab-intelligence" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]">
                      <Brain className="w-3 h-3 mr-1.5" /> Intelligence
                    </TabsTrigger>
                    <TabsTrigger value="notes" data-testid="drawer-tab-notes" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]">
                      <MessageSquare className="w-3 h-3 mr-1.5" /> Your Notes
                    </TabsTrigger>
                    <TabsTrigger value="signals" data-testid="drawer-tab-signals" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]">
                      <Signal className="w-3 h-3 mr-1.5" /> Signals
                    </TabsTrigger>
                    <TabsTrigger value="related" data-testid="drawer-tab-related" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]">
                      <Link2 className="w-3 h-3 mr-1.5" /> Related Documents
                    </TabsTrigger>
                  </TabsList>
                  <div className="flex-1 overflow-y-auto px-6 py-5 relative min-h-0" data-testid="drawer-body">
                    {/* DRAFT watermark overlay — visible only in creation mode, only on Document tab content */}
                    {mode === "creation" && activeTab === "document" && (
                      <DocumentDrawerWatermark />
                    )}
                    <TabsContent value="document">
                      <DocumentTab doc={doc} contextId={contextId} mode={mode} onPatched={() => {
                        api.get(`/contexts/${contextId}/documents/${doc.id}`).then(({ data }) => setDoc(data));
                      }} />
                    </TabsContent>
                    <TabsContent value="intelligence">
                      <IntelligenceTab doc={doc} contextId={contextId} mode={mode} navigate={navigate} />
                    </TabsContent>
                    <TabsContent value="notes">
                      <NotesTab doc={doc} contextId={contextId} />
                    </TabsContent>
                    <TabsContent value="signals">
                      <SignalsTab doc={doc} contextId={contextId} />
                    </TabsContent>
                    <TabsContent value="related">
                      <RelatedTab doc={doc} contextId={contextId} onOpenDoc={pushDoc} />
                    </TabsContent>
                  </div>
                </Tabs>
              </div>

              {/* Footer 5-CTA bar */}
              <footer className="border-t border-[var(--rule)] px-6 py-3 flex items-center gap-2 flex-wrap" data-testid="drawer-cta-bar">
                <Button
                  size="sm" variant="outline" onClick={() => navigate(buildSolvaUrl())}
                  data-testid="drawer-cta-use-in-solva" data-href={buildSolvaUrl()}
                >
                  <Sparkles className="w-3 h-3 mr-1.5" /> Use in Solva
                </Button>
                <Button
                  size="sm" variant="outline" onClick={() => navigate(buildChatUrl())}
                  data-testid="drawer-cta-use-in-chat" data-href={buildChatUrl()}
                >
                  <MessageSquare className="w-3 h-3 mr-1.5" /> Use in Chat
                </Button>
                <Button
                  size="sm" variant="outline" onClick={onGenerateBrief}
                  disabled={briefing}
                  data-testid="drawer-cta-generate-brief"
                  data-action="generate-briefing-from-document"
                >
                  {briefing ? <Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> : <FileText className="w-3 h-3 mr-1.5" />}
                  {briefing ? "Generating…" : "Generate brief"}
                </Button>
                <Button
                  size="sm" variant="outline" onClick={() => navigate(buildHypothesisUrl())}
                  data-testid="drawer-cta-test-hypothesis" data-href={buildHypothesisUrl()}
                >
                  <Wand2 className="w-3 h-3 mr-1.5" /> Test hypothesis
                </Button>
                <Button
                  size="sm" variant="outline" onClick={() => setShareOpen(true)}
                  data-testid="drawer-cta-share"
                >
                  <Share2 className="w-3 h-3 mr-1.5" /> Share document
                </Button>
              </footer>
            </>
          )}
        </SheetContent>
      </Sheet>

      {/* Share modal — ports legacy electronic tracking via
          /api/contexts/{cid}/documents/{did}/share + /engagement. */}
      {doc && (
        <ShareDocumentModal
          open={shareOpen}
          onOpenChange={setShareOpen}
          docId={doc.id}
          docTitle={doc.name || doc.original_filename}
          contextId={contextId}
        />
      )}
    </>
  );
}
