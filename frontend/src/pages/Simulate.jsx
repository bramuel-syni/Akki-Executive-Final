import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  ArrowRight, Loader2, TrendingUp, TrendingDown, Activity,
  Target, HelpCircle, Sparkles, Trash2, Clock,
} from "lucide-react";
import CommentThread from "@/components/collab/CommentThread";
import CompositionStrip from "@/components/trace/CompositionStrip";

const HORIZON_OPTS = [
  { value: "1y",   label: "1 year" },
  { value: "3y",   label: "3 years" },
  { value: "1y3y", label: "1y + 3y" },
];

const HYPOTHESIS_STARTERS = [
  "If our largest corporate borrower is acquired, what's the one- and three-year impact on our loan book and capital?",
  "Assume Kenya's benchmark rate is cut 200bps over 12 months. How does this play out on our net interest margin and deposit mix?",
  "What if AI-enabled fraud doubles in our sector within a year? Where does it hit us first?",
  "If a major competitor exits the SME lending segment, what are our plausible trajectories over 3 years?",
];

/**
 * ScenarioRow — full-width horizontal scenario card.
 *
 * Replaces the iter-prior 3-column vertical grid that gave each card too
 * narrow a measure. The user feedback was explicit: "Use horizontal cards
 * rather than vertical for Best Case, Base Case, and Stress Case. Vertical
 * cards make the text harder to read because line lengths are too short."
 *
 * Layout: a thin coloured rail on the left, label/icon in a fixed-width
 * gutter, body running across the rest of the row at proper measure
 * (~75-80 chars). Stacks back to a single column under 768px.
 */
function ScenarioRow({ icon: Icon, tone, label, body }) {
  if (!body) return null;
  const tones = {
    best:   { rail: "bg-emerald-600",          label: "text-emerald-700",       chip: "bg-emerald-50 border-emerald-200" },
    base:   { rail: "bg-[var(--accent)]",      label: "text-[var(--accent)]",   chip: "bg-[var(--accent-soft)] border-[var(--accent)]/20" },
    stress: { rail: "bg-red-700",              label: "text-red-700",           chip: "bg-red-50 border-red-200" },
  };
  const t = tones[tone] || tones.base;
  return (
    <div className="flex flex-col md:flex-row gap-0 md:gap-5 bg-white border border-[var(--rule)] rounded-md overflow-hidden" data-testid={`scenario-row-${tone}`}>
      {/* Left rail + label gutter — 180px on desktop, full-width strip on mobile */}
      <div className={`flex md:flex-col items-center md:items-start gap-2 md:gap-3 md:w-[180px] shrink-0 px-4 md:px-5 py-3 md:py-5 border-b md:border-b-0 md:border-r border-[var(--rule)] ${t.chip}`}>
        <div className={`w-1 h-5 md:h-12 rounded-sm ${t.rail}`} />
        <div className="flex md:flex-col items-center md:items-start gap-2 md:gap-1.5">
          <Icon className={`w-3.5 h-3.5 ${t.label}`} strokeWidth={1.8} />
          <p className={`text-[10.5px] uppercase tracking-[0.2em] font-mono ${t.label}`}>{label}</p>
        </div>
      </div>
      {/* Body — runs across the rest of the row at proper measure */}
      <p className="akki-serif text-[15px] leading-[1.7] text-[var(--deep)] px-5 py-4 md:py-5 flex-1 min-w-0">
        {body}
      </p>
    </div>
  );
}

