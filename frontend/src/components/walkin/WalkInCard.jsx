/**
 * WalkInCard — calm, repeated touch across briefs / minutes / decks.
 *
 * Iter58 improvement: a single sharp question AKKI thinks the user should
 * walk into their next conversation with. Cheap (Sonnet, no deep budget),
 * cached on the artefact. First visit kicks off generation; subsequent
 * visits read the cache.
 *
 * Usage:
 *   <WalkInCard kind="brief"   contextId={cid} artefactId={brief.id} />
 *   <WalkInCard kind="minutes" contextId={cid} artefactId={doc.id}   />
 *   <WalkInCard kind="deck"    contextId={cid} artefactId={deck.id}  />
 */
import React, { useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { ArrowRight, Loader2, RefreshCw, MessageCircle } from "lucide-react";

export default function WalkInCard({ kind, contextId, artefactId, initial }) {
  const [data, setData] = useState(initial || null);
  const [loading, setLoading] = useState(!initial && !!artefactId);
  const [err, setErr] = useState(null);
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    if (initial || !artefactId || !contextId) return;
    let live = true;
    setLoading(true);
    setErr(null);
    api
      .post("/walkin", { kind, artefact_id: artefactId, context_id: contextId })
      .then((r) => { if (live) setData(r.data?.walkin_question || null); })
      .catch((e) => { if (live) setErr(apiErrorMessage(e)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [kind, artefactId, contextId, initial]);

  const regenerate = async () => {
    if (!artefactId || regenerating) return;
    setRegenerating(true);
    try {
      const r = await api.post("/walkin/regenerate", {
        kind, artefact_id: artefactId, context_id: contextId,
      });
      setData(r.data?.walkin_question || null);
    } catch (e) {
      setErr(apiErrorMessage(e));
    } finally {
      setRegenerating(false);
    }
  };

  const continueInChat = () => {
    if (!data?.body) return;
    const url = `/app/chat?prompt=${encodeURIComponent(data.body)}&new=1&seed_title=${encodeURIComponent(data.body.slice(0, 60))}`;
    window.location.href = url;
  };

  if (!artefactId) return null;

  if (loading) {
    return (
      <div
        className="bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-sm px-5 py-4 flex items-center gap-3 text-[12.5px] italic text-[var(--muted)]"
        data-testid={`walkin-card-${kind}-loading`}
      >
        <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--accent)]" />
        AKKI is sharpening one question for you…
      </div>
    );
  }

  if (err && !data) {
    return null;
  }

  if (!data) return null;

  return (
    <div
      className="bg-[var(--cream-deep)]/30 border border-[var(--accent)]/20 rounded-sm px-5 py-4"
      data-testid={`walkin-card-${kind}`}
    >
      <div className="flex items-start justify-between gap-4 mb-2.5">
        <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] flex items-center gap-1.5">
          <MessageCircle className="w-3 h-3" strokeWidth={1.7} />
          Walk in with this question
        </p>
        <button
          type="button"
          onClick={regenerate}
          disabled={regenerating}
          className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] hover:text-[var(--accent)] flex items-center gap-1 disabled:opacity-50"
          data-testid={`walkin-card-${kind}-regenerate`}
          title="Get a different question (free — uses standard tier)"
        >
          {regenerating ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <RefreshCw className="w-3 h-3" />
          )}
          New
        </button>
      </div>
      <p
        className="akki-serif text-[16px] text-[var(--ink)] leading-snug"
        data-testid={`walkin-card-${kind}-body`}
      >
        "{data.body}"
      </p>
      {data.why && (
        <p className="text-[12px] text-[var(--muted)] italic mt-2 leading-relaxed">
          {data.why}
        </p>
      )}
      <div className="mt-4 flex justify-end">
        <button
          type="button"
          onClick={continueInChat}
          className="text-[11.5px] uppercase tracking-[0.14em] text-[var(--accent)] hover:underline flex items-center gap-1.5"
          data-testid={`walkin-card-${kind}-continue`}
        >
          Continue in Chat <ArrowRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}
