import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { GitBranch, FileText, ArrowRight, ChevronRight } from "lucide-react";

const RELATION_LABEL = {
  update: "Update",
  follow_up: "Follow-up",
  additional_context: "Context",
  correction: "Correction",
};

/**
 * Renders the ancestor chain + descendants for a document, so a user on a
 * given document can see the continuity thread (what came before, what
 * followed).
 */
export default function DocumentThread({ doc }) {
  const [thread, setThread] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!doc?.id || !doc?.context_id) return;
    try {
      const { data } = await api.get(`/contexts/${doc.context_id}/documents/${doc.id}/thread`);
      setThread(data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [doc]);

  useEffect(() => { load(); }, [load]);

  if (loading) return null;
  if (!thread) return null;

  const { ancestors = [], descendants = [] } = thread;
  // If there's only self in ancestors and no descendants, no thread to show.
  if (ancestors.length <= 1 && descendants.length === 0) return null;

  return (
    <section
      className="mt-8 bg-[var(--cream-deep)]/60 border border-[var(--rule)] rounded-md p-5"
      data-testid="document-thread"
    >
      <div className="flex items-center gap-2 mb-4">
        <GitBranch className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
        <p className="akki-overline">Document thread · {ancestors.length + descendants.length} docs in continuity</p>
      </div>

      <ol className="space-y-2">
        {ancestors.map((a, idx) => {
          const isSelf = a.id === doc.id;
          const isLast = idx === ancestors.length - 1 && descendants.length === 0;
          return (
            <ThreadItem key={a.id} d={a} selfId={doc.id} isSelf={isSelf} isLast={isLast} />
          );
        })}
        {descendants.map((d, idx) => (
          <ThreadItem
            key={d.id}
            d={d}
            selfId={doc.id}
            isSelf={false}
            isLast={idx === descendants.length - 1}
            isDescendant
          />
        ))}
      </ol>

      <p className="text-[10.5px] text-[var(--muted)] mt-4 italic">
        AKKI flags inconsistencies across the thread when it generates signals or answers Ask questions on these documents.
      </p>
    </section>
  );
}

function ThreadItem({ d, selfId, isSelf, isLast, isDescendant }) {
  return (
    <li
      className="flex items-start gap-3"
      data-testid={`thread-item-${d.id}`}
      data-self={isSelf}
    >
      <div className="relative flex flex-col items-center shrink-0 pt-1">
        <div className={`w-2.5 h-2.5 rounded-full ${isSelf ? "bg-[var(--accent)] ring-2 ring-[var(--accent)]/25" : "bg-[var(--rule)] border border-[var(--ink)]/30"}`} />
        {!isLast && <div className="w-px flex-1 mt-1 bg-[var(--rule)]" style={{ minHeight: 24 }} />}
      </div>
      <div className={`flex-1 min-w-0 pb-4 ${isSelf ? "" : ""}`}>
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-[10px] uppercase tracking-wider ${isSelf ? "text-[var(--accent)] font-medium" : "text-[var(--muted)]"}`}>
            {isSelf ? "You are here" : (new Date(d.created_at).toLocaleDateString())}
          </span>
          {d.relation_type && (
            <span className="text-[10px] uppercase tracking-wider text-[var(--accent)] bg-[var(--accent-soft)] px-1.5 py-0.5 rounded">
              {RELATION_LABEL[d.relation_type] || d.relation_type}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <FileText className="w-3 h-3 text-[var(--muted)] shrink-0" strokeWidth={1.8} />
          {isSelf ? (
            <span className="akki-serif text-[14.5px] text-[var(--ink)] font-medium">{d.name}</span>
          ) : (
            <Link to={`/app/documents/${d.id}`} className="akki-serif text-[14.5px] text-[var(--deep)] hover:text-[var(--accent)] transition-colors">
              {d.name}
            </Link>
          )}
        </div>
        {d.description && (
          <p className="text-[12px] text-[var(--muted)] leading-snug mt-1 line-clamp-2 max-w-[62ch]">
            {d.description}
          </p>
        )}
      </div>
    </li>
  );
}