function SimulationViewer({ sim, onArchive }) {
  return (
    <article className="akki-fade-up space-y-8" data-testid={`simulation-view-${sim.id}`}>
      <header>
        <p className="akki-overline mb-2">
          Simulation · {new Date(sim.created_at).toLocaleDateString()}
          {sim.horizon === "1y3y" ? " · 1y + 3y" : ` · ${sim.horizon}`}
        </p>
        <h1 className="akki-serif text-[30px] leading-[1.2] text-[var(--ink)] font-normal mb-3">{sim.title}</h1>
        <p className="akki-lead text-[var(--deep)] italic mb-0">"{sim.hypothesis}"</p>
      </header>

      {sim.one_year && (
        <section>
          <h2 className="akki-overline mb-3">One-year trajectory</h2>
          <div className="space-y-3">
            <ScenarioRow icon={TrendingUp}   tone="best"   label="Best case"   body={sim.one_year?.best} />
            <ScenarioRow icon={Activity}     tone="base"   label="Base case"   body={sim.one_year?.base} />
            <ScenarioRow icon={TrendingDown} tone="stress" label="Stress case" body={sim.one_year?.stress} />
          </div>
        </section>
      )}

      {sim.three_year && (
        <section>
          <h2 className="akki-overline mb-3">Three-year trajectory</h2>
          <div className="space-y-3">
            <ScenarioRow icon={TrendingUp}   tone="best"   label="Best case"   body={sim.three_year?.best} />
            <ScenarioRow icon={Activity}     tone="base"   label="Base case"   body={sim.three_year?.base} />
            <ScenarioRow icon={TrendingDown} tone="stress" label="Stress case" body={sim.three_year?.stress} />
          </div>
        </section>
      )}

      {sim.watchlist?.length > 0 && (
        <section className="bg-white border border-[var(--rule)] rounded-md p-5 relative">
          <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)] rounded-l-md" />
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
            <p className="akki-overline">Watchlist — early-warning indicators</p>
          </div>
          <div className="space-y-3">
            {sim.watchlist.map((w, i) => (
              <div key={i} className="flex items-start gap-3 pt-3 first:pt-0 border-t first:border-t-0 border-[var(--rule)]/60">
                <span className="text-[12px] font-mono text-[var(--accent)] mt-0.5">{String(i + 1).padStart(2, "0")}</span>
                <div className="flex-1 min-w-0">
                  <p className="akki-serif text-[15px] text-[var(--ink)] leading-snug">{w.indicator}</p>
                  <p className="text-[12.5px] text-[var(--muted)] mt-1">
                    <span className="text-[var(--accent)]">Trigger:</span> {w.early_warning}
                  </p>
                  {w.committee && (
                    <span className="inline-block mt-2 akki-context-chip">{w.committee}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {sim.assumptions?.length > 0 && (
        <section>
          <h2 className="akki-overline mb-3">Assumptions</h2>
          <ul className="space-y-2">
            {sim.assumptions.map((a, i) => (
              <li key={i} className="flex gap-2 akki-serif text-[14px] text-[var(--deep)]">
                <span className="text-[var(--muted)]">·</span>
                <span>{a}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {sim.question_for_management && (
        <section className="bg-[var(--accent-soft)]/60 border border-[var(--accent)]/30 rounded-md p-5">
          <div className="flex items-center gap-2 mb-2">
            <HelpCircle className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
            <p className="akki-overline">Question for management</p>
          </div>
          <p className="akki-serif text-[16px] leading-[1.6] text-[var(--ink)] italic">
            "{sim.question_for_management}"
          </p>
        </section>
      )}

      <div className="pt-5 border-t border-[var(--rule)] flex items-center justify-between text-[12px] text-[var(--muted)]">
        <span>AKKI synthesis · mode: {sim.mode || "synth"}</span>
        <button
          onClick={() => onArchive(sim)}
          className="akki-gesture text-[12.5px]"
          data-testid={`simulation-archive-${sim.id}`}
        >
          <Trash2 className="w-3.5 h-3.5" /> Archive
        </button>
      </div>

      <CompositionStrip artefact={sim} kind="simulation" />
      <CommentThread artefactType="simulation" artefactId={sim.id} />
    </article>
  );
}

export default function Simulate() {
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;
  const [list, setList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [hypothesis, setHypothesis] = useState("");
  const [horizon, setHorizon] = useState("1y3y");
  const [committeeId, setCommitteeId] = useState("all");
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState("");

  const committees = activeContext?.committees || [];

  const load = useCallback(async () => {
    if (!contextId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/simulations`);
      setList(data);
      if (data.length > 0 && !selected) setSelected(data[0]);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId, selected]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setSelected(null); }, [contextId]);

  const onRun = async () => {
    const text = hypothesis.trim();
    if (text.length < 10) { toast.message("Write at least a sentence for AKKI to work with."); return; }
    setRunning(true);
    setStage("Reading Context Object and active signals…");
    const timers = [
      setTimeout(() => setStage("Reasoning through base / best / stress…"), 8000),
      setTimeout(() => setStage("Drafting the watchlist and assumptions…"), 20000),
      setTimeout(() => setStage("Still working — complex scenarios can take a minute…"), 40000),
    ];
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/simulate`,
        {
          hypothesis: text,
          horizon,
          committee_id: committeeId === "all" ? null : committeeId,
        },
        { timeout: 180000 },
      );
      toast.success("Simulation ready");
      setHypothesis("");
      setSelected(data);
      setList((prev) => [data, ...prev]);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally {
      timers.forEach(clearTimeout);
      setStage("");
      setRunning(false);
    }
  };

  const onArchive = async (sim) => {
    try {
      await api.delete(`/contexts/${contextId}/simulations/${sim.id}`);
      toast.success("Simulation archived");
      setList((prev) => prev.filter((x) => x.id !== sim.id));
      if (selected?.id === sim.id) setSelected(null);
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const visibleList = useMemo(() => {
    if (committeeId === "all") return list;
    return list.filter((s) => s.committee_id === committeeId);
  }, [list, committeeId]);

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-sm text-[var(--muted)]">No company selected.</div></AppShell>;
  }

  return (
    <AppShell>
      <div className="h-[calc(100vh-4rem)] akki-w-medium grid grid-cols-1 lg:grid-cols-[320px_1fr] overflow-hidden">
        {/* LEFT — compose + list */}
        <aside className="border-r border-[var(--rule)] bg-[var(--cream)] flex flex-col min-h-0" data-testid="simulate-rail">
          <div className="px-5 py-6 border-b border-[var(--rule)] bg-white">
            <p className="akki-overline mb-1 flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Simulate
            </p>
            <h1 className="akki-serif text-[20px] font-normal text-[var(--ink)] mb-1">Test a hypothesis.</h1>
            <p className="text-[11.5px] text-[var(--muted)] leading-relaxed">
              Past simulations live below.
            </p>
          </div>

          <div className="flex-1 overflow-y-auto" data-testid="simulate-history">
            {loading ? (
              <div className="p-5 text-center text-[11px] uppercase tracking-widest text-[var(--muted)]">Loading…</div>
            ) : visibleList.length === 0 ? (
              <div className="p-6 text-center text-[11.5px] text-[var(--muted)] leading-relaxed">
                No simulations yet. Run your first on the right.
              </div>
            ) : (
              <div className="p-2">
                {visibleList.map((s) => {
                  const active = selected?.id === s.id;
                  return (
                    <button
                      key={s.id}
                      onClick={() => setSelected(s)}
                      className={`w-full text-left px-3 py-2.5 rounded-sm mb-1 transition-colors border ${
                        active
                          ? "bg-white border-[var(--accent)]/60"
                          : "border-transparent hover:bg-white"
                      }`}
                      data-testid={`simulate-list-${s.id}`}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <Clock className="w-2.5 h-2.5 text-[var(--muted)]" />
                        <span className="text-[10px] text-[var(--muted)]">
                          {new Date(s.created_at).toLocaleDateString()} · {s.horizon === "1y3y" ? "1y+3y" : s.horizon}
                        </span>
                      </div>
                      <p className={`text-[12.5px] font-medium leading-snug line-clamp-2 ${active ? "text-[var(--ink)]" : "text-[var(--deep)]"}`}>
                        {s.title}
                      </p>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </aside>

        {/* RIGHT — input-first journey */}
        <main className="overflow-y-auto bg-[var(--cream)]" data-testid="simulate-detail">
          <div className="akki-w-narrow px-8 py-10">
            {selected && !running ? (
              <>
                <div className="flex items-center justify-between mb-4 gap-3 flex-wrap">
                  <button
                    onClick={() => setSelected(null)}
                    className="text-[11.5px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1"
                    data-testid="simulate-back"
                  >
                    ← Back
                  </button>
                  {/* Prominent New Simulation button — users running multiple
                      sims should not have to back out. */}
                  <Button
                    onClick={() => { setSelected(null); setHypothesis(""); }}
                    className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[12.5px] h-9 px-4"
                    data-testid="simulate-new-btn"
                  >
                    <Sparkles className="w-3.5 h-3.5 mr-1.5" /> New simulation
                  </Button>
                </div>
                <SimulationViewer sim={selected} onArchive={onArchive} />
              </>
            ) : (
              <>
                {/* Hero — what is Simulate, in two lines */}
                <header className="mb-6 akki-fade-up" data-testid="simulate-hero">
                  <p className="akki-overline mb-2">Simulate · hypothesis testing</p>
                  <h1 className="akki-serif text-[28px] leading-[1.2] text-[var(--ink)] font-normal mb-2">
                    Pressure-test a "what-if" before the board does.
                  </h1>
                  <p className="text-[14px] text-[var(--deep)] leading-relaxed max-w-2xl">
                    Drop in any claim someone is asking the board to act on — a major investment, a market scenario, a risk forecast — and AKKI returns three plausible trajectories (best, base, stress), the indicators to watch, and the single sharpest question to put to management.
                  </p>
                </header>

                {/* Numbered journey strip — three cards = the input/output flow.
                    Each card is intentionally bare so the user knows EXACTLY
                    where to act. */}
                <div className="grid grid-cols-3 gap-2 mb-4 text-[10.5px] uppercase tracking-[0.2em] font-mono text-[var(--muted)]" data-testid="simulate-journey-strip">
                  <div className="border-l-2 border-[var(--accent)] pl-2">01 · You write the hypothesis</div>
                  <div className="border-l-2 border-[var(--rule)] pl-2">02 · AKKI runs it</div>
                  <div className="border-l-2 border-[var(--rule)] pl-2">03 · You get three trajectories + a watchlist</div>
                </div>

                {/* INPUT CARD — large, central, the obvious thing to use */}
                <div className="bg-white border border-[var(--rule)] rounded-md p-5 mb-4" data-testid="simulate-input-card">
                  <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-2">
                    Your hypothesis
                  </p>
                  <textarea
                    value={hypothesis}
                    onChange={(e) => setHypothesis(e.target.value)}
                    placeholder="e.g. If our largest corporate borrower is acquired, what's the impact on our loan book and capital over the next year and three years?"
                    rows={4}
                    disabled={running}
                    className="w-full bg-transparent text-[15px] resize-none focus:outline-none akki-serif leading-relaxed"
                    data-testid="simulate-hypothesis-input"
                  />
                  <div className="flex items-center justify-between gap-3 pt-3 mt-2 border-t border-[var(--rule)] flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      <label className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono">Horizon</label>
                      <select
                        value={horizon}
                        onChange={(e) => setHorizon(e.target.value)}
                        className="text-[12px] border border-[var(--rule)] rounded-sm bg-white px-2 py-1.5 focus:outline-none focus:border-[var(--accent)]"
                        data-testid="simulate-horizon-select"
                      >
                        {HORIZON_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                      {committees.length > 0 && (
                        <>
                          <label className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono ml-2">Scope</label>
                          <select
                            value={committeeId}
                            onChange={(e) => setCommitteeId(e.target.value)}
                            className="text-[12px] border border-[var(--rule)] rounded-sm bg-white px-2 py-1.5 focus:outline-none focus:border-[var(--accent)]"
                            data-testid="simulate-committee-select"
                          >
                            <option value="all">Full board</option>
                            {committees.map((cm) => <option key={cm.id} value={cm.id}>{cm.name}</option>)}
                          </select>
                        </>
                      )}
                    </div>
                    <Button
                      onClick={onRun}
                      disabled={running || !hypothesis.trim()}
                      className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[13px] h-9 px-5"
                      data-testid="simulate-run-btn"
                    >
                      {running
                        ? <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Running…</>
                        : <><Sparkles className="w-3.5 h-3.5 mr-2" /> Run simulation</>}
                    </Button>
                  </div>
                  {running && stage && (
                    <div className="text-[11.5px] text-[var(--deep)] italic bg-[var(--accent-soft)] border border-[var(--accent)]/20 rounded-sm px-2.5 py-1.5 flex items-center gap-1.5 mt-3" data-testid="simulate-stage">
                      <Loader2 className="w-3 h-3 animate-spin text-[var(--accent)] shrink-0" />
                      <span className="flex-1 truncate">{stage}</span>
                    </div>
                  )}
                </div>

                {/* Starters — only show when input is empty */}
                {!running && hypothesis.trim().length < 10 && (
                  <div className="bg-white border border-dashed border-[var(--rule)] rounded-md p-5" data-testid="simulate-starters">
                    <p className="akki-overline mb-3">Don't know how to start? Try one of these</p>
                    <ul className="space-y-2">
                      {HYPOTHESIS_STARTERS.map((s, i) => (
                        <li key={i}>
                          <button
                            onClick={() => setHypothesis(s)}
                            className="text-left text-[13px] text-[var(--deep)] hover:text-[var(--accent)] leading-snug"
                            data-testid={`simulate-starter-${i}`}
                          >
                            <span className="text-[var(--accent)] mr-1.5">→</span> {s}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {running && !selected && (
                  <div className="bg-white border border-[var(--rule)] rounded-md p-12 text-center mt-4">
                    <Loader2 className="w-8 h-8 animate-spin text-[var(--accent)] mx-auto mb-4" />
                    <p className="akki-lead mb-1">Thinking through your hypothesis…</p>
                    <p className="text-[12.5px] text-[var(--muted)] italic">{stage || "Working…"}</p>
                  </div>
                )}
              </>
            )}
          </div>
        </main>
      </div>
    </AppShell>
  );
}
