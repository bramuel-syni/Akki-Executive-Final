/**
 * WorkStudio — Phase 13.3 unified artefacts-in-flight landing.
 *
 * One entry point that lists everything the user is currently drafting
 * across briefings, decks, and reports for the active context. Each
 * row links straight to the existing detail surface (Studio block
 * composer, ReportsTab, etc.) — this page is a hub, not a rebuild.
 *
 * Sources (read-only):
 *   - GET /api/contexts/{cid}/briefings              → status != "sent"
 *   - GET /api/contexts/{cid}/decks                  → status != "sent"
 *   - GET /api/contexts/{cid}/cycle/reports/inbox    → status != "sent"/"finalised"
 *
 * UI:
 *   - Tabs: All / Briefings / Decks / Reports (with counts)
 *   - Sort by `updated_at desc` within each tab
 *   - Each row: title · sensitivity chip · validated badge · last-edit
 *   - "Start new" buttons up top (briefing / deck / report)
 *
 * Phase 13.3 reads `?view=` and `?seed_kind=&seed_id=` query params:
 *   - `?view=decks` lands on the Decks tab (used by /app/decks redirect).
 *   - `?seed_kind=&seed_id=` shows a contextual banner saying the artefact
 *     is in scope (the actual seed-into-composer wiring lands in 14.x).
 */
