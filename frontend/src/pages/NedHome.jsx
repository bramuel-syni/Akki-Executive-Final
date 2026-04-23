import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  CalendarDays, Users, FileText, Sparkles, ArrowRight, Plus,
  Landmark, AlertTriangle, TrendingUp, CircleSlash, ShieldCheck,
  Layers, ScrollText,
} from "lucide-react";

const SECTOR_LABEL = {
  banking: "Banking",
  insurance: "Insurance",
  retail: "Retail",
  fintech: "Fintech",
  telco: "Telco",
  energy: "Energy",
  healthcare: "Healthcare",
  logistics: "Logistics",
  mining: "Mining",
  agriculture: "Agriculture",
  manufacturing: "Manufacturing",
  public_sector: "Public sector",
};

/** Stable pseudo-random that produces a "days until next meeting" based on context id.
 *  Not a real calendar — this is a preview placeholder until M6 Integrations land. */
function daysUntilNextMeeting(contextId) {
  let h = 0;
  for (let i = 0; i < (contextId || "").length; i++) h = (h * 31 + contextId.charCodeAt(i)) >>> 0;
  return (h % 28) + 1; // 1–28 days
}

function formatMeetingDate(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

function BoardCard({ ctx, stats, daysAway }) {
  const urgent = stats?.risks_high || 0;
  const sector = ctx.sector ? SECTOR_LABEL[ctx.sector] || ctx.sector : null;

  return (
    <Link
      to="/app/highlights"
      onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent("akki:switch-context", { detail: ctx.id })); }}
      className="block bg-white border border-[#E1E6ED] rounded-sm p-5 hover:border-[#C9A961]/60 hover:shadow-sm transition-all group relative"
      data-testid={`board-card-${ctx.id}`}
    >
      {urgent > 0 && (
        <span className="absolute top-3 right-3 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm text-[9px] uppercase tracking-wider bg-red-50 text-red-700 border border-red-200 font-semibold">
          <AlertTriangle className="w-2.5 h-2.5" /> {urgent} urgent
        </span>
      )}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 bg-[#0A1F44] text-[#C9A961] rounded-sm flex items-center justify-center shrink-0">
          <Landmark className="w-4 h-4" strokeWidth={1.8} />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-[#0A1F44] truncate">{ctx.name}</p>
          <p className="text-[10px] uppercase tracking-wider text-slate-400 truncate">
            {sector || "Board"} {ctx.jurisdiction ? `· ${ctx.jurisdiction}` : ""}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <p className="text-[9px] uppercase tracking-[0.2em] text-slate-400 mb-1">Next meeting</p>
          <p className="text-[13px] text-[#0A1F44] font-medium flex items-center gap-1">
            <CalendarDays className="w-3 h-3 text-[#C9A961]" /> {formatMeetingDate(daysAway)}
          </p>
          <p className="text-[10px] text-slate-400 mt-0.5">in {daysAway} day{daysAway === 1 ? "" : "s"}</p>
        </div>
        <div>
          <p className="text-[9px] uppercase tracking-[0.2em] text-slate-400 mb-1">Pack</p>
          <p className="text-[13px] text-[#0A1F44] font-medium flex items-center gap-1">
            <FileText className="w-3 h-3 text-[#C9A961]" /> {stats?.docs || 0} doc{(stats?.docs || 0) === 1 ? "" : "s"}
          </p>
          <p className="text-[10px] text-slate-400 mt-0.5">{stats?.signals || 0} signals ready</p>
        </div>
      </div>

      <div className="flex items-center justify-between text-[11px] text-slate-500 pt-3 border-t border-[#E1E6ED]">
        <span>{stats?.docs ? "Pack in progress" : "No pack yet"}</span>
        <span className="inline-flex items-center gap-1 text-[#C9A961] group-hover:translate-x-0.5 transition-transform">
          Open <ArrowRight className="w-3 h-3" />
        </span>
      </div>
    </Link>
  );
}

