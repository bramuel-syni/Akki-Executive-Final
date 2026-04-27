import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Sparkles, ScrollText, Send, Eye, BookOpen, FileText, Building2 } from "lucide-react";

/**
 * InSummaryTiles — neat hook tiles on Home that surface the user's most
 * frequently-checked numbers in a quick-scan grid:
 *
 *   - Signals          (count + critical/high/medium breakdown)
 *   - Briefings        (unread + last update)
 *   - Cycle status     (open submissions / outstanding)
 *   - Document journal (count + last add)
 *
 * Each tile shows: kicker, primary number, breakdown line, freshness
 * timestamp, link to the surface. No charts, no bars; just numbers and
 * text — Economist register.
 */

function fmtRelative(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now - d;
    const diffM = Math.round(diffMs / 60000);
    if (diffM < 1) return "just now";
    if (diffM < 60) return `${diffM} min ago`;
    const diffH = Math.round(diffM / 60);
    if (diffH < 24) return `${diffH} hr ago`;
    const diffD = Math.round(diffH / 24);
    if (diffD < 7) return `${diffD} d ago`;
    return d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "2-digit" });
  } catch { return "—"; }
}

export default function InSummaryTiles() {
  const { activeContext, contexts: allContexts } = useAuth();
  const cid = activeContext?.id;
  const [data, setData] = useState({
    signals: [], briefings: [], submissions: [], checklists: [], docs: [],
    reports: [], members: [],
  });
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    if (!cid) return;
    try {
      const [sg, br, sb, cl, dc, rp, mb] = await Promise.all([
        api.get(`/contexts/${cid}/signals`).catch(() => ({ data: [] })),
        api.get(`/contexts/${cid}/briefings`).catch(() => ({ data: { briefings: [] } })),
        api.get(`/contexts/${cid}/submissions`).catch(() => ({ data: { submissions: [] } })),
        api.get(`/contexts/${cid}/checklists`).catch(() => ({ data: { checklists: [] } })),
        api.get(`/contexts/${cid}/documents`).catch(() => ({ data: { documents: [] } })),
        api.get(`/contexts/${cid}/reports`).catch(() => ({ data: { reports: [] } })),
        api.get(`/contexts/${cid}/members`).catch(() => ({ data: [] })),
      ]);
      setData({
        signals: Array.isArray(sg.data) ? sg.data : (sg.data.signals || []),
        briefings: Array.isArray(br.data) ? br.data : (br.data.briefings || []),
        submissions: sb.data.submissions || [],
        checklists: cl.data.checklists || [],
        docs: Array.isArray(dc.data) ? dc.data : (dc.data.documents || dc.data.docs || []),
        reports: Array.isArray(rp.data) ? rp.data : (rp.data.reports || []),
        members: Array.isArray(mb.data) ? mb.data : (mb.data.members || []),
      });
    } catch { /* swallow — tiles render with zeros */ }
    finally { setLoaded(true); }
  }, [cid]);
  useEffect(() => { load(); }, [load]);

  const tiles = useMemo(() => {
    // Signals carry `type` (risk | opportunity | gap) and `confidence`
    // (high | medium | low) — NOT severity/priority. Bucket them
    // accordingly so the breakdown actually populates.
    const sigByType = data.signals.reduce((acc, s) => {
      const t = (s.type || "risk").toLowerCase();
      acc[t] = (acc[t] || 0) + 1;
      return acc;
    }, {});
    const lastSig = data.signals.length ? data.signals.reduce((latest, s) => {
      const t = s.created_at || s.updated_at;
      return t && (!latest || t > latest) ? t : latest;
    }, null) : null;

    const briefUnread = data.briefings.filter((b) => !b.read_at && !b.read).length;
    const lastBrief = data.briefings.length ? (data.briefings[0]?.created_at || data.briefings[0]?.published_at) : null;

    const submitted = data.submissions.length;
    const dispatched = data.checklists.filter((c) => c.status === "dispatched").length;
    const submittedNames = new Set(data.submissions.map((s) => s.reportee_name));
    const outstanding = data.checklists.filter((c) => c.status === "dispatched" && !submittedNames.has(c.reportee_name)).length;
    const lastSub = data.submissions.length ? (data.submissions[0]?.received_at || data.submissions[0]?.created_at) : null;

    const docCount = data.docs.length;
    const lastDoc = data.docs.length ? (data.docs[0]?.uploaded_at || data.docs[0]?.created_at) : null;

    // ── Reports sent (this company): final/sent reports the user has authored
    const reportsSent = data.reports.filter((r) =>
      ["sent", "delivered", "final", "approved"].includes((r.status || "").toLowerCase())
    ).length;
    const reportsTotal = data.reports.length;
    const lastReport = data.reports.length
      ? (data.reports[0]?.sent_at || data.reports[0]?.created_at)
      : null;

    // ── Network: companies + people across the user's portfolio
    const companies = (allContexts || []).filter((c) => c.status !== "archived").length;
    // Members on the active company (admins + reportees + collaborators)
    const teamMembers = data.members.length;

    return [
      {
        key: "signals", to: "/app/prepare", icon: Sparkles,
        kicker: "Signals", count: data.signals.length,
        breakdown: [
          { label: "Risks",         n: sigByType.risk || 0,        tone: "text-red-700" },
          { label: "Opportunities", n: sigByType.opportunity || 0, tone: "text-emerald-700" },
          { label: "Gaps",          n: sigByType.gap || 0,         tone: "text-amber-700" },
        ],
        last: lastSig,
      },
      {
        key: "briefings", to: "/app/prepare", icon: ScrollText,
        kicker: "Briefings", count: data.briefings.length,
        breakdown: [
          { label: "Unread", n: briefUnread, tone: "text-[var(--accent)]" },
          { label: "Read", n: data.briefings.length - briefUnread, tone: "text-[var(--muted)]" },
        ],
        last: lastBrief,
      },
      {
        key: "cycle", to: "/app/cycle", icon: Send,
        kicker: "Cycle", count: submitted,
        sublabel: "submitted",
        breakdown: [
          { label: "Outstanding", n: outstanding, tone: outstanding > 0 ? "text-amber-700" : "text-[var(--muted)]" },
          { label: "Dispatched", n: dispatched, tone: "text-[var(--deep)]" },
        ],
        last: lastSub,
      },
      {
        key: "reports", to: "/app/cycle", icon: FileText,
        kicker: "Reports", count: reportsSent,
        sublabel: "sent",
        breakdown: [
          { label: "Total drafted", n: reportsTotal, tone: "text-[var(--deep)]" },
        ],
        last: lastReport,
      },
      {
        key: "documents", to: "/app/workspace", icon: BookOpen,
        kicker: "Document Journal", count: docCount,
        breakdown: [],
        last: lastDoc,
      },
      {
        key: "network", to: "/app/manage", icon: Building2,
        kicker: "Network", count: companies,
        sublabel: "companies",
        breakdown: [
          { label: "Team members on this company", n: teamMembers, tone: "text-[var(--deep)]" },
        ],
        last: null,
      },
    ];
  }, [data, allContexts]);

  if (!cid) return null;

  return (
    <section className="mb-7 shrink-0" data-testid="home-in-summary">
      <p className="akki-overline mb-3">In summary</p>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {tiles.map((t) => {
          const Icon = t.icon;
          return (
            <Link
              key={t.key} to={t.to}
              className="bg-white border border-[var(--rule)] hover:border-[var(--accent)]/40 rounded-lg p-4 transition-colors flex flex-col group"
              data-testid={`summary-tile-${t.key}`}
            >
              <div className="flex items-start justify-between mb-2">
                <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono">{t.kicker}</p>
                <Icon className="w-3.5 h-3.5 text-[var(--muted)]" strokeWidth={1.6} />
              </div>
              <p className="akki-serif text-[28px] text-[var(--ink)] leading-none mb-2" data-testid={`summary-count-${t.key}`}>
                {loaded ? t.count : "—"}
                {t.sublabel && <span className="text-[12px] text-[var(--muted)] ml-1.5 italic">{t.sublabel}</span>}
              </p>
              {t.breakdown && t.breakdown.length > 0 && (
                <ul className="space-y-0.5 mb-2 flex-1">
                  {t.breakdown.map((b, i) => (
                    <li key={i} className={`text-[11.5px] ${b.tone}`}>
                      <span className="font-medium">{b.n}</span> {b.label.toLowerCase()}
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-[10px] uppercase tracking-wider text-[var(--muted)] mt-auto">
                Last update {fmtRelative(t.last)}
              </p>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
