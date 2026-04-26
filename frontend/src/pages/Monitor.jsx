import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  Activity, AlertTriangle, ArrowRight, Briefcase, Eye, FileText,
  Landmark, Send, Sparkles, TrendingUp, Users, ScrollText, Layers,
} from "lucide-react";

/**
 * Monitor — role-adaptive mission-critical touchpoints.
 *
 * Light experience that answers "what should I be paying attention to as
 * a CEO/CFO/COO/Commercial/NED right now". Composes from existing data
 * (signals, cycle, reports, briefings, document engagement, mentions)
 * via GET /api/contexts/{cid}/monitor?function=...
 *
 * Function selection persists in localStorage so the user lands on the
 * same view next time without round-tripping the backend.
 */

const EXEC_FUNCTIONS = [
  { key: "ceo", label: "CEO", description: "Cross-functional pulse" },
  { key: "cfo", label: "CFO", description: "Financial · Risk · Audit" },
  { key: "coo", label: "COO", description: "Operations · People" },
  { key: "commercial", label: "Commercial", description: "Strategy · Growth" },
  { key: "other", label: "Other", description: "Generic executive view" },
];

const NED_FUNCTIONS = [
  { key: "ned", label: "NED", description: "Cross-board reading" },
];

function getDefaultFunction(activeRole) {
  if (activeRole === "ned") return "ned";
  try {
    const saved = localStorage.getItem("akki_monitor_function");
    if (saved && EXEC_FUNCTIONS.some((f) => f.key === saved)) return saved;
  } catch { /* ignore */ }
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
  const { activeContext, activeRole } = useAuth();
  const cid = activeContext?.id;
  const [fn, setFn] = useState(() => getDefaultFunction(activeRole));
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  // Re-pin function when role flips
  useEffect(() => {
    setFn(getDefaultFunction(activeRole));
  }, [activeRole]);

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

  const onPickFn = (key) => {
    setFn(key);
    if (activeRole !== "ned") {
      try { localStorage.setItem("akki_monitor_function", key); } catch { /* ignore */ }
    }
  };

  const FUNCTIONS = activeRole === "ned" ? NED_FUNCTIONS : EXEC_FUNCTIONS;
  const activeFn = useMemo(() => FUNCTIONS.find((f) => f.key === fn) || FUNCTIONS[0], [FUNCTIONS, fn]);

  return (
    <AppShell>
      <div className="h-[calc(100vh-4rem)] max-w-[1100px] mx-auto px-8 overflow-y-auto" data-testid="monitor-page">
        <div className="pt-10 pb-8">
          <p className="akki-overline mb-2 flex items-center gap-2">
            <Activity className="w-3 h-3 text-[var(--accent)]" /> Monitor · Mission-critical touchpoints
          </p>
          <h1 className="akki-greeting mb-2">What needs your attention.</h1>
          <p className="akki-meta max-w-2xl">
            A focused view of {activeContext?.name || "this context"} adapted to how {activeRole === "ned" ? "you read across boards" : "you run your function"}. Tiles compose from your signals, cycle, reports, and document engagement.
          </p>

          {/* Function chip strip — only shown for executives */}
          {activeRole !== "ned" && (
            <div className="mt-6 flex items-center gap-2 flex-wrap" data-testid="monitor-function-strip">
              <span className="text-[11px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono mr-2">Acting as</span>
              {FUNCTIONS.map((f) => (
                <button
                  key={f.key}
                  onClick={() => onPickFn(f.key)}
                  className={`px-3 py-1.5 text-[12.5px] rounded-full border transition-colors ${
                    fn === f.key
                      ? "bg-[var(--ink)] text-white border-[var(--ink)]"
                      : "bg-white border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"
                  }`}
                  data-testid={`monitor-fn-${f.key}`}
                  title={f.description}
                >
                  {f.label}
                </button>
              ))}
              <span className="text-[11.5px] text-[var(--muted)] italic ml-2">{activeFn.description}</span>
            </div>
          )}
        </div>

        {loading ? (
          <div className="bg-white border border-[var(--rule)] rounded-lg p-12 text-center text-[12px] uppercase tracking-widest text-[var(--muted)]">
            Reading what's moving…
          </div>
        ) : !data ? (
          <div className="bg-white border border-[var(--rule)] rounded-lg p-12 text-center text-[13px] text-[var(--muted)] italic">
            Nothing to monitor yet on this context.
          </div>
        ) : (
          <MonitorTiles data={data} fn={fn} />
        )}
      </div>
    </AppShell>
  );
}

