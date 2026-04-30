/**
 * WorkflowsHub — Home consolidation per user feedback.
 *
 * Combines what previously lived as four separate stacked components:
 *   - PlayReadyCards (auto-launch trigger)
 *   - AgendaEvolutionCard (what's changed since last meeting)
 *   - PlaysInProgressStrip (resume chips)
 *   - QuickActions (intent tiles)
 *
 * Into one hub with a compact tab-switcher so the home page no longer
 * feels like sprawling walls of text. Default tab is whatever is most
 * urgent: 'Ready' if any auto-launched play is waiting, otherwise
 * 'Quick actions'.
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import PlayReadyCards from "@/components/home/PlayReadyCards";
import AgendaEvolutionCard from "@/components/home/AgendaEvolutionCard";
import PlaysInProgressStrip from "@/components/home/PlaysInProgressStrip";
import QuickActions from "@/components/home/QuickActions";
import InboundQueueCard from "@/components/home/InboundQueueCard";
import { Sparkles, Calendar, Layers, Zap, Inbox } from "lucide-react";

export default function WorkflowsHub() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [readyCount, setReadyCount] = useState(0);
  const [activeCount, setActiveCount] = useState(0);
  const [inboundCount, setInboundCount] = useState(0);

  const load = useCallback(async () => {
    if (!cid) return;
    try {
      const { data } = await api.get(`/contexts/${cid}/plays`);
      const plays = data.plays || [];
      setReadyCount(plays.filter((p) => p.auto_launched && !p.auto_launch_seen && ["active", "paused"].includes(p.status)).length);
      setActiveCount(plays.filter((p) => ["active", "paused"].includes(p.status)).length);
    } catch { /* noop */ }
    try {
      const { data } = await api.get("/me/inbound-queue/counts");
      setInboundCount(data.total_pending || 0);
    } catch { /* noop */ }
  }, [cid]);
  useEffect(() => { load(); }, [load]);

  const tabs = useMemo(() => ([
    { key: "actions", label: "Quick actions",       icon: Zap,      count: null },
    { key: "ready",   label: "Ready for you",       icon: Sparkles, count: readyCount },
    { key: "agenda",  label: "Since last meeting",  icon: Calendar, count: null },
    { key: "active",  label: "In progress",         icon: Layers,   count: activeCount },
    { key: "inbound", label: "Inbound review",      icon: Inbox,    count: inboundCount },
  ]), [readyCount, activeCount, inboundCount]);

  // Default to the most urgent tab: inbound quarantine > play ready > actions.
  const pickInitial = () => {
    if (inboundCount > 0) return "inbound";
    if (readyCount > 0) return "ready";
    return "actions";
  };
  const [tab, setTab] = useState(pickInitial);
  useEffect(() => { setTab(pickInitial()); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readyCount, inboundCount]);

  return (
    <section className="bg-white border border-[var(--rule)] rounded-lg mb-5 shrink-0" data-testid="home-workflows-hub">
      <div className="border-b border-[var(--rule)] px-4 py-2 flex items-center gap-1 overflow-x-auto">
        <p className="akki-overline mr-3 shrink-0">Workflows</p>
        {tabs.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`relative flex items-center gap-1.5 px-3 py-1.5 text-[12.5px] rounded-sm transition-colors ${
                active
                  ? "text-[var(--ink)] bg-[var(--cream-deep)]/60"
                  : "text-[var(--muted)] hover:text-[var(--deep)]"
              }`}
              data-testid={`workflows-tab-${t.key}`}
            >
              <Icon className={`w-3.5 h-3.5 ${active ? "text-[var(--accent)]" : ""}`} strokeWidth={1.7} />
              <span>{t.label}</span>
              {typeof t.count === "number" && t.count > 0 && (
                <span className={`text-[10px] tabular-nums px-1.5 py-0.5 rounded-full ${active ? "bg-[var(--accent)] text-white" : "bg-[var(--rule)] text-[var(--muted)]"}`}>
                  {t.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="p-4" data-testid={`workflows-panel-${tab}`}>
        {tab === "actions" && <QuickActions />}
        {tab === "ready" && <PlayReadyCards />}
        {tab === "agenda" && <AgendaEvolutionCard />}
        {tab === "active" && <PlaysInProgressStrip />}
        {tab === "inbound" && <InboundQueueCard />}
      </div>
    </section>
  );
}