import React, { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import ValidatedBadge from "@/components/trust/ValidatedBadge";
import { toast } from "sonner";
import {
  FileText, Presentation, ScrollText, Plus, Loader2, ArrowRight, AlertCircle,
  Layers, Sparkles, Inbox,
} from "lucide-react";

function shortAge(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const ms = Date.now() - d.getTime();
    const mins = Math.floor(ms / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch { return "—"; }
}

function SensitivityChip({ s }) {
  if (!s || !s.label) return null;
  const cls = {
    Public: "bg-emerald-50 text-emerald-700 border-emerald-100",
    Internal: "bg-sky-50 text-sky-700 border-sky-100",
    Confidential: "bg-amber-50 text-amber-800 border-amber-100",
    Restricted: "bg-rose-50 text-rose-700 border-rose-100",
  }[s.label] || "bg-[var(--cream-deep)] text-[var(--deep)] border-[var(--rule)]";
  return (
    <span className={`inline-flex items-center text-[10.5px] uppercase tracking-[0.14em] font-medium border rounded-sm px-1.5 py-[2px] ${cls}`}>
      {s.label}
    </span>
  );
}

function ArtefactRow({ kind, item }) {
  const href = item.href || "#";
  const updated = item.updated_at || item.modified_at || item.created_at;
  const Icon = kind === "briefing" ? ScrollText : kind === "deck" ? Presentation : FileText;
  return (
    <li className="border border-[var(--rule)] rounded-md bg-white px-4 py-3 flex items-start sm:items-center gap-3 flex-col sm:flex-row" data-testid="work-studio-row">
      <Icon className="w-4 h-4 text-[var(--deep)] shrink-0 mt-1 sm:mt-0" strokeWidth={1.7} />
      <div className="min-w-0 flex-1">
        <p className="text-[14px] text-[var(--ink)] truncate">{item.title || "Untitled"}</p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <span className="text-[11px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
            {kind} · {item.status || "draft"}
          </span>
          <SensitivityChip s={item.sensitivity} />
          {item.synisense_version >= 1 && (
            <span className="text-[10px] uppercase tracking-[0.14em] font-mono text-[var(--accent)]">shielded</span>
          )}
          {item.validation && <ValidatedBadge result={item.validation} />}
        </div>
      </div>
      <span className="text-[11.5px] text-[var(--muted)] shrink-0 sm:ml-2" title={updated || ""}>
        {shortAge(updated)}
      </span>
      <Link to={href} className="shrink-0">
        <Button variant="ghost" size="sm" className="text-[12.5px] text-[var(--accent)] hover:bg-[var(--accent-soft)]">
          Open <ArrowRight className="w-3.5 h-3.5 ml-1" />
        </Button>
      </Link>
    </li>
  );
}

async function loadAll(cid) {
  // Each request is independent; one failure must NOT take the page
  // down. We collect partial results and surface a banner if any
  // source errored.
  const out = { briefings: [], decks: [], reports: [], errors: [] };
  try {
    const { data } = await api.get(`/contexts/${cid}/briefings`);
    const items = (data?.items || data?.briefings || []).filter((b) => (b.status || "draft") !== "sent");
    out.briefings = items.map((b) => ({ ...b, href: `/app/studio/composer/briefing/${b.id}` }));
  } catch (e) { out.errors.push(["briefings", apiErrorMessage(e)]); }
  try {
    const { data } = await api.get(`/contexts/${cid}/decks`);
    const items = (data?.items || data?.decks || []).filter((d) => (d.status || "draft") !== "sent");
    out.decks = items.map((d) => ({ ...d, href: `/app/decks/${d.id}` }));
  } catch (e) { out.errors.push(["decks", apiErrorMessage(e)]); }
  try {
    const { data } = await api.get(`/contexts/${cid}/cycle/reports/inbox`);
    const items = (data?.reports || data?.items || []).filter((r) => {
      const s = (r.status || "draft").toLowerCase();
      return s !== "sent" && s !== "finalised" && s !== "finalized" && s !== "complete";
    });
    out.reports = items.map((r) => ({ ...r, href: `/app/cycle?tab=overview&report=${r.id}` }));
  } catch (e) { out.errors.push(["reports", apiErrorMessage(e)]); }
  return out;
}

export default function WorkStudio() {
  const { activeContext } = useAuth();
  const cid = activeContext?.id;
  const [searchParams, setSearchParams] = useSearchParams();
  const initialView = (() => {
    const v = (searchParams.get("view") || "all").toLowerCase();
    return ["all", "briefings", "decks", "reports"].includes(v) ? v : "all";
  })();
  const [view, setView] = useState(initialView);
  const [data, setData] = useState({ briefings: [], decks: [], reports: [], errors: [] });
  const [loading, setLoading] = useState(true);
  const seedKind = searchParams.get("seed_kind");
  const seedId = searchParams.get("seed_id");

  useEffect(() => {
    if (!cid) return;
    let cancelled = false;
    setLoading(true);
    loadAll(cid).then((res) => {
      if (cancelled) return;
      setData(res);
      setLoading(false);
      res.errors.forEach(([k, msg]) => toast.error(`Could not load ${k}: ${msg}`));
    });
    return () => { cancelled = true; };
  }, [cid]);

  const onView = (next) => {
    setView(next);
    const sp = new URLSearchParams(searchParams);
    if (next === "all") sp.delete("view"); else sp.set("view", next);
    setSearchParams(sp, { replace: true });
  };

  const visible = useMemo(() => {
    const sortDesc = (a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0);
    const briefings = [...(data.briefings || [])].sort(sortDesc);
    const decks = [...(data.decks || [])].sort(sortDesc);
    const reports = [...(data.reports || [])].sort(sortDesc);
    if (view === "briefings") return { briefings, decks: [], reports: [] };
    if (view === "decks")     return { briefings: [], decks, reports: [] };
    if (view === "reports")   return { briefings: [], decks: [], reports };
    return { briefings, decks, reports };
  }, [data, view]);

  if (!cid) {
    return (
      <AppShell>
        <div className="p-12 text-center text-[var(--muted)] text-sm">No context selected.</div>
      </AppShell>
    );
  }

  const totalCount =
    (data.briefings?.length || 0) + (data.decks?.length || 0) + (data.reports?.length || 0);

  const TABS = [
    { id: "all",        label: "All",        n: totalCount,                     icon: Layers },
    { id: "briefings",  label: "Briefings",  n: data.briefings?.length || 0,    icon: ScrollText },
    { id: "decks",      label: "Decks",      n: data.decks?.length || 0,        icon: Presentation },
    { id: "reports",    label: "Reports",    n: data.reports?.length || 0,      icon: FileText },
  ];

  return (
    <AppShell>
      <div className="max-w-[1100px] mx-auto px-8 py-10" data-testid="work-studio">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Work Studio · {activeContext.name}
        </p>
        <h1 className="akki-greeting mb-2">In flight.</h1>
        <p className="akki-meta max-w-2xl">
          Everything you have open across briefings, decks, and reports for{" "}
          <strong className="text-[var(--ink)]">{activeContext.name}</strong>. Sorted by last edit.
        </p>

        {seedKind && seedId && (
          <div className="mt-5 px-4 py-3 bg-[var(--accent-soft)] border border-[var(--accent)]/20 rounded-sm text-[12.5px] text-[var(--ink)] flex items-center gap-2" data-testid="work-studio-seed-banner">
            <Inbox className="w-3.5 h-3.5 text-[var(--accent)]" />
            <span>
              <strong className="font-medium">{seedKind}</strong> <span className="font-mono text-[11px] text-[var(--muted)]">{seedId}</span> is in scope. Open a draft below to wire it in (composer-seed wiring lands in 14.x).
            </span>
          </div>
        )}

        {/* Start new actions */}
        <div className="flex flex-wrap items-center gap-2 mt-6 mb-6" data-testid="work-studio-new-row">
          <Link to="/app/cycle?tab=briefs">
            <Button variant="outline" size="sm" className="rounded-sm border-[var(--rule)] text-[12.5px]" data-testid="work-studio-new-briefing">
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Start a briefing
            </Button>
          </Link>
          <Link to="/app/decks">
            <Button variant="outline" size="sm" className="rounded-sm border-[var(--rule)] text-[12.5px]" data-testid="work-studio-new-deck">
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Start a deck
            </Button>
          </Link>
          <Link to="/app/cycle?tab=overview">
            <Button variant="outline" size="sm" className="rounded-sm border-[var(--rule)] text-[12.5px]" data-testid="work-studio-new-report">
              <Plus className="w-3.5 h-3.5 mr-1.5" /> Start a report
            </Button>
          </Link>
        </div>

        {/* Inner tabs */}
        <div className="border-b border-[var(--rule)] flex items-stretch gap-0 mb-6 flex-wrap" data-testid="work-studio-tabs">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = view === t.id;
            return (
              <button
                key={t.id}
                onClick={() => onView(t.id)}
                className={`px-5 py-3 text-[14px] inline-flex items-center gap-2 border-b-2 -mb-px transition-colors ${
                  active
                    ? "border-[var(--accent)] text-[var(--ink)] font-medium"
                    : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
                }`}
                data-testid={`work-studio-tab-${t.id}${active ? "-active" : ""}`}
                aria-current={active ? "page" : undefined}
              >
                <Icon className="w-3.5 h-3.5" strokeWidth={1.7} />
                {t.label}
                <span className="text-[11px] text-[var(--muted)] font-mono">· {t.n}</span>
              </button>
            );
          })}
        </div>

        {loading ? (
          <div className="p-12 text-center text-[var(--muted)] text-sm flex items-center justify-center gap-2" data-testid="work-studio-loading">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading what's in flight…
          </div>
        ) : totalCount === 0 ? (
          <div className="p-12 text-center border border-[var(--rule)] rounded-md bg-white" data-testid="work-studio-empty">
            <Layers className="w-6 h-6 text-[var(--muted)] mx-auto mb-3" />
            <p className="text-[14px] text-[var(--ink)] font-medium">Nothing in flight.</p>
            <p className="text-[12.5px] text-[var(--muted)] mt-1 max-w-md mx-auto">
              Start a briefing, deck, or report above. Drafts you save will land here.
            </p>
          </div>
        ) : (
          <div className="space-y-10" data-testid="work-studio-sections">
            {visible.briefings.length > 0 && (
              <section data-testid="work-studio-section-briefings">
                <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-3">
                  Briefings <span className="text-[12px] text-[var(--muted)]">· {visible.briefings.length}</span>
                </h2>
                <ul className="space-y-2">
                  {visible.briefings.map((b) => <ArtefactRow key={`brf-${b.id}`} kind="briefing" item={b} />)}
                </ul>
              </section>
            )}
            {visible.decks.length > 0 && (
              <section data-testid="work-studio-section-decks">
                <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-3">
                  Decks <span className="text-[12px] text-[var(--muted)]">· {visible.decks.length}</span>
                </h2>
                <ul className="space-y-2">
                  {visible.decks.map((d) => <ArtefactRow key={`dck-${d.id}`} kind="deck" item={d} />)}
                </ul>
              </section>
            )}
            {visible.reports.length > 0 && (
              <section data-testid="work-studio-section-reports">
                <h2 className="akki-serif text-[18px] text-[var(--ink)] mb-3">
                  Reports <span className="text-[12px] text-[var(--muted)]">· {visible.reports.length}</span>
                </h2>
                <ul className="space-y-2">
                  {visible.reports.map((r) => <ArtefactRow key={`rpt-${r.id}`} kind="report" item={r} />)}
                </ul>
              </section>
            )}
            {data.errors.length > 0 && (
              <div className="p-4 bg-amber-50 border border-amber-100 rounded-md text-[12px] text-amber-900 flex items-center gap-2" data-testid="work-studio-partial-banner">
                <AlertCircle className="w-3.5 h-3.5" />
                Some surfaces failed to load — you're seeing partial results. Refresh to retry.
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