function MonitorTiles({ data, fn }) {
  const totalAttention =
    (data.cycle?.overdue?.length || 0) +
    (data.cycle?.awaiting_approval?.length || 0) +
    (data.reports_pending?.length || 0);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-5 pb-12" data-testid="monitor-tiles">
      {/* Signals tile */}
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
            <Link to="/app/highlights" className="akki-gesture text-[12.5px] mt-3 inline-flex items-center gap-1">
              Open Signals <ArrowRight className="w-3 h-3" />
            </Link>
          </>
        ) : (
          <p className="text-[13px] text-[var(--muted)] italic">No signals match your function on this context.</p>
        )}
      </Tile>

      {/* Cycle tile */}
      <Tile
        icon={Send}
        kicker="Reporting cycle"
        title={
          totalAttention > 0
            ? `${totalAttention} item${totalAttention === 1 ? "" : "s"} need${totalAttention === 1 ? "s" : ""} you.`
            : "Cycle is clear."
        }
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
        {data.cycle?.in_flight?.length > 0 && totalAttention === 0 && (
          <div className="mb-3">
            <p className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] mb-1.5">Out for response</p>
            <ul className="space-y-1">
              {data.cycle.in_flight.slice(0, 3).map((c) => (
                <li key={c.id} className="text-[12.5px] text-[var(--deep)]">
                  <strong>{c.reportee_name}</strong> · due {c.deadline_date}
                </li>
              ))}
            </ul>
          </div>
        )}
        {totalAttention === 0 && data.cycle?.in_flight?.length === 0 && data.cycle?.matched_reportees === 0 && (
          <p className="text-[13px] text-[var(--muted)] italic">No reportees match your function. Add areas of ownership in the Cycle page.</p>
        )}
        <Link to="/app/cycle" className="akki-gesture text-[12.5px] mt-2 inline-flex items-center gap-1">
          Open Cycle <ArrowRight className="w-3 h-3" />
        </Link>
      </Tile>

      {/* Reports tile */}
      <Tile
        icon={ScrollText}
        kicker="Reports awaiting you"
        title={data.reports_pending?.length ? `${data.reports_pending.length} on your desk.` : "No reports waiting."}
        testid="monitor-tile-reports"
      >
        {data.reports_pending?.length > 0 ? (
          <ul className="space-y-2">
            {data.reports_pending.slice(0, 4).map((r) => (
              <li key={r.id} className="text-[12.5px] text-[var(--deep)] flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="truncate">{r.title}</p>
                  <p className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] mt-0.5">
                    {r.stage === "draft" ? "Your draft" : "Pending review"} · {fmtRelative(r.updated_at)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-[var(--muted)] italic">Inbox clear.</p>
        )}
        <Link to="/app/cycle?tab=reports" className="akki-gesture text-[12.5px] mt-3 inline-flex items-center gap-1">
          Open reports <ArrowRight className="w-3 h-3" />
        </Link>
      </Tile>

      {/* Document engagement OR NED open threads */}
      {fn === "ned" ? (
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
          <Link to="/app/workspace" className="akki-gesture text-[12.5px] mt-3 inline-flex items-center gap-1">
            Open Document Journal <ArrowRight className="w-3 h-3" />
          </Link>
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
