/**
 * Questions — Patch 14.
 *
 * Cross-context list of questions assigned to the current user, plus
 * per-cycle list when a `?cycle=` query param is provided.
 *
 * ListingShell foundation. Drawer pattern matches Work Studio / Monitor.
 *
 * Routes:
 *   /app/questions                            — my questions across contexts
 *   /app/cycle/:cycleId/questions             — questions on a specific cycle
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import {
  MessageSquare, Plus, ArrowRight, Loader2, X as XIcon, CheckCircle2,
  Zap, MessageCircle, Check,
} from "lucide-react";
import ListingShell from "@/components/common/ListingShell";
import takeToSolva from "@/lib/takeToSolva";


function relTime(iso) {
  if (!iso) return "—";
  try {
    const ms = Date.now() - new Date(iso).getTime();
    const days = Math.floor(ms / (24 * 60 * 60 * 1000));
    if (days < 1) return "today";
    if (days < 30) return `${days}d ago`;
    return new Date(iso).toLocaleDateString();
  } catch { return "—"; }
}


function QuestionRow({ row, onOpen }) {
  const isAnswered = row.status === "answered";
  return (
    <button
      type="button"
      onClick={() => onOpen(row)}
      className="w-full text-left border border-[var(--rule)] rounded-sm bg-white px-5 py-4 hover:border-[var(--ink)] transition-colors"
      data-testid={`question-row-${row.id}`}
    >
      <div className="flex items-start gap-4">
        <MessageSquare
          className={isAnswered ? "w-4 h-4 text-[var(--muted)] mt-1 shrink-0" : "w-4 h-4 text-[var(--ink)] mt-1 shrink-0"}
          strokeWidth={1.7}
        />
        <div className="flex-1 min-w-0">
          <p
            className="akki-serif text-[14.5px] text-[var(--ink)] leading-snug line-clamp-2"
            data-testid={`question-row-text-${row.id}`}
          >
            {row.text}
          </p>
          <p className="text-[11.5px] text-[var(--muted)] font-mono mt-2 inline-flex items-center gap-2 flex-wrap">
            <span>Asked {relTime(row.asked_at)}</span>
            <span className="opacity-50">·</span>
            <span>{isAnswered ? "Answered" : "Open"}</span>
            {row.answered_at && (
              <>
                <span className="opacity-50">·</span>
                <span>Responded {relTime(row.answered_at)}</span>
              </>
            )}
          </p>
        </div>
        {isAnswered ? (
          <CheckCircle2 className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" strokeWidth={1.7} />
        ) : (
          <ArrowRight className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" />
        )}
      </div>
    </button>
  );
}


function QuestionDrawer({ row, contextIdGetter, onClose, onAnswered, navigate }) {
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [markBusy, setMarkBusy] = useState(false);

  // ── Track B Phase B3 hotfix (2026-06-04) — hoisted above the
  // `if (!row) return null` early-return at the line below. Adding
  // these `useState` calls after the early-return broke React's
  // hook-order contract: initial mount with `row=null` ran 4 hooks
  // then returned; the row-click re-render then tried to run 13
  // hooks → "Rendered more hooks than during the previous render."
  // Closures over the setters resolve identically from the handler
  // bodies below — no behaviour change.
  const [shareOpen, setShareOpen] = useState(false);
  const [shareRecipients, setShareRecipients] = useState("");
  const [shareMessage, setShareMessage] = useState("");
  const [shareBusy, setShareBusy] = useState(false);
  const [reopenBusy, setReopenBusy] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkDocs, setLinkDocs] = useState([]);
  const [linkLoading, setLinkLoading] = useState(false);
  const [linkBusy, setLinkBusy] = useState(false);

  useEffect(() => { setAnswer(""); }, [row?.id]);

  if (!row) return null;
  const open = !!row;
  const isAnswered = row.status === "answered";

  const submit = async () => {
    const cid = contextIdGetter ? contextIdGetter(row) : row.context_id;
    if (!cid) {
      toast.error("Missing context id for this question.");
      return;
    }
    if (!answer.trim()) return;
    setBusy(true);
    try {
      await api.post(
        `/contexts/${cid}/questions/${row.id}/answer`,
        { text: answer.trim() },
      );
      toast.success("Answer recorded.");
      onAnswered && onAnswered();
      onClose && onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setBusy(false); }
  };

  // Q4Y P0-C3 (2026-02 fork-resume) — "Mark as Answered" without
  // composing a body. Idempotent on the backend. Reuses the same
  // contextIdGetter the answer-submit path uses.
  const markAnswered = async () => {
    const cid = contextIdGetter ? contextIdGetter(row) : row.context_id;
    if (!cid) {
      toast.error("Missing context id for this question.");
      return;
    }
    setMarkBusy(true);
    try {
      await api.post(
        `/contexts/${cid}/questions/${row.id}/mark-answered`,
        {},
      );
      toast.success("Marked answered.");
      onAnswered && onAnswered();
      onClose && onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setMarkBusy(false); }
  };

  // Q4Y P1-C1 (2026-02 fork-resume) — "Use in Solva" CTA. Reuses
  // the canonical Pulse pattern via `lib/takeToSolva.js` →
  // `/app/solva/session/new?ctx_type=question&ctx_id={row.id}`.
  // The backend resolver lives at
  // `routers/solva_v2.py::fetch_take_to_solva_seed` (kind="question").
  const useInSolva = () => {
    onClose && onClose();
    takeToSolva({ navigate, kind: "question", id: row.id });
  };

  // Q4Y P1-C2 (2026-02 fork-resume) — "Use in Chat" CTA. Mirrors
  // the canonical DocumentDrawer/TaskDrawer pattern via
  // `/app/chat?ctx_type=question&ctx_id={row.id}`. Backend allow-
  // list extended at `routers/chat.py::LinkedContextIn`; seed shape
  // handled in `_seed_from_context`.
  const useInChat = () => {
    onClose && onClose();
    if (typeof navigate === "function") {
      navigate(
        `/app/chat?ctx_type=question&ctx_id=${encodeURIComponent(row.id)}`,
      );
    }
  };

  // ── Track B Phase B3 (2026-06-04) — Share / Reopen / Link Response ──
  // (state declarations hoisted above the early-return — see top of fn.)
  const onShareSubmit = async () => {
    const cid = contextIdGetter ? contextIdGetter(row) : row.context_id;
    if (!cid) { toast.error("Missing context id."); return; }
    const recipients = shareRecipients
      .split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
    if (recipients.length === 0) {
      toast.error("Enter at least one recipient.");
      return;
    }
    setShareBusy(true);
    try {
      await api.post(`/contexts/${cid}/questions/${row.id}/share`, {
        recipient_emails: recipients,
        message: shareMessage.trim() || null,
      });
      toast.success("Share recorded.");
      setShareOpen(false);
      setShareRecipients("");
      setShareMessage("");
      onAnswered && onAnswered();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setShareBusy(false); }
  };

  const onReopen = async () => {
    const cid = contextIdGetter ? contextIdGetter(row) : row.context_id;
    if (!cid) { toast.error("Missing context id."); return; }
    setReopenBusy(true);
    try {
      await api.post(`/contexts/${cid}/questions/${row.id}/reopen`);
      toast.success("Question reopened.");
      onAnswered && onAnswered();
      onClose && onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setReopenBusy(false); }
  };

  const openLinkPicker = async () => {
    const cid = contextIdGetter ? contextIdGetter(row) : row.context_id;
    if (!cid) { toast.error("Missing context id."); return; }
    setLinkOpen(true);
    setLinkLoading(true);
    try {
      const { data } = await api.get(`/contexts/${cid}/documents`);
      setLinkDocs(Array.isArray(data) ? data : []);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setLinkLoading(false); }
  };
  const selectLinkDoc = async (docId) => {
    const cid = contextIdGetter ? contextIdGetter(row) : row.context_id;
    setLinkBusy(true);
    try {
      await api.post(`/contexts/${cid}/questions/${row.id}/link-response`, {
        document_id: docId,
      });
      toast.success("Response document linked.");
      setLinkOpen(false);
      onAnswered && onAnswered();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setLinkBusy(false); }
  };

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose && onClose()}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-[480px] sm:w-[480px] overflow-y-auto bg-[var(--paper)] p-0"
        data-testid="question-drawer"
      >
        <div className="px-6 py-5 border-b border-[var(--rule)] flex items-start gap-3 sticky top-0 bg-[var(--paper)] z-10">
          <div className="min-w-0 flex-1">
            <SheetHeader className="text-left">
              <SheetTitle className="akki-serif text-[16px] text-[var(--ink)] leading-snug">
                Question
              </SheetTitle>
              <SheetDescription className="text-[12px] text-[var(--muted)]">
                {isAnswered ? "Answered" : "Open"} · {relTime(row.asked_at)}
              </SheetDescription>
            </SheetHeader>
          </div>
          <button onClick={onClose} type="button" className="text-[var(--muted)] hover:text-[var(--ink)] p-1" aria-label="Close drawer" data-testid="question-drawer-close">
            <XIcon className="w-4 h-4" />
          </button>
        </div>
        <div className="px-6 py-5 space-y-4">
          <div>
            <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] mb-1.5">The question</p>
            <p className="akki-serif text-[14.5px] leading-[1.65] text-[var(--ink)] whitespace-pre-wrap" data-testid="question-drawer-text">{row.text}</p>
          </div>
          {isAnswered && (
            <div data-testid="question-drawer-answer">
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] mb-1.5">Answer</p>
              <p className="akki-serif text-[14px] leading-[1.65] text-[var(--ink)] whitespace-pre-wrap border-l-2 border-[var(--rule)] pl-3">
                {row.answer_text}
              </p>
              <p className="text-[11px] text-[var(--muted)] font-mono mt-1.5">
                Recorded {relTime(row.answered_at)}
              </p>
            </div>
          )}
          {!isAnswered && (
            <div data-testid="question-drawer-composer">
              <Label className="text-[12px]" htmlFor="answer-text">Compose answer</Label>
              <textarea
                id="answer-text"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                rows={5}
                placeholder="Markdown supported."
                className="mt-1.5 w-full border border-[var(--rule)] rounded-sm px-3 py-2 text-[13.5px] bg-white"
                data-testid="question-drawer-textarea"
              />
              <div className="flex justify-end mt-3">
                <Button
                  type="button"
                  onClick={submit}
                  disabled={busy || !answer.trim()}
                  className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
                  data-testid="question-drawer-submit"
                >
                  {busy && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}
                  Submit answer
                </Button>
              </div>
            </div>
          )}

          {/* Q4Y P0-C3 + P1-C1 + P1-C2 (2026-02 fork-resume) —
              Drawer CTA strip. Surfaces below the composer (or the
              answer pane when isAnswered). Mark-answered hidden if
              already answered. Use-in-Solva + Use-in-Chat available
              both before and after answer so a re-investigation is
              always one click away. */}
          <div
            className="border-t border-[var(--rule)] pt-4 flex flex-wrap gap-2"
            data-testid="question-drawer-cta-strip"
          >
            {!isAnswered && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={markAnswered}
                disabled={markBusy}
                className="rounded-sm border-[var(--rule)] text-[12px]"
                data-testid="question-drawer-mark-answered"
              >
                {markBusy
                  ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  : <Check className="w-3.5 h-3.5 mr-1.5" />}
                Mark as Answered
              </Button>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={useInSolva}
              className="rounded-sm border-[var(--rule)] text-[12px]"
              data-testid="question-drawer-use-in-solva"
            >
              <Zap className="w-3.5 h-3.5 mr-1.5" />
              Use in Solva
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={useInChat}
              className="rounded-sm border-[var(--rule)] text-[12px]"
              data-testid="question-drawer-use-in-chat"
            >
              <MessageCircle className="w-3.5 h-3.5 mr-1.5" />
              Use in Chat
            </Button>
            {/* Track B Phase B3 (2026-06-04) — Share */}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShareOpen(true)}
              className="rounded-sm border-[var(--rule)] text-[12px]"
              data-testid="question-drawer-share"
            >
              Share
            </Button>
            {/* Track B Phase B3 (2026-06-04) — Reopen (Answered only) */}
            {isAnswered && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onReopen}
                disabled={reopenBusy}
                className="rounded-sm border-[var(--rule)] text-[12px]"
                data-testid="question-drawer-reopen"
              >
                {reopenBusy
                  ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                  : null}
                Reopen
              </Button>
            )}
            {/* Track B Phase B3 (2026-06-04) — Link response doc */}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={openLinkPicker}
              className="rounded-sm border-[var(--rule)] text-[12px]"
              data-testid="question-drawer-link-response"
            >
              Link response document
            </Button>
          </div>

          {/* Track B Phase B3 (2026-06-04) — Related document (when linked).
              source_doc_id is set when the question was generated from a
              document; response_doc_id is set when a user attached a
              follow-up response doc. Both render here. */}
          {(row.source_doc_id || row.response_doc_id) && (
            <div className="mb-4 border border-[var(--rule)] rounded-sm p-3 bg-[var(--cream-deep)]/30" data-testid="question-drawer-related-docs">
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-1.5">Related documents</p>
              {row.source_doc_id && (
                <button
                  type="button"
                  onClick={() => navigate(`/app/documents?id=${encodeURIComponent(row.source_doc_id)}`)}
                  className="block text-[12.5px] text-[var(--ink)] hover:underline"
                  data-testid="question-drawer-source-doc"
                >
                  Source: {row.source_doc_title || row.source_doc_id}
                </button>
              )}
              {row.response_doc_id && (
                <button
                  type="button"
                  onClick={() => navigate(`/app/documents?id=${encodeURIComponent(row.response_doc_id)}`)}
                  className="block text-[12.5px] text-[var(--ink)] hover:underline mt-1"
                  data-testid="question-drawer-response-doc"
                >
                  Response: {row.response_doc_id}
                </button>
              )}
            </div>
          )}

          {/* Share modal */}
          {shareOpen && (
            <div
              className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
              data-testid="question-drawer-share-modal"
            >
              <div className="bg-white border border-[var(--rule)] rounded-sm w-full max-w-md p-5">
                <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-2">Share question</p>
                <input
                  type="text"
                  value={shareRecipients}
                  onChange={(e) => setShareRecipients(e.target.value)}
                  placeholder="recipient@company.com, …"
                  className="w-full text-[13px] border border-[var(--rule)] rounded-sm px-2 py-1.5 mb-2"
                  data-testid="question-drawer-share-recipients"
                />
                <textarea
                  value={shareMessage}
                  onChange={(e) => setShareMessage(e.target.value)}
                  placeholder="Optional message"
                  rows={3}
                  className="w-full text-[13px] border border-[var(--rule)] rounded-sm px-2 py-1.5 mb-3"
                  data-testid="question-drawer-share-message"
                />
                <div className="flex gap-2 justify-end">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setShareOpen(false)} disabled={shareBusy}>Cancel</Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={onShareSubmit}
                    disabled={shareBusy || !shareRecipients.trim()}
                    data-testid="question-drawer-share-send"
                  >
                    {shareBusy ? "Sending…" : "Send"}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Link-response picker */}
          {linkOpen && (
            <div
              className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
              data-testid="question-drawer-link-picker"
            >
              <div className="bg-white border border-[var(--rule)] rounded-sm w-full max-w-lg p-5">
                <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-2">
                  Select a response document
                </p>
                {linkLoading ? (
                  <p className="text-[12.5px] text-[var(--muted)]">Loading documents…</p>
                ) : linkDocs.length === 0 ? (
                  <p className="text-[12.5px] text-[var(--muted)]">No documents in this context.</p>
                ) : (
                  <ul className="max-h-[40vh] overflow-y-auto space-y-1 mb-3">
                    {linkDocs.map((d) => (
                      <li key={d.id}>
                        <button
                          type="button"
                          onClick={() => selectLinkDoc(d.id)}
                          disabled={linkBusy}
                          className="w-full text-left px-3 py-2 hover:bg-[var(--cream-deep)]/40 text-[13px] text-[var(--ink)] border border-[var(--rule)] rounded-sm"
                          data-testid={`question-drawer-link-doc-${d.id}`}
                        >
                          {d.title || d.filename || d.id}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="flex justify-end">
                  <Button type="button" variant="ghost" size="sm" onClick={() => setLinkOpen(false)}>Cancel</Button>
                </div>
              </div>
            </div>
          )}

          {(row.history || []).length > 0 && (
            <div data-testid="question-drawer-history">
              <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--ink)] mb-2">History</p>
              <ol className="space-y-2">
                {row.history.map((h, i) => (
                  <li key={i} className="text-[12px] text-[var(--muted)] border-l border-[var(--rule)] pl-2">
                    <span className="font-mono text-[10.5px] uppercase tracking-[0.14em]">{relTime(h.ts)} · {h.kind}</span>
                    {h.note && <p className="mt-0.5">{h.note}</p>}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}


function RaiseQuestionModal({ open, onClose, contextId, cycleId, onCreated }) {
  const [text, setText] = useState("");
  const [assignee, setAssignee] = useState("");
  const [team, setTeam] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || !contextId) return undefined;
    api.get(`/contexts/${contextId}/team-catalogue`).then(({ data }) => {
      setTeam(data?.members || data?.items || []);
    }).catch(() => setTeam([]));
    return undefined;
  }, [open, contextId]);

  useEffect(() => {
    if (!open) { setText(""); setAssignee(""); }
  }, [open]);

  const submit = async () => {
    if (!text.trim() || !cycleId) return;
    setBusy(true);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/cycles/${cycleId}/questions`,
        { text: text.trim(), assignee_account_id: assignee || null },
      );
      toast.success("Question raised.");
      onCreated && onCreated(data);
      onClose && onClose();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && !busy && onClose && onClose()}>
      <DialogContent className="bg-[var(--parchment)]" data-testid="raise-question-modal">
        <DialogHeader>
          <DialogTitle className="akki-serif text-[18px] text-[var(--ink)]">Raise a question</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label className="text-[12px]" htmlFor="rq-text">Question</Label>
            <textarea
              id="rq-text"
              autoFocus
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              className="mt-1 w-full border border-[var(--rule)] rounded-sm px-2 py-2 text-[13.5px] bg-white"
              data-testid="raise-question-text"
            />
          </div>
          <div>
            <Label className="text-[12px]" htmlFor="rq-assignee">Assign to</Label>
            <select
              id="rq-assignee"
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
              className="mt-1 w-full border border-[var(--rule)] rounded-sm px-2 py-2 text-[13.5px] bg-white"
              data-testid="raise-question-assignee"
            >
              <option value="">— Unassigned —</option>
              {team.map((m) => (
                <option key={m.id || m.account_id || m.email} value={m.account_id || m.id}>
                  {m.name || m.display_name || m.email}
                </option>
              ))}
            </select>
          </div>
        </div>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button
            type="button"
            onClick={submit}
            disabled={busy || !text.trim()}
            className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
            data-testid="raise-question-submit"
          >
            {busy && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}
            Raise question
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}


export default function Questions() {
  const { activeContext } = useAuth();
  const navigate = useNavigate();
  const { cycleId: routeCycleId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();

  const filter = searchParams.get("filter") || "open";
  const q = searchParams.get("q") || "";
  // Q4Y P0-S1 (2026-02 fork-resume) — sort key from URL. Defaults to
  // "recent" (legacy `asked_at desc`). Other keys: `oldest`,
  // `answered_at_desc`. Backend supports all three via
  // `routers/questions.py::_SORT_KEYS`.
  const sort = searchParams.get("sort") || "recent";
  // Phase I.6 (2026-05-27) — close-loop wire from CompanyHome Card 4
  // subtext segments: deep link `/app/questions?role=board|ceo|team`.
  const askerRole = searchParams.get("role") || "";

  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [drawerRow, setDrawerRow] = useState(null);
  const [raiseOpen, setRaiseOpen] = useState(false);

  const setParam = (k, v) => {
    const sp = new URLSearchParams(searchParams);
    // Defaults stripped from the URL so the canonical share-link
    // shape stays clean. `filter` defaults to "open"; `sort` to
    // "recent". Other keys drop on empty value.
    const isDefault = (
      (k === "filter" && v === "open") ||
      (k === "sort" && v === "recent")
    );
    if (!v || isDefault) sp.delete(k); else sp.set(k, v);
    setSearchParams(sp, { replace: true });
  };

  const clearAskerRole = () => {
    const sp = new URLSearchParams(searchParams);
    sp.delete("role");
    setSearchParams(sp, { replace: true });
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      let data;
      if (routeCycleId && activeContext?.id) {
        const r = await api.get(
          `/contexts/${activeContext.id}/cycles/${routeCycleId}/questions`,
          {
            params: {
              status: filter === "all" ? "all" : filter,
              sort,
              ...(askerRole ? { asker_role: askerRole } : {}),
            },
          },
        );
        data = r.data;
      } else {
        const r = await api.get("/me/questions", {
          params: {
            status: filter === "all" ? "all" : filter,
            page, page_size: 10,
            sort,
            // Q4Y P1-F3 (2026-02 fork-resume) — server-side text
            // search. Pass `q` to the backend so cross-page hits
            // surface; client-side filter below stays as a belt-
            // and-suspenders narrowing of the already-narrow page.
            ...(q ? { q } : {}),
            ...(askerRole ? { asker_role: askerRole } : {}),
          },
        });
        data = r.data;
      }
      let rows = data?.items || [];
      if (q) {
        const lc = q.toLowerCase();
        rows = rows.filter((row) => (row.text || "").toLowerCase().includes(lc));
      }
      setItems(rows);
      setTotal(data?.total ?? rows.length);
    } catch (e) {
      setItems([]);
      setTotal(0);
    } finally { setLoading(false); }
  }, [routeCycleId, activeContext?.id, filter, page, q, askerRole, sort]);

  useEffect(() => { load(); }, [load]);

  // Context-id resolution for the drawer answer call. When listing a
  // single cycle, every row shares the active context. When listing
  // /api/me/questions cross-context, each row carries its own context_id.
  const contextIdGetter = useCallback((row) => row.context_id || activeContext?.id, [activeContext?.id]);

  const filterTabs = [
    { key: "open",     label: "Open",     count: undefined },
    { key: "answered", label: "Answered", count: undefined },
    { key: "all",      label: "All",      count: undefined },
  ];

  return (
    <AppShell>
      <div className="akki-w-medium px-8 py-10" data-testid="questions-page">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <MessageSquare className="w-3 h-3 text-[var(--accent)]" /> Questions
          {routeCycleId && (
            <button
              onClick={() => navigate("/app/questions")}
              className="ml-2 text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] hover:text-[var(--ink)]"
              data-testid="questions-all-contexts-link"
            >
              ↑ All contexts
            </button>
          )}
        </p>
        <h1 className="akki-greeting mb-2">
          {routeCycleId ? "Questions on this agenda" : "Questions for you"}
        </h1>
        <p className="akki-meta max-w-2xl mb-7">
          {routeCycleId
            ? "Questions raised on this agenda. Answer to flip status."
            : "Questions assigned to you across all contexts. Answer to flip status."}
        </p>

        {/* Phase I.6 (2026-05-27) — Active-filter chip for the
            asker_role deep-link from CompanyHome Card 4 segments.
            Only renders when `?role=` is present. Click X clears. */}
        {askerRole && (
          <div className="mb-5 inline-flex items-center gap-2" data-testid={`questions-role-chip-${askerRole}`}>
            <span className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-[0.12em] font-mono bg-[var(--ink)] text-[var(--parchment)] rounded-sm px-2.5 py-1">
              Role: {askerRole === "ceo" ? "CEO" : askerRole}
              <button
                type="button"
                onClick={clearAskerRole}
                className="hover:opacity-80 focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/50 rounded-sm"
                data-testid="questions-role-chip-clear"
                aria-label="Clear role filter"
              >
                ✕
              </button>
            </span>
          </div>
        )}

        <ListingShell
          testId="questions-listing"
          searchValue={q}
          onSearchChange={(v) => setParam("q", v)}
          searchPlaceholder="Search questions…"
          filterTabs={filterTabs}
          activeFilterKey={filter}
          onFilterChange={(k) => setParam("filter", k)}
          sortOptions={[
            { key: "recent",           label: "Most recent" },
            { key: "oldest",           label: "Oldest" },
            { key: "answered_at_desc", label: "Recently answered" },
          ]}
          activeSortKey={sort}
          onSortChange={(k) => setParam("sort", k)}
          pageSize={10}
          page={page}
          totalCount={total}
          onPageChange={(n) => setPage(n)}
          isLoading={loading}
          controlsRight={routeCycleId && activeContext?.id && (
            <Button
              type="button"
              size="sm"
              onClick={() => setRaiseOpen(true)}
              className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
              data-testid="questions-raise"
            >
              <Plus className="w-3.5 h-3.5 mr-1" /> Raise question
            </Button>
          )}
          emptyState={
            <div className="border border-dashed border-[var(--rule)] rounded-sm bg-[var(--parchment)] px-6 py-8 text-center" data-testid="questions-empty">
              {/* Track B Phase B3 (2026-06-04) — G23. Verbatim copy
                  from the Google Login + Doc Reader + Calendar +
                  Open Questions QA doc, paragraph 26:
                  "You have not generated any questions yet. Go to a
                  document to generate questions." with CTA
                  "Go to Document". The legacy Z2.4 "Run Solva on a
                  document" CTA is folded into this verbatim QA
                  empty-state when the filter is Open or All. */}
              <p className="akki-serif text-[15px] text-[var(--ink)]" data-testid="questions-empty-headline">
                {filter === "answered"
                  ? "No answered questions to show."
                  : "You have not generated any questions yet. Go to a document to generate questions."}
              </p>
              {filter === "answered" && (
                <p className="text-[12.5px] text-[var(--muted)] mt-1">
                  Once you answer a question it appears here.
                </p>
              )}
              {filter !== "answered" && (
                <div className="mt-5">
                  <Button
                    type="button"
                    onClick={() => navigate("/app/documents")}
                    className="bg-[var(--ink)] hover:bg-[var(--ink)]/90 text-[var(--parchment)] rounded-sm"
                    data-testid="questions-empty-go-to-document"
                  >
                    Go to Document
                  </Button>
                </div>
              )}
            </div>
          }
        >
          <ul className="space-y-2" data-testid="questions-list">
            {items.map((row) => (
              <QuestionRow key={row.id} row={row} onOpen={setDrawerRow} />
            ))}
          </ul>
        </ListingShell>
      </div>

      <QuestionDrawer
        row={drawerRow}
        contextIdGetter={contextIdGetter}
        onClose={() => setDrawerRow(null)}
        onAnswered={() => load()}
        navigate={navigate}
      />

      {routeCycleId && activeContext?.id && (
        <RaiseQuestionModal
          open={raiseOpen}
          onClose={() => setRaiseOpen(false)}
          contextId={activeContext.id}
          cycleId={routeCycleId}
          onCreated={() => load()}
        />
      )}
    </AppShell>
  );
}
