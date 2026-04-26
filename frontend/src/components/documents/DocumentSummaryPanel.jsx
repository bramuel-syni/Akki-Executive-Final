/**
 * DocumentSummaryPanel — AKKI's read of one document.
 *
 * Sits in the Document Viewer right rail. Auto-generates a summary the
 * first time the user opens the document; cached thereafter on the doc
 * record so subsequent opens are instant. A small "Re-read" gesture
 * lets the user force-refresh.
 *
 *   • TL;DR — 2-line executive summary
 *   • Highlights — the parts the reader should know
 *   • Questions — what to walk into the room with
 */
import React, { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Sparkles, Loader2, RotateCw, BookOpen, AlertCircle } from "lucide-react";

export default function DocumentSummaryPanel({ contextId, document: doc }) {
  const [summary, setSummary] = useState(doc?.akki_summary || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const generate = useCallback(async (refresh = false) => {
    if (!contextId || !doc?.id) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/documents/${doc.id}/summary`,
        null,
        { params: { refresh: refresh ? true : undefined }, timeout: 120000 },
      );
      setSummary(data);
      if (refresh) toast.success("Re-read complete.");
    } catch (e) {
      const msg = apiErrorMessage(e);
      setError(msg);
      if (refresh) toast.error(msg);
    } finally {
      setLoading(false);
    }
  }, [contextId, doc?.id]);

  // Auto-generate on first mount when no cached summary exists.
  useEffect(() => {
    if (!doc?.id) return;
    setSummary(doc.akki_summary || null);
    setError(null);
    if (!doc.akki_summary && doc.extracted_chars > 0) {
      generate(false);
    }
  }, [doc?.id, doc?.akki_summary, doc?.extracted_chars, generate]);

  if (!doc) {
    return (
      <div className="bg-white border border-[#E1E6ED] rounded-md p-6 text-center" data-testid="doc-summary-empty">
        <BookOpen className="w-7 h-7 text-[var(--muted)]/40 mx-auto mb-3" strokeWidth={1.2} />
        <p className="akki-overline mb-2">Document summary</p>
        <p className="text-[12.5px] text-[var(--muted)] leading-relaxed max-w-[28ch] mx-auto">
          Click any document to the left. AKKI will read it and surface what matters.
        </p>
      </div>
    );
  }

  if (doc.extracted_chars === 0) {
    return (
      <div className="bg-white border border-[#E1E6ED] rounded-md p-5" data-testid="doc-summary-no-text">
        <p className="akki-overline mb-2">Document summary</p>
        <p className="text-[12.5px] text-[var(--muted)] italic">
          AKKI couldn't extract text from this document, so a summary isn't possible.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#E1E6ED] rounded-md p-5" data-testid="doc-summary-panel">
      <div className="flex items-center justify-between mb-3">
        <p className="akki-overline flex items-center gap-1.5">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Document summary
        </p>
        {summary && !loading && (
          <button
            onClick={() => generate(true)}
            className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] hover:text-[var(--accent)] inline-flex items-center gap-1"
            data-testid="doc-summary-refresh"
            title="Ask AKKI to re-read this document"
          >
            <RotateCw className="w-3 h-3" /> Re-read
          </button>
        )}
      </div>

      {loading && !summary && (
        <div className="text-center py-8" data-testid="doc-summary-loading">
          <Loader2 className="w-5 h-5 animate-spin text-[var(--accent)] mx-auto mb-3" />
          <p className="text-[12px] text-[var(--muted)] italic">AKKI is reading…</p>
        </div>
      )}

      {error && !summary && (
        <div className="bg-red-50 border border-red-200 rounded-sm p-3 text-[12px] text-red-700" data-testid="doc-summary-error">
          <AlertCircle className="w-3.5 h-3.5 inline mr-1 -mt-0.5" />
          {error}
          <button
            onClick={() => generate(true)}
            className="ml-2 text-[11px] underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {summary && (
        <div className="space-y-4" data-testid="doc-summary-content">
          {summary.tldr && (
            <section>
              <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono mb-1.5">TL;DR</p>
              <p className="akki-serif text-[14px] leading-[1.65] text-[var(--ink)]">
                {summary.tldr}
              </p>
            </section>
          )}

          {summary.highlights?.length > 0 && (
            <section data-testid="doc-summary-highlights">
              <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono mb-1.5">What matters</p>
              <ul className="space-y-2">
                {summary.highlights.map((h, i) => (
                  <li key={i} className="flex gap-2 text-[13px] leading-[1.55] text-[var(--deep)]">
                    <span className="text-[var(--accent)] font-mono text-[10.5px] mt-1 shrink-0">{String(i + 1).padStart(2, "0")}</span>
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {summary.questions?.length > 0 && (
            <section data-testid="doc-summary-questions" className="bg-[var(--accent-soft)]/40 border border-[var(--accent)]/20 rounded-sm p-3">
              <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] font-mono mb-1.5">Walk in asking</p>
              <ul className="space-y-1.5">
                {summary.questions.map((q, i) => (
                  <li key={i} className="text-[13px] italic text-[var(--ink)] leading-[1.55] akki-serif">
                    "{q}"
                  </li>
                ))}
              </ul>
            </section>
          )}

          {loading && (
            <p className="text-[11px] text-[var(--muted)] italic flex items-center gap-1.5 pt-2 border-t border-[#E1E6ED]">
              <Loader2 className="w-3 h-3 animate-spin" /> Re-reading…
            </p>
          )}
        </div>
      )}
    </div>
  );
}
