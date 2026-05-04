/**
 * HomeExecutive — Phase 13.3 executive-specific home.
 *
 * Emphasis: in-flight briefings/decks/reports (Work Studio preview),
 * this week's cycle reportee submissions, pending action items,
 * upcoming cycle dates. Reuses the existing surfaces wholesale rather
 * than rebuilding them — the legacy executive home is what most users
 * already see, so we wrap LegacyAppHome and supplement it with a
 * compact Work Studio preview at the top.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import ExecutiveHomeShell from "@/pages/ExecutiveHomeShell";
import { Briefcase, ScrollText, Presentation, FileText, ArrowRight } from "lucide-react";

/**
 * Compact Work Studio preview — mounts at the very top of the executive
 * home as a single, dense row. Click any segment to land on Work Studio
 * with the right tab active.
 */
function WorkStudioPreview({ contextId }) {
  const [counts, setCounts] = useState({ briefings: 0, decks: 0, reports: 0 });
  useEffect(() => {
    if (!contextId) return;
    let dead = false;
    Promise.all([
      api.get(`/contexts/${contextId}/briefings`).then(({ data }) => (data?.items || data?.briefings || []).filter((b) => (b.status || "draft") !== "sent").length).catch(() => 0),
      api.get(`/contexts/${contextId}/decks`).then(({ data }) => (data?.items || data?.decks || []).filter((d) => (d.status || "draft") !== "sent").length).catch(() => 0),
      api.get(`/contexts/${contextId}/cycle/reports/inbox`).then(({ data }) => {
        const items = data?.reports || data?.items || [];
        return items.filter((r) => {
          const s = (r.status || "draft").toLowerCase();
          return s !== "sent" && s !== "finalised" && s !== "finalized";
        }).length;
      }).catch(() => 0),
    ]).then(([b, d, r]) => { if (!dead) setCounts({ briefings: b, decks: d, reports: r }); });
    return () => { dead = true; };
  }, [contextId]);

  const total = counts.briefings + counts.decks + counts.reports;
  if (total === 0) return null;

  return (
    <div className="max-w-[1280px] mx-auto px-6 pt-4" data-testid="home-exec-work-studio-preview">
      <Link to="/app/work-studio" className="block px-5 py-3 border border-[var(--rule)] bg-white rounded-md hover:bg-[var(--cream-deep)]/40 transition-colors">
        <div className="flex items-center gap-6 flex-wrap">
          <p className="akki-overline text-[var(--muted)] flex items-center gap-2">
            <Briefcase className="w-3 h-3" /> Work Studio · in flight
          </p>
          <div className="flex items-center gap-5 text-[13px] text-[var(--ink)]">
            <span className="inline-flex items-center gap-1.5"><ScrollText className="w-3.5 h-3.5 text-[var(--deep)]" strokeWidth={1.7} /> {counts.briefings} briefings</span>
            <span className="inline-flex items-center gap-1.5"><Presentation className="w-3.5 h-3.5 text-[var(--deep)]" strokeWidth={1.7} /> {counts.decks} decks</span>
            <span className="inline-flex items-center gap-1.5"><FileText className="w-3.5 h-3.5 text-[var(--deep)]" strokeWidth={1.7} /> {counts.reports} reports</span>
          </div>
          <span className="ml-auto text-[12px] text-[var(--accent)] inline-flex items-center gap-1">
            Open Work Studio <ArrowRight className="w-3 h-3" />
          </span>
        </div>
      </Link>
    </div>
  );
}

export default function HomeExecutive() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  return (
    <div data-testid="home-executive">
      <WorkStudioPreview contextId={cid} />
      {/* Reuse the existing executive home shell wholesale — same telemetry,
          same spinning-up cards, just topped by the Work Studio band
          when there's something in flight. */}
      <ExecutiveHomeShell />
    </div>
  );
}
