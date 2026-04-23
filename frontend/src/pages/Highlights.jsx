import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import {
  Sparkles, AlertTriangle, TrendingUp, CircleSlash, ShieldCheck, X,
  Loader2, ArrowRight, FileText, Filter, Activity, MessageSquareText,
} from "lucide-react";

const TYPE_CONFIG = {
  risk:        { label: "Risk",        plural: "Risks",         icon: AlertTriangle, cls: "bg-red-50 text-red-700 border-red-200",         dot: "bg-red-500" },
  opportunity: { label: "Opportunity", plural: "Opportunities", icon: TrendingUp,    cls: "bg-emerald-50 text-emerald-700 border-emerald-200", dot: "bg-emerald-500" },
  gap:         { label: "Gap",         plural: "Gaps",          icon: CircleSlash,   cls: "bg-amber-50 text-amber-700 border-amber-200",    dot: "bg-amber-500" },
};
const CONF_CONFIG = {
  high:   "text-emerald-700 bg-emerald-50 border-emerald-200",
  medium: "text-amber-700 bg-amber-50 border-amber-200",
  low:    "text-slate-600 bg-slate-100 border-slate-200",
};
const TRUST_COLOR = {
  trusted: "text-emerald-700",
  mixed:   "text-amber-700",
  weak:    "text-red-700",
  unrated: "text-slate-500",
};

function formatRelative(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  try { return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }); }
  catch { return iso; }
}

