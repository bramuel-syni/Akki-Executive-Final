import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import {
  ArrowRight, FileText, Send, Eye, Activity, ScrollText, Sparkles,
} from "lucide-react";

/**
 * QuickActions — DYNAMIC workflow dock on Home.
 *
 * Apr-2026 user feedback: "Make the workflow dock dynamic — front the
 * most popular feature, the most unused, new features, monitor-your-
 * performance, etc."
 *
 * How it works:
 *   1. Every tile carries a static role gate + a `priority(state)`
 *      function that returns a numeric score (higher = surface first).
 *   2. We compute scores from the user's actual data (unread briefings,
 *      pending reports, in-progress plays) and sort.
 *   3. Top 3 render. Static intent tiles are still represented, but the
 *      dock now reflects what's most actionable RIGHT NOW.
 */
const TILE_DEFS = [
  {
    key: "review_submissions",
    role: "executive", playType: "board_pack", stageHint: 0,
    label: "Review what your team sent",
    body: "Open the Q-cycle inbox, see who's reported and where the gaps are.",
    icon: Eye,
    // Boost when there are pending submissions to review.
    priority: (s) => 50 + (s.pendingReports * 5) + (s.outstandingChecklists * 3),
  },
  {
    key: "send_deck",
    role: "executive", playType: "board_pack", stageHint: 3,
    label: "Send the deck up",
    body: "Move a finalised report to the next reviewer in your chain.",
    icon: Send,
    priority: (s) => 40 + (s.readyToShip * 8),
  },
  {
    key: "prepare_meeting",
    role: "any", playType: "pre_board", stageHint: 0,
    label: "Read & catch-up for tomorrow",
    body: "Pull in a freshly-arrived board pack. Walk in with a one-page brief.",
    icon: FileText,
    priority: (s) => 60 + (s.unreadBriefings * 6) + (s.recentDocs * 2),
  },
  {
    key: "monitor_performance",
    role: "any", customRoute: "/app/monitor",
    label: "Monitor your performance",
    body: "Dials, drift, and where you're spending vs delivering — for this company.",
    icon: Activity,
    // Steady mid-priority — always within reach but never noisy.
    priority: () => 35,
  },
  {
    key: "catch_up_briefings",
    role: "any", customRoute: "/app/prepare",
    label: "Catch up on briefings",
    body: "Open the briefings you haven't read yet. Quiet pile, fast read.",
    icon: ScrollText,
    // Only surfaces when there are unread briefings.
    priority: (s) => s.unreadBriefings === 0 ? 0 : 55 + (s.unreadBriefings * 4),
  },
  {
    key: "try_signals",
    role: "any", customRoute: "/app/prepare?tab=signals",
    label: "Surface signals on something",
    body: "Risks, opportunities, gaps — generated against a focus you choose.",
    icon: Sparkles,
    // Surfaces strongly when no signals exist yet (new feature nudge).
    priority: (s) => s.totalSignals === 0 ? 70 : 25,
  },
];

