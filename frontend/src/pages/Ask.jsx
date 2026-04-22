import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  MessageSquareText, Send, Loader2, FileText, ShieldCheck,
  ArrowRight, User,
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

/** Render assistant answer, highlighting [doc:xxx] citations inline. */
function renderAnswer(answer, sources) {
  if (!answer) return null;
  const parts = answer.split(/(\[doc:[a-f0-9-]+\])/g);
  const nameById = Object.fromEntries((sources || []).map((s) => [s.doc_id, s.doc_name]));
  return parts.map((p, i) => {
    const m = p.match(/^\[doc:([a-f0-9-]+)\]$/);
    if (!m) return <span key={i}>{p}</span>;
    const id = m[1];
    const name = nameById[id];
    return (
      <span
        key={i}
        className="inline-flex items-center gap-1 px-1.5 py-0.5 mx-0.5 rounded-sm text-[10px] bg-[#C9A961]/10 text-[#0A1F44] border border-[#C9A961]/30 font-medium"
        title={name || id}
        data-testid={`citation-${id}`}
      >
        <FileText className="w-2.5 h-2.5" strokeWidth={2.2} />
        {name || id.slice(0, 8)}
      </span>
    );
  });
}

function QAExchange({ record, accountName }) {
  return (
    <div className="space-y-4" data-testid={`ask-exchange-${record.id}`}>
      {/* Question */}
      <div className="flex gap-3">
        <div className="w-7 h-7 bg-[#0A1F44] text-white flex items-center justify-center rounded-sm shrink-0">
          <User className="w-3.5 h-3.5" strokeWidth={2} />
        </div>
        <div className="flex-1 bg-white border border-[#E1E6ED] rounded-sm p-4">
          <div className="flex items-center justify-between mb-1">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
              {accountName || "You"}
            </p>
            <p className="text-[10px] text-slate-400">{formatTime(record.created_at)}</p>
          </div>
          <p className="text-sm text-[#0A1F44] leading-relaxed whitespace-pre-wrap">{record.question}</p>
        </div>
      </div>

      {/* Answer */}
      <div className="flex gap-3">
        <div className="w-7 h-7 bg-[#C9A961] text-[#0A1F44] flex items-center justify-center rounded-sm shrink-0 font-bold text-xs">
          A
        </div>
        <div className="flex-1 bg-slate-50 border border-[#E1E6ED] rounded-sm p-4">
          <div className="flex items-center justify-between mb-1">
            <p className="text-[10px] uppercase tracking-wider text-[#C9A961] font-semibold">AKKI</p>
            {record.mode && (
              <p className="text-[10px] text-slate-400 font-mono">mode: {record.mode}</p>
            )}
          </div>
          <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
            {renderAnswer(record.answer, record.sources)}
          </div>
          {record.sources?.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-[#E1E6ED]">
              <span className="text-[10px] uppercase tracking-[0.2em] text-slate-400 self-center">Grounded in</span>
              {record.sources.map((s) => (
                <span
                  key={s.doc_id}
                  className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-[11px] bg-white text-slate-700 border border-[#E1E6ED]"
                  data-testid={`ask-source-${record.id}-${s.doc_id}`}
                >
                  <FileText className="w-3 h-3 text-[#C9A961]" strokeWidth={2} />
                  {s.doc_name}
                  <span className={`ml-1 ${TRUST_COLOR[s.data_trust] || TRUST_COLOR.unrated}`}>· {s.data_trust}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Ask() {
  const { account, activeContext } = useAuth();
  const contextId = activeContext?.id;

  const [history, setHistory] = useState([]);       // newest-first from API; we render oldest-first
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

  useEffect(() => { load(); }, [load]);

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
      const { data } = await api.post(`/contexts/${contextId}/ask`, { question: q });
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

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-slate-500 text-sm">No context selected.</div></AppShell>;
  }

  return (
    <AppShell>
      <div className="p-8 max-w-4xl mx-auto flex flex-col min-h-[calc(100vh-4rem)]">
        <div className="mb-6">
          <p className="akki-overline mb-2">Ask · Module M5</p>
          <h1 className="text-3xl font-light tracking-tight text-[#0A1F44]">Grounded Q&amp;A</h1>
          <p className="text-sm text-slate-500 mt-2 max-w-2xl">
            Ask anything about this context. Answers are grounded strictly in your uploaded documents with inline citations. If the answer isn't there, AKKI will say so.
          </p>
        </div>

        {/* History */}
        <div className="flex-1 space-y-8 mb-6" data-testid="ask-history">
          {loading ? (
            <div className="p-12 text-center text-xs uppercase tracking-widest text-slate-400">Loading…</div>
          ) : ordered.length === 0 ? (
            <div className="bg-white border border-[#E1E6ED] rounded-sm p-12 text-center" data-testid="ask-empty-state">
              <MessageSquareText className="w-10 h-10 text-slate-300 mx-auto mb-4" strokeWidth={1.3} />
              <p className="text-sm text-slate-600 mb-1 font-medium">No questions yet</p>
              <p className="text-xs text-slate-500 max-w-sm mx-auto mb-4">
                Upload documents to Workspace, then ask AKKI a question. Every answer cites its source.
              </p>
              <Link to="/app/workspace" className="inline-flex items-center gap-1 text-xs text-[#C9A961] hover:underline font-medium">
                Open Workspace <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          ) : (
            ordered.map((r) => <QAExchange key={r.id} record={r} accountName={account?.name} />)
          )}
          {asking && (
            <div className="flex gap-3" data-testid="ask-thinking">
              <div className="w-7 h-7 bg-[#C9A961] text-[#0A1F44] flex items-center justify-center rounded-sm shrink-0 font-bold text-xs">
                A
              </div>
              <div className="flex-1 bg-slate-50 border border-[#E1E6ED] rounded-sm p-4">
                <p className="text-xs text-slate-500 italic flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#C9A961]" />
                  AKKI is reading your documents…
                </p>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Composer */}
        <form
          onSubmit={onAsk}
          className="sticky bottom-0 bg-[#FAFBFC] pt-4 pb-2"
          data-testid="ask-composer"
        >
          <div className="bg-white border border-[#E1E6ED] rounded-sm p-3">
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="What would you like to know? (⌘/Ctrl + Enter to send)"
              className="rounded-sm min-h-[84px] border-0 focus-visible:ring-0 resize-none text-sm"
              disabled={asking}
              data-testid="ask-question-input"
            />
            <div className="flex items-center justify-between pt-2 border-t border-[#E1E6ED] mt-2">
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-400">
                <ShieldCheck className="w-3 h-3" strokeWidth={2} />
                Synisense shielded · grounded answers only
              </div>
              <Button
                type="submit"
                disabled={asking || !question.trim()}
                className="bg-[#0A1F44] hover:bg-[#0E2958] text-white rounded-sm h-9 px-4"
                data-testid="ask-submit-btn"
              >
                {asking ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Asking…</>
                ) : (
                  <><Send className="w-4 h-4 mr-2" /> Ask</>
                )}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
