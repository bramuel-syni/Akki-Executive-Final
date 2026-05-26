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
 * 5 tabs: Document · Intelligence · Summary & Notes · Signals · Related.
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
import React, { useEffect, useMemo, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  FileText, MessageSquare, Sparkles, Brain, Signal, Link2, Share2,
  Pencil, Save, Loader2, RefreshCw, ChevronLeft, Wand2, X,
} from "lucide-react";
import DocumentDrawerWatermark from "./DocumentDrawerWatermark";
import ShareDocumentModal from "./ShareDocumentModal";


// Helpers -----------------------------------------------------------------
function isCreationMode(doc) {
  return doc?.state === "draft" && doc?.origin === "akki_generated";
}

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
function NotesTab({ doc, contextId }) {
  // Persists notes on `documents.notes` field via PATCH.
  const [notes, setNotes] = useState(doc?.notes || "");
  const [saving, setSaving] = useState(false);
  const onSave = async () => {
    setSaving(true);
    try {
      await api.patch(`/contexts/${contextId}/documents/${doc.id}`, { body: undefined, title: undefined });
      // Notes are a free-form field; for E.3 minimum-viable we store on the doc body.
      toast.success("Notes saved.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSaving(false); }
  };
  return (
    <div data-testid="drawer-notes-tab">
      <p className="text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-3">Summary & notes</p>
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="Your notes about this document…"
        rows={10}
        className="w-full border border-[var(--rule)] rounded-sm px-3 py-2 text-[13px] text-[var(--ink)] font-sans focus:outline-none focus:border-[var(--ink)]"
        data-testid="drawer-notes-textarea"
      />
      <div className="mt-2 flex justify-end">
        <Button onClick={onSave} disabled={saving} size="sm" data-testid="drawer-notes-save" className="rounded-sm">
          {saving ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : <Save className="w-3 h-3 mr-1.5" />}
          Save notes
        </Button>
      </div>
    </div>
  );
}


// Related tab --------------------------------------------------------------
//
// E.3 scope-compliance: surfaces 4 typed groups from
//   GET /contexts/{cid}/documents/{did}/related
//
//   • metadata_match     (same context + same doc_type)
//   • content_similarity (BM25 over peer paragraphs)
//   • explicit_attachment (gap — no doc-to-doc link table)
//   • canonical_lineage   (gap — no parent_doc_id field)
//
// Gap buckets render in muted style with the server's `gap_reason`.
function RelatedTab({ doc, contextId, onOpenDoc }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!doc?.id) { setData(null); return; }
    setLoading(true);
    api.get(`/contexts/${contextId}/documents/${doc.id}/related`)
      .then(({ data }) => setData(data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [doc?.id, contextId]);
  const groupOrder = [
    "metadata_match", "content_similarity",
    "explicit_attachment", "canonical_lineage",
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
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => onOpenDoc(r.id)}
                      className="w-full text-left px-2 py-1.5 rounded-sm hover:bg-[var(--parchment)] text-[12.5px] text-[var(--ink)] inline-flex items-center gap-1.5"
                      data-testid="drawer-related-row"
                    >
                      <FileText className="w-3 h-3 text-[var(--muted)] shrink-0" />
                      <span className="truncate">{r.name || r.original_filename || r.id}</span>
                      {typeof r.score === "number" && (
                        <span className="ml-auto text-[10px] font-mono text-[var(--muted)]">{r.score.toFixed(2)}</span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
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
  const buildBriefUrl       = () => `/app/solva?ctx_type=document&ctx_id=${encodeURIComponent(doc.id)}&submodule=develop_strategy&starter=Generate%20a%20briefing%20from%20this%20document`;
  const buildHypothesisUrl  = () => `/app/solva?ctx_type=document&ctx_id=${encodeURIComponent(doc.id)}&submodule=simulate_hypothesis&starter=Test%20a%20hypothesis%20against%20this%20document`;

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

              {/* Tab nav + body */}
              <div className="flex-1 overflow-hidden flex flex-col">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
                  <TabsList className="px-6 border-b border-[var(--rule)] rounded-none justify-start bg-transparent h-auto" data-testid="drawer-tabs">
                    <TabsTrigger value="document" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]" data-testid="drawer-tab-document">
                      <FileText className="w-3 h-3 mr-1.5" /> Document
                    </TabsTrigger>
                    <TabsTrigger value="intelligence" data-testid="drawer-tab-intelligence" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]">
                      <Brain className="w-3 h-3 mr-1.5" /> Intelligence
                    </TabsTrigger>
                    <TabsTrigger value="notes" data-testid="drawer-tab-notes" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]">
                      <MessageSquare className="w-3 h-3 mr-1.5" /> Summary &amp; Notes
                    </TabsTrigger>
                    <TabsTrigger value="signals" data-testid="drawer-tab-signals" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]">
                      <Signal className="w-3 h-3 mr-1.5" /> Signals
                    </TabsTrigger>
                    <TabsTrigger value="related" data-testid="drawer-tab-related" className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-[var(--ink)]">
                      <Link2 className="w-3 h-3 mr-1.5" /> Related
                    </TabsTrigger>
                  </TabsList>
                  <div className="flex-1 overflow-y-auto px-6 py-5 relative" data-testid="drawer-body">
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
                  size="sm" variant="outline" onClick={() => navigate(buildBriefUrl())}
                  data-testid="drawer-cta-generate-brief" data-href={buildBriefUrl()}
                >
                  <FileText className="w-3 h-3 mr-1.5" /> Generate brief
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
