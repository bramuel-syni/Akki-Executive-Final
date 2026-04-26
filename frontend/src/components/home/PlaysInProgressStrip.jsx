import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

/**
 * Home stream — "In progress" chips for any active or paused Plays in the
 * active context. Restrained, single-line, oxblood-underlined Play name.
 *
 * Renders nothing if there are no active Plays — Plays are invitational,
 * not insistent.
 */
export default function PlaysInProgressStrip() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [plays, setPlays] = useState([]);

  const load = useCallback(async () => {
    if (!cid) return;
    try {
      const { data } = await api.get(`/contexts/${cid}/plays`);
      setPlays((data.plays || []).filter((p) => ["active", "paused"].includes(p.status)));
    } catch { setPlays([]); }
  }, [cid]);
  useEffect(() => { load(); }, [load]);

  if (plays.length === 0) return null;

  return (
    <div className="mb-5 space-y-1.5 shrink-0" data-testid="home-plays-strip">
      {plays.map((p) => {
        const stage = p.stages?.[p.current_stage];
        return (
          <Link
            key={p.id}
            to={`/app/plays/${p.id}`}
            className="block bg-[var(--cream-deep)]/60 border border-[var(--rule)] rounded-md px-4 py-2.5 hover:border-[var(--accent)]/40 transition-colors group"
            data-testid={`home-play-chip-${p.id}`}
          >
            <p className="text-[13.5px] flex items-center gap-3 flex-wrap">
              <span className="akki-serif text-[var(--ink)] decoration-[var(--accent)] decoration-2 underline-offset-4 underline">
                {p.name}
              </span>
              <span className="text-[var(--muted)]">·</span>
              <span className="text-[var(--deep)] italic">{stage?.name}</span>
              {p.status === "paused" && (
                <span className="text-[10.5px] uppercase tracking-wider text-amber-700 font-mono">paused</span>
              )}
              <span className="ml-auto text-[var(--accent)] group-hover:underline">Open →</span>
            </p>
          </Link>
        );
      })}
    </div>
  );
}
