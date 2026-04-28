/**
 * DocumentPlayContext — third panel on the Document Journal right rail.
 *
 * Apr-2026 backlog item: surface the workflow context for the document
 * being read. Today the link is light-touch — we list the user's active
 * plays in the context and offer one click to jump into them. When
 * play↔document linkage ships, this panel can highlight which plays
 * actually consumed this doc.
 */
import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Compass, ArrowRight } from "lucide-react";

const STAGE_LABELS = {
  board_pack: ["Inbox", "Compose", "Review", "Send up"],
  pre_board: ["Read", "Brief", "Question"],
};

export default function DocumentPlayContext({ contextId }) {
  const [plays, setPlays] = useState([]);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    if (!contextId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/plays`);
      const active = (data?.plays || []).filter((p) => p.status === "active");
      setPlays(active);
    } catch { setPlays([]); }
    finally { setLoaded(true); }
  }, [contextId]);
  useEffect(() => { load(); }, [load]);

  if (!loaded) return null;

  return (
    <section
      className="bg-white border border-[var(--rule)] rounded-md"
      data-testid="doc-play-context"
    >
      <div className="px-4 py-3 border-b border-[var(--rule)] flex items-center gap-2">
        <Compass className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.7} />
        <p className="akki-overline">Workflow context</p>
        <span className="ml-auto text-[11px] text-[var(--muted)] tabular-nums">
          {plays.length === 0 ? "—" : `${plays.length} active`}
        </span>
      </div>
      <div className="px-4 py-3">
        {plays.length === 0 ? (
          <p className="text-[12px] text-[var(--muted)] italic leading-snug">
            No workflows are running in this company. Start one from the Workflows hub on Home and this document can plug in.
          </p>
        ) : (
          <ul className="space-y-2">
            {plays.slice(0, 4).map((p) => {
              const stages = STAGE_LABELS[p.play_type] || [];
              const stageLabel = stages[p.current_stage] || `Stage ${p.current_stage + 1}`;
              return (
                <li key={p.id}>
                  <Link
                    to={`/app/plays/${p.id}`}
                    className="flex items-start gap-2 hover:bg-[var(--cream-deep)]/30 rounded-sm px-2 py-1.5 -mx-2 group transition-colors"
                    data-testid={`doc-play-link-${p.id}`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="akki-serif text-[13px] text-[var(--ink)] leading-tight truncate group-hover:text-[var(--accent)]">
                        {p.title || (p.play_type === "board_pack" ? "Board pack" : "Pre-board read")}
                      </p>
                      <p className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] mt-0.5">
                        {stageLabel} · {p.play_type.replace("_", " ")}
                      </p>
                    </div>
                    <ArrowRight className="w-3 h-3 text-[var(--muted)] group-hover:text-[var(--accent)] mt-1 shrink-0" />
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
