import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import AppShell from "@/components/layout/AppShell";
import StreamCard from "@/components/stream/StreamCard";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  Sparkles, Loader2, ArrowRight, X, ShieldCheck, FileText,
  SlidersHorizontal, Zap, GitBranch, Eye,
} from "lucide-react";
import ActModal from "@/components/act/ActModal";
import AllLensesModal from "@/components/lens/AllLensesModal";
import HighlightsStats from "@/components/highlights/HighlightsStats";

const CONFIDENCE_LABEL = { high: "High confidence", medium: "Medium confidence", low: "Low confidence" };

export default function Highlights() {
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;

  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [genStage, setGenStage] = useState("");
  const [focus, setFocus] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [minConf, setMinConf] = useState("all");
  const [committeeFilter, setCommitteeFilter] = useState("all");
  const [actOn, setActOn] = useState(null);  // signal currently being acted on
  const [lensSignal, setLensSignal] = useState(null);  // signal for AllLensesModal

  // Reset committee filter when switching contexts
  useEffect(() => { setCommitteeFilter("all"); }, [contextId]);

  const committees = activeContext?.committees || [];

  const load = useCallback(async () => {
    if (!contextId) return;
    try {
      const { data } = await api.get(`/contexts/${contextId}/signals`);
      setSignals(data);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [contextId]);

  useEffect(() => { load(); }, [load]);

  const onGenerate = async () => {
    setGenerating(true);
    setGenStage("Reading your documents…");
    const timers = [
      setTimeout(() => setGenStage("Looking for patterns a sharp NED would notice…"), 8000),
      setTimeout(() => setGenStage("Drafting signals and cross-checking citations…"), 18000),
      setTimeout(() => setGenStage("Still working — complex packs can take up to a minute…"), 35000),
    ];
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/signals/generate`,
        { focus: focus.trim() || null },
        { timeout: 120000 }
      );
      toast.success(`${data.signals.length} signals generated`);
      setFocus("");
      await load();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally {
      timers.forEach(clearTimeout);
      setGenStage("");
      setGenerating(false);
    }
  };

  const filtered = useMemo(() => {
    return signals.filter((s) => {
      if (typeFilter !== "all" && s.type !== typeFilter) return false;
      if (minConf === "high" && s.confidence !== "high") return false;
      if (minConf === "medium" && s.confidence === "low") return false;
      if (committeeFilter !== "all" && s.committee_id !== committeeFilter) return false;
      return true;
    });
  }, [signals, typeFilter, minConf, committeeFilter]);

  const counts = useMemo(() => {
    const a = { all: signals.length, risk: 0, opportunity: 0, gap: 0 };
    signals.forEach((s) => { a[s.type] = (a[s.type] || 0) + 1; });
    return a;
  }, [signals]);

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-[var(--muted)] text-sm">No context selected.</div></AppShell>;
  }

  const scopes = [
    { key: "all", label: "All", count: counts.all },
    { key: "risk", label: "Risks", count: counts.risk },
    { key: "opportunity", label: "Opportunities", count: counts.opportunity },
    { key: "gap", label: "Gaps", count: counts.gap },
  ];

  return (
    <AppShell>
      <div className="max-w-[1280px] mx-auto px-8 py-10">
        {/* Header */}
        <div className="mb-6 akki-fade-up">
          <p className="akki-overline mb-2">Highlights · {activeContext.name}</p>
          <h1 className="akki-greeting mb-2">Signals worth your attention.</h1>
          <p className="akki-meta max-w-2xl">
            AKKI reads your documents and surfaces risks, opportunities, and gaps. Every signal cites its source.
          </p>
        </div>

        {/* Generator */}
        <div className="bg-white border border-[var(--rule)] rounded-lg p-5 mb-8 akki-fade-up">
          <div className="flex items-stretch gap-3">
            <Input
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              placeholder="Focus (optional) — e.g. liquidity · cyber exposure · succession"
              className="rounded-md h-10 text-sm flex-1 border-[var(--rule)] bg-[var(--cream)]"
              disabled={generating}
              data-testid="signals-focus-input"
            />
            <Button
              onClick={onGenerate}
              disabled={generating}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-10 px-5 font-medium"
              data-testid="signals-generate-btn"
            >
              {generating
                ? <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Generating…</>
                : <><Sparkles className="w-3.5 h-3.5 mr-2" /> Generate signals</>}
            </Button>
          </div>
          {generating && genStage && (
            <div className="mt-3 flex items-center gap-2 text-[12px] text-[var(--deep)] bg-[var(--accent-soft)] border border-[var(--accent)]/20 rounded-md px-3 py-2" data-testid="signals-progress">
              <Loader2 className="w-3 h-3 animate-spin text-[var(--accent)]" />
              <span className="italic">{genStage}</span>
              <span className="ml-auto text-[10px] uppercase tracking-wider text-[var(--muted)]">Usually 20–60s</span>
            </div>
          )}
        </div>

        {/* Stats strip — donut of confidence distribution + sparkline of
            volume-over-time. Sits above the committee filter so the reader
            first sees *shape*, then scopes, then individual cards. */}
        <HighlightsStats signals={filtered} />

        {/* Committee filter — only shown if this context has sub-committees */}
        {committees.length > 0 && (
          <div
            className="flex items-center gap-2 mb-4 flex-wrap akki-fade-up"
            data-testid="highlights-committee-filter"
          >
            <span className="akki-overline mr-1">Scope</span>
            <button
              data-selected={committeeFilter === "all"}
              onClick={() => setCommitteeFilter("all")}
              className="akki-scope-chip"
              data-testid="committee-filter-all"
            >
              Full board
            </button>
            {committees.map((cm) => (
              <button
                key={cm.id}
                data-selected={committeeFilter === cm.id}
                onClick={() => setCommitteeFilter(cm.id)}
                className="akki-scope-chip"
                data-testid={`committee-filter-${cm.id}`}
                title={cm.your_role ? `You: ${cm.your_role}` : undefined}
              >
                {cm.name}
                {cm.your_role === "chair" && (
                  <span className="ml-1.5 text-[9px] uppercase tracking-wider text-[var(--accent)]">chair</span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* Filter bar */}
        <div className="flex items-center gap-6 mb-6 border-b border-[var(--rule)] pb-1 akki-fade-up" data-testid="highlights-filters">
          {scopes.map((s) => (
            <button
              key={s.key}
              data-selected={typeFilter === s.key}
              onClick={() => setTypeFilter(s.key)}
              className="akki-scope-chip"
              data-testid={`filter-${s.key}`}
            >
              {s.label} <span className="text-[var(--muted)]/70 ml-1">{s.count}</span>
            </button>
          ))}
          <div className="ml-auto flex items-center gap-3">
            <SlidersHorizontal className="w-3.5 h-3.5 text-[var(--muted)]" />
            {[["all", "All"], ["medium", "Medium+"], ["high", "High"]].map(([k, l]) => (
              <button
                key={k}
                data-selected={minConf === k}
                onClick={() => setMinConf(k)}
                className="akki-scope-chip text-[13px]"
                data-testid={`filter-conf-${k}`}
              >
                {l}
              </button>
            ))}
          </div>
        </div>

        {/* Stream */}
        {loading ? (
          <div className="p-16 text-center text-xs uppercase tracking-widest text-[var(--muted)]">Loading…</div>
        ) : signals.length === 0 ? (
          <div className="bg-white border border-[var(--rule)] rounded-lg p-12 text-center" data-testid="signals-empty-state">
            <Sparkles className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
            <p className="akki-lead mb-2">No signals yet.</p>
            <p className="text-[13px] text-[var(--muted)] mb-5 max-w-md mx-auto">
              Upload documents to the Workspace, then press Generate to let AKKI surface risks, opportunities, and gaps.
            </p>
            <Link to="/app/workspace" className="akki-gesture">
              Open Workspace <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-16 text-center text-sm text-[var(--muted)]">No signals match your filter.</div>
        ) : (
          <motion.div
            className="space-y-4"
            data-testid="signals-grid"
            initial="hidden" animate="show"
            variants={{
              hidden: {},
              show: { transition: { staggerChildren: 0.06, delayChildren: 0.05 } },
            }}
          >
            {filtered.map((s) => (
              <motion.div
                key={s.id}
                variants={{
                  hidden: { opacity: 0, y: 8 },
                  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.2, 0.8, 0.2, 1] } },
                }}
              >
                <SignalStreamCard signal={s} onLoad={load} onAct={setActOn} onLens={setLensSignal} />
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>

      <ActModal
        open={!!actOn}
        onOpenChange={(open) => { if (!open) setActOn(null); }}
        signal={actOn}
        contextId={contextId}
      />

      <AllLensesModal
        open={!!lensSignal}
        onClose={() => setLensSignal(null)}
        signal={lensSignal}
      />
    </AppShell>
  );
}

/** Thin wrapper that maps a signal to the StreamCard shape + adds a summary row
 *  with inline [doc:xxx] citations and dismiss action. */
function SignalStreamCard({ signal, onLoad, onAct, onLens }) {
  const [confirmingDismiss, setConfirmingDismiss] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [traceEvents, setTraceEvents] = useState(null);
  const [traceLoading, setTraceLoading] = useState(false);

  const onDismiss = async () => {
    try {
      await api.delete(`/contexts/${signal.context_id}/signals/${signal.id}`);
      toast.success("Signal dismissed");
      onLoad?.();
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const openTrace = async () => {
    setTraceOpen(true);
    if (traceEvents || !signal.pipeline_run_id) return;
    setTraceLoading(true);
    try {
      const { data } = await api.get(
        `/contexts/${signal.context_id}/pipeline/events`,
        { params: { pipeline_run_id: signal.pipeline_run_id, limit: 50 } }
      );
      setTraceEvents(data || []);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setTraceLoading(false); }
  };

  // Render summary with inline [doc:xxx] chips
  const summaryNodes = useMemo(() => renderWithCitations(signal.summary, signal.sources), [signal]);

  const chips = [
    { label: CONFIDENCE_LABEL[signal.confidence] || "Medium confidence" },
    { label: (signal.data_trust || "unrated") + " data" },
  ];

  return (
    <article
      className="akki-stream-card group akki-fade-up"
      data-severity={signal.type === "opportunity" ? "opportunity" : signal.type === "gap" ? "gap" : "risk"}
      data-testid={`signal-card-${signal.id}`}
    >
      <button
        onClick={(e) => { e.stopPropagation(); confirmingDismiss ? onDismiss() : setConfirmingDismiss(true); setTimeout(() => setConfirmingDismiss(false), 3000); }}
        className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 text-[var(--muted)] hover:text-[var(--accent)] transition-opacity"
        title={confirmingDismiss ? "Click again to confirm" : "Dismiss"}
        data-testid={`signal-dismiss-${signal.id}`}
      >
        <X className="w-4 h-4" />
      </button>

      {/* Row 1 */}
      <div className="flex items-center gap-3 mb-3">
        <span className="akki-type-badge inline-flex items-center gap-1.5 capitalize">
          {signal.type}
        </span>
        <span className="text-[12px] text-[var(--muted)]">{relativeTime(signal.created_at)}</span>
        <span className={`text-[10px] uppercase tracking-wider ml-auto flex items-center gap-1 ${
          signal.data_trust === "trusted" ? "text-[var(--opportunity)]" :
          signal.data_trust === "weak" ? "text-[var(--risk)]" : "text-[var(--muted)]"
        }`}>
          <ShieldCheck className="w-3 h-3" /> {signal.data_trust || "unrated"}
        </span>
      </div>

      {/* Row 2: Georgia headline + summary */}
      <p className="akki-lead mb-2">{signal.headline}</p>
      <p className="text-[14px] text-[var(--deep)] leading-relaxed mb-4 whitespace-pre-wrap">
        {summaryNodes}
      </p>

      {/* Row 3: chips + gestures */}
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div className="flex flex-wrap gap-2">
          {chips.map((c, i) => <span key={i} className="akki-context-chip">{c.label}</span>)}
        </div>
        <div className="flex gap-4 items-center">
          {signal.sources?.[0] && (
            <Link to={`/app/documents/${signal.sources[0].doc_id}`} className="akki-gesture text-[13px]">
              Open source <ArrowRight className="w-3 h-3" />
            </Link>
          )}
          {signal.pipeline_run_id && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); openTrace(); }}
              className="akki-gesture text-[13px]"
              data-testid={`signal-trace-${signal.id}`}
            >
              <GitBranch className="w-3 h-3" strokeWidth={2} /> Trace
            </button>
          )}
          {/* High-conf risk/gap signals get the All-lenses CTA promoted to a
              full pill button — the chairman's instinct to stress-test
              something serious from every angle. */}
          {(signal.confidence === "high" && (signal.type === "risk" || signal.type === "gap")) ? (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onLens?.(signal); }}
              className="inline-flex items-center gap-1.5 bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-full px-3 py-1.5 text-[12px] font-medium transition-colors"
              data-testid={`signal-lens-primary-${signal.id}`}
            >
              <Eye className="w-3 h-3" strokeWidth={2.2} />
              See this through all six lenses
            </button>
          ) : (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onLens?.(signal); }}
              className="akki-gesture text-[13px]"
              data-testid={`signal-lens-all-${signal.id}`}
              title="Apply every lens to this signal, in parallel"
            >
              <Eye className="w-3 h-3" strokeWidth={2} /> All lenses
            </button>
          )}
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onAct?.(signal); }}
            className="akki-gesture text-[13px]"
            data-testid={`signal-act-${signal.id}`}
          >
            <Zap className="w-3 h-3" strokeWidth={2} /> Act on this
          </button>
        </div>
      </div>

      {/* Trace drawer — pipeline audit for this signal */}
      {traceOpen && (
        <div
          className="mt-5 pt-5 border-t border-[var(--rule)] akki-fade-up"
          data-testid={`signal-trace-drawer-${signal.id}`}
        >
          <div className="flex items-center gap-2 mb-3">
            <GitBranch className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
            <p className="akki-overline">How this signal was generated</p>
            <button
              onClick={() => setTraceOpen(false)}
              className="ml-auto text-[11px] text-[var(--muted)] hover:text-[var(--accent)]"
            >
              Close
            </button>
          </div>
          {signal.verifier_note && (
            <div className="mb-3 bg-[var(--accent-soft)]/60 border-l-2 border-[var(--accent)] pl-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-1">Verifier's note</p>
              <p className="akki-serif italic text-[13.5px] text-[var(--deep)] leading-relaxed">
                {signal.verifier_note}
              </p>
            </div>
          )}
          {traceLoading ? (
            <p className="text-[12px] text-[var(--muted)] italic py-2">Loading trace…</p>
          ) : traceEvents && traceEvents.length > 0 ? (
            <ol className="relative pl-5 space-y-2.5">
              {traceEvents.slice().reverse().map((ev) => (
                <li key={ev.id} className="relative">
                  <span className="absolute -left-5 top-1.5 w-2 h-2 rounded-full bg-[var(--accent)]" />
                  <div className="flex items-baseline gap-2">
                    <span className="text-[11.5px] font-mono text-[var(--accent)]">{ev.type}</span>
                    <span className="text-[10.5px] text-[var(--muted)]">{new Date(ev.created_at).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-[12px] text-[var(--deep)] leading-snug mt-0.5">
                    {summariseEvent(ev)}
                  </p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-[12px] text-[var(--muted)] italic py-2">No pipeline events recorded.</p>
          )}
          <p className="text-[10.5px] text-[var(--muted)] mt-3 italic">
            Pipeline run: <span className="font-mono">{signal.pipeline_run_id?.slice(0, 8)}…</span>
          </p>
        </div>
      )}
    </article>
  );
}

function summariseEvent(ev) {
  const p = ev.payload || {};
  switch (ev.type) {
    case "pipeline.started":
      return `${p.doc_count || 0} documents in scope${p.focus ? ` · focus: ${p.focus}` : ""}`;
    case "signal.candidate_drafted":
      return `Stage 1 — ${p.count || 0} candidates drafted by LLM (mode: ${p.mode || "synth"})`;
    case "signal.verified":
      return `Stage 2 — ${p.accepted || 0} accepted, ${p.rejected || 0} rejected${p.verifier_failed ? " (verifier failed — candidates kept)" : ""}`;
    case "signal.persisted":
      return `Stage 3 — ${p.count || 0} signals written to the board stream`;
    case "pipeline.completed":
      return `Finished — ${p.persisted || 0} persisted, ${p.rejected || 0} rejected`;
    default:
      return ev.type;
  }
}

function renderWithCitations(text, sources) {
  if (!text) return null;
  const BLOCK = /\[doc:[a-f0-9-]+(?:[,\s]+doc:[a-f0-9-]+)*\]/g;
  const ID = /[a-f0-9-]{8,}/g;
  const parts = text.split(BLOCK);
  const matches = text.match(BLOCK) || [];
  const nameById = Object.fromEntries((sources || []).map((s) => [s.doc_id, s]));
  const out = [];
  parts.forEach((p, i) => {
    if (p) out.push(<span key={`p-${i}`}>{p}</span>);
    if (matches[i]) {
      const ids = matches[i].match(ID) || [];
      ids.forEach((id, j) => {
        const src = nameById[id];
        const label = src?.doc_name || id.slice(0, 8);
        out.push(
          <Link
            key={`c-${i}-${j}`}
            to={`/app/documents/${id}`}
            className="inline-flex items-center gap-0.5 px-1 py-0 mx-0.5 rounded-sm text-[10.5px] bg-[var(--accent-soft)] text-[var(--accent)] border border-[var(--accent)]/30 font-medium hover:bg-[var(--accent)]/15 transition-colors align-baseline"
            title={label}
          >
            <FileText className="w-2.5 h-2.5" strokeWidth={2.2} />
            {label}
          </Link>
        );
      });
    }
  });
  return out;
}

function relativeTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  try { return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }); }
  catch { return iso; }
}
