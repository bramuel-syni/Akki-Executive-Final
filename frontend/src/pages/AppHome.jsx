import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import StreamCard from "@/components/stream/StreamCard";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  ArrowRight, FileText, Sparkles, ScrollText, MessageSquareText,
  Landmark, Briefcase, CalendarDays, Plus, Archive,
} from "lucide-react";

const CONFIDENCE_LABEL = { high: "High confidence", medium: "Medium confidence", low: "Low confidence" };

function greeting(name) {
  const h = new Date().getHours();
  const g = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  return `${g}, ${name}.`;
}

/** Build items the "attention stream" cares about, ranked by freshness. */
function buildStreamItems({ signals, briefings, documents, activeContext }) {
  const items = [];

  signals.forEach((s) => {
    items.push({
      _kind: "signal",
      id: s.id,
      type: s.type, // risk | opportunity | gap
      timestamp: s.created_at,
      lead: s.headline,
      chips: [
        ...(activeContext ? [{ label: activeContext.name }] : []),
        { label: CONFIDENCE_LABEL[s.confidence] || "Medium confidence" },
        ...(s.sources?.[0] ? [{ label: s.sources[0].doc_name?.slice(0, 40) }] : []),
      ],
      to: "/app/highlights",
      gesture: { label: "Open signal", to: "/app/highlights" },
      sortKey: new Date(s.created_at).getTime(),
    });
  });

  briefings.forEach((b) => {
    items.push({
      _kind: "briefing",
      id: b.id,
      type: "briefing",
      timestamp: b.created_at,
      lead: b.title,
      chips: [
        ...(activeContext ? [{ label: activeContext.name }] : []),
        { label: `${b.items?.length || 0} items` },
        { label: `v${b.version}` },
      ],
      to: "/app/briefings",
      gesture: { label: "Open briefing", to: "/app/briefings" },
      sortKey: new Date(b.created_at).getTime() + 500,
    });
  });

  documents.slice(0, 3).forEach((d) => {
    items.push({
      _kind: "document",
      id: d.id,
      type: "document",
      timestamp: d.created_at,
      lead: d.name,
      chips: [
        ...(activeContext ? [{ label: activeContext.name }] : []),
        { label: d.data_trust || "unrated" },
        ...(d.extracted_chars ? [{ label: `${(d.extracted_chars / 1000).toFixed(1)}k chars extracted` }] : []),
      ],
      to: `/app/documents/${d.id}`,
      gesture: { label: "Open document", to: `/app/documents/${d.id}` },
      sortKey: new Date(d.created_at).getTime() - 1000,
    });
  });

  return items.sort((a, b) => b.sortKey - a.sortKey);
}