export default function QuickActions() {
  const navigate = useNavigate();
  const { activeContext, activeRole } = useAuth();
  const cid = activeContext?.id;
  const [plays, setPlays] = useState([]);
  const [state, setState] = useState({
    unreadBriefings: 0, pendingReports: 0, outstandingChecklists: 0,
    readyToShip: 0, recentDocs: 0, totalSignals: 0,
  });
  const [starting, setStarting] = useState(null);

  const load = useCallback(async () => {
    if (!cid) return;
    try {
      const [pl, br, rp, cl, dc, sg] = await Promise.all([
        api.get(`/contexts/${cid}/plays`).catch(() => ({ data: { plays: [] } })),
        api.get(`/contexts/${cid}/briefings`).catch(() => ({ data: { briefings: [] } })),
        api.get(`/contexts/${cid}/reports`).catch(() => ({ data: { reports: [] } })),
        api.get(`/contexts/${cid}/checklists`).catch(() => ({ data: { checklists: [] } })),
        api.get(`/contexts/${cid}/documents`).catch(() => ({ data: { documents: [] } })),
        api.get(`/contexts/${cid}/signals`).catch(() => ({ data: [] })),
      ]);
      const briefings = Array.isArray(br.data) ? br.data : (br.data.briefings || []);
      const reports = Array.isArray(rp.data) ? rp.data : (rp.data.reports || []);
      const checklists = cl.data.checklists || [];
      const docs = Array.isArray(dc.data) ? dc.data : (dc.data.documents || dc.data.docs || []);
      const signals = Array.isArray(sg.data) ? sg.data : (sg.data?.signals || []);
      const sevenDaysAgo = Date.now() - 7 * 24 * 3600 * 1000;
      setPlays((pl.data.plays || []).filter((p) => ["active", "paused"].includes(p.status)));
      setState({
        unreadBriefings: briefings.filter((b) => !b.read_at && !b.read).length,
        pendingReports: reports.filter((r) => (r.status || "").toLowerCase() === "in_review").length,
        outstandingChecklists: checklists.filter((c) => c.status === "dispatched").length,
        readyToShip: reports.filter((r) => (r.status || "").toLowerCase() === "ready").length,
        recentDocs: docs.filter((d) => d.created_at && new Date(d.created_at).getTime() >= sevenDaysAgo).length,
        totalSignals: signals.length,
      });
    } catch { /* keep zero state */ }
  }, [cid]);
  useEffect(() => { load(); }, [load]);

  const findExisting = (playType) => plays.find((p) => p.play_type === playType);

  const onStart = async (tile) => {
    if (!cid) { toast.error("No active context."); return; }
    // Custom-route tiles (Monitor, Prepare nudges) navigate directly.
    if (tile.customRoute) {
      navigate(tile.customRoute);
      return;
    }
    setStarting(tile.key);
    const existing = findExisting(tile.playType);
    try {
      let playId;
      if (existing) {
        playId = existing.id;
        if (existing.current_stage !== tile.stageHint) {
          await api.post(`/contexts/${cid}/plays/${existing.id}/jump`, {
            stage_idx: tile.stageHint, confirm: true,
          });
        }
      } else {
        const { data } = await api.post(`/contexts/${cid}/plays`, { play_type: tile.playType });
        playId = data.play.id;
        if (tile.stageHint > 0) {
          await api.post(`/contexts/${cid}/plays/${playId}/jump`, {
            stage_idx: tile.stageHint, confirm: true,
          });
        }
      }
      navigate(`/app/plays/${playId}`);
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setStarting(null); }
  };

  // Strict role isolation + dynamic prioritisation. Tiles with
  // priority <= 0 are filtered out (e.g. "catch up on briefings"
  // when there's nothing to catch up on).
  const visible = useMemo(() => {
    return TILE_DEFS
      .filter((t) => t.role === "any" || t.role === activeRole)
      .map((t) => ({ ...t, _score: t.priority?.(state) ?? 0 }))
      .filter((t) => t._score > 0)
      .sort((a, b) => b._score - a._score)
      .slice(0, 3);
  }, [state, activeRole]);

  if (!cid) return null;

  return (
    <section className="mb-7 shrink-0" data-testid="home-quick-actions">
      <p className="akki-overline mb-3">Quick actions</p>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {visible.map((t) => {
          const existing = t.playType ? findExisting(t.playType) : null;
          const Icon = t.icon;
          const cta = t.customRoute ? "Open" : (existing ? "Resume" : "Start");
          return (
            <button
              key={t.key}
              onClick={() => onStart(t)}
              disabled={starting === t.key}
              className="text-left bg-white border border-[var(--rule)] hover:border-[var(--accent)]/40 rounded-lg p-4 transition-colors group flex flex-col h-full"
              data-testid={`home-action-${t.key}`}
            >
              <div className="flex items-start gap-3 mb-2">
                <Icon className="w-4 h-4 text-[var(--accent)] mt-1 shrink-0" strokeWidth={1.7} />
                <p className="akki-serif text-[16px] text-[var(--ink)] leading-tight flex-1">{t.label}</p>
              </div>
              <p className="text-[12.5px] text-[var(--deep)] italic leading-relaxed mb-3 flex-1">{t.body}</p>
              <p className="text-[11.5px] text-[var(--accent)] inline-flex items-center gap-1 group-hover:underline">
                {cta} <ArrowRight className="w-3 h-3" />
              </p>
            </button>
          );
        })}
      </div>
    </section>
  );
}
