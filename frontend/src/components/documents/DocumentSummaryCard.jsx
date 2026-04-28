/**
 * DocumentSummaryCard — replaces the persistent Ask pane on /app/workspace
 * when the user has a document selected.
 *
 * Per user feedback (iter57): "Replace the chat function in my documents
 * with a document summary card that populates when you select a document.
 * You can flick on continue in chat, which will move you to chat to
 * continue the conversation."
 *
 * Behaviour:
 *   - No doc selected → soft empty state ("Pick a document to read AKKI's
 *     read of it here").
 *   - Doc selected → summary, key points, next questions, with a single
 *     "Continue in Chat" button that hands off to /app/chat with the doc
 *     primed as the active source.
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowRight, FileText, Loader2, MessageCircle, Sparkles } from "lucide-react";

const SUMMARY_KIND_LABEL = {
  summary:   "AKKI summary",
  key_points: "Key points",
  questions:  "Questions to walk in with",
};

export default function DocumentSummaryCard({ contextId, docId }) {
  const navigate = useNavigate();
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!contextId || !docId) {
      setDoc(null);
      return;
    }
    let live = true;
    setLoading(true);
    setErr(null);
    api
      .get(`/contexts/${contextId}/documents/${docId}`)
      .then((r) => { if (live) setDoc(r.data); })
      .catch((e) => { if (live) setErr(apiErrorMessage(e)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [contextId, docId]);

  const continueInChat = () => {
    if (!docId) return;
    navigate(`/app/chat?doc=${encodeURIComponent(docId)}`);
  };

  if (!docId) {
    return (
      <div className="h-full flex flex-col items-center justify-center px-8 text-center bg-[var(--cream)]" data-testid="doc-summary-empty">
        <FileText className="w-8 h-8 text-[var(--muted)] mb-4" strokeWidth={1.4} />
        <p className="akki-serif text-[16px] text-[var(--ink)] mb-1.5">
          Pick a document.
        </p>
        <p className="text-[12.5px] text-[var(--muted)] italic max-w-xs leading-snug">
          AKKI's read of it — summary, key points, questions to walk in with — will appear here.
          You can continue in chat with one click.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-[var(--cream)] overflow-hidden" data-testid="doc-summary-card">
      <header className="px-5 py-4 border-b border-[var(--rule)] bg-white">
        <p className="akki-overline mb-1">Document · summary</p>
        <h2 className="akki-serif text-[18px] text-[var(--ink)] leading-snug truncate" data-testid="doc-summary-title">
          {doc?.name || doc?.original_filename || "Loading…"}
        </h2>
        {doc?.data_trust && (
          <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mt-1.5">
            {doc.data_trust} · {doc.doc_type || "doc"}
            {doc.created_at && (
              <> · added {new Date(doc.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</>
            )}
          </p>
        )}
      </header>

      <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
        {loading && (
          <div className="flex items-center gap-2 text-[12.5px] italic text-[var(--muted)]">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--accent)]" />
            AKKI is reading the document…
          </div>
        )}
        {err && (
          <p className="text-[12.5px] text-rose-700" data-testid="doc-summary-error">{err}</p>
        )}
        {!loading && !err && doc && (
          <>
            <Section
              kind="summary"
              icon={Sparkles}
              body={doc.akki_summary || doc.preview || null}
              fallback="No summary yet — click 'Continue in Chat' to ask AKKI to read it."
            />
            {doc.akki_key_points?.length > 0 && (
              <Section
                kind="key_points"
                icon={ArrowRight}
                body={null}
                items={doc.akki_key_points}
              />
            )}
            {doc.akki_questions?.length > 0 && (
              <Section
                kind="questions"
                icon={MessageCircle}
                body={null}
                items={doc.akki_questions}
              />
            )}
          </>
        )}
      </div>

      <footer className="px-5 py-4 border-t border-[var(--rule)] bg-white">
        <Button
          onClick={continueInChat}
          className="w-full bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-10"
          data-testid="doc-summary-continue-chat"
        >
          <MessageCircle className="w-3.5 h-3.5 mr-2" />
          Continue in Chat
          <ArrowRight className="w-3.5 h-3.5 ml-2" />
        </Button>
        <p className="text-[10.5px] text-[var(--muted)] mt-2 text-center">
          Hands off the document context to a fresh chat thread.
        </p>
      </footer>
    </div>
  );
}

function Section({ kind, icon: Icon, body, items, fallback }) {
  return (
    <section data-testid={`doc-summary-section-${kind}`}>
      <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mb-2 flex items-center gap-1.5">
        <Icon className="w-3 h-3 text-[var(--accent)]" strokeWidth={1.7} />
        {SUMMARY_KIND_LABEL[kind]}
      </p>
      {body && (
        <p className="text-[14px] text-[var(--ink)] leading-relaxed whitespace-pre-wrap">
          {body}
        </p>
      )}
      {items && items.length > 0 && (
        <ul className="space-y-1.5 text-[13.5px] text-[var(--ink)] list-disc list-inside marker:text-[var(--accent)]">
          {items.map((it, i) => <li key={i}>{it}</li>)}
        </ul>
      )}
      {!body && (!items || items.length === 0) && fallback && (
        <p className="text-[12.5px] italic text-[var(--muted)]">{fallback}</p>
      )}
    </section>
  );
}