function SignalCard({ signal, onDismiss }) {
  const cfg = TYPE_CONFIG[signal.type] || TYPE_CONFIG.risk;
  const I = cfg.icon;
  return (
    <article
      className="bg-white border-b border-[#E1E6ED] px-6 py-5 hover:bg-slate-50/40 transition-colors group relative"
      data-testid={`signal-card-${signal.id}`}
    >
      {/* Dismiss — top-right on hover */}
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <button
            className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600 transition-opacity"
            data-testid={`signal-dismiss-${signal.id}`}
            title="Dismiss"
          >
            <X className="w-4 h-4" />
          </button>
        </AlertDialogTrigger>
        <AlertDialogContent className="rounded-sm">
          <AlertDialogHeader>
            <AlertDialogTitle>Dismiss this signal?</AlertDialogTitle>
            <AlertDialogDescription>
              It will be hidden from your Highlights. The audit log preserves the generation event.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-sm">Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-red-600 hover:bg-red-700 rounded-sm"
              onClick={() => onDismiss(signal)}
              data-testid={`signal-confirm-dismiss-${signal.id}`}
            >
              Dismiss
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Type strip + meta line (Twitter-esque username row) */}
      <div className="flex items-center gap-2 text-[11px] mb-2">
        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm font-medium uppercase tracking-wider border text-[10px] ${cfg.cls}`}>
          <I className="w-3 h-3" strokeWidth={2} /> {cfg.label}
        </span>
        <span className="text-slate-300">·</span>
        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm font-medium uppercase tracking-wider border text-[10px] ${CONF_CONFIG[signal.confidence] || CONF_CONFIG.medium}`}>
          {signal.confidence || "medium"} confidence
        </span>
        <span className="text-slate-300">·</span>
        <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider ${TRUST_COLOR[signal.data_trust] || TRUST_COLOR.unrated}`}>
          <ShieldCheck className="w-3 h-3" strokeWidth={2} />
          {signal.data_trust || "unrated"}
        </span>
        <span className="text-slate-300">·</span>
        <span className="text-[10px] text-slate-400">{formatRelative(signal.created_at)}</span>
      </div>

      {/* Headline + body */}
      <h3 className="text-[17px] font-medium text-[#0A1F44] tracking-tight mb-1.5 leading-snug">
        {signal.headline}
      </h3>
      <p className="text-[14px] text-slate-700 leading-relaxed whitespace-pre-wrap">
        {signal.summary}
      </p>

      {/* Sources row */}
      {signal.sources?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {signal.sources.map((s) => (
            <Link
              key={s.doc_id}
              to={`/app/documents/${s.doc_id}`}
              className="inline-flex items-center gap-1.5 px-1.5 py-0.5 rounded-sm text-[10.5px] bg-slate-50 text-slate-700 border border-[#E1E6ED] hover:border-[#C9A961]/60 transition-colors"
              data-testid={`signal-source-${signal.id}-${s.doc_id}`}
            >
              <FileText className="w-3 h-3 text-[#C9A961]" strokeWidth={2} />
              {s.doc_name}
              <span className={`${TRUST_COLOR[s.data_trust] || TRUST_COLOR.unrated}`}>· {s.data_trust}</span>
            </Link>
          ))}
        </div>
      )}

      {/* Action row */}
      <div className="flex items-center gap-5 mt-4 text-[11px] text-slate-500">
        <Link
          to="/app/ask"
          className="inline-flex items-center gap-1.5 hover:text-[#C9A961] transition-colors"
          data-testid={`signal-ask-${signal.id}`}
        >
          <MessageSquareText className="w-3.5 h-3.5" strokeWidth={1.8} /> Ask about this
        </Link>
        {signal.sources?.[0]?.doc_id && (
          <Link
            to={`/app/documents/${signal.sources[0].doc_id}`}
            className="inline-flex items-center gap-1.5 hover:text-[#0A1F44] transition-colors"
          >
            <FileText className="w-3.5 h-3.5" strokeWidth={1.8} /> Open source
          </Link>
        )}
        {signal.mode && (
          <span className="ml-auto text-[10px] font-mono text-slate-400">mode: {signal.mode}</span>
        )}
      </div>
    </article>
  );
}

export default function Highlights() {
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;

  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [genStage, setGenStage] = useState("");
  const [focus, setFocus] = useState("");

  // Filters
  const [activeTypes, setActiveTypes] = useState({ risk: true, opportunity: true, gap: true });
  const [activeTrust, setActiveTrust] = useState({ trusted: true, mixed: true, weak: true, unrated: true });
  const [minConfidence, setMinConfidence] = useState("all"); // all|high|medium

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
    const stageTimers = [
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
      stageTimers.forEach(clearTimeout);
      setGenStage("");
      setGenerating(false);
    }
  };

  const onDismiss = async (signal) => {
    try {
      await api.delete(`/contexts/${contextId}/signals/${signal.id}`);
      setSignals((prev) => prev.filter((s) => s.id !== signal.id));
      toast.success("Signal dismissed");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  const filtered = useMemo(() => {
    return signals.filter((s) => {
      if (!activeTypes[s.type]) return false;
      if (!activeTrust[s.data_trust || "unrated"]) return false;
      if (minConfidence === "high" && s.confidence !== "high") return false;
      if (minConfidence === "medium" && s.confidence === "low") return false;
      return true;
    });
  }, [signals, activeTypes, activeTrust, minConfidence]);

  const counts = useMemo(() => {
    const acc = { risk: 0, opportunity: 0, gap: 0 };
    signals.forEach((s) => { acc[s.type] = (acc[s.type] || 0) + 1; });
    return acc;
  }, [signals]);

  const recentDocs = useMemo(() => {
    const seen = new Map();
    signals.forEach((s) => {
      (s.sources || []).forEach((src) => {
        if (!seen.has(src.doc_id)) seen.set(src.doc_id, src);
      });
    });
    return Array.from(seen.values()).slice(0, 6);
  }, [signals]);

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-slate-500 text-sm">No context selected.</div></AppShell>;
  }

  return (
    <AppShell>
      <div className="max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-[220px_1fr_280px] min-h-[calc(100vh-4rem)]">
        {/* LEFT RAIL — Filters / scope */}
        <aside className="hidden lg:block border-r border-[#E1E6ED] bg-slate-50/50" data-testid="highlights-left-rail">
          <div className="sticky top-16 p-5 space-y-5">
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <Filter className="w-3 h-3 text-[#C9A961]" />
                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-semibold">Filters</p>
              </div>
              <p className="text-[10px] text-slate-400">Scope: {activeContext.name}</p>
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-2">Type</p>
              <div className="space-y-1">
                {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
                  <label key={key} className="flex items-center gap-2 text-[12px] text-slate-700 cursor-pointer hover:text-[#0A1F44]">
                    <input
                      type="checkbox"
                      checked={activeTypes[key]}
                      onChange={(e) => setActiveTypes((p) => ({ ...p, [key]: e.target.checked }))}
                      className="rounded-sm accent-[#C9A961]"
                      data-testid={`filter-type-${key}`}
                    />
                    <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
                    <span className="flex-1">{cfg.plural}</span>
                    <span className="text-[10px] text-slate-400">{counts[key] || 0}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-2">Data trust</p>
              <div className="space-y-1">
                {["trusted", "mixed", "weak", "unrated"].map((t) => (
                  <label key={t} className="flex items-center gap-2 text-[12px] text-slate-700 cursor-pointer hover:text-[#0A1F44]">
                    <input
                      type="checkbox"
                      checked={activeTrust[t]}
                      onChange={(e) => setActiveTrust((p) => ({ ...p, [t]: e.target.checked }))}
                      className="rounded-sm accent-[#C9A961]"
                      data-testid={`filter-trust-${t}`}
                    />
                    <span className={`capitalize ${TRUST_COLOR[t]}`}>{t}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold mb-2">Confidence</p>
              <div className="space-y-1">
                {[["all", "All"], ["medium", "Medium+"], ["high", "High only"]].map(([k, l]) => (
                  <label key={k} className="flex items-center gap-2 text-[12px] text-slate-700 cursor-pointer hover:text-[#0A1F44]">
                    <input
                      type="radio"
                      name="minConfidence"
                      checked={minConfidence === k}
                      onChange={() => setMinConfidence(k)}
                      className="accent-[#C9A961]"
                      data-testid={`filter-confidence-${k}`}
                    />
                    {l}
                  </label>
                ))}
              </div>
            </div>

            <div className="pt-5 border-t border-[#E1E6ED]">
              <Link to="/app/workspace" className="text-[11px] text-[#C9A961] hover:underline inline-flex items-center gap-1">
                Manage documents <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </aside>

        {/* CENTRAL FEED */}
        <main className="border-r border-[#E1E6ED] bg-white min-h-0" data-testid="highlights-feed">
          {/* Feed header with generator */}
          <div className="sticky top-16 z-10 bg-white/95 backdrop-blur-sm border-b border-[#E1E6ED] px-6 py-4">
            <div className="flex items-baseline justify-between mb-3">
              <div>
                <p className="akki-overline mb-0.5">Highlights · Module M5</p>
                <h1 className="text-2xl font-light tracking-tight text-[#0A1F44]">Signals feed</h1>
              </div>
              <span className="text-[10px] uppercase tracking-wider text-slate-400" data-testid="signals-count">
                {filtered.length}/{signals.length} showing
              </span>
            </div>
            <div className="flex items-stretch gap-2">
              <Input
                value={focus}
                onChange={(e) => setFocus(e.target.value)}
                placeholder="Focus (optional) — e.g. liquidity · supply chain · governance"
                className="rounded-sm h-9 text-sm flex-1"
                data-testid="signals-focus-input"
                disabled={generating}
              />
              <Button
                onClick={onGenerate}
                disabled={generating}
                className="bg-[#C9A961] hover:bg-[#B39556] text-[#0A1F44] rounded-sm h-9 px-4 font-medium shrink-0"
                data-testid="signals-generate-btn"
              >
                {generating ? <><Loader2 className="w-3.5 h-3.5 mr-2 animate-spin" /> Generating…</>
                  : <><Sparkles className="w-3.5 h-3.5 mr-2" /> Generate</>}
              </Button>
            </div>
            {generating && genStage && (
              <div
                className="mt-3 flex items-center gap-2 text-[11px] text-slate-500 bg-[#C9A961]/5 border border-[#C9A961]/20 rounded-sm px-3 py-2"
                data-testid="signals-progress"
              >
                <Loader2 className="w-3 h-3 animate-spin text-[#C9A961]" />
                <span className="italic">{genStage}</span>
                <span className="ml-auto text-[10px] uppercase tracking-wider text-slate-400">Usually 20–60s</span>
              </div>
            )}
          </div>

          {/* Feed body */}
          {loading ? (
            <div className="p-16 text-center text-xs uppercase tracking-widest text-slate-400">Loading…</div>
          ) : signals.length === 0 ? (
            <div className="p-16 text-center" data-testid="signals-empty-state">
              <Sparkles className="w-10 h-10 text-slate-300 mx-auto mb-4" strokeWidth={1.3} />
              <p className="text-sm text-slate-600 mb-1 font-medium">No signals yet</p>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Upload documents to the Workspace, then press <strong>Generate</strong> to let AKKI surface risks, opportunities, and gaps.
              </p>
              <Link to="/app/workspace" className="inline-flex items-center gap-1 text-[11px] text-[#C9A961] hover:underline font-medium mt-4">
                Open Workspace <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-16 text-center text-sm text-slate-500">
              No signals match your filters.
            </div>
          ) : (
            <div data-testid="signals-grid">
              {filtered.map((s) => (
                <SignalCard key={s.id} signal={s} onDismiss={onDismiss} />
              ))}
            </div>
          )}
        </main>

        {/* RIGHT RAIL — Activity / related docs */}
        <aside className="hidden lg:block bg-slate-50/50" data-testid="highlights-right-rail">
          <div className="sticky top-16 p-5 space-y-6">
            <div>
              <div className="flex items-center gap-1.5 mb-3">
                <Activity className="w-3 h-3 text-[#C9A961]" />
                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-semibold">At a glance</p>
              </div>
              <div className="space-y-2">
                {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
                  <div key={key} className="bg-white border border-[#E1E6ED] rounded-sm p-3 flex items-center gap-3">
                    <div className={`w-8 h-8 flex items-center justify-center rounded-sm border ${cfg.cls}`}>
                      <cfg.icon className="w-3.5 h-3.5" strokeWidth={2} />
                    </div>
                    <div className="flex-1">
                      <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">{cfg.plural}</p>
                      <p className="text-xl font-light text-[#0A1F44] leading-none mt-0.5">{counts[key] || 0}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {recentDocs.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-semibold mb-2">Source documents</p>
                <div className="space-y-1">
                  {recentDocs.map((d) => (
                    <Link
                      key={d.doc_id}
                      to={`/app/documents/${d.doc_id}`}
                      className="flex items-center gap-2 px-2 py-2 bg-white border border-[#E1E6ED] rounded-sm hover:border-[#C9A961]/60 transition-colors"
                      data-testid={`recent-doc-${d.doc_id}`}
                    >
                      <FileText className="w-3.5 h-3.5 text-[#C9A961] shrink-0" strokeWidth={2} />
                      <span className="text-[11.5px] text-slate-700 truncate flex-1">{d.doc_name}</span>
                      <span className={`text-[9px] uppercase ${TRUST_COLOR[d.data_trust] || TRUST_COLOR.unrated}`}>
                        {d.data_trust}
                      </span>
                    </Link>
                  ))}
                </div>
              </div>
            )}

            <div className="pt-5 border-t border-[#E1E6ED]">
              <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-semibold mb-2">Next step</p>
              <Link
                to="/app/ask"
                className="flex items-center gap-2 bg-[#0A1F44] hover:bg-[#0E2958] text-white rounded-sm p-3 transition-colors"
              >
                <MessageSquareText className="w-4 h-4 text-[#C9A961]" />
                <div className="flex-1">
                  <p className="text-xs font-medium">Ask AKKI</p>
                  <p className="text-[10px] text-white/60">Follow up on any signal</p>
                </div>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
