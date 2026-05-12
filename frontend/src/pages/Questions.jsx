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
} from "lucide-react";
import ListingShell from "@/components/common/ListingShell";


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


function QuestionDrawer({ row, contextIdGetter, onClose, onAnswered }) {
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);

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

  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [drawerRow, setDrawerRow] = useState(null);
  const [raiseOpen, setRaiseOpen] = useState(false);

  const setParam = (k, v) => {
    const sp = new URLSearchParams(searchParams);
    if (!v || v === "open") sp.delete(k); else sp.set(k, v);
    setSearchParams(sp, { replace: true });
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      let data;
      if (routeCycleId && activeContext?.id) {
        const r = await api.get(
          `/contexts/${activeContext.id}/cycles/${routeCycleId}/questions`,
          { params: { status: filter === "all" ? "all" : filter } },
        );
        data = r.data;
      } else {
        const r = await api.get("/api/me/questions", {
          params: { status: filter === "all" ? "all" : filter, page, page_size: 10 },
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
  }, [routeCycleId, activeContext?.id, filter, page, q]);

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

        <ListingShell
          testId="questions-listing"
          searchValue={q}
          onSearchChange={(v) => setParam("q", v)}
          searchPlaceholder="Search questions…"
          filterTabs={filterTabs}
          activeFilterKey={filter}
          onFilterChange={(k) => setParam("filter", k)}
          sortOptions={[
            { key: "recent", label: "Most recent" },
            { key: "oldest", label: "Oldest" },
          ]}
          activeSortKey="recent"
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
              <p className="akki-serif text-[15px] text-[var(--ink)]">
                {filter === "answered" ? "No answered questions to show." : "Nothing waiting on you."}
              </p>
              <p className="text-[12.5px] text-[var(--muted)] mt-1">
                {filter === "answered"
                  ? "Once you answer a question it appears here."
                  : "When NEDs raise questions assigned to you, they land in this list."}
              </p>
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
