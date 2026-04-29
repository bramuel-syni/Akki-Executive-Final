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
  RotateCw, Check, Pause, Download,
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
  const [proStatus, setProStatus] = useState(null);

  useEffect(() => {
    let live = true;
    setLoading(true);
    Promise.all([
      api.get("/solve/clusters").catch(() => ({ data: { clusters: [] } })),
      api.get("/solve/sessions").catch(() => ({ data: { items: [] } })),
      api.get("/solve/pro-status").catch(() => ({ data: null })),
    ])
      .then(([c, s, p]) => {
        if (!live) return;
        setClusters(c.data?.clusters || []);
        setRecent(s.data?.items || []);
        setProStatus(p.data || null);
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
            proStatus={proStatus}
          />
        )}
        {view === "session" && session && (
          <SessionView
            session={session}
            cluster={activeCluster}
            onUpdate={onSessionUpdate}
            onExit={exitToPicker}
            proStatus={proStatus}
          />
        )}
      </div>
    </AppShell>
  );
}

// ─── Picker ────────────────────────────────────────────────────────────
function PickerView({ clusters, recent, loading, onPick, onResume, onRestart }) {
  const active = recent.filter((r) => r.status === "active");
  const completed = recent.filter((r) => r.status === "completed").slice(0, 3);
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

      {completed.length > 0 && (
        <section className="mb-10" data-testid="solve-completed-list">
          <p className="akki-overline mb-3">Completed — hand off ready</p>
          <ul className="bg-white border border-[var(--rule)] rounded-sm divide-y divide-[var(--rule)]">
            {completed.map((s) => (
              <li
                key={s.id}
                className="px-5 py-3 flex items-center justify-between gap-3"
                data-testid={`solve-completed-${s.id}`}
              >
                <div className="min-w-0">
                  <p className="akki-serif text-[15px] text-[var(--ink)] truncate">
                    {s.cluster_label}
                  </p>
                  <p className="text-[11px] text-[var(--muted)] mt-0.5">
                    Completed · {new Date(s.completed_at || s.updated_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button
                    size="sm" variant="outline" className="border-[var(--rule)]"
                    onClick={() => onResume(s.id)}
                    data-testid={`solve-completed-open-${s.id}`}
                  >
                    Open <ArrowRight className="w-3 h-3 ml-1.5" />
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
function IntentView({ cluster, intent, onIntentChange, proTier, onProTierChange, onBack, onStart, busy, proStatus }) {
  const useExample = () => onIntentChange(cluster.example_question || "");
  const isPro = !!proStatus?.is_pro;
  const grantClaimed = !!proStatus?.free_grant?.claimed_this_month;
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
        <div className="mt-5 pt-4 border-t border-[var(--rule)] flex items-start gap-3">
          <input
            type="checkbox"
            id="solve-pro"
            checked={proTier}
            onChange={(e) => onProTierChange(e.target.checked)}
            className="accent-[var(--accent)] w-3.5 h-3.5 mt-0.5"
            data-testid="solve-intent-pro-toggle"
          />
          <label htmlFor="solve-pro" className="text-[12.5px] text-[var(--deep)] cursor-pointer leading-relaxed flex-1">
            <span className="block">Pro synthesis (deep tier · Opus)</span>
            {isPro ? (
              <span className="block text-[11px] text-[var(--accent)] mt-0.5" data-testid="solve-pro-state-pro">
                Pro account — unlimited deep synthesis.
              </span>
            ) : grantClaimed ? (
              <span className="block text-[11px] text-[var(--muted)] mt-0.5" data-testid="solve-pro-state-locked">
                You've used your free deep synthesis this month. Pro accounts get unlimited deep synthesis on every Solve.
              </span>
            ) : (
              <span className="block text-[11px] text-[var(--muted)] mt-0.5" data-testid="solve-pro-state-free">
                <span className="text-[var(--accent)]">1 free deep synthesis</span> available this month. Pro plan gets unlimited.
              </span>
            )}
          </label>
        </div>
        {!isPro && grantClaimed && proTier && (
          <div className="mt-3 bg-[var(--cream-deep)]/50 border border-[var(--accent)]/30 rounded-sm px-4 py-3 flex items-start gap-3" data-testid="solve-pro-upgrade-cta">
            <Sparkles className="w-4 h-4 text-[var(--accent)] mt-0.5" />
            <div className="flex-1">
              <p className="akki-serif text-[14px] text-[var(--ink)] mb-1">
                Subscribe to Pro for unlimited deep synthesis.
              </p>
              <p className="text-[11.5px] text-[var(--muted)] mb-2">
                $29/mo gets you unlimited Opus-tier diagnoses across every Solve session you run, plus the rest of AKKI Pro. You'll still get the standard tier on this session at no charge.
              </p>
              <a
                href="/app/settings?tab=billing"
                className="inline-block text-[11.5px] uppercase tracking-[0.14em] text-[var(--accent)] hover:underline"
                data-testid="solve-pro-upgrade-link"
              >
                Open billing →
              </a>
            </div>
          </div>
        )}
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

  const hasSynthesis = !!(session.synthesis?.body);
  const downloadPdf = () => {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/solve/sessions/${session.id}/export.pdf`;
    const tok = localStorage.getItem("akki_access_token");
    fetch(url, { headers: tok ? { Authorization: `Bearer ${tok}` } : {}, credentials: "include" })
      .then((r) => {
        if (!r.ok) throw new Error("Failed to export PDF");
        return r.blob();
      })
      .then((blob) => {
        const u = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = u;
        a.download = `akki_solve_${session.id.slice(0, 8)}.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(u);
      })
      .catch((e) => toast.error(e.message || "Couldn't export PDF."));
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
          {hasSynthesis && (
            <Button
              size="sm" variant="outline"
              onClick={downloadPdf}
              className="border-[var(--rule)]"
              data-testid="solve-session-pdf"
            >
              <Download className="w-3 h-3 mr-1.5" /> PDF
            </Button>
          )}
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

      {completed && session.lockin && (
        <HandoffStrip session={session} onUpdate={onUpdate} />
      )}

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
      <ul className="space-y-3 text-[13px] text-[var(--deep)] leading-relaxed">
        {comparables.map((c, i) => (
          <li key={c.id || i} data-testid={`solve-comparable-${i}`}>
            {typeof c === "string" ? (
              c
            ) : (
              <>
                <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--muted)] mb-1">
                  {(c.sector_tag || "any").replace(/_/g, " ")} · {(c.scale_tag || "—").replace(/_/g, " ")}
                </p>
                <p className="akki-serif text-[13.5px] text-[var(--ink)] mb-1">
                  {c.diagnosis_summary || c.summary || JSON.stringify(c)}
                </p>
                {c.what_worked && (
                  <p className="text-[12px]"><span className="text-[var(--accent)]">Worked:</span> {c.what_worked}</p>
                )}
                {c.what_didnt && (
                  <p className="text-[12px]"><span className="text-[var(--muted)]">Didn't:</span> {c.what_didnt}</p>
                )}
              </>
            )}
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
        Use the handoff strip below to push them into a Brief, a Decks
        outline, or your context's question bank.
      </p>
    </div>
  );
}

function HandoffStrip({ session, onUpdate }) {
  const [busy, setBusy] = useState(null); // 'brief' | 'decks' | 'cycle' | null
  const [done, setDone] = useState(() => {
    const map = {};
    for (const h of (session.handoffs || [])) map[h.target] = h.artefact_id;
    return map;
  });
  const [contextId, setContextId] = useState(session.context_id || "");
  const [contexts, setContexts] = useState([]);
  const [recommended, setRecommended] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get("/auth/me")
      .then((r) => {
        const list = (r.data?.contexts || []).filter(
          (c) => c.status !== "archived" && c.type !== "sandbox"
        );
        setContexts(list);
        if (!contextId && list.length === 1) setContextId(list[0].id);
      })
      .catch(() => {});
  }, []); // eslint-disable-line

  // Smart suggestion: NED contexts → cycle (board-room follow-up);
  // executive_personal contexts where a question bank already exists → cycle;
  // else → brief (the safe default that captures the diagnosis as a one-pager).
  useEffect(() => {
    if (!contextId || done.brief || done.decks || done.cycle) return;
    const ctx = contexts.find((c) => c.id === contextId);
    if (!ctx) return;
    const isNed = (ctx.type || "").startsWith("ned");
    if (isNed) {
      setRecommended("cycle");
      return;
    }
    // Probe questions bank size — if user has an active reporting cycle already,
    // suggest cycle; else suggest brief.
    api.get(`/contexts/${contextId}/questions?status=open`)
      .then((r) => {
        const count = (r.data?.questions || []).length;
        setRecommended(count > 0 ? "cycle" : "brief");
      })
      .catch(() => setRecommended("brief"));
  }, [contextId, contexts, done.brief, done.decks, done.cycle]);

  const fire = async (target) => {
    setErr("");
    if (!contextId) {
      setErr("Pick a context to push the handoff into.");
      return;
    }
    setBusy(target);
    try {
      const path = target === "decks" ? "/handoff/decks" : `/handoff/${target}`;
      const payload = target === "decks"
        ? { context_id: contextId, audience: "Board" }
        : { context_id: contextId };
      const { data } = await api.post(`/solve/sessions/${session.id}${path}`, payload);
      const id = (data.briefing || data.outline || data.questions?.[0])?.id;
      if (id) setDone((d) => ({ ...d, [target]: id }));
      toast.success(target === "brief"
        ? data.already_exists ? "Brief already created — opened existing." : "Brief created."
        : target === "decks"
          ? data.already_exists ? "Decks outline already exists." : "Decks outline seeded — refine and render."
          : data.already_exists ? "Cycle questions already seeded." : `Seeded ${data.questions?.length || 0} cycle question${data.questions?.length===1?"":"s"}.`
      );
      // Refetch so handoffs[] stays in sync
      const fresh = await api.get(`/solve/sessions/${session.id}`).catch(() => null);
      if (fresh?.data) onUpdate?.(fresh.data);
    } catch (e) {
      setErr(apiErrorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const targets = [
    { id: "brief",  label: "Create a Brief",        sub: "Synthesis as opening + lockin as items" },
    { id: "decks",  label: "Seed a Decks outline",  sub: "Editable outline, ready for deep render" },
    { id: "cycle",  label: "Push to Question Bank", sub: "1–3 board questions for the next cycle" },
  ];
  const recommendedLabel = recommended && targets.find((t) => t.id === recommended)?.label;

  return (
    <div
      className="mt-4 bg-white border border-[var(--rule)] rounded-sm p-5"
      data-testid="solve-handoff-strip"
    >
      <div className="flex items-baseline justify-between mb-3">
        <p className="akki-overline text-[var(--accent)]">
          Hand off the diagnosis
        </p>
        {recommendedLabel && !done[recommended] && (
          <p className="text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)]" data-testid="solve-handoff-recommendation">
            Recommended for this context: <span className="text-[var(--accent)]">{recommendedLabel}</span>
          </p>
        )}
      </div>
      {contexts.length > 1 && (
        <div className="mb-4">
          <label className="block text-[10.5px] uppercase tracking-[0.16em] text-[var(--muted)] mb-1.5">
            Push to context
          </label>
          <select
            value={contextId}
            onChange={(e) => setContextId(e.target.value)}
            className="w-full bg-white border border-[var(--rule)] rounded-sm px-3 py-2 text-[13px]"
            data-testid="solve-handoff-context-select"
          >
            <option value="">— pick a context —</option>
            {contexts.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      )}
      <ul className="grid sm:grid-cols-3 gap-3">
        {targets.map((t) => {
          const isRecommended = recommended === t.id && !done[t.id];
          return (
            <li key={t.id}>
              <button
                type="button"
                onClick={() => fire(t.id)}
                disabled={busy !== null}
                className={`w-full text-left p-4 rounded-sm border transition-colors ${
                  done[t.id]
                    ? "bg-emerald-50 border-emerald-200"
                    : isRecommended
                      ? "bg-[var(--cream-deep)]/60 border-[var(--accent)] ring-1 ring-[var(--accent)]/40"
                      : "bg-[var(--cream-deep)]/30 border-[var(--rule)] hover:border-[var(--accent)]"
                }`}
                data-testid={`solve-handoff-${t.id}`}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  {done[t.id] ? <Check className="w-3 h-3 text-emerald-700" /> : null}
                  {busy === t.id ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                  {isRecommended ? <Sparkles className="w-3 h-3 text-[var(--accent)]" /> : null}
                  <p className="akki-serif text-[14px] text-[var(--ink)]">{t.label}</p>
                </div>
                <p className="text-[11.5px] text-[var(--muted)] leading-snug">
                  {done[t.id] ? "Created — click to view" : t.sub}
                </p>
              </button>
            </li>
          );
        })}
      </ul>
      {err && (
        <p className="mt-3 text-[11.5px] text-red-700" data-testid="solve-handoff-error">
          {err}
        </p>
      )}
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
