/**
 * HomeNed — Phase 13.3 NED-specific home.
 *
 * Emphasis: cross-board (Pulse placeholder), latest minutes to catch up
 * on, signals awaiting action, next board cycle phase. Reuses
 * `AgendaEvolutionCard`, `HighlightsStats`, and the existing CycleStrip
 * — we are NOT building new feature surfaces here, just reorganising
 * the priority of what's already shipped.
 *
 * Calibri sans for body, Georgia for the H1, accent only used twice on
 * this page (NED overline + Pulse pill) per UI/UX brief.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import HighlightsStats from "@/components/highlights/HighlightsStats";
import AgendaEvolutionCard from "@/components/home/AgendaEvolutionCard";
import CycleStrip from "@/components/cycle/CycleStrip";
import useIsMobile from "@/hooks/useIsMobile";
import { Activity, Landmark, ArrowRight, Clock, ScrollText } from "lucide-react";

function MinutesPreview({ contextId }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!contextId) return;
    let dead = false;
    setLoading(true);
    api.get(`/contexts/${contextId}/minutes`)
      .then(({ data }) => { if (!dead) setItems((data?.items || []).slice(0, 4)); })
      .catch(() => { if (!dead) setItems([]); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [contextId]);
  if (loading) return null;
  if (items.length === 0) {
    return (
      <div className="p-4 border border-[var(--rule)] bg-white rounded-md text-[12.5px] text-[var(--muted)]" data-testid="home-ned-minutes-empty">
        No minutes uploaded yet — forward last meeting's minutes to your AKKI inbound address and
        they'll surface here.
      </div>
    );
  }
  return (
    <ul className="space-y-2" data-testid="home-ned-minutes-list">
      {items.map((m) => (
        <li key={m.id} className="border border-[var(--rule)] rounded-md bg-white px-3 py-2.5">
          <p className="text-[13.5px] text-[var(--ink)] truncate">{m.title || m.filename || "Minutes"}</p>
          <p className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mt-1">
            {m.meeting_date || m.created_at?.slice(0, 10)}
          </p>
        </li>
      ))}
    </ul>
  );
}

function SignalsAwaitingAction({ contextId }) {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!contextId) return;
    let dead = false;
    setLoading(true);
    api.get(`/contexts/${contextId}/signals`)
      .then(({ data }) => { if (!dead) setSignals((data?.signals || data?.items || []).slice(0, 8)); })
      .catch(() => { if (!dead) setSignals([]); })
      .finally(() => { if (!dead) setLoading(false); });
    return () => { dead = true; };
  }, [contextId]);
  if (loading) return null;
  if (signals.length === 0) {
    return (
      <div className="p-4 border border-[var(--rule)] bg-white rounded-md text-[12.5px] text-[var(--muted)]" data-testid="home-ned-signals-empty">
        No signals on the board yet. Run a fresh signals pass under{" "}
        <Link to="/app/cycle?tab=signals" className="underline underline-offset-4">Cycle Manager → Signals</Link>.
      </div>
    );
  }
  return (
    <div data-testid="home-ned-signals">
      <HighlightsStats signals={signals} />
    </div>
  );
}

export default function HomeNed() {
  const { activeContext, account } = useAuth();
  const cid = activeContext?.id;
  const isMobile = useIsMobile();
  return (
    <AppShell>
      <div className="max-w-[1100px] mx-auto px-8 py-10" data-testid="home-ned">
        <p className="akki-overline mb-2 text-[var(--accent)] flex items-center gap-2">
          <Landmark className="w-3 h-3" /> NED home · {activeContext?.name || "—"}
        </p>
        <h1 className="akki-greeting mb-2">
          Catch up across the boards you sit on.
        </h1>
        <p className="akki-meta max-w-2xl mb-8">
          The five things that move quietly between meetings: minutes, signals, the next cycle
          phase, plus the cross-board Pulse view when it lands.
        </p>

        {cid && <CycleStrip contextId={cid} isMobile={isMobile} />}

        <div className="grid lg:grid-cols-2 gap-8 mt-8">
          {/* Pulse cross-board card */}
          <Link to="/app/pulse" className="block p-6 border border-[var(--accent)]/30 bg-[var(--accent)]/[0.04] rounded-md hover:bg-[var(--accent)]/[0.08] transition-colors" data-testid="home-ned-pulse-card">
            <p className="akki-overline mb-2 text-[var(--accent)] flex items-center gap-1.5">
              <Activity className="w-3 h-3" /> Akki Pulse
            </p>
            <h2 className="akki-serif text-[22px] text-[var(--ink)] mb-2">Cross-board patterns are coming next phase.</h2>
            <p className="text-[13.5px] text-[var(--deep)] leading-relaxed mb-3">
              When Pulse lands, this card lights up with capital pressure, succession risk, and
              regulatory drift surfacing across the boards you sit on — attributed back to source.
            </p>
            <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">
              See the holding page <ArrowRight className="w-3 h-3" />
            </span>
          </Link>

          {/* Latest minutes */}
          <div data-testid="home-ned-minutes-card">
            <div className="flex items-center justify-between mb-3">
              <h2 className="akki-serif text-[18px] text-[var(--ink)] inline-flex items-center gap-2">
                <ScrollText className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Latest minutes
              </h2>
              <Link to="/app/cycle?tab=minutes" className="text-[12.5px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1">
                Open <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
            {cid && <MinutesPreview contextId={cid} />}
          </div>
        </div>

        {/* Signals awaiting action */}
        <section className="mt-10" data-testid="home-ned-signals-section">
          <div className="flex items-center justify-between mb-3">
            <h2 className="akki-serif text-[20px] text-[var(--ink)] inline-flex items-center gap-2">
              <Activity className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Signals awaiting action
            </h2>
            <Link to="/app/cycle?tab=signals" className="text-[12.5px] text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1">
              Open Signals <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {cid && <SignalsAwaitingAction contextId={cid} />}
        </section>

        {/* Agenda evolution — reused from existing component */}
        <section className="mt-10">
          {cid && <AgendaEvolutionCard contextId={cid} />}
        </section>
      </div>
    </AppShell>
  );
}
