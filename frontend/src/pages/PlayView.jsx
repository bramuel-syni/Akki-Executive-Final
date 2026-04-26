import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AppShell from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { ChevronRight, Pause, X, Play as PlayIcon, Loader2 } from "lucide-react";

import { boardPackStageView } from "@/components/plays/BoardPackStages";
import { preBoardStageView } from "@/components/plays/PreBoardStages";

/**
 * PlayShell — the choreography primitive.
 *
 * Two regions sit under universal chrome (AppShell): a 64px Play header
 * strip with the Play name, current stage name, and a "Stages" affordance,
 * and a 60/40 split below it that the active stage's components own.
 *
 * Cadence:
 *   - No progress bar, no percentage, no checklist.
 *   - Stage transitions = name fade with a short editorial phrase.
 *   - "Stages" panel lets the executive see where she is and jump back.
 *     Forward jumps require a confirm — trust-first, but the journey
 *     should feel deliberate.
 */
const STAGE_RENDERERS = {
  board_pack: boardPackStageView,
  pre_board: preBoardStageView,
};

function StagesPanel({ open, onClose, play, onJump }) {
  if (!open || !play) return null;
  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      onClick={onClose}
      data-testid="stages-panel-overlay"
    >
      <aside
        className="w-[320px] bg-[var(--cream)] border-l border-[var(--rule)] h-full overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        data-testid="stages-panel"
      >
        <header className="px-5 py-4 border-b border-[var(--rule)]">
          <p className="akki-overline mb-1">{play.name}</p>
          <p className="text-[12px] text-[var(--muted)] italic">{play.outcome}</p>
        </header>
        <ol className="py-2">
          {play.stages.map((s) => {
            const isCurrent = s.idx === play.current_stage;
            const isPast = s.idx < play.current_stage || play.status === "completed";
            const tone = isCurrent ? "text-[var(--ink)]"
              : isPast ? "text-[var(--deep)]"
              : "text-[var(--muted)]";
            return (
              <li key={s.key}>
                <button
                  onClick={() => onJump(s.idx)}
                  className={`w-full text-left px-5 py-3 hover:bg-[var(--cream-deep)]/40 transition-colors ${tone}`}
                  data-testid={`stages-row-${s.key}`}
                >
                  <div className="flex items-center gap-2">
                    {isCurrent && <span className="w-1 h-4 bg-[var(--accent)] rounded-sm" />}
                    <span className={`akki-serif text-[15px] ${isCurrent ? "" : ""}`}>{s.name}</span>
                  </div>
                  <p className="text-[11.5px] text-[var(--muted)] italic ml-3 mt-0.5 leading-snug">
                    {s.transition}
                  </p>
                </button>
              </li>
            );
          })}
        </ol>
        <footer className="px-5 py-4 border-t border-[var(--rule)] flex flex-col gap-2">
          <button onClick={onClose} className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] text-left">
            Close panel
          </button>
        </footer>
      </aside>
    </div>
  );
}

function PlayHeader({ play, transitioning, onOpenStages, onPause, onResume, onExit }) {
  const stage = play.stages?.[play.current_stage];
  return (
    <div
      className="h-16 bg-[var(--cream-deep)]/60 border-b border-[var(--rule)] flex items-center px-8 gap-6"
      data-testid="play-header"
    >
      <div className="flex-1 min-w-0">
        <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-0.5">
          {play.name}
        </p>
        <div className="relative h-6">
          <p
            key={play.current_stage}
            className={`akki-serif text-[18px] text-[var(--ink)] absolute inset-0 transition-opacity duration-300 ${transitioning ? "opacity-0" : "opacity-100"}`}
            data-testid="play-current-stage"
          >
            {stage?.name}
          </p>
        </div>
      </div>
      <button
        onClick={onOpenStages}
        className="text-[12px] text-[var(--deep)] hover:text-[var(--accent)] underline-offset-4 hover:underline"
        data-testid="play-open-stages"
      >
        Stages
      </button>
      {play.status === "active" ? (
        <button onClick={onPause} className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1" data-testid="play-pause">
          <Pause className="w-3 h-3" /> Pause
        </button>
      ) : play.status === "paused" ? (
        <button onClick={onResume} className="text-[12px] text-[var(--accent)] hover:underline inline-flex items-center gap-1" data-testid="play-resume">
          <PlayIcon className="w-3 h-3" /> Resume
        </button>
      ) : null}
      <button onClick={onExit} className="text-[12px] text-[var(--muted)] hover:text-red-700 inline-flex items-center gap-1" data-testid="play-exit">
        <X className="w-3 h-3" /> Exit
      </button>
    </div>
  );
}

