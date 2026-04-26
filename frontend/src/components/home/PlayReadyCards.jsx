import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Sparkles } from "lucide-react";

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

  if (plays.length === 0) {
    // Render an unobtrusive empty-state card so the 2-up layout next to
    // AgendaEvolutionCard doesn't collapse. Reads as restraint, not absence.
    return (
      <article className="bg-white border border-dashed border-[var(--rule)] rounded-md p-4" data-testid="home-play-ready-empty">
        <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono mb-1.5 flex items-center gap-1.5">
          <Sparkles className="w-3 h-3" /> Ready for you
        </p>
        <p className="text-[13px] text-[var(--muted)] italic leading-relaxed">
          Nothing waiting. When a cycle dispatches or a workflow needs your attention, it'll surface here.
        </p>
      </article>
    );
  }

  return (
    <div className="space-y-2 shrink-0" data-testid="home-play-ready">
      {plays.map((p) => {
        const stage = p.stages?.[p.current_stage];
        const cycleName = p.state?.cycle_name;
        return (
          <article
            key={p.id}
            className="bg-[var(--cream-deep)] border border-[var(--accent)]/40 rounded-md p-4 shadow-[0_2px_24px_-12px_rgba(124,38,38,0.25)]"
            data-testid={`home-play-ready-${p.id}`}
          >
            <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-1.5 flex items-center gap-2">
              Ready for you
              <span className="text-[var(--muted)]/60">·</span>
              <span className="text-[var(--ink)]">{p.name}</span>
            </p>
            <h3 className="akki-serif text-[17px] text-[var(--ink)] leading-snug mb-1">
              {cycleName ? `${cycleName} just dispatched.` : "A new cycle just dispatched."}
            </h3>
            <p className="akki-serif text-[13px] text-[var(--deep)] italic leading-relaxed mb-3">
              {stage?.transition || "Time to look at what's there."}
            </p>
            <div className="flex items-center gap-2">
              <Link
                to={`/app/plays/${p.id}`}
                className="inline-flex items-center gap-1 px-2.5 py-1 bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[12px] rounded-md"
                data-testid={`home-play-ready-open-${p.id}`}
              >
                Open the workflow →
              </Link>
              <button
                onClick={() => dismiss(p.id)}
                className="text-[11.5px] text-[var(--muted)] hover:text-[var(--ink)]"
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
