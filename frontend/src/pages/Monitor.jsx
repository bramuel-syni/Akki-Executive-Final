import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import StrategicGoalsPanel from "@/components/monitor/StrategicGoalsPanel";
import {
  Activity, AlertTriangle, ArrowRight, Eye, FileText,
  Send, Sparkles, Target, ScrollText, Layers, Pencil, X, Loader2,
} from "lucide-react";

/**
 * Monitor — board-level performance tracker.
 *
 * What's reported:
 *   • Strategic Goals — the headline (board-tracked KPIs against targets +
 *     dates, with current score and probability of success)
 *   • Function-relevant signals/cycle/reports/engagement (composed by
 *     /api/contexts/{cid}/monitor)
 *   • For NEDs — the same goals appear in scorecard form (expectation +
 *     score + probability)
 *
 * Function (CEO/CFO/COO/Commercial) is NOT user-selectable. It's derived
 * from account.preferences.executive_function. The user sets it once via
 * the small "Set your function" affordance; thereafter Monitor renders
 * the role's view automatically.
 */

const FUNCTION_LABEL = {
  ceo: "Chief Executive",
  cfo: "Chief Financial",
  coo: "Chief Operating",
  commercial: "Commercial",
  ned: "Non-Executive Director",
};

const FUNCTION_DESCRIPTION = {
  ceo: "Cross-functional pulse",
  cfo: "Financial · Risk · Audit",
  coo: "Operations · People",
  commercial: "Strategy · Growth",
  ned: "Cross-board reading",
};

function deriveFunction(account, activeRole) {
  if (activeRole === "ned") return "ned";
  const stored = account?.preferences?.executive_function;
  if (stored && ["ceo", "cfo", "coo", "commercial"].includes(stored)) return stored;
  return "ceo";
}

function fmtRelative(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  } catch { return "—"; }
}

