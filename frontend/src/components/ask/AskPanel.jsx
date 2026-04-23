import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  MessageSquareText, Send, Loader2, FileText, ShieldCheck, User,
} from "lucide-react";

const TRUST_COLOR = {
  trusted: "text-emerald-700",
  mixed:   "text-amber-700",
  weak:    "text-red-700",
  unrated: "text-slate-500",
};

function formatTime(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
  catch { return iso; }
}

/** Render assistant answer with inline [doc:xxx] citations as chips.
 *  Supports both `[doc:xxx]` and `[doc:xxx, doc:yyy]` formats. */
function renderAnswer(answer, sources, onCitationClick) {
  if (!answer) return null;
  const BLOCK = /\[doc:[a-f0-9-]+(?:[,\s]+doc:[a-f0-9-]+)*\]/g;
  const ID = /[a-f0-9-]{8,}/g;
  const parts = answer.split(BLOCK);
  const matches = answer.match(BLOCK) || [];
  const nameById = Object.fromEntries((sources || []).map((s) => [s.doc_id, s.doc_name]));
  const out = [];
  const chipFor = (id, keyBase) => {
    const name = nameById[id];
    const Chip = onCitationClick ? "button" : "span";
    return (
      <Chip
        key={keyBase}
        type={onCitationClick ? "button" : undefined}
        onClick={onCitationClick ? () => onCitationClick(id) : undefined}
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 mx-0.5 rounded-sm text-[10px] bg-[var(--accent)]/10 text-[var(--ink)] border border-[var(--accent)]/30 font-medium ${
          onCitationClick ? "hover:bg-[var(--accent)]/25 cursor-pointer transition-colors" : ""
        }`}
        title={name || id}
        data-testid={`citation-${id}`}
      >
        <FileText className="w-2.5 h-2.5" strokeWidth={2.2} />
        {name || id.slice(0, 8)}
      </Chip>
    );
  };
  parts.forEach((p, i) => {
    if (p) out.push(<span key={`p-${i}`}>{p}</span>);
    if (matches[i]) {
      const ids = matches[i].match(ID) || [];
      ids.forEach((id, j) => out.push(chipFor(id, `${i}-${j}`)));
    }
  });
  return out;
}

function QAExchange({ record, accountName, onCitationClick }) {
  return (
    <div className="space-y-3" data-testid={`ask-exchange-${record.id}`}>
      <div className="flex gap-2.5">
        <div className="w-6 h-6 bg-[var(--navy)] text-white flex items-center justify-center rounded-sm shrink-0">
          <User className="w-3 h-3" strokeWidth={2} />
        </div>
        <div className="flex-1 bg-white border border-[#E1E6ED] rounded-sm p-3">
          <div className="flex items-center justify-between mb-1">
            <p className="text-[9px] uppercase tracking-wider text-slate-500 font-semibold">
              {accountName || "You"}
            </p>
            <p className="text-[9px] text-slate-400">{formatTime(record.created_at)}</p>
          </div>
          <p className="text-[13px] text-[var(--ink)] leading-relaxed whitespace-pre-wrap">{record.question}</p>
        </div>
      </div>

      <div className="flex gap-2.5">
        <div className="w-6 h-6 bg-[var(--navy)] text-white flex items-center justify-center rounded-sm shrink-0 font-bold text-[10px] akki-serif">
          A
        </div>
        <div className="flex-1 bg-slate-50 border border-[#E1E6ED] rounded-sm p-3">
          <div className="flex items-center justify-between mb-1">
            <p className="text-[9px] uppercase tracking-wider text-[var(--accent)] font-semibold">AKKI</p>
            {record.mode && (
              <p className="text-[9px] text-slate-400 font-mono">mode: {record.mode}</p>
            )}
          </div>
          <div className="text-[13px] text-slate-700 leading-relaxed whitespace-pre-wrap">
            {renderAnswer(record.answer, record.sources, onCitationClick)}
          </div>
          {record.sources?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3 pt-2 border-t border-[#E1E6ED]">
              <span className="text-[9px] uppercase tracking-[0.2em] text-slate-400 self-center">Grounded in</span>
              {record.sources.map((s) => (
                <button
                  key={s.doc_id}
                  type="button"
                  onClick={() => onCitationClick?.(s.doc_id)}
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[10px] bg-white text-slate-700 border border-[#E1E6ED] hover:border-[var(--accent)]/50 transition-colors"
                  data-testid={`ask-source-${record.id}-${s.doc_id}`}
                >
                  <FileText className="w-2.5 h-2.5 text-[var(--accent)]" strokeWidth={2} />
                  {s.doc_name}
                  <span className={`ml-0.5 ${TRUST_COLOR[s.data_trust] || TRUST_COLOR.unrated}`}>· {s.data_trust}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Reusable Ask panel.
 * Props:
 *   contextId - required
 *   accountName - optional display name for the question bubble
 *   prefillQuestion - optional string to pre-populate the composer (used by suggestion chips)
 *   onCitationClick(docId) - optional; called when the user clicks a [doc:xxx] chip
 *   dense - true reduces padding (used in split-panel)
 *   header - optional JSX rendered above the history
 */
export default function AskPanel({
  contextId,
  accountName,
  prefillQuestion,
  onCitationClick,
  dense = false,
  header,
}) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const endRef = useRef(null);

  const load = useCallback(async () => {
    if (!contextId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/ask`);
      setHistory(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId]);

  useEffect(() => { setLoading(true); load(); }, [load]);

  // Allow parent to pre-populate the composer (e.g. from suggestion chips)
  useEffect(() => {
    if (prefillQuestion) setQuestion(prefillQuestion);
  }, [prefillQuestion]);

  const ordered = useMemo(
    () => [...history].sort((a, b) => new Date(a.created_at) - new Date(b.created_at)),
    [history]
  );

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [ordered.length, asking]);

  const onAsk = async (e) => {
    e?.preventDefault?.();
    const q = question.trim();
    if (!q || asking) return;
    setAsking(true);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/ask`,
        { question: q },
        { timeout: 120000 }
      );
      setHistory((prev) => [data, ...prev]);
      setQuestion("");
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setAsking(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      onAsk();
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0" data-testid="ask-panel">
      {header}
      <div
        className={`flex-1 overflow-y-auto ${dense ? "p-4" : "p-6"} space-y-6`}
        data-testid="ask-history"
      >
        {loading ? (
          <div className="p-8 text-center text-xs uppercase tracking-widest text-slate-400">Loading…</div>
        ) : ordered.length === 0 ? (
          <div className="p-8 text-center" data-testid="ask-empty-state">
            <MessageSquareText className="w-8 h-8 text-slate-300 mx-auto mb-3" strokeWidth={1.3} />
            <p className="text-xs text-slate-600 mb-1 font-medium">No questions yet</p>
            <p className="text-[11px] text-slate-500 max-w-xs mx-auto">
              Ask AKKI anything about the documents in this context. Every answer cites its sources.
            </p>
          </div>
        ) : (
          ordered.map((r) => (
            <QAExchange
              key={r.id}
              record={r}
              accountName={accountName}
              onCitationClick={onCitationClick}
            />
          ))
        )}
        {asking && (
          <div className="flex gap-2.5" data-testid="ask-thinking">
            <div className="w-6 h-6 bg-[var(--navy)] text-white flex items-center justify-center rounded-sm shrink-0 font-bold text-[10px] akki-serif">
              A
            </div>
            <div className="flex-1 bg-slate-50 border border-[#E1E6ED] rounded-sm p-3">
              <p className="text-[11px] text-slate-500 italic flex items-center gap-2">
                <Loader2 className="w-3 h-3 animate-spin text-[var(--accent)]" />
                AKKI is reading your documents…
              </p>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={onAsk}
        className={`border-t border-[#E1E6ED] bg-white ${dense ? "p-3" : "p-4"}`}
        data-testid="ask-composer"
      >
        <Textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask a question… (⌘/Ctrl + Enter)"
          className={`rounded-sm border-0 focus-visible:ring-0 resize-none text-sm ${dense ? "min-h-[64px]" : "min-h-[84px]"}`}
          disabled={asking}
          data-testid="ask-question-input"
        />
        <div className="flex items-center justify-between pt-2 mt-1 border-t border-[#E1E6ED]">
          <div className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-slate-400">
            <ShieldCheck className="w-3 h-3" strokeWidth={2} />
            Synisense shielded
          </div>
          <Button
            type="submit"
            disabled={asking || !question.trim()}
            className="bg-[var(--ink)] hover:bg-[#0E2958] text-white rounded-sm h-8 px-3 text-xs"
            data-testid="ask-submit-btn"
          >
            {asking ? (
              <><Loader2 className="w-3 h-3 mr-1.5 animate-spin" /> Asking…</>
            ) : (
              <><Send className="w-3 h-3 mr-1.5" /> Ask</>
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
