/**
 * BoardpackTab — Cycle Manager → Boardpack (Phase M.3).
 *
 * Replaced the legacy "Briefs" subtab. Lists every boardpack for the
 * active context (a boardpack = the aggregated set of documents
 * submitted in one board cycle, with an Akki-generated commentary on
 * the whole pack). Click a row to expand the commentary inline. Click
 * a doc within the pack to open the Reading Viewer in a modal.
 *
 * Endpoints:
 *   GET  /api/contexts/{cid}/boardpacks
 *   GET  /api/contexts/{cid}/boardpacks/{bpid}
 *   POST /api/contexts/{cid}/boardpacks/{bpid}/regenerate-commentary
 *
 * The in-flight Brief artefact creation flow (legacy `briefs`
 * collection, surfaced previously via `<Prepare forceTab="brief" />`)
 * is no longer rendered here. Its endpoints remain live and the
 * data is intact — Phase N decides where to re-home it. M.3 commits
 * the Boardpack as the canonical Cycle Manager surface.
 */
import React, { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, FileText, RefreshCw, Sparkles } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export default function BoardpackTab() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [regenBusy, setRegenBusy] = useState(null);

  useEffect(() => {
    if (!cid) return;
    let dead = false;
    setLoading(true);
    setError(null);
    api.get(`/contexts/${cid}/boardpacks`)
      .then(({ data }) => { if (!dead) setItems(data.items || []); })
      .catch((e) => { if (!dead) setError(e?.response?.data?.detail || e.message); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [cid]);

  const grouped = useMemo(() => {
    const out = new Map();
    for (const bp of items) {
      const key = bp.cycle_label || "Uncycled";
      if (!out.has(key)) out.set(key, []);
      out.get(key).push(bp);
    }
    return Array.from(out.entries());
  }, [items]);

  const handleRegenerate = async (bp) => {
    setRegenBusy(bp.id);
    try {
      const { data } = await api.post(
        `/contexts/${cid}/boardpacks/${bp.id}/regenerate-commentary`,
      );
      setItems((prev) => prev.map((x) => x.id === bp.id ? data : x));
    } catch (e) {
      alert(e?.response?.data?.detail || "Regenerate failed.");
    } finally {
      setRegenBusy(null);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-[14px] text-[var(--muted)] font-[Calibri]">
        Loading boardpacks…
      </div>
    );
  }
  if (error) {
    return (
      <div className="p-6 text-[14px] text-red-600 font-[Calibri]" role="alert">
        {error}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="px-8 py-16 text-center text-[14px] text-[var(--muted)] font-[Calibri]">
        <Sparkles className="mx-auto mb-3 w-5 h-5 text-[var(--accent)]" />
        No boardpacks yet. As your cycle progresses, board materials
        you receive accumulate into packs here.
      </div>
    );
  }

  return (
    <div className="max-w-[1100px] mx-auto px-8 py-8" data-testid="boardpack-tab">
      <p className="akki-overline mb-2">Boardpack</p>
      <h2 className="akki-greeting mb-3">Materials, by cycle.</h2>
      <p className="akki-meta max-w-2xl mb-6">
        Every pack the board has received, grouped by reporting cycle.
        Click a pack for Akki's commentary on what changed and what
        warrants discussion. Click any document inside the pack to read it.
      </p>

      <div className="space-y-8">
        {grouped.map(([label, packs]) => (
          <section key={label}>
            <h3 className="akki-overline mb-3 text-[var(--deep)]">{label}</h3>
            <ul className="border border-[var(--rule)] rounded-md overflow-hidden bg-white">
              {packs.map((bp) => {
                const open = expandedId === bp.id;
                const docCount = (bp.document_ids || []).length;
                const hasCommentary = !!(bp.commentary && bp.commentary.trim().length);
                return (
                  <li key={bp.id} className="border-b border-[var(--rule)] last:border-b-0">
                    <button
                      type="button"
                      onClick={() => setExpandedId(open ? null : bp.id)}
                      data-testid={`boardpack-row-${bp.id}`}
                      className="w-full px-5 py-3 flex items-center gap-3 text-left hover:bg-[var(--cream-deep)]/30 transition-colors"
                      aria-expanded={open}
                      aria-controls={`boardpack-body-${bp.id}`}
                    >
                      {open ? (
                        <ChevronDown className="w-4 h-4 text-[var(--muted)] shrink-0" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-[var(--muted)] shrink-0" />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="text-[14px] text-[var(--ink)] font-medium leading-tight truncate">
                          {bp.title || "Untitled boardpack"}
                        </div>
                        <div className="text-[12px] text-[var(--muted)] mt-0.5 flex items-center gap-2 flex-wrap">
                          <FileText className="w-3 h-3" />
                          <span>{docCount} {docCount === 1 ? "document" : "documents"}</span>
                          {!hasCommentary && (
                            <span className="text-[var(--accent)]">· commentary not yet generated</span>
                          )}
                        </div>
                      </div>
                    </button>
                    {open && (
                      <div
                        id={`boardpack-body-${bp.id}`}
                        className="px-12 pb-5 pt-1 bg-[var(--cream)]/40"
                      >
                        <div className="flex justify-end mb-3">
                          <button
                            type="button"
                            onClick={() => handleRegenerate(bp)}
                            disabled={regenBusy === bp.id}
                            data-testid={`boardpack-regenerate-${bp.id}`}
                            className="text-[12px] text-[var(--accent)] inline-flex items-center gap-1 hover:underline disabled:opacity-50"
                          >
                            <RefreshCw className={`w-3 h-3 ${regenBusy === bp.id ? "animate-spin" : ""}`} />
                            {regenBusy === bp.id ? "Regenerating commentary…" : "Regenerate commentary"}
                          </button>
                        </div>

                        <div className="prose prose-sm max-w-none text-[var(--ink)] font-[Georgia] leading-relaxed text-[14.5px] whitespace-pre-wrap">
                          {bp.commentary || (
                            <span className="italic text-[var(--muted)]">
                              Click "Regenerate commentary" to ask Akki for a 600–1000 word read on this pack.
                            </span>
                          )}
                        </div>

                        {(bp.document_ids || []).length > 0 && (
                          <div className="mt-6 border-t border-[var(--rule)] pt-4">
                            <p className="akki-overline mb-2 text-[var(--muted)]">Documents in this pack</p>
                            <ul className="space-y-1">
                              {(bp.document_ids || []).map((did) => (
                                <li key={did}>
                                  <a
                                    href={`/app/documents/${did}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[13px] text-[var(--accent)] hover:underline inline-flex items-center gap-1.5"
                                  >
                                    <FileText className="w-3 h-3" />
                                    {did.slice(0, 8)}…
                                  </a>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