export default function PlayView() {
  const { playId } = useParams();
  const navigate = useNavigate();
  const { activeContext, contexts } = useAuth();
  const [play, setPlay] = useState(null);
  const [contextId, setContextId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stagesOpen, setStagesOpen] = useState(false);
  const [transitioning, setTransitioning] = useState(false);

  // Resolve the right context for THIS play. The play knows its own context
  // server-side, but we don't have a global lookup endpoint. We try the
  // active context first, then walk the user's other contexts. Cheap because
  // most users have ≤ 6 contexts and most of the time the active one is right.
  const load = useCallback(async () => {
    setLoading(true);
    const candidates = [];
    if (activeContext?.id) candidates.push(activeContext.id);
    for (const c of contexts || []) if (c.id && !candidates.includes(c.id)) candidates.push(c.id);
    for (const ctxId of candidates) {
      try {
        const { data } = await api.get(`/contexts/${ctxId}/plays/${playId}`);
        setPlay(data.play);
        setContextId(ctxId);
        setLoading(false);
        // Auto-launched plays light up the Home PLAY READY card; mark
        // them seen as soon as the executive opens the Play view so the
        // card doesn't keep shouting.
        if (data.play.auto_launched && !data.play.auto_launch_seen) {
          api.post(`/contexts/${ctxId}/plays/${playId}/seen`).catch(() => {});
        }
        return;
      } catch { /* try next ctx */ }
    }
    setLoading(false);
    toast.error("Play not found in any of your contexts.");
  }, [playId, activeContext, contexts]);
  useEffect(() => { load(); }, [load]);

  const advance = useCallback(async () => {
    if (!play || !contextId) return;
    setTransitioning(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/plays/${play.id}/advance`);
      setTimeout(() => {
        setPlay(data.play);
        setTimeout(() => setTransitioning(false), 50);
      }, 600);
    } catch (e) {
      setTransitioning(false);
      toast.error(apiErrorMessage(e));
    }
  }, [play, contextId]);

  const jump = useCallback(async (stageIdx) => {
    if (!play || !contextId) return;
    setStagesOpen(false);
    const goingForward = stageIdx > play.current_stage;
    if (goingForward && !confirm("Jump ahead before completing the current stage?")) return;
    try {
      const { data } = await api.post(`/contexts/${contextId}/plays/${play.id}/jump`,
        { stage_idx: stageIdx, confirm: goingForward });
      setPlay(data.play);
    } catch (e) { toast.error(apiErrorMessage(e)); }
  }, [play, contextId]);

  const onPause = async () => {
    if (!play || !contextId) return;
    setPlay((prev) => prev ? { ...prev, status: "paused" } : prev); // optimistic
    try {
      const { data } = await api.post(`/contexts/${contextId}/plays/${play.id}/pause`);
      setPlay(data.play);
      toast.message("Paused. Pick up where you left off.");
    } catch (e) {
      // rollback
      setPlay((prev) => prev ? { ...prev, status: "active" } : prev);
      toast.error(apiErrorMessage(e));
    }
  };
  const onResume = async () => {
    if (!play || !contextId) return;
    setPlay((prev) => prev ? { ...prev, status: "active" } : prev); // optimistic
    try {
      const { data } = await api.post(`/contexts/${contextId}/plays/${play.id}/resume`);
      setPlay(data.play);
    } catch (e) {
      setPlay((prev) => prev ? { ...prev, status: "paused" } : prev);
      toast.error(apiErrorMessage(e));
    }
  };
  const onExit = async () => {
    if (!play || !contextId) return;
    if (!confirm("Exit this Play? You can start it again later.")) return;
    try {
      await api.post(`/contexts/${contextId}/plays/${play.id}/exit`);
      navigate("/app");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const patchState = useCallback(async (patch) => {
    if (!play || !contextId) return;
    const { data } = await api.patch(`/contexts/${contextId}/plays/${play.id}/state`, { state: patch });
    setPlay(data.play);
  }, [play, contextId]);

  const StageView = useMemo(() => {
    if (!play) return null;
    const renderer = STAGE_RENDERERS[play.play_type];
    return renderer ? renderer(play) : null;
  }, [play]);

  if (loading) return <AppShell><div className="p-12 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</div></AppShell>;
  if (!play) return <AppShell><div className="p-12 text-center text-[var(--muted)]">Play not found.</div></AppShell>;

  const StageComponent = StageView?.[play.current_stage];
  return (
    <AppShell>
      <PlayHeader
        play={play}
        transitioning={transitioning}
        onOpenStages={() => setStagesOpen(true)}
        onPause={onPause}
        onResume={onResume}
        onExit={onExit}
      />
      <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-0 min-h-[calc(100vh-12rem)]" data-testid="play-body">
        {StageComponent ? (
          <StageComponent
            play={play}
            contextId={contextId}
            onAdvance={advance}
            onPatchState={patchState}
            transitioning={transitioning}
          />
        ) : (
          <div className="p-12 text-[var(--muted)]">No renderer for {play.play_type}.</div>
        )}
      </div>
      <StagesPanel
        open={stagesOpen}
        onClose={() => setStagesOpen(false)}
        play={play}
        onJump={jump}
      />
    </AppShell>
  );
}