export default function NedHome({ welcome }) {
  const { account, contexts, switchContext } = useAuth();
  const nedContexts = useMemo(
    () => contexts.filter((c) => c.my_role === "ned" || c.type?.startsWith("ned")),
    [contexts]
  );
  const [statsById, setStatsById] = useState({});

  // Fetch doc + signal counts for each NED context in parallel
  useEffect(() => {
    if (!nedContexts.length) return;
    let cancelled = false;
    (async () => {
      const results = await Promise.all(
        nedContexts.map(async (c) => {
          try {
            const [docsRes, sigRes] = await Promise.all([
              api.get(`/contexts/${c.id}/documents`),
              api.get(`/contexts/${c.id}/signals`),
            ]);
            const signals = sigRes.data || [];
            return [
              c.id,
              {
                docs: (docsRes.data || []).length,
                signals: signals.length,
                risks_high: signals.filter((s) => s.type === "risk" && s.confidence === "high").length,
                signalsList: signals,
              },
            ];
          } catch {
            return [c.id, { docs: 0, signals: 0, risks_high: 0, signalsList: [] }];
          }
        })
      );
      if (!cancelled) setStatsById(Object.fromEntries(results));
    })();
    return () => { cancelled = true; };
  }, [nedContexts]);

  // Listen for board card clicks — switch context then navigate
  useEffect(() => {
    const handler = (e) => { switchContext(e.detail); window.location.href = "/app/highlights"; };
    window.addEventListener("akki:switch-context", handler);
    return () => window.removeEventListener("akki:switch-context", handler);
  }, [switchContext]);

  const sortedBoards = useMemo(() => {
    return [...nedContexts]
      .map((c) => ({ ctx: c, days: daysUntilNextMeeting(c.id) }))
      .sort((a, b) => a.days - b.days);
  }, [nedContexts]);

  // Cross-Board Pulse: show only when ≥2 NED contexts AND at least one signal aggregated
  const pulse = useMemo(() => {
    if (nedContexts.length < 2) return null;
    const byType = { risk: 0, opportunity: 0, gap: 0 };
    let totalHighRisk = 0;
    Object.values(statsById).forEach((s) => {
      (s.signalsList || []).forEach((sig) => {
        byType[sig.type] = (byType[sig.type] || 0) + 1;
        if (sig.type === "risk" && sig.confidence === "high") totalHighRisk++;
      });
    });
    const total = byType.risk + byType.opportunity + byType.gap;
    if (total === 0) return null;
    return { byType, total, totalHighRisk, boardsCount: nedContexts.length };
  }, [statsById, nedContexts.length]);

  return (
    <div className="p-8 max-w-7xl mx-auto" data-testid="ned-home">
      {welcome}

      {/* Cross-Board Pulse */}
      {pulse && (
        <div
          className="mb-8 bg-[#0A1F44] text-white rounded-sm border border-[#0A1F44] relative overflow-hidden"
          data-testid="cross-board-pulse"
        >
          <div className="absolute top-0 right-0 w-1/3 h-full bg-gradient-to-l from-[#C9A961]/20 to-transparent" />
          <div className="relative p-6">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-[#C9A961]" />
              <p className="akki-overline text-white/70">Cross-Board Pulse · across {pulse.boardsCount} boards</p>
            </div>
            <h2 className="text-xl font-light tracking-tight mb-4">
              {pulse.totalHighRisk > 0
                ? <><span className="text-[#C9A961]">{pulse.totalHighRisk} high-confidence risks</span> surface across your boards this cycle.</>
                : <><span className="text-[#C9A961]">{pulse.total} signals</span> are live across your boards.</>}
            </h2>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="bg-white/5 border border-white/10 rounded-sm p-3">
                <AlertTriangle className="w-4 h-4 text-red-300 mx-auto mb-1" />
                <p className="text-2xl font-light">{pulse.byType.risk}</p>
                <p className="text-[10px] uppercase tracking-wider text-white/50">Risks</p>
              </div>
              <div className="bg-white/5 border border-white/10 rounded-sm p-3">
                <TrendingUp className="w-4 h-4 text-emerald-300 mx-auto mb-1" />
                <p className="text-2xl font-light">{pulse.byType.opportunity}</p>
                <p className="text-[10px] uppercase tracking-wider text-white/50">Opportunities</p>
              </div>
              <div className="bg-white/5 border border-white/10 rounded-sm p-3">
                <CircleSlash className="w-4 h-4 text-amber-300 mx-auto mb-1" />
                <p className="text-2xl font-light">{pulse.byType.gap}</p>
                <p className="text-[10px] uppercase tracking-wider text-white/50">Gaps</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Boards grid */}
      <div className="mb-10">
        <div className="flex items-end justify-between mb-4">
          <div>
            <p className="akki-overline mb-1">Your boards</p>
            <h3 className="text-xl font-medium tracking-tight text-[#0A1F44]">
              {sortedBoards.length} board{sortedBoards.length === 1 ? "" : "s"}, ordered by meeting proximity
            </h3>
          </div>
          <Link to="/app/contexts/new">
            <Button variant="outline" className="rounded-sm h-9 border-[#E1E6ED] text-sm" data-testid="add-board-btn">
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Add a board
            </Button>
          </Link>
        </div>

        {sortedBoards.length === 0 ? (
          <div className="bg-white border border-[#E1E6ED] rounded-sm p-12 text-center" data-testid="ned-home-empty">
            <Landmark className="w-10 h-10 text-slate-300 mx-auto mb-4" strokeWidth={1.3} />
            <p className="text-sm text-slate-600 mb-1 font-medium">No NED contexts yet</p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto mb-4">
              Add the boards you serve on. Each context stays isolated — documents, signals, and conversations are scoped to the board.
            </p>
            <Link to="/app/contexts/new">
              <Button className="bg-[#C9A961] hover:bg-[#B39556] text-[#0A1F44] rounded-sm h-9 text-sm">
                <Plus className="w-3.5 h-3.5 mr-1.5" /> Create first board
              </Button>
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="board-grid">
            {sortedBoards.map(({ ctx, days }) => (
              <BoardCard key={ctx.id} ctx={ctx} stats={statsById[ctx.id]} daysAway={days} />
            ))}
          </div>
        )}
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Link to="/app/workspace" className="bg-white border border-[#E1E6ED] rounded-sm p-5 hover:border-[#C9A961]/60 transition-colors group">
          <FileText className="w-5 h-5 text-[#C9A961] mb-3" strokeWidth={1.6} />
          <p className="text-sm font-medium text-[#0A1F44] mb-1">Upload a pack</p>
          <p className="text-xs text-slate-500 mb-3">Drop board minutes, reports, agendas.</p>
          <span className="text-[11px] text-[#C9A961] inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            Go to Workspace <ArrowRight className="w-3 h-3" />
          </span>
        </Link>
        <Link to="/app/highlights" className="bg-white border border-[#E1E6ED] rounded-sm p-5 hover:border-[#C9A961]/60 transition-colors group">
          <Sparkles className="w-5 h-5 text-[#C9A961] mb-3" strokeWidth={1.6} />
          <p className="text-sm font-medium text-[#0A1F44] mb-1">Generate signals</p>
          <p className="text-xs text-slate-500 mb-3">Risks, opportunities, gaps — grounded in your pack.</p>
          <span className="text-[11px] text-[#C9A961] inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            Open Highlights <ArrowRight className="w-3 h-3" />
          </span>
        </Link>
        <Link to="/app/briefings" className="bg-white border border-[#E1E6ED] rounded-sm p-5 hover:border-[#C9A961]/60 transition-colors group">
          <ScrollText className="w-5 h-5 text-[#C9A961] mb-3" strokeWidth={1.6} />
          <p className="text-sm font-medium text-[#0A1F44] mb-1">Compose briefing</p>
          <p className="text-xs text-slate-500 mb-3">1–2 page PDF or DOCX for the meeting.</p>
          <span className="text-[11px] text-[#C9A961] inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            Open Briefings <ArrowRight className="w-3 h-3" />
          </span>
        </Link>
        <Link to="/app/ask" className="bg-white border border-[#E1E6ED] rounded-sm p-5 hover:border-[#C9A961]/60 transition-colors group">
          <Layers className="w-5 h-5 text-[#C9A961] mb-3" strokeWidth={1.6} />
          <p className="text-sm font-medium text-[#0A1F44] mb-1">Ask a question</p>
          <p className="text-xs text-slate-500 mb-3">Grounded answers with citations.</p>
          <span className="text-[11px] text-[#C9A961] inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            Open Ask <ArrowRight className="w-3 h-3" />
          </span>
        </Link>
      </div>
    </div>
  );
}
