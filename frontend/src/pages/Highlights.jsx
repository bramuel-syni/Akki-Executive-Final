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
  Loader2, ArrowRight, FileText,
} from "lucide-react";

const TYPE_CONFIG = {
  risk:        { label: "Risk",        plural: "Risks",         icon: AlertTriangle, cls: "bg-red-50 text-red-700 border-red-200" },
  opportunity: { label: "Opportunity", plural: "Opportunities", icon: TrendingUp,    cls: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  gap:         { label: "Gap",         plural: "Gaps",          icon: CircleSlash,   cls: "bg-amber-50 text-amber-700 border-amber-200" },
};

const CONF_CONFIG = {
  high:   "text-emerald-700 bg-emerald-50 border-emerald-200",
  medium: "text-amber-700 bg-amber-50 border-amber-200",
  low:    "text-slate-600 bg-slate-100 border-slate-200",
};

const TRUST_CONFIG = {
  trusted: "text-emerald-700",
  mixed:   "text-amber-700",
  weak:    "text-red-700",
  unrated: "text-slate-500",
};

function formatDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
  catch { return iso; }
}

function SignalCard({ signal, onDismiss }) {
  const cfg = TYPE_CONFIG[signal.type] || TYPE_CONFIG.risk;
  const I = cfg.icon;
  return (
    <div
      className="bg-white border border-[#E1E6ED] rounded-sm p-5 hover:border-slate-300 transition-colors group"
      data-testid={`signal-card-${signal.id}`}
    >
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider border ${cfg.cls}`}>
            <I className="w-3 h-3" strokeWidth={2} /> {cfg.label}
          </span>
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[10px] font-medium uppercase tracking-wider border ${CONF_CONFIG[signal.confidence] || CONF_CONFIG.medium}`}>
            {signal.confidence || "medium"} confidence
          </span>
          <span className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider ${TRUST_CONFIG[signal.data_trust] || TRUST_CONFIG.unrated}`}>
            <ShieldCheck className="w-3 h-3" strokeWidth={2} />
            {signal.data_trust || "unrated"}
          </span>
        </div>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <button
              className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600 transition-opacity"
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
      </div>

      <h3 className="text-lg font-medium text-[#0A1F44] tracking-tight mb-2 leading-snug">
        {signal.headline}
      </h3>
      <p className="text-sm text-slate-600 leading-relaxed mb-4 whitespace-pre-wrap">
        {signal.summary}
      </p>

      {signal.sources?.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-3 border-t border-[#E1E6ED]">
          <span className="text-[10px] uppercase tracking-[0.2em] text-slate-400 self-center">Sources</span>
          {signal.sources.map((s) => (
            <span
              key={s.doc_id}
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm text-[11px] bg-slate-50 text-slate-700 border border-[#E1E6ED]"
              data-testid={`signal-source-${signal.id}-${s.doc_id}`}
            >
              <FileText className="w-3 h-3 text-[#C9A961]" strokeWidth={2} />
              {s.doc_name}
              <span className={`ml-1 ${TRUST_CONFIG[s.data_trust] || TRUST_CONFIG.unrated}`}>· {s.data_trust}</span>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between mt-3 text-[10px] uppercase tracking-wider text-slate-400">
        <span>{formatDate(signal.created_at)}</span>
        {signal.mode && <span className="font-mono">mode: {signal.mode}</span>}
      </div>
    </div>
  );
}

export default function Highlights() {
  const { activeContext } = useAuth();
  const contextId = activeContext?.id;

  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [focus, setFocus] = useState("");

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
    try {
      const { data } = await api.post(`/contexts/${contextId}/signals/generate`, {
        focus: focus.trim() || null,
      });
      toast.success(`${data.signals.length} signals generated`);
      setFocus("");
      await load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
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

  const byType = useMemo(() => {
    const acc = { risk: 0, opportunity: 0, gap: 0 };
    signals.forEach((s) => { acc[s.type] = (acc[s.type] || 0) + 1; });
    return acc;
  }, [signals]);

  if (!contextId) {
    return <AppShell><div className="p-12 text-center text-slate-500 text-sm">No context selected.</div></AppShell>;
  }

  return (
    <AppShell>
      <div className="p-8 max-w-7xl mx-auto">
        <div className="mb-8">
          <p className="akki-overline mb-2">Highlights · Module M5</p>
          <h1 className="text-3xl font-light tracking-tight text-[#0A1F44]">Signals</h1>
          <p className="text-sm text-slate-500 mt-2 max-w-2xl">
            AKKI surfaces risks, opportunities, and gaps grounded strictly in your uploaded documents. Every signal cites its sources. Weak-trust documents are flagged.
          </p>
        </div>

        {/* Generator */}
        <div className="mb-8 bg-white border border-[#E1E6ED] rounded-sm p-5">
          <div className="flex items-end gap-3 flex-wrap">
            <div className="flex-1 min-w-[240px] space-y-1.5">
              <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Focus (optional)</p>
              <Input
                value={focus}
                onChange={(e) => setFocus(e.target.value)}
                placeholder="e.g. liquidity risk · supply chain · governance gaps"
                className="rounded-sm h-10"
                data-testid="signals-focus-input"
                disabled={generating}
              />
            </div>
            <Button
              onClick={onGenerate}
              disabled={generating}
              className="bg-[#C9A961] hover:bg-[#B39556] text-[#0A1F44] rounded-sm h-10 px-5 font-medium"
              data-testid="signals-generate-btn"
            >
              {generating ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Generating…</>
              ) : (
                <><Sparkles className="w-4 h-4 mr-2" /> Generate signals</>
              )}
            </Button>
          </div>
          <p className="text-[11px] text-slate-500 mt-3 leading-relaxed">
            Signals are generated from documents currently in your Workspace. Upload at least one document first.
            <Link to="/app/workspace" className="text-[#C9A961] hover:underline ml-1 inline-flex items-center gap-1">
              Open Workspace <ArrowRight className="w-3 h-3" />
            </Link>
          </p>
        </div>

        {/* Summary strip */}
        {signals.length > 0 && (
          <div className="grid grid-cols-3 gap-px bg-[#E1E6ED] border border-[#E1E6ED] mb-8" data-testid="signals-summary">
            {Object.entries(TYPE_CONFIG).map(([key, cfg]) => {
              const I = cfg.icon;
              return (
                <div key={key} className="bg-white p-4 flex items-center gap-3">
                  <div className={`w-9 h-9 flex items-center justify-center rounded-sm border ${cfg.cls}`}>
                    <I className="w-4 h-4" strokeWidth={2} />
                  </div>
                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">{cfg.plural}</p>
                    <p className="text-2xl font-light text-[#0A1F44]">{byType[key] || 0}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Signals list */}
        {loading ? (
          <div className="p-12 text-center text-xs uppercase tracking-widest text-slate-400">Loading…</div>
        ) : signals.length === 0 ? (
          <div className="bg-white border border-[#E1E6ED] rounded-sm p-16 text-center" data-testid="signals-empty-state">
            <Sparkles className="w-10 h-10 text-slate-300 mx-auto mb-4" strokeWidth={1.3} />
            <p className="text-sm text-slate-600 mb-1 font-medium">No signals yet</p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Upload documents to the Workspace, then press <strong>Generate signals</strong> above to let AKKI surface risks, opportunities, and gaps.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5" data-testid="signals-grid">
            {signals.map((s) => (
              <SignalCard key={s.id} signal={s} onDismiss={onDismiss} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
