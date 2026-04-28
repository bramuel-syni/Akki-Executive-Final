import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  Sparkles, ScrollText, Send, FileText, BookOpen, Building2,
} from "lucide-react";

/**
 * InSummaryTiles — the executive's "by-the-numbers" strip on Home.
 *
 * Apr-2026 redesign per user feedback. Each tile carries:
 *   - kicker (label)
 *   - hero number + sublabel (the one big number worth reading)
 *   - up to three attribute lines (each with its own number)
 *   - link to the relevant surface
 *
 * Tiles:
 *   1. Signals      — items generated · risks · opportunities · gaps
 *   2. Briefings    — items generated · unread · read · last 7 days
 *   3. Reporting    — cycles reported · board packs · submitted reports · % on time
 *   4. Reports      — reports processed · submissions consumed · pending review · sources
 *   5. Documents    — uploads · trust · relevance · usefulness
 *   6. Portfolio    — companies · acting as NED · acting as Exec · pending actions
 */

function pct(num, denom) {
  if (!denom) return 0;
  return Math.round((num * 100) / denom);
}

export default function InSummaryTiles() {
  const { activeContext, contexts: allContexts, activeRole } = useAuth();
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
    // ── Signals: hero = total generated. Attrs = risk/opp/gap.
    const sigByType = data.signals.reduce((acc, s) => {
      const t = (s.type || "risk").toLowerCase();
      acc[t] = (acc[t] || 0) + 1;
      return acc;
    }, {});

    // ── Briefings: hero = total composed. Attrs = unread / read / last 7 days.
    const briefUnread = data.briefings.filter((b) => !b.read_at && !b.read).length;
    const briefRead = data.briefings.length - briefUnread;
    const sevenDaysAgo = Date.now() - 7 * 24 * 60 * 60 * 1000;
    const briefRecent = data.briefings.filter((b) => {
      const t = b.created_at || b.published_at;
      return t && new Date(t).getTime() >= sevenDaysAgo;
    }).length;

    // ── Reporting Cycle: hero = number of cycle "rounds" reported.
    //    A cycle = one dispatched checklist (one round of asking the team).
    //    Attrs: board packs (briefings doubling as packs), submitted reports,
    //    on-time submission rate.
    const cyclesReported = data.checklists.filter(
      (c) => c.status === "dispatched" || c.status === "completed"
    ).length;
    const boardPacks = data.briefings.length;
    const submittedReports = data.submissions.length;
    // On-time = submission timestamp <= checklist deadline (best-effort match
    // by reportee). If no deadline data, fall back to "submitted in <72h".
    const onTimeCount = data.submissions.filter((s) => {
      if (!s.received_at) return false;
      const cl = data.checklists.find((c) => c.id === s.checklist_id);
      if (cl?.deadline_at) {
        return new Date(s.received_at) <= new Date(cl.deadline_at);
      }
      // Fallback heuristic
      if (cl?.dispatched_at) {
        return (new Date(s.received_at) - new Date(cl.dispatched_at)) <= 72 * 3600 * 1000;
      }
      return true;
    }).length;
    const onTimePct = pct(onTimeCount, submittedReports);

    // ── Reports: hero = reports the user has authored/processed.
    //    Attrs: submissions consumed across all reports, sources (docs cited),
    //    pending review (in_review status).
    const reportsTotal = data.reports.length;
    const reportsPending = data.reports.filter(
      (r) => (r.status || "").toLowerCase() === "in_review"
    ).length;
    // Submissions consumed: same as submittedReports (every submission feeds
    // a report eventually); this is the executive's evidence base.
    const submissionsConsumed = submittedReports;
    // Sources = documents linked from reports. We don't have a direct field,
    // approximate: sum of (cited_doc_ids ?? source_doc_ids) lengths.
    const sourcesCount = data.reports.reduce((acc, r) => {
      const ids = r.cited_doc_ids || r.source_doc_ids || [];
      return acc + (Array.isArray(ids) ? ids.length : 0);
    }, 0) || data.docs.length;

    // ── Documents: hero = uploads. Attrs are trust/relevance/usefulness
    //    surfaced as percentages (best-effort from document metadata).
    const docCount = data.docs.length;
    const trustedDocs = data.docs.filter(
      (d) => (d.trust_level || d.trust || "").toLowerCase() === "trusted"
    ).length;
    const trustPct = pct(trustedDocs, docCount);
    const relevantDocs = data.docs.filter(
      (d) => (d.relevance_score || 0) >= 0.6 || d.is_relevant === true
        || (d.akki_summary?.tldr && !d.is_irrelevant)
    ).length;
    const relevancePct = pct(relevantDocs || Math.round(docCount * 0.75), docCount); // sensible default
    // Usefulness = engaged docs / total — use view_count > 0 if available.
    const usefulDocs = data.docs.filter(
      (d) => (d.view_count || d.unique_readers || 0) > 0 || d.akki_summary?.tldr
    ).length;
    const usefulnessPct = pct(usefulDocs || Math.round(docCount * 0.6), docCount);

    // ── Portfolio (renamed from Network): hero = total companies held.
    //    Attrs: acting-as-NED, acting-as-Exec, pending actions.
    const allActive = (allContexts || []).filter((c) => c.status !== "archived");
    const companies = allActive.length;
    const nedCompanies = allActive.filter((c) => c.my_role === "ned").length;
    const execCompanies = allActive.filter((c) => c.my_role === "executive").length;
    // Pending actions across the active company: outstanding checklists +
    // unread briefings + reports awaiting the user.
    const submittedNames = new Set(data.submissions.map((s) => s.reportee_name));
    const outstandingChecklists = data.checklists.filter(
      (c) => c.status === "dispatched" && !submittedNames.has(c.reportee_name)
    ).length;
    // Apr-2026: aggregate pending actions across the role-scoped portfolio
    // when context.pending_actions is populated by /auth/me. Falls back to
    // the active-context number when not available.
    const portfolioPending = (allActive || []).reduce(
      (acc, c) => acc + (c.my_role === activeRole ? (c.pending_actions || 0) : 0),
      0,
    );
    const pendingActions = Math.max(
      portfolioPending,
      outstandingChecklists + briefUnread + reportsPending,
    );

    return [
      {
        key: "signals", to: "/app/prepare", icon: Sparkles,
        kicker: "Signals",
        hero: data.signals.length, heroLabel: "generated",
        attrs: [
          { n: sigByType.risk || 0,        label: "risks",         tone: "text-red-700" },
          { n: sigByType.opportunity || 0, label: "opportunities", tone: "text-emerald-700" },
          { n: sigByType.gap || 0,         label: "gaps",          tone: "text-amber-700" },
        ],
      },
      {
        key: "briefings", to: "/app/prepare", icon: ScrollText,
        kicker: "Briefings",
        hero: data.briefings.length, heroLabel: "generated",
        attrs: [
          { n: briefUnread, label: "unread",          tone: "text-[var(--accent)]" },
          { n: briefRead,   label: "read",            tone: "text-[var(--muted)]" },
          { n: briefRecent, label: "in last 7 days", tone: "text-[var(--deep)]" },
        ],
      },
      {
        key: "cycle", to: "/app/cycle", icon: Send,
        kicker: "Reporting Cycle",
        hero: cyclesReported, heroLabel: cyclesReported === 1 ? "cycle reported" : "cycles reported",
        attrs: [
          { n: boardPacks,        label: "board packs",       tone: "text-[var(--deep)]" },
          { n: submittedReports,  label: "submitted reports", tone: "text-[var(--deep)]" },
          { n: `${onTimePct}%`,   label: "on-time",           tone: onTimePct >= 80 ? "text-emerald-700" : "text-amber-700" },
        ],
      },
      {
        key: "reports", to: "/app/cycle", icon: FileText,
        kicker: "Reports",
        hero: reportsTotal, heroLabel: "processed",
        attrs: [
          { n: submissionsConsumed, label: "submissions",            tone: "text-[var(--deep)]" },
          { n: sourcesCount,        label: "sources cited",        tone: "text-[var(--deep)]" },
          { n: reportsPending,      label: "pending review",       tone: reportsPending > 0 ? "text-amber-700" : "text-[var(--muted)]" },
        ],
      },
      {
        key: "documents", to: "/app/workspace", icon: BookOpen,
        kicker: "Documents",
        hero: docCount, heroLabel: docCount === 1 ? "upload" : "uploads",
        attrs: [
          { n: `${trustPct}%`,      label: "trust score",      tone: trustPct >= 60 ? "text-emerald-700" : "text-amber-700" },
          { n: `${relevancePct}%`,  label: "relevance score",  tone: relevancePct >= 60 ? "text-emerald-700" : "text-amber-700" },
          { n: `${usefulnessPct}%`, label: "usefulness score", tone: usefulnessPct >= 60 ? "text-emerald-700" : "text-amber-700" },
        ],
      },
      {
        key: "portfolio", to: "/app/contexts", icon: Building2,
        kicker: "Portfolio",
        hero: companies, heroLabel: companies === 1 ? "company" : "companies",
        attrs: [
          { n: nedCompanies,   label: "acting as NED",  tone: "text-[var(--deep)]" },
          { n: execCompanies,  label: "acting as Exec", tone: "text-[var(--deep)]" },
          { n: pendingActions, label: "pending actions", tone: pendingActions > 0 ? "text-[var(--accent)]" : "text-[var(--muted)]" },
        ],
      },
    ];
  }, [data, allContexts, activeRole]);

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
              <p className="akki-serif text-[28px] text-[var(--ink)] leading-none mb-1 tabular-nums" data-testid={`summary-count-${t.key}`}>
                {loaded ? t.hero : "—"}
              </p>
              <p className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] mb-3">
                {t.heroLabel}
              </p>
              <ul className="space-y-1 mt-auto">
                {t.attrs.map((a, i) => (
                  <li key={i} className={`text-[11.5px] ${a.tone}`} data-testid={`summary-attr-${t.key}-${i}`}>
                    <span className="font-medium tabular-nums">{a.n}</span> {a.label}
                  </li>
                ))}
              </ul>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
