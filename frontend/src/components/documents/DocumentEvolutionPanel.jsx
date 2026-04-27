/**
 * DocumentEvolutionPanel — NED's view of how a document has changed.
 *
 * Surfaces the document's predecessor chain (via /thread) plus AKKI's
 * "what changed" diff between the current and the immediate predecessor.
 * Power feature for NEDs tracking recurring CFO/CEO reports across
 * cycles — drift, softening, and quiet omissions get flagged.
 *
 *   • Top: the chain (predecessors → this doc → successors)
 *   • Body: "What changed" against the immediate predecessor
 *   • Footer: link new predecessor / unlink
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  Layers, Loader2, RotateCw, ArrowRight, ArrowDownRight, Link2,
  Unlink, Plus, Minus, HelpCircle, CalendarClock,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

function fmtDate(s) {
  if (!s) return "";
  try { return new Date(s).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }); }
  catch { return s; }
}

export default function DocumentEvolutionPanel({ contextId, document: doc, onLinkChange }) {
  const [thread, setThread] = useState({ ancestors: [], descendants: [] });
  const [diff, setDiff] = useState(null);
  const [previousDoc, setPreviousDoc] = useState(null);
  const [loadingThread, setLoadingThread] = useState(false);
  const [loadingDiff, setLoadingDiff] = useState(false);
  const [error, setError] = useState(null);

  const loadThread = useCallback(async () => {
    if (!contextId || !doc?.id) return;
    setLoadingThread(true);
    try {
      const { data } = await api.get(`/contexts/${contextId}/documents/${doc.id}/thread`);
      setThread({
        ancestors: data?.ancestors || [],
        descendants: data?.descendants || [],
      });
    } catch (e) { /* silent — empty thread is normal */ }
    finally { setLoadingThread(false); }
  }, [contextId, doc?.id]);

  const loadDiff = useCallback(async (refresh = false) => {
    if (!contextId || !doc?.id || !doc?.related_doc_id) {
      setDiff(null); setPreviousDoc(null); return;
    }
    setLoadingDiff(true);
    setError(null);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/documents/${doc.id}/evolution-diff`,
        null,
        { params: { refresh: refresh ? true : undefined }, timeout: 120000 },
      );
      setDiff(data?.diff || null);
      setPreviousDoc(data?.previous_doc || null);
      if (refresh && data?.diff) toast.success("Re-read complete.");
    } catch (e) {
      setError(apiErrorMessage(e));
      if (refresh) toast.error(apiErrorMessage(e));
    } finally { setLoadingDiff(false); }
  }, [contextId, doc?.id, doc?.related_doc_id]);

  useEffect(() => { loadThread(); }, [loadThread]);
  useEffect(() => { loadDiff(false); }, [loadDiff]);

  // Build the linear chain for display: ancestors first, then this, then descendants.
  const chain = useMemo(() => {
    const cur = doc ? { ...doc, is_current: true } : null;
    const ancestors = thread.ancestors.filter((a) => a.id !== doc?.id);
    return [...ancestors, ...(cur ? [cur] : []), ...thread.descendants];
  }, [doc, thread]);

  if (!doc) return null;

  const hasChain = chain.length >= 2;

  return (
    <div className="bg-white border border-[#E1E6ED] rounded-md p-5" data-testid="doc-evolution-panel">
      <div className="flex items-center justify-between mb-3">
        <p className="akki-overline flex items-center gap-1.5">
          <Layers className="w-3 h-3 text-[var(--accent)]" /> Evolution
        </p>
        <div className="flex items-center gap-3">
          <LinkVersionDialog
            contextId={contextId}
            doc={doc}
            onChange={() => { onLinkChange?.(); loadThread(); loadDiff(true); }}
          />
          {diff && !loadingDiff && (
            <button
              onClick={() => loadDiff(true)}
              className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] hover:text-[var(--accent)] inline-flex items-center gap-1"
              data-testid="doc-evolution-rediff"
              title="Ask AKKI to re-compare"
            >
              <RotateCw className="w-3 h-3" /> Re-compare
            </button>
          )}
        </div>
      </div>

      {/* Chain ribbon */}
      {loadingThread ? (
        <p className="text-[12px] text-[var(--muted)] italic">Loading chain…</p>
      ) : !hasChain ? (
        <div className="text-[12.5px] text-[var(--muted)] italic leading-relaxed">
          No prior or successor versions linked. Use{" "}
          <strong className="text-[var(--deep)] not-italic">Link previous version</strong>{" "}
          above to start tracking how this report evolves across cycles.
        </div>
      ) : (
        <ol className="space-y-1.5 mb-4" data-testid="doc-evolution-chain">
          {chain.map((node, i) => {
            const isCurrent = node.is_current;
            const isPredecessor = !isCurrent && i < chain.findIndex((n) => n.is_current);
            return (
              <li
                key={node.id}
                className={`flex items-center gap-2 text-[12px] ${
                  isCurrent ? "text-[var(--ink)]" : "text-[var(--muted)]"
                }`}
                data-testid={`doc-evolution-node-${node.id}`}
              >
                {isPredecessor ? (
                  <ArrowDownRight className="w-3 h-3 shrink-0 text-[var(--muted)]/60" />
                ) : isCurrent ? (
                  <span className="w-3 h-3 rounded-full bg-[var(--accent)] shrink-0" aria-label="current" />
                ) : (
                  <ArrowRight className="w-3 h-3 shrink-0 text-[var(--muted)]/60" />
                )}
                <span className="truncate" style={{ paddingLeft: isPredecessor ? `${(chain.findIndex((n) => n.is_current) - i - 1) * 10}px` : 0 }}>
                  <span className={isCurrent ? "akki-serif" : ""}>{node.name || node.original_filename}</span>
                </span>
                <span className="shrink-0 inline-flex items-center gap-1 text-[10.5px] tabular-nums text-[var(--muted)]/80 ml-auto">
                  <CalendarClock className="w-2.5 h-2.5" />
                  {fmtDate(node.created_at)}
                </span>
              </li>
            );
          })}
        </ol>
      )}

      {/* Diff body */}
      {loadingDiff && !diff && (
        <div className="text-center py-6" data-testid="doc-evolution-loading">
          <Loader2 className="w-5 h-5 animate-spin text-[var(--accent)] mx-auto mb-2" />
          <p className="text-[12px] text-[var(--muted)] italic">AKKI is comparing versions…</p>
        </div>
      )}

      {error && !diff && (
        <div className="bg-red-50 border border-red-200 rounded-sm p-3 text-[12px] text-red-700">
          {error}
          <button onClick={() => loadDiff(true)} className="ml-2 underline">Retry</button>
        </div>
      )}

      {diff && previousDoc && (
        <div className="space-y-3 pt-3 border-t border-[#E1E6ED]" data-testid="doc-evolution-diff">
          <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] font-mono">
            What changed since
          </p>
          <p className="text-[12.5px] text-[var(--deep)] italic -mt-2">
            {previousDoc.name} · {fmtDate(previousDoc.created_at)}
          </p>

          {diff.what_changed && (
            <p className="akki-serif text-[14px] leading-[1.6] text-[var(--ink)]">
              {diff.what_changed}
            </p>
          )}

          {diff.added_or_strengthened?.length > 0 && (
            <section data-testid="doc-evolution-added">
              <p className="text-[10.5px] uppercase tracking-[0.18em] text-emerald-700 font-mono mb-1.5 flex items-center gap-1">
                <Plus className="w-3 h-3" /> Added or strengthened
              </p>
              <ul className="space-y-1">
                {diff.added_or_strengthened.map((x, i) => (
                  <li key={i} className="text-[12.5px] text-[var(--deep)] leading-snug pl-3 border-l border-emerald-300">{x}</li>
                ))}
              </ul>
            </section>
          )}

          {diff.weakened_or_removed?.length > 0 && (
            <section data-testid="doc-evolution-weakened">
              <p className="text-[10.5px] uppercase tracking-[0.18em] text-amber-700 font-mono mb-1.5 flex items-center gap-1">
                <Minus className="w-3 h-3" /> Weakened or removed
              </p>
              <ul className="space-y-1">
                {diff.weakened_or_removed.map((x, i) => (
                  <li key={i} className="text-[12.5px] text-[var(--deep)] leading-snug pl-3 border-l border-amber-300">{x}</li>
                ))}
              </ul>
            </section>
          )}

          {diff.questions_for_management?.length > 0 && (
            <section className="bg-[var(--accent-soft)]/40 border border-[var(--accent)]/20 rounded-sm p-3" data-testid="doc-evolution-questions">
              <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] font-mono mb-1.5 flex items-center gap-1">
                <HelpCircle className="w-3 h-3" /> Put on the table
              </p>
              <ul className="space-y-1.5">
                {diff.questions_for_management.map((q, i) => (
                  <li key={i} className="text-[13px] italic akki-serif text-[var(--ink)] leading-snug">
                    "{q}"
                  </li>
                ))}
              </ul>
            </section>
          )}

          {loadingDiff && (
            <p className="text-[11px] text-[var(--muted)] italic flex items-center gap-1.5 pt-2 border-t border-[#E1E6ED]">
              <Loader2 className="w-3 h-3 animate-spin" /> Re-comparing…
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** Dialog for picking a predecessor doc — or unlinking the current one. */
function LinkVersionDialog({ contextId, doc, onChange }) {
  const [open, setOpen] = useState(false);
  const [docs, setDocs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const { data } = await api.get(`/contexts/${contextId}/documents`, { params: { limit: 200 } });
        setDocs((data || []).filter((d) => d.id !== doc.id));
      } catch (e) { toast.error(apiErrorMessage(e)); }
    })();
  }, [open, contextId, doc?.id]);

  const filtered = useMemo(() => {
    const f = filter.trim().toLowerCase();
    if (!f) return docs;
    return docs.filter((d) => (d.name || d.original_filename || "").toLowerCase().includes(f));
  }, [docs, filter]);

  const link = async (predId) => {
    setBusy(true);
    try {
      await api.patch(`/contexts/${contextId}/documents/${doc.id}`, { related_doc_id: predId });
      toast.success(predId ? "Linked." : "Unlinked.");
      setOpen(false);
      onChange?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          className="text-[10.5px] uppercase tracking-wider text-[var(--accent)] hover:opacity-80 inline-flex items-center gap-1"
          data-testid="doc-evolution-link-btn"
          title="Link this document as a successor of an earlier version"
        >
          <Link2 className="w-3 h-3" /> {doc?.related_doc_id ? "Change link" : "Link previous version"}
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-lg bg-[var(--cream)] border-[var(--rule)]">
        <DialogHeader>
          <DialogTitle className="akki-serif font-normal">Link this document to its predecessor</DialogTitle>
        </DialogHeader>
        <p className="text-[12.5px] text-[var(--muted)] leading-relaxed mb-3">
          Tracking the same report across cycles? Pick the earlier version below. AKKI will then surface what's drifted.
        </p>
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter…"
          className="w-full bg-white border border-[var(--rule)] rounded-sm px-3 py-2 text-[13px] mb-3 focus:outline-none focus:border-[var(--accent)]"
          data-testid="doc-evolution-link-filter"
        />
        <div className="max-h-[40vh] overflow-y-auto border border-[var(--rule)] rounded-sm bg-white">
          {filtered.length === 0 ? (
            <p className="text-[12px] text-[var(--muted)] italic p-4 text-center">
              {docs.length === 0 ? "No other documents in this company yet." : "No matches."}
            </p>
          ) : filtered.map((d) => (
            <button
              key={d.id}
              disabled={busy}
              onClick={() => link(d.id)}
              className={`w-full text-left px-3 py-2 hover:bg-[var(--cream-deep)]/50 border-b border-[var(--rule)] last:border-b-0 ${
                doc?.related_doc_id === d.id ? "bg-[var(--accent-soft)]/40" : ""
              }`}
              data-testid={`doc-evolution-link-opt-${d.id}`}
            >
              <p className="text-[13px] text-[var(--ink)] truncate">{d.name || d.original_filename}</p>
              <p className="text-[11px] text-[var(--muted)] tabular-nums">{fmtDate(d.created_at)}</p>
            </button>
          ))}
        </div>
        {doc?.related_doc_id && (
          <Button
            variant="outline"
            onClick={() => link(null)}
            disabled={busy}
            className="mt-3 border-[var(--rule)] hover:border-red-400 hover:text-red-700"
            data-testid="doc-evolution-unlink-btn"
          >
            <Unlink className="w-3.5 h-3.5 mr-1.5" /> Unlink predecessor
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}