export default function AppHome() {
  const { account, activeContext, activeRole, contexts } = useAuth();
  const contextId = activeContext?.id;
  const [signals, setSignals] = useState([]);
  const [briefings, setBriefings] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scope, setScope] = useState("all");

  const load = useCallback(async () => {
    if (!contextId) { setLoading(false); return; }
    setLoading(true);
    try {
      const [s, b, d] = await Promise.all([
        api.get(`/contexts/${contextId}/signals`),
        api.get(`/contexts/${contextId}/briefings`),
        api.get(`/contexts/${contextId}/documents`),
      ]);
      setSignals(s.data || []);
      setBriefings(b.data || []);
      setDocuments(d.data || []);
    } catch { /* silent — empty stream will render */ }
    finally { setLoading(false); }
  }, [contextId]);

  useEffect(() => { load(); }, [load]);

  const items = useMemo(() => {
    const all = buildStreamItems({ signals, briefings, documents, activeContext });
    if (scope === "all") return all;
    if (scope === "signals") return all.filter((i) => i._kind === "signal");
    if (scope === "briefings") return all.filter((i) => i._kind === "briefing");
    if (scope === "documents") return all.filter((i) => i._kind === "document");
    return all;
  }, [signals, briefings, documents, activeContext, scope]);

  const isDeclared = account?.declared_role && account.declared_role !== "undeclared";
  const auditComplete = !!activeContext?.progress_state?.onboarding_completed;
  const firstName = (account?.name || "there").split(" ")[0];

  // Role-aware scope chips — v4.2 spec says chips adapt per role
  const scopeChips = useMemo(() => {
    const base = [
      { key: "all", label: "All" },
      { key: "signals", label: "Signals" },
      { key: "briefings", label: "Briefings" },
      { key: "documents", label: "Documents" },
    ];
    return base;
  }, []);

  const RoleIcon = activeRole === "ned" ? Landmark : Briefcase;

  // Onboarding gate
  if (!isDeclared || !auditComplete) {
    return (
      <AppShell>
        <div className="max-w-3xl mx-auto px-8 py-16 akki-fade-up">
          <p className="akki-overline mb-3">Home · {activeContext?.name || "Your context"}</p>
          <h1 className="akki-greeting mb-6">{greeting(firstName)}</h1>
          <div className="bg-white border border-[var(--rule)] rounded-lg p-10 relative overflow-hidden">
            <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)]" />
            <p className="akki-overline mb-3">Next · 7 minutes</p>
            <h2 className="akki-title-22 mb-4">
              {!isDeclared
                ? <>Declare your role. Run the audit to unlock your signals.</>
                : <>Finish the board-focused audit to unlock your signals.</>}
            </h2>
            <p className="text-[15px] text-[var(--deep)] leading-relaxed mb-8 max-w-xl akki-serif">
              Seven role-specific questions establish your Context Object — the foundation for every signal, briefing, and lens session.
            </p>
            <Link to="/onboarding">
              <Button className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-10 px-5 font-medium" data-testid="start-onboarding-btn">
                {!isDeclared ? "Begin audit" : "Resume audit"} <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-[1280px] mx-auto px-8 py-10 grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-10">
        {/* Main attention stream */}
        <div className="min-w-0" data-testid="attention-stream">
          {/* Greeting */}
          <div className="mb-8 akki-fade-up">
            <p className="akki-overline mb-2 flex items-center gap-2">
              <RoleIcon className="w-3 h-3 text-[var(--accent)]" strokeWidth={2} />
              Acting as {activeRole === "ned" ? "Non-Executive Director" : "Executive"}
              <span className="text-[var(--muted)]/60">·</span>
              <span>{activeContext?.name}</span>
            </p>
            <h1 className="akki-greeting">{greeting(firstName)}</h1>
            <p className="akki-meta mt-2 max-w-xl">
              {items.length === 0
                ? "Your workspace is quiet. Upload a pack to let AKKI surface signals."
                : `${items.length} thing${items.length === 1 ? "" : "s"} worth your attention in ${activeContext?.name}.`}
            </p>
          </div>

          {/* Scope chips */}
          <div className="flex items-center gap-6 mb-6 border-b border-[var(--rule)] pb-1 akki-fade-up" data-testid="scope-chips">
            {scopeChips.map((c) => (
              <button
                key={c.key}
                data-selected={scope === c.key}
                onClick={() => setScope(c.key)}
                className="akki-scope-chip"
                data-testid={`scope-${c.key}`}
              >
                {c.label}
              </button>
            ))}
            <div className="ml-auto flex items-center gap-2 text-[12px] text-[var(--muted)]">
              <span>{items.length} items</span>
            </div>
          </div>

          {/* Stream */}
          {loading ? (
            <div className="p-16 text-center text-xs uppercase tracking-widest text-[var(--muted)]">Loading…</div>
          ) : items.length === 0 ? (
            <div className="bg-white border border-[var(--rule)] rounded-lg p-12 text-center" data-testid="home-empty">
              <FileText className="w-10 h-10 text-[var(--muted)]/40 mx-auto mb-4" strokeWidth={1.3} />
              <p className="akki-lead mb-2">Nothing to attend to yet.</p>
              <p className="text-[13px] text-[var(--muted)] mb-5">Upload a pack to let AKKI surface signals, then compose a briefing for your next meeting.</p>
              <Link to="/app/workspace">
                <Button className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-9 px-4 text-sm">
                  <FileText className="w-3.5 h-3.5 mr-2" /> Upload a pack
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-4">
              {items.map((it) => (
                <StreamCard
                  key={`${it._kind}-${it.id}`}
                  type={it.type}
                  lead={it.lead}
                  timestamp={it.timestamp}
                  chips={it.chips}
                  gesture={it.gesture}
                  to={it.to}
                  data-testid={`stream-${it._kind}-${it.id}`}
                />
              ))}
            </div>
          )}
        </div>

        {/* Companion rail — 280px, cream, v4.2 */}
        <aside className="hidden lg:block" data-testid="companion-rail">
          <div className="sticky top-[88px] space-y-8">
            <div>
              <p className="akki-overline mb-3">Sources in this context</p>
              {documents.length === 0 ? (
                <p className="text-[12px] text-[var(--muted)] italic">No documents yet.</p>
              ) : (
                <div className="space-y-1">
                  {documents.slice(0, 5).map((d) => (
                    <Link
                      key={d.id}
                      to={`/app/documents/${d.id}`}
                      className="flex items-center gap-2 py-1.5 px-2 rounded-sm hover:bg-[var(--cream-deep)] group"
                    >
                      <FileText className="w-3.5 h-3.5 text-[var(--accent)] shrink-0" strokeWidth={1.8} />
                      <span className="text-[13px] text-[var(--deep)] truncate flex-1">{d.name}</span>
                    </Link>
                  ))}
                  <Link to="/app/workspace" className="akki-gesture mt-2 ml-2 text-[13px]">
                    All documents <ArrowRight className="w-3 h-3" />
                  </Link>
                </div>
              )}
            </div>

            <div>
              <p className="akki-overline mb-3">Recent briefings</p>
              {briefings.length === 0 ? (
                <p className="text-[12px] text-[var(--muted)] italic">No briefings composed.</p>
              ) : (
                <div className="space-y-1">
                  {briefings.slice(0, 3).map((b) => (
                    <Link
                      key={b.id}
                      to="/app/briefings"
                      className="flex items-start gap-2 py-1.5 px-2 rounded-sm hover:bg-[var(--cream-deep)] group"
                    >
                      <ScrollText className="w-3.5 h-3.5 text-[var(--accent)] shrink-0 mt-0.5" strokeWidth={1.8} />
                      <div className="min-w-0 flex-1">
                        <p className="text-[13px] text-[var(--deep)] truncate">{b.title}</p>
                        <p className="text-[11px] text-[var(--muted)]">v{b.version} · {b.items?.length || 0} items</p>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>

            <div className="border-t border-[var(--rule)] pt-5">
              <p className="akki-overline mb-3">Quick actions</p>
              <div className="space-y-2">
                <Link to="/app/workspace" className="flex items-center gap-2 text-[13px] text-[var(--deep)] hover:text-[var(--accent)]">
                  <FileText className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} /> Upload pack
                </Link>
                <Link to="/app/highlights" className="flex items-center gap-2 text-[13px] text-[var(--deep)] hover:text-[var(--accent)]">
                  <Sparkles className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} /> Generate signals
                </Link>
                <Link to="/app/briefings" className="flex items-center gap-2 text-[13px] text-[var(--deep)] hover:text-[var(--accent)]">
                  <ScrollText className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} /> Compose briefing
                </Link>
                <Link to="/app/workspace" className="flex items-center gap-2 text-[13px] text-[var(--deep)] hover:text-[var(--accent)]">
                  <MessageSquareText className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} /> Ask a question
                </Link>
              </div>
            </div>

            {contexts.length > 1 && (
              <div className="border-t border-[var(--rule)] pt-5">
                <p className="akki-overline mb-3">Other contexts</p>
                <div className="space-y-1">
                  {contexts.filter((c) => c.id !== contextId).slice(0, 4).map((c) => (
                    <p key={c.id} className="text-[12.5px] text-[var(--muted)] truncate">{c.name}</p>
                  ))}
                </div>
              </div>
            )}
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