export default function Monitor() {
  const { account, activeContext, activeRole, refreshContexts } = useAuth();
  const cid = activeContext?.id;
  const fn = deriveFunction(account, activeRole);
  const fnSet = !!account?.preferences?.executive_function;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editFn, setEditFn] = useState(false);

  const load = useCallback(async () => {
    if (!cid) return;
    setLoading(true);
    try {
      const { data: d } = await api.get(`/contexts/${cid}/monitor`, { params: { function: fn } });
      setData(d);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setLoading(false); }
  }, [cid, fn]);
  useEffect(() => { load(); }, [load]);

  const isNED = activeRole === "ned";

  return (
    <AppShell>
      <div className="h-[calc(100vh-4rem)] akki-w-medium px-8 overflow-y-auto" data-testid="monitor-page">
        <div className="pt-10 pb-6">
          <p className="akki-overline mb-2 flex items-center gap-2">
            <Activity className="w-3 h-3 text-[var(--accent)]" />
            Monitor · {isNED ? "Board scorecard" : "Performance tracker"}
          </p>
          <h1 className="akki-greeting mb-2">
            {isNED ? "What's expected. Where it stands." : "Strategic goals against where you are."}
          </h1>
          <p className="akki-meta max-w-2xl">
            {isNED
              ? `Each expectation set for ${activeContext?.name || "this board"}, the current score, and the probability of hitting it.`
              : `${FUNCTION_LABEL[fn] || "Executive"} view of ${activeContext?.name || "this company"} — board-tracked goals you own, plus signals and cycle items adapted to your function.`}
          </p>

          {/* Function indicator — read-only, with a small change affordance.
              The chip strip from iter27 is gone — the system populates this
              based on profile, not user selection. */}
          {!isNED && (
            <div className="mt-4 flex items-center gap-2 text-[12px]" data-testid="monitor-function-indicator">
              <span className="akki-context-chip">{FUNCTION_LABEL[fn]} ({fn.toUpperCase()})</span>
              <span className="text-[var(--muted)] italic">{FUNCTION_DESCRIPTION[fn]}</span>
              <button
                onClick={() => setEditFn(true)}
                className="text-[var(--muted)] hover:text-[var(--accent)] inline-flex items-center gap-1 ml-1"
                data-testid="monitor-edit-fn"
              >
                <Pencil className="w-3 h-3" /> change
              </button>
            </div>
          )}

          {/* First-time onboarding nudge — fires once until the user picks
              a function. Quiet inline editorial banner, not a modal. */}
          {!isNED && !fnSet && (
            <div
              className="mt-5 bg-[var(--cream-deep)]/60 border border-[var(--accent)]/20 rounded-md px-4 py-3 flex items-start gap-3"
              data-testid="monitor-fn-nudge"
            >
              <Sparkles className="w-4 h-4 text-[var(--accent)] mt-0.5 shrink-0" />
              <div className="flex-1">
                <p className="text-[12.5px] text-[var(--ink)] leading-relaxed">
                  AKKI is showing you the <strong>CEO</strong> view by default. Set your function once and Monitor will adapt — signals filtered to what your role tracks, goals scoped to your department.
                </p>
              </div>
              <Button
                size="sm"
                onClick={() => setEditFn(true)}
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[12px] h-7"
                data-testid="monitor-fn-nudge-cta"
              >
                Set my function
              </Button>
            </div>
          )}
        </div>

        {/* PRIMARY — Strategic goals tracker */}
        <StrategicGoalsPanel
          contextId={cid}
          fn={fn}
          isNED={isNED}
          onChange={load}
        />

        {/* SECONDARY — function-relevant tiles */}
        {loading ? (
          <div className="bg-white border border-[var(--rule)] rounded-lg p-12 text-center text-[12px] uppercase tracking-widest text-[var(--muted)] mt-6">
            Reading what's moving…
          </div>
        ) : data ? (
          <div className="mt-8" data-testid="monitor-secondary">
            <p className="akki-overline mb-3">Around the goals</p>
            <SecondaryTiles data={data} fn={fn} isNED={isNED} />
          </div>
        ) : null}

        {editFn && (
          <FunctionPickerModal
            current={fn}
            onClose={() => setEditFn(false)}
            onSaved={async () => { setEditFn(false); await refreshContexts?.(); load(); }}
          />
        )}
      </div>
    </AppShell>
  );
}

