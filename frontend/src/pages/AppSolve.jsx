/**
 * AppSolve — `/app/solve`. Real AKKI Solve module (iter61 Wave 1).
 *
 * Replaces the iter58 placeholder. Renders three views:
 *
 *   1. Picker     — list of clusters + resume your last session
 *   2. Intent     — capture the user's framing, start a session
 *   3. Session    — 4-phase walk (Surface → Depth → Synthesis → Lock-in)
 *
 * Backend at /api/solve/{clusters,sessions,sessions/:id/{turn,restart,abandon}}.
 */
import React, { useEffect, useRef, useState } from "react";
import AppShell from "@/components/layout/AppShell";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  ArrowRight, ArrowLeft, Sparkles, Loader2, Layers,
  RotateCw, Check, Pause,
} from "lucide-react";

const PHASE_ORDER = ["surface", "depth", "synthesis", "lockin"];
const PHASE_LABEL = {
  surface:   "Surface",
  depth:     "Depth",
  synthesis: "Synthesis",
  lockin:    "Lock-in",
};

export default function AppSolve() {
  const [view, setView] = useState("picker");      // picker | intent | session
  const [clusters, setClusters] = useState([]);
  const [activeCluster, setActiveCluster] = useState(null);
  const [intent, setIntent] = useState("");
  const [proTier, setProTier] = useState(false);
  const [session, setSession] = useState(null);
  const [recent, setRecent] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    setLoading(true);
    Promise.all([
      api.get("/solve/clusters").catch(() => ({ data: { clusters: [] } })),
      api.get("/solve/sessions").catch(() => ({ data: { items: [] } })),
    ])
      .then(([c, s]) => {
        if (!live) return;
        setClusters(c.data?.clusters || []);
        setRecent(s.data?.items || []);
      })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, []);

  const pickCluster = (c) => {
    setActiveCluster(c);
    setIntent(c.example_question ? "" : "");
    setView("intent");
  };

  const resume = async (sid) => {
    setBusy(true);
    try {
      const { data } = await api.get(`/solve/sessions/${sid}`);
      setSession(data);
      setActiveCluster(clusters.find((c) => c.id === data.cluster_id) || null);
      setView("session");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const restart = async (sid) => {
    if (!window.confirm("Start over with the same cluster + intent? Your old session is preserved as 'abandoned'.")) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/solve/sessions/${sid}/restart`);
      setSession(data);
      setView("session");
      const list = await api.get("/solve/sessions").catch(() => ({ data: { items: [] } }));
      setRecent(list.data?.items || []);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const startSession = async () => {
    if (!activeCluster || intent.trim().length < 20) return;
    setBusy(true);
    try {
      const { data } = await api.post("/solve/sessions", {
        cluster_id: activeCluster.id,
        intent: intent.trim(),
        pro_tier: proTier,
      });
      setSession(data);
      setView("session");
      const list = await api.get("/solve/sessions").catch(() => ({ data: { items: [] } }));
      setRecent(list.data?.items || []);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const onSessionUpdate = (updated) => {
    setSession(updated);
  };
  const exitToPicker = () => {
    setSession(null);
    setActiveCluster(null);
    setIntent("");
    setView("picker");
    api.get("/solve/sessions").then((r) => setRecent(r.data?.items || [])).catch(() => {});
  };

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto px-6 py-10" data-testid="app-solve">
        {view === "picker" && (
          <PickerView
            clusters={clusters}
            recent={recent}
            loading={loading}
            onPick={pickCluster}
            onResume={resume}
            onRestart={restart}
          />
        )}
        {view === "intent" && activeCluster && (
          <IntentView
            cluster={activeCluster}
            intent={intent}
            onIntentChange={setIntent}
            proTier={proTier}
            onProTierChange={setProTier}
            onBack={() => { setActiveCluster(null); setView("picker"); }}
            onStart={startSession}
            busy={busy}
          />
        )}
        {view === "session" && session && (
          <SessionView
            session={session}
            cluster={activeCluster}
            onUpdate={onSessionUpdate}
            onExit={exitToPicker}
          />
        )}
      </div>
    </AppShell>
  );
}

// ─── Picker ────────────────────────────────────────────────────────────
function PickerView({ clusters, recent, loading, onPick, onResume, onRestart }) {
  const active = recent.filter((r) => r.status === "active");
  return (
    <>
      <header className="mb-10">
        <p className="akki-overline mb-2 flex items-center gap-1.5 text-[var(--accent)]">
          <Layers className="w-3 h-3" /> Akki Solve · structured pause
        </p>
        <h1 className="akki-serif text-4xl text-[var(--ink)] tracking-tight leading-[1.05] mb-4">
          What's the problem you've been carrying?
        </h1>
        <p className="text-[15px] text-[var(--deep)] leading-relaxed max-w-[58ch]">
          Pick the archetype closest to what you're sitting with. Solve will
          walk you through Surface → Depth → Synthesis → Lock-in. Free
          accounts get a Sonnet-streamed synthesis; Pro accounts get the
          deep-tier (Opus) synthesis.
        </p>
      </header>

      {active.length > 0 && (
        <section className="mb-10" data-testid="solve-resume-list">
          <p className="akki-overline mb-3">Continue where you were</p>
          <ul className="bg-white border border-[var(--rule)] rounded-sm divide-y divide-[var(--rule)]">
            {active.slice(0, 3).map((s) => (
              <li
                key={s.id}
                className="px-5 py-3 flex items-center justify-between gap-3"
                data-testid={`solve-resume-${s.id}`}
              >
                <div className="min-w-0">
                  <p className="akki-serif text-[15px] text-[var(--ink)] truncate">
                    {s.cluster_label}
                  </p>
                  <p className="text-[11px] text-[var(--muted)] mt-0.5">
                    {PHASE_LABEL[s.phase]} · {new Date(s.updated_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button
                    size="sm" variant="outline" className="border-[var(--rule)]"
                    onClick={() => onResume(s.id)}
                    data-testid={`solve-resume-btn-${s.id}`}
                  >
                    Continue <ArrowRight className="w-3 h-3 ml-1.5" />
                  </Button>
                  <Button
                    size="sm" variant="ghost" className="text-[var(--muted)]"
                    onClick={() => onRestart(s.id)}
                    data-testid={`solve-restart-btn-${s.id}`}
                  >
                    <RotateCw className="w-3 h-3 mr-1.5" /> Start over
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section data-testid="solve-cluster-grid">
        <p className="akki-overline mb-3">The 12 clusters</p>
        {loading ? (
          <p className="text-[12.5px] italic text-[var(--muted)]">Loading…</p>
        ) : (
          <ul className="grid sm:grid-cols-2 gap-3">
            {clusters.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => onPick(c)}
                  className="w-full text-left bg-white border border-[var(--rule)] hover:border-[var(--accent)] rounded-sm p-5 transition-colors group"
                  data-testid={`solve-cluster-${c.id}`}
                >
                  <p className="akki-serif text-[16px] text-[var(--ink)] group-hover:text-[var(--accent)] transition-colors mb-1.5 leading-snug">
                    {c.label}
                  </p>
                  <p className="text-[12.5px] text-[var(--muted)] leading-snug italic">
                    {c.blurb}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

// ─── Intent ───────────────────────────────────────────────────────────
function IntentView({ cluster, intent, onIntentChange, proTier, onProTierChange, onBack, onStart, busy }) {
  const useExample = () => onIntentChange(cluster.example_question || "");
  return (
    <>
      <button
        type="button"
        onClick={onBack}
        className="text-[11.5px] uppercase tracking-[0.16em] text-[var(--muted)] hover:text-[var(--ink)] mb-6 inline-flex items-center gap-1"
        data-testid="solve-intent-back"
      >
        <ArrowLeft className="w-3 h-3" /> Pick a different cluster
      </button>
      <p className="akki-overline mb-2 text-[var(--accent)]">
        <Layers className="w-3 h-3 inline mr-1.5" /> {cluster.label}
      </p>
      <h1 className="akki-serif text-4xl text-[var(--ink)] tracking-tight leading-[1.05] mb-4 max-w-[24ch]">
        Tell Solve, in your own words.
      </h1>
      <p className="text-[14px] text-[var(--deep)] leading-relaxed mb-7 max-w-[58ch]">
        Don't polish. Two or three sentences is fine. Solve uses this to
        anchor the rest of the session — Surface, Depth, Synthesis, Lock-in.
      </p>

      <div className="bg-white border border-[var(--rule)] rounded-sm p-6 mb-6" data-testid="solve-intent-card">
        <Textarea
          value={intent}
          onChange={(e) => onIntentChange(e.target.value)}
          placeholder={cluster.example_question || "What's the problem you've been carrying?"}
          className="min-h-[140px] akki-serif text-[15px]"
          data-testid="solve-intent-input"
        />
        {cluster.example_question && (
          <button
            type="button"
            onClick={useExample}
            className="mt-2 text-[11.5px] uppercase tracking-[0.14em] text-[var(--accent)] hover:underline"
            data-testid="solve-intent-use-example"
          >
            Use the example
          </button>
        )}
        <div className="mt-5 pt-4 border-t border-[var(--rule)] flex items-center gap-3">
          <input
            type="checkbox"
            id="solve-pro"
            checked={proTier}
            onChange={(e) => onProTierChange(e.target.checked)}
            className="accent-[var(--accent)] w-3.5 h-3.5"
            data-testid="solve-intent-pro-toggle"
          />
          <label htmlFor="solve-pro" className="text-[12.5px] text-[var(--deep)] cursor-pointer">
            Pro synthesis (deep tier · Opus)
            <span className="ml-2 text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)]">
              requires Pro account
            </span>
          </label>
        </div>
      </div>

      <div className="flex justify-end gap-3">
        <Button
          onClick={onStart}
          disabled={intent.trim().length < 20 || busy}
          className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-11 px-7"
          data-testid="solve-intent-start"
        >
          {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
          Begin Solve session <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </>
  );
}

// ─── Session ───────────────────────────────────────────────────────────
function SessionView({ session, cluster, onUpdate, onExit }) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const turnsRef = useRef(null);

  useEffect(() => {
    if (turnsRef.current) {
      turnsRef.current.scrollTop = turnsRef.current.scrollHeight;
    }
  }, [session.turns?.length, session.phase]);

  const completed = session.status === "completed";
  const phaseIdx = session.phase_index ?? 0;

  const submitTurn = async () => {
    if (draft.trim().length < 2 || busy) return;
    setBusy(true);
    try {
      const { data } = await api.post(`/solve/sessions/${session.id}/turn`, {
        user_text: draft.trim(),
      });
      onUpdate(data);
      setDraft("");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const abandon = async () => {
    if (!window.confirm("Pause and leave this session for later? You can resume from the picker.")) return;
    setBusy(true);
    try {
      await api.post(`/solve/sessions/${session.id}/abandon`);
      onExit();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="solve-session">
      <header className="mb-7 flex items-start justify-between gap-3 flex-wrap">
        <div>
          <p className="akki-overline mb-1 text-[var(--accent)]">
            <Layers className="w-3 h-3 inline mr-1.5" /> {session.cluster_label}
            {session.pro_tier && (
              <span className="ml-2 text-[10.5px] uppercase tracking-[0.16em] text-[var(--accent)] border border-[var(--accent)]/30 px-1.5 py-0.5 rounded-sm">
                Pro
              </span>
            )}
          </p>
          <h1 className="akki-serif text-2xl text-[var(--ink)] leading-snug max-w-[60ch]">
            {session.intent}
          </h1>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button
            size="sm" variant="ghost"
            onClick={onExit}
            className="text-[var(--muted)]"
            data-testid="solve-session-exit"
          >
            Back
          </Button>
          {!completed && (
            <Button
              size="sm" variant="outline"
              onClick={abandon}
              disabled={busy}
              className="border-[var(--rule)]"
              data-testid="solve-session-pause"
            >
              <Pause className="w-3 h-3 mr-1.5" /> Pause for later
            </Button>
          )}
        </div>
      </header>

      <PhaseStepper currentIdx={phaseIdx} completed={completed} />

      <div
        ref={turnsRef}
        className="bg-white border border-[var(--rule)] rounded-sm p-5 mb-5 max-h-[60vh] overflow-y-auto space-y-5"
        data-testid="solve-session-turns"
      >
        {(session.turns || []).map((t) => (
          <Turn key={t.id} turn={t} />
        ))}
        {session.synthesis?.comparables?.length > 0 && (
          <ComparablesPanel comparables={session.synthesis.comparables} />
        )}
        {completed && session.lockin && (
          <CompletedBanner />
        )}
      </div>

      {!completed && (
        <div className="bg-white border border-[var(--rule)] rounded-sm p-4" data-testid="solve-session-composer">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={`Your ${PHASE_LABEL[session.phase]} reply…`}
            className="min-h-[100px] akki-serif text-[14px]"
            data-testid="solve-session-input"
            disabled={busy}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                submitTurn();
              }
            }}
          />
          <div className="mt-3 flex items-center justify-between">
            <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
              ⌘ ↵ to send · phase {phaseIdx + 1}/4
            </p>
            <Button
              onClick={submitTurn}
              disabled={draft.trim().length < 2 || busy}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-9 px-5"
              data-testid="solve-session-send"
            >
              {busy ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <ArrowRight className="w-3.5 h-3.5 mr-1.5" />}
              {busy ? "Solve is thinking…" : `Send · advance to ${PHASE_LABEL[PHASE_ORDER[phaseIdx + 1]] || "complete"}`}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function Turn({ turn }) {
  const isUser = turn.role === "user";
  return (
    <div data-testid={`solve-turn-${turn.id}`}>
      <p className={`text-[10.5px] uppercase tracking-[0.18em] mb-1.5 ${isUser ? "text-[var(--muted)]" : "text-[var(--accent)]"}`}>
        {isUser ? "You" : "Solve"} · {PHASE_LABEL[turn.phase] || turn.phase}
        {turn.tier === "deep" && " · deep"}
      </p>
      <div className={`akki-serif text-[14.5px] leading-[1.7] whitespace-pre-wrap ${isUser ? "text-[var(--deep)]" : "text-[var(--ink)]"}`}>
        {turn.text}
      </div>
    </div>
  );
}

function ComparablesPanel({ comparables }) {
  return (
    <div
      className="bg-[var(--cream-deep)]/40 border-l-2 border-[var(--accent)] pl-4 py-2"
      data-testid="solve-comparables"
    >
      <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] mb-2">
        Comparables · triangulation
      </p>
      <ul className="space-y-2 text-[13px] text-[var(--deep)] leading-relaxed">
        {comparables.map((c, i) => (
          <li key={i} data-testid={`solve-comparable-${i}`}>
            {typeof c === "string" ? c : (c.summary || JSON.stringify(c))}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CompletedBanner() {
  return (
    <div className="bg-emerald-50 border border-emerald-200 rounded-sm px-4 py-3 flex items-start gap-3" data-testid="solve-completed-banner">
      <Check className="w-4 h-4 text-emerald-700 mt-0.5" />
      <p className="text-[13px] text-emerald-900 leading-relaxed">
        Session complete. Your diagnosis and lock-in commitments are saved.
        Come back to it from the picker, or generate a brief / deck from
        the synthesis (coming in Wave 2).
      </p>
    </div>
  );
}

function PhaseStepper({ currentIdx, completed }) {
  return (
    <ol className="flex items-center gap-1.5 mb-6" data-testid="solve-phase-stepper">
      {PHASE_ORDER.map((p, i) => {
        const active = i === currentIdx && !completed;
        const done = i < currentIdx || completed;
        return (
          <React.Fragment key={p}>
            <li className="flex items-center gap-2">
              <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono border ${
                active ? "border-[var(--accent)] text-[var(--accent)]" :
                done ? "border-[var(--ink)] bg-[var(--ink)] text-[var(--cream)]" :
                "border-[var(--rule)] text-[var(--muted)]"
              }`}>
                {done ? "✓" : i + 1}
              </span>
              <span className={`text-[10.5px] uppercase tracking-[0.16em] ${
                active ? "text-[var(--accent)]" : done ? "text-[var(--ink)]" : "text-[var(--muted)]"
              }`}>
                {PHASE_LABEL[p]}
              </span>
            </li>
            {i < PHASE_ORDER.length - 1 && (
              <span className="flex-1 h-px bg-[var(--rule)] mx-2" />
            )}
          </React.Fragment>
        );
      })}
    </ol>
  );
}
