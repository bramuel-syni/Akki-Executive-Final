import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AppShell from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ArrowRight, Lock, Sparkles } from "lucide-react";

/**
 * Plays library — the formal "what's available, what's in progress" page.
 * Lives at /app/plays. Slice 1 only ships the Board Pack Play as
 * available; the rest are visible but locked, so the executive can see
 * the shape of the journey roadmap without being pushed.
 */
export default function PlaysLibrary() {
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [plays, setPlays] = useState([]);
  const [active, setActive] = useState([]);
  const [starting, setStarting] = useState(null);

  const load = useCallback(async () => {
    try {
      const lib = await api.get("/plays/library");
      setPlays(lib.data.plays || []);
      if (cid) {
        const mine = await api.get(`/contexts/${cid}/plays`);
        setActive((mine.data.plays || []).filter((p) => ["active", "paused"].includes(p.status)));
      }
    } catch (e) { toast.error(apiErrorMessage(e)); }
  }, [cid]);
  useEffect(() => { load(); }, [load]);

  const start = async (playType) => {
    if (!cid) { toast.error("No active context."); return; }
    setStarting(playType);
    try {
      const { data } = await api.post(`/contexts/${cid}/plays`, { play_type: playType });
      navigate(`/app/plays/${data.play.id}`);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setStarting(null); }
  };

  const exec = plays.filter((p) => p.audience === "executive");
  const ned = plays.filter((p) => p.audience === "ned");

  return (
    <AppShell>
      <div className="max-w-[1200px] mx-auto px-8 py-10">
        <header className="mb-10 akki-fade-up">
          <p className="akki-overline mb-2 text-[var(--accent)]">Workflows · Choreography for board work</p>
          <h1 className="akki-greeting mb-2">Named journeys, not feature tours.</h1>
          <p className="akki-meta max-w-2xl">
            A Workflow is a staged path through AKKI to a recognisable outcome —
            a board pack you've committed to, a meeting you've prepared for,
            a month you've actually closed. Pick one. AKKI handles the in-between.
          </p>
        </header>

        {active.length > 0 && (
          <section className="mb-12" data-testid="plays-in-progress">
            <p className="akki-overline mb-3">In progress</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {active.map((p) => {
                const stage = p.stages?.[p.current_stage];
                return (
                  <button
                    key={p.id}
                    onClick={() => navigate(`/app/plays/${p.id}`)}
                    className="text-left bg-white border border-[var(--accent)]/30 rounded-lg p-5 hover:border-[var(--accent)] transition-colors"
                    data-testid={`plays-resume-${p.id}`}
                  >
                    <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-1">{p.name}</p>
                    <p className="akki-serif text-[18px] text-[var(--ink)] leading-snug mb-1">{stage?.name}</p>
                    <p className="text-[12.5px] text-[var(--muted)] italic">{stage?.transition}</p>
                  </button>
                );
              })}
            </div>
          </section>
        )}

        {[
          ["For executives", exec],
          ["For non-executives", ned],
        ].map(([title, list]) => (
          <section key={title} className="mb-10">
            <p className="akki-overline mb-4">{title}</p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {list.map((p) => (
                <article
                  key={p.type}
                  className={`bg-white border ${p.available ? "border-[var(--rule)] hover:border-[var(--accent)]/40" : "border-dashed border-[var(--rule)]"} rounded-lg p-5 transition-colors flex flex-col`}
                  data-testid={`plays-card-${p.type}`}
                >
                  <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-2">{p.audience === "executive" ? "EXEC" : "NED"}</p>
                  <h3 className="akki-serif text-[18px] text-[var(--ink)] mb-2">{p.name}</h3>
                  <p className="text-[13px] text-[var(--deep)] italic mb-4 flex-1">{p.outcome}</p>
                  {p.available ? (
                    <Button
                      onClick={() => start(p.type)}
                      disabled={starting === p.type}
                      className="bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white self-start"
                      data-testid={`plays-start-${p.type}`}
                    >
                      {starting === p.type
                        ? <>Starting…</>
                        : <><Sparkles className="w-3.5 h-3.5 mr-1.5" /> Start →</>}
                    </Button>
                  ) : (
                    <p className="text-[11.5px] text-[var(--muted)] inline-flex items-center gap-1.5 italic">
                      <Lock className="w-3 h-3" /> Coming next
                    </p>
                  )}
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </AppShell>
  );
}
