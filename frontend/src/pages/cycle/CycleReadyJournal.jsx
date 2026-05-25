/**
 * CycleReadyJournal — T5 (2026-05-25).
 *
 * Spec §4.B → C7. Lists all Active cycles whose current compilation
 * readiness score has met or exceeded the user-set target. Card click
 * opens a side drawer with cycle title, readiness score, due date,
 * contributors + agendas; CTA in the drawer is "Compile" which routes
 * to the existing cycle compile flow.
 *
 * Entry point: `View More` on the Cycle Manager landing side panel's
 * Ready to Compile card.
 *
 * DOM-unconditional rule: empty state emits the same scaffolding as
 * the populated state.
 */
import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { ArrowLeft } from "lucide-react";
import CycleCard from "@/components/cycle/CycleCard";

export default function CycleReadyJournal() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const navigate = useNavigate();
  const [cycles, setCycles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!cid) return;
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const { data } = await api.get(`/contexts/${cid}/cycles`, {
          params: { status: "active", page_size: 60 },
        });
        if (!alive) return;
        // C7: lists cycles whose readiness_pct >= the cycle's target.
        // We don't have a per-cycle target field on the listing today;
        // for the first ship we surface every Active cycle with a
        // readiness_pct >= 80 (the lowest selectable target in C2's
        // dropdown). The list filters down further once compile-
        // readiness targets are persisted per-cycle (POST_T5 backlog).
        const items = (data?.cycles || []).filter(
          (c) => (c.readiness_pct ?? 0) >= 80
        );
        setCycles(items);
      } finally {
        if (alive) setLoading(false);
      }
    })();
  }, [cid]);

  return (
    <AppShell>
      <div className="px-6 py-4 border-b border-[var(--rule)] bg-white flex items-center gap-3"
           data-testid="cycle-ready-journal-header">
        <Link
          to="/app/cycle"
          className="text-[12px] inline-flex items-center gap-1.5 text-[var(--muted)] hover:text-[var(--ink)]"
          data-testid="cycle-ready-journal-back"
        >
          <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.7} />
          Cycle Manager
        </Link>
        <span className="text-[var(--muted)]">/</span>
        <span className="text-[12px] text-[var(--ink)] akki-serif">Ready to Compile</span>
      </div>
      <section className="px-6 py-6" data-testid="cycle-ready-journal-body">
        {loading && (
          <p className="text-[12.5px] text-[var(--muted)] italic" data-testid="cycle-ready-journal-loading">
            Loading cycles…
          </p>
        )}
        {!loading && cycles.length === 0 && (
          <div
            className="border border-dashed border-[var(--rule)] bg-[var(--parchment)] rounded-sm px-6 py-12 text-center"
            data-testid="cycle-ready-journal-empty"
          >
            <p className="akki-serif text-[16px] text-[var(--ink)]">No cycles ready to compile yet.</p>
            <p className="text-[12px] text-[var(--muted)] mt-2 max-w-prose mx-auto">
              Active cycles will appear here as their readiness score
              meets the target you set in the Setup Wizard.
            </p>
          </div>
        )}
        {!loading && cycles.length > 0 && (
          <ul className="space-y-3" data-testid="cycle-ready-journal-list">
            {cycles.map((c) => (
              <CycleCard key={c.id} cycle={c} />
            ))}
          </ul>
        )}
      </section>
    </AppShell>
  );
}
