/**
 * HomeDual — Phase 13.3 layout for users who declared `dual` role.
 *
 * Two-column split: executive cards on the left, NED cards on the
 * right. On narrow screens (< 1024px) the columns stack so neither
 * gets buried. Each column reuses the same building blocks the
 * dedicated single-role home pages use — we explicitly do NOT
 * rebuild data fetching here.
 */
import React from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { Briefcase, Landmark, ArrowRight, Activity, ScrollText, Presentation, FileText } from "lucide-react";
import CycleStrip from "@/components/cycle/CycleStrip";
import useIsMobile from "@/hooks/useIsMobile";
import AddDocumentCard from "@/components/home/AddDocumentCard";
import AllDocumentsButton from "@/components/home/AllDocumentsButton";

export default function HomeDual() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const isMobile = useIsMobile();
  return (
    <AppShell>
      <div className="akki-w-medium px-8 py-10" data-testid="home-dual">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Briefcase className="w-3 h-3" /><Landmark className="w-3 h-3" /> Executive + NED home · {activeContext?.name || "—"}
        </p>
        <h1 className="akki-greeting mb-2">
          Run the business on the left. Sit on the boards on the right.
        </h1>
        <p className="akki-meta max-w-2xl mb-6">
          AKKI splits the home so neither side gets buried. Cycle and Pulse continue to scope by
          your active context.
        </p>

        {/* Phase E (D-006) — Document Journal entry-point hoisted into
            the page-title band so it's visible above the fold at
            1920×1100 without scrolling. */}
        <div className="mb-8" data-testid="home-dual-all-documents-strip">
          <AllDocumentsButton />
        </div>

        {cid && <CycleStrip contextId={cid} isMobile={isMobile} />}

        <div className="grid lg:grid-cols-2 gap-8 mt-8">
          {/* Executive column */}
          <section className="space-y-4" data-testid="home-dual-exec-col">
            <h2 className="akki-serif text-[22px] text-[var(--ink)] inline-flex items-center gap-2">
              <Briefcase className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Running the business
            </h2>
            <AddDocumentCard />
            <Link to="/app/work-studio" className="block p-5 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors">
              <p className="akki-overline mb-2 text-[var(--muted)]">Work Studio</p>
              <p className="text-[14px] text-[var(--ink)] mb-1">In-flight briefings, decks, and reports for {activeContext?.name || "this company"}.</p>
              <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">Open Work Studio <ArrowRight className="w-3 h-3" /></span>
            </Link>
            <Link to="/app/cycle?tab=overview" className="block p-5 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors">
              <p className="akki-overline mb-2 text-[var(--muted)]">Cycle Manager → Overview</p>
              <p className="text-[14px] text-[var(--ink)] mb-1">Reportee submissions this week, the question bank, the report you're drafting.</p>
              <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">Open Cycle <ArrowRight className="w-3 h-3" /></span>
            </Link>
            <Link to="/app/cycle?tab=actions" className="block p-5 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors">
              <p className="akki-overline mb-2 text-[var(--muted)]">Pending action items</p>
              <p className="text-[14px] text-[var(--ink)] mb-1">Signal actions, in-flight plays, and submissions still open.</p>
              <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">Open Actions <ArrowRight className="w-3 h-3" /></span>
            </Link>
          </section>

          {/* NED column */}
          <section className="space-y-4" data-testid="home-dual-ned-col">
            <h2 className="akki-serif text-[22px] text-[var(--ink)] inline-flex items-center gap-2">
              <Landmark className="w-4 h-4 text-[var(--deep)]" strokeWidth={1.7} /> Sitting on the boards
            </h2>
            <Link to="/app/pulse" className="block p-5 border border-[var(--accent)]/30 bg-[var(--accent)]/[0.04] rounded-md hover:bg-[var(--accent)]/[0.08] transition-colors">
              <p className="akki-overline mb-2 text-[var(--accent)] flex items-center gap-1.5"><Activity className="w-3 h-3" /> Akki Pulse</p>
              <p className="text-[14px] text-[var(--ink)] mb-1">Cross-board patterns surface here in the next phase.</p>
              <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">See the holding page <ArrowRight className="w-3 h-3" /></span>
            </Link>
            <Link to="/app/cycle?tab=minutes" className="block p-5 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors">
              <p className="akki-overline mb-2 text-[var(--muted)]">Latest minutes</p>
              <p className="text-[14px] text-[var(--ink)] mb-1">What was committed at the last meeting and what's still open.</p>
              <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">Open Minutes <ArrowRight className="w-3 h-3" /></span>
            </Link>
            <Link to="/app/cycle?tab=signals" className="block p-5 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors">
              <p className="akki-overline mb-2 text-[var(--muted)]">Signals awaiting action</p>
              <p className="text-[14px] text-[var(--ink)] mb-1">What's drifted on the board you sit on, and where it sits in the cycle.</p>
              <span className="text-[12.5px] text-[var(--accent)] inline-flex items-center gap-1">Open Signals <ArrowRight className="w-3 h-3" /></span>
            </Link>
          </section>
        </div>
      </div>
    </AppShell>
  );
}