function SecondaryTiles({ data, fn, isNED }) {
  const totalAttention =
    (data.cycle?.overdue?.length || 0) +
    (data.cycle?.awaiting_approval?.length || 0) +
    (data.reports_pending?.length || 0);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pb-12" data-testid="monitor-tiles">
      <Tile
        icon={Sparkles}
        kicker={fn === "cfo" ? "Financial & risk signals" : fn === "coo" ? "Operational signals" : fn === "commercial" ? "Strategic & opportunity signals" : "Signals"}
        title={data.signals?.total ? `${data.signals.total} signal${data.signals.total === 1 ? "" : "s"} on your radar.` : "Quiet on signals."}
        testid="monitor-tile-signals"
      >
        {data.signals?.total > 0 ? (
          <>
            <div className="flex gap-3 text-[12px] mb-3 flex-wrap">
              <Stat label="high confidence" value={data.signals.high_confidence} />
              <Stat label="risks" value={data.signals.risks} tone="warning" />
              <Stat label="opportunities" value={data.signals.opportunities} tone="positive" />
            </div>
            <ul className="space-y-2">
              {data.signals.top.slice(0, 3).map((s) => (
                <li key={s.id} className="text-[12.5px] text-[var(--deep)] leading-snug border-l-2 border-[var(--rule)] pl-3 hover:border-[var(--accent)]">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--muted)] mr-2 font-mono">{s.type}</span>
                  {s.headline}
                </li>
              ))}
            </ul>
            <Link to="/app/prepare" className="akki-gesture text-[12.5px] mt-3 inline-flex items-center gap-1">
              Open Signals <ArrowRight className="w-3 h-3" />
            </Link>
          </>
        ) : (
          <p className="text-[13px] text-[var(--muted)] italic">No signals match your function on this company.</p>
        )}
      </Tile>

      <Tile
        icon={Send}
        kicker="Reporting cycle"
        title={totalAttention > 0 ? `${totalAttention} item${totalAttention === 1 ? "" : "s"} need${totalAttention === 1 ? "s" : ""} you.` : "Cycle is clear."}
        testid="monitor-tile-cycle"
      >
        {data.cycle?.overdue?.length > 0 && (
          <div className="mb-3" data-testid="monitor-overdue">
            <p className="text-[10.5px] uppercase tracking-wider text-red-700 font-medium mb-1.5">Overdue</p>
            <ul className="space-y-1">
              {data.cycle.overdue.slice(0, 3).map((c) => (
                <li key={c.id} className="text-[12.5px] text-[var(--deep)] flex items-start gap-2">
                  <AlertTriangle className="w-3 h-3 text-red-700 mt-0.5 shrink-0" />
                  <span><strong>{c.reportee_name}</strong> · {c.cycle_name} · {c.overdue_days}d past</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {data.cycle?.awaiting_approval?.length > 0 && (
          <div className="mb-3" data-testid="monitor-awaiting">
            <p className="text-[10.5px] uppercase tracking-wider text-amber-700 font-medium mb-1.5">Awaiting your sign-off</p>
            <ul className="space-y-1">
              {data.cycle.awaiting_approval.slice(0, 3).map((c) => (
                <li key={c.id} className="text-[12.5px] text-[var(--deep)]">
                  <strong>{c.reportee_name}</strong> · {c.questions_count} draft question{c.questions_count === 1 ? "" : "s"}
                </li>
              ))}
            </ul>
          </div>
        )}
        {totalAttention === 0 && data.cycle?.matched_reportees === 0 && (
          <p className="text-[13px] text-[var(--muted)] italic">No reportees match your function. Add areas of ownership in the Cycle page.</p>
        )}
        <Link to="/app/cycle" className="akki-gesture text-[12.5px] mt-2 inline-flex items-center gap-1">
          Open Cycle <ArrowRight className="w-3 h-3" />
        </Link>
      </Tile>

      <Tile
        icon={ScrollText}
        kicker="Reports awaiting you"
        title={data.reports_pending?.length ? `${data.reports_pending.length} on your desk.` : "No reports waiting."}
        testid="monitor-tile-reports"
      >
        {data.reports_pending?.length > 0 ? (
          <ul className="space-y-2">
            {data.reports_pending.slice(0, 4).map((r) => (
              <li key={r.id} className="text-[12.5px] text-[var(--deep)]">
                <p className="truncate">{r.title}</p>
                <p className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] mt-0.5">
                  {r.stage === "draft" ? "Your draft" : "Pending review"} · {fmtRelative(r.updated_at)}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-[var(--muted)] italic">Inbox clear.</p>
        )}
      </Tile>

      {isNED ? (
        <Tile
          icon={Layers}
          kicker="Open threads"
          title={data.ned?.open_threads ? `${data.ned.open_threads} mention${data.ned.open_threads === 1 ? "" : "s"} unread.` : "Inbox quiet."}
          testid="monitor-tile-ned"
        >
          {data.ned?.recent_mentions?.length > 0 ? (
            <ul className="space-y-2">
              {data.ned.recent_mentions.slice(0, 4).map((m, i) => (
                <li key={i} className="text-[12.5px] text-[var(--deep)] border-l-2 border-[var(--rule)] pl-3">
                  {m.preview}
                  <p className="text-[10.5px] text-[var(--muted)] mt-0.5">{fmtRelative(m.created_at)}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-[var(--muted)] italic">No unread mentions across your boards.</p>
          )}
        </Tile>
      ) : (
        <Tile
          icon={Eye}
          kicker="Document engagement"
          title={data.document_engagement?.length ? `Your packs are being read.` : "No reads yet on docs you've uploaded."}
          testid="monitor-tile-engagement"
        >
          {data.document_engagement?.length > 0 ? (
            <ul className="space-y-2">
              {data.document_engagement.slice(0, 5).map((d) => (
                <li key={d.id} className="text-[12.5px] text-[var(--deep)] flex items-center justify-between gap-3">
                  <Link to={`/app/documents/${d.id}`} className="truncate hover:text-[var(--accent)] flex-1 min-w-0">
                    {d.name}
                  </Link>
                  <span className="text-[11.5px] text-[var(--muted)] shrink-0">
                    {d.unique_readers} reader{d.unique_readers === 1 ? "" : "s"}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-[var(--muted)] italic">Last-30-days view counts will appear once readers open your packs.</p>
          )}
        </Tile>
      )}
    </div>
  );
}

function Tile({ icon: Icon, kicker, title, children, testid }) {
  return (
    <article className="bg-white border border-[var(--rule)] rounded-md p-5 relative overflow-hidden" data-testid={testid}>
      <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)]/20" />
      <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono mb-2 flex items-center gap-1.5">
        <Icon className="w-3 h-3" /> {kicker}
      </p>
      <h3 className="akki-serif text-[18px] text-[var(--ink)] leading-snug mb-3">{title}</h3>
      {children}
    </article>
  );
}

function Stat({ label, value, tone = "neutral" }) {
  const toneClass = tone === "warning" ? "text-amber-700" : tone === "positive" ? "text-emerald-700" : "text-[var(--ink)]";
  return (
    <span className={`inline-flex items-baseline gap-1 ${toneClass}`}>
      <strong className="text-[14px]">{value}</strong>
      <span className="text-[10.5px] uppercase tracking-wider text-[var(--muted)]">{label}</span>
    </span>
  );
}

function FunctionPickerModal({ current, onClose, onSaved }) {
  const [pick, setPick] = useState(current);
  const [busy, setBusy] = useState(false);
  const FUNCTIONS = [
    { key: "ceo", label: "Chief Executive (CEO)", desc: "Cross-functional pulse" },
    { key: "cfo", label: "Chief Financial (CFO)", desc: "Financial · Risk · Audit" },
    { key: "coo", label: "Chief Operating (COO)", desc: "Operations · People" },
    { key: "commercial", label: "Commercial", desc: "Strategy · Growth" },
  ];
  const save = async () => {
    setBusy(true);
    try {
      await api.patch("/accounts/me", { preferences: { executive_function: pick } });
      toast.success("Function set.");
      onSaved();
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-white rounded-md shadow-xl border border-[var(--rule)] w-full max-w-md mx-4 p-6" onClick={(e) => e.stopPropagation()} data-testid="monitor-fn-modal">
        <div className="flex items-center justify-between mb-4">
          <h2 className="akki-serif text-[18px] text-[var(--ink)]">Set your function</h2>
          <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--ink)]"><X className="w-4 h-4" /></button>
        </div>
        <p className="text-[12.5px] text-[var(--muted)] italic mb-4">
          We'll surface signals, cycle items, and strategic goals adapted to this function. You can change it any time.
        </p>
        <div className="space-y-2">
          {FUNCTIONS.map((f) => (
            <button
              key={f.key}
              onClick={() => setPick(f.key)}
              className={`w-full text-left px-4 py-3 rounded-md border transition-colors ${pick === f.key ? "border-[var(--accent)] bg-[var(--cream-deep)]" : "border-[var(--rule)] hover:bg-[var(--cream-deep)]/50"}`}
              data-testid={`monitor-fn-pick-${f.key}`}
            >
              <p className="text-[14px] text-[var(--ink)] font-medium">{f.label}</p>
              <p className="text-[12px] text-[var(--muted)] italic">{f.desc}</p>
            </button>
          ))}
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <Button type="button" variant="ghost" onClick={onClose} className="text-[12px] h-8">Cancel</Button>
          <Button onClick={save} disabled={busy} className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[12px] h-8" data-testid="monitor-fn-save">
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}
