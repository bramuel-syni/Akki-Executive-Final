import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

/**
 * Home stream — "PLAY READY" trigger cards for any auto-launched plays
 * the executive hasn't opened yet. Sits ABOVE the in-progress strip.
 *
 * The card isn't a notification with a checkmark; it's an editorial
 * observation: "your cycle just dispatched, time to look at what's there."
 *
 * Renders nothing if no auto-launched + unseen plays exist — restraint
 * over insistence.
 */
export default function PlayReadyCards() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [plays, setPlays] = useState([]);

  const load = useCallback(async () => {
    if (!cid) return;
    try {
      const { data } = await api.get(`/contexts/${cid}/plays`);
      setPlays((data.plays || []).filter(
        (p) => p.auto_launched && !p.auto_launch_seen
            && ["active", "paused"].includes(p.status),
      ));
    } catch { setPlays([]); }
  }, [cid]);
  useEffect(() => { load(); }, [load]);

  const dismiss = async (playId) => {
    if (!cid) return;
    try {
      await api.post(`/contexts/${cid}/plays/${playId}/seen`);
      setPlays((prev) => prev.filter((p) => p.id !== playId));
    } catch { /* swallow — UI removes optimistically */ }
  };

  if (plays.length === 0) return null;

  return (
    <div className="mb-5 space-y-2 shrink-0" data-testid="home-play-ready">
      {plays.map((p) => {
        const stage = p.stages?.[p.current_stage];
        const cycleName = p.state?.cycle_name;
        return (
          <article
            key={p.id}
            className="bg-[var(--cream-deep)] border border-[var(--accent)]/40 rounded-md p-5 shadow-[0_2px_24px_-12px_rgba(124,38,38,0.25)]"
            data-testid={`home-play-ready-${p.id}`}
          >
            <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-2 flex items-center gap-2">
              Play ready
              <span className="text-[var(--muted)]/60">·</span>
              <span className="text-[var(--ink)]">{p.name}</span>
            </p>
            <h3 className="akki-serif text-[20px] text-[var(--ink)] leading-snug mb-1">
              {cycleName ? `${cycleName} just dispatched.` : "A new cycle just dispatched."}
            </h3>
            <p className="akki-serif text-[14.5px] text-[var(--deep)] italic leading-relaxed mb-4 max-w-2xl">
              {stage?.transition || "Time to look at what's there."}
            </p>
            <div className="flex items-center gap-3">
              <Link
                to={`/app/plays/${p.id}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[13px] rounded-md"
                data-testid={`home-play-ready-open-${p.id}`}
              >
                Open the Play →
              </Link>
              <button
                onClick={() => dismiss(p.id)}
                className="text-[12.5px] text-[var(--muted)] hover:text-[var(--ink)]"
                data-testid={`home-play-ready-dismiss-${p.id}`}
              >
                Not now
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}
