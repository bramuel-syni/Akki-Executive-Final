import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import AppShell from "@/components/layout/AppShell";
import StreamCard from "@/components/stream/StreamCard";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  ArrowRight, FileText, Sparkles, ScrollText, Landmark, Briefcase,
  Layers,
} from "lucide-react";

const CONFIDENCE_LABEL = { high: "High confidence", medium: "Medium confidence", low: "Low confidence" };

function greeting(name) {
  const h = new Date().getHours();
  const g = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  return `${g}, ${name}.`;
}

const HOME_TABS = [
  { key: "signals",   label: "Top signals",    icon: Sparkles,   viewAllTo: "/app/highlights" },
  { key: "briefings", label: "Top briefings",  icon: ScrollText, viewAllTo: "/app/briefings" },
  { key: "documents", label: "New documents",  icon: FileText,   viewAllTo: "/app/workspace" },
];

export default function AppHome() {
  const { account, activeContext, activeRole, contexts } = useAuth();
  const contextId = activeContext?.id;
  const [signals, setSignals] = useState([]);
  const [briefings, setBriefings] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("signals");

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
    } catch { /* silent — empty sections render */ }
    finally { setLoading(false); }
  }, [contextId]);

  useEffect(() => { load(); }, [load]);

  // Top 3 signals: prefer high-conf risks first, then high-conf others, then the rest by recency
  const topSignals = useMemo(() => {
    const score = (s) => (s.confidence === "high" ? 2 : s.confidence === "medium" ? 1 : 0)
                        + (s.type === "risk" ? 0.5 : 0);
    return [...signals].sort((a, b) => {
      const sc = score(b) - score(a);
      if (sc !== 0) return sc;
      return new Date(b.created_at) - new Date(a.created_at);
    }).slice(0, 3);
  }, [signals]);

  const topBriefings = useMemo(
    () => [...briefings].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 2),
    [briefings]
  );

  const newDocs = useMemo(
    () => [...documents].sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 3),
    [documents]
  );

  const isDeclared = account?.declared_role && account.declared_role !== "undeclared";
  const auditComplete = !!activeContext?.progress_state?.onboarding_completed;
  const firstName = (account?.name || "there").split(" ")[0];
  const RoleIcon = activeRole === "ned" ? Landmark : Briefcase;

  if (!isDeclared || !auditComplete) {
    return (
      <AppShell>
        <div className="max-w-3xl mx-auto px-8 py-16 akki-fade-up">
          <p className="akki-overline mb-3">Home · {activeContext?.name || "Your context"}</p>
          <h1 className="akki-greeting mb-6">{greeting(firstName)}</h1>
          <div className="bg-white border border-[var(--rule)] rounded-lg p-10 relative overflow-hidden">
            <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)]" />
            <p className="akki-overline mb-3">Next · 7 minutes</p>
            <h2 className="akki-serif text-[22px] mb-4">
              {!isDeclared
                ? <>Declare your role. Run the audit to unlock your signals.</>
                : <>Finish the board-focused audit to unlock your signals.</>}
            </h2>
            <p className="akki-serif text-[15px] text-[var(--deep)] leading-relaxed mb-8 max-w-xl">
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
      {/* Fixed-height page: only inner content column scrolls */}
      <div className="h-[calc(100vh-4rem)] max-w-[1280px] mx-auto px-8 grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-10 overflow-hidden">
        {/* Main — sticky header + scrolling stream */}
        <div className="flex flex-col min-h-0 py-8">
          <div className="mb-6 akki-fade-up shrink-0">
            <p className="akki-overline mb-2 flex items-center gap-2">
              <RoleIcon className="w-3 h-3 text-[var(--accent)]" strokeWidth={2} />
              Acting as {activeRole === "ned" ? "Non-Executive Director" : "Executive"}
              <span className="text-[var(--muted)]/60">·</span>
              <span>{activeContext?.name}</span>
            </p>
            <h1 className="akki-greeting">{greeting(firstName)}</h1>
            <p className="akki-meta mt-2 max-w-xl">
              {signals.length + briefings.length + documents.length === 0
                ? "Your workspace is quiet. Upload a pack to let AKKI surface signals."
                : `A brief scan of what's moving in ${activeContext?.name}.`}
            </p>
          </div>

          <div className="flex-1 min-h-0 flex flex-col overflow-hidden" data-testid="home-sections">
            {/* Tab strip — next to each other per user's ask */}
            <div className="shrink-0 flex items-center border-b border-[var(--rule)] mb-5">
              <div className="flex items-center gap-0" data-testid="home-tabs">
                {HOME_TABS.map((t) => {
                  const Icon = t.icon;
                  const active = activeTab === t.key;
                  const count = t.key === "signals" ? signals.length
                              : t.key === "briefings" ? briefings.length
                              : documents.length;
                  return (
                    <button
                      key={t.key}
                      onClick={() => setActiveTab(t.key)}
                      className={`relative flex items-center gap-2 px-4 py-2.5 text-[13.5px] transition-colors ${
                        active
                          ? "text-[var(--ink)] font-medium"
                          : "text-[var(--muted)] hover:text-[var(--deep)]"
                      }`}
                      data-testid={`home-tab-${t.key}`}
                    >
                      <Icon className={`w-3.5 h-3.5 ${active ? "text-[var(--accent)]" : ""}`} strokeWidth={1.8} />
                      <span>{t.label}</span>
                      <span className={`text-[11px] ${active ? "text-[var(--accent)]" : "text-[var(--muted)]/70"}`}>
                        {count}
                      </span>
                      {active && (
                        <span className="absolute left-0 right-0 -bottom-px h-[2px] bg-[var(--accent)]" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Scrolling panel — only one active stream visible */}
            <div className="flex-1 min-h-0 overflow-y-auto pr-2 -mr-2 pb-8" data-testid="home-scroll">
              {(() => {
                const currentTab = HOME_TABS.find((t) => t.key === activeTab);
                const hasItems =
                  (activeTab === "signals"   && topSignals.length > 0) ||
                  (activeTab === "briefings" && topBriefings.length > 0) ||
                  (activeTab === "documents" && newDocs.length > 0);
                const totalCount =
                  activeTab === "signals"   ? signals.length
                  : activeTab === "briefings" ? briefings.length
                  : documents.length;
                return (
                  <>
                    {activeTab === "signals" && (
                      <section data-testid="section-top-signals">
                        {loading ? (
                          <div className="h-24 flex items-center text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</div>
                        ) : topSignals.length === 0 ? (
                          <EmptySlot
                            icon={Sparkles}
                            copy="Upload a pack to let AKKI surface risks, opportunities, and gaps."
                            cta={{ label: "Upload pack", to: "/app/workspace" }}
                          />
                        ) : (
                          <motion.div
                            className="space-y-3"
                            initial="hidden" animate="show"
                            variants={{
                              hidden: {},
                              show: { transition: { staggerChildren: 0.06 } },
                            }}
                          >
                            {topSignals.map((s) => (
                              <motion.div
                                key={s.id}
                                variants={{
                                  hidden: { opacity: 0, y: 6 },
                                  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
                                }}
                              >
                                <StreamCard
                                  type={s.type}
                                  lead={s.headline}
                                  timestamp={s.created_at}
                                  chips={[
                                    { label: CONFIDENCE_LABEL[s.confidence] || "Medium confidence" },
                                    { label: (s.data_trust || "unrated") + " data" },
                                  ]}
                                  to="/app/highlights"
                                  gesture={{ label: "Open signal", to: "/app/highlights" }}
                                  data-testid={`home-signal-${s.id}`}
                                />
                              </motion.div>
                            ))}
                          </motion.div>
                        )}
                      </section>
                    )}

                    {activeTab === "briefings" && (
                      <section data-testid="section-top-briefings">
                        {loading ? null : topBriefings.length === 0 ? (
                          <EmptySlot
                            icon={ScrollText}
                            copy={signals.length === 0
                              ? "Briefings bundle your signals into a printable page. Generate signals first."
                              : "No briefings yet — compose your first for the next meeting."}
                            cta={signals.length === 0
                              ? { label: "Generate signals", to: "/app/highlights" }
                              : { label: "Compose briefing", to: "/app/briefings" }}
                          />
                        ) : (
                          <div className="space-y-3">
                            {topBriefings.map((b) => (
                              <StreamCard
                                key={b.id}
                                type="briefing"
                                lead={b.title}
                                timestamp={b.created_at}
                                chips={[
                                  { label: `v${b.version}` },
                                  { label: `${b.items?.length || 0} items` },
                                ]}
                                to="/app/briefings"
                                gesture={{ label: "Open briefing", to: "/app/briefings" }}
                                data-testid={`home-briefing-${b.id}`}
                              />
                            ))}
                          </div>
                        )}
                      </section>
                    )}

                    {activeTab === "documents" && (
                      <section data-testid="section-new-documents">
                        {loading ? null : newDocs.length === 0 ? (
                          <EmptySlot
                            icon={FileText}
                            copy="Drop a board pack, minute, or report in Workspace to get started."
                            cta={{ label: "Open Workspace", to: "/app/workspace" }}
                          />
                        ) : (
                          <div className="space-y-3">
                            {newDocs.map((d) => (
                              <StreamCard
                                key={d.id}
                                type="document"
                                lead={d.name}
                                timestamp={d.created_at}
                                chips={[
                                  { label: d.data_trust || "unrated" },
                                  ...(d.extracted_chars ? [{ label: `${(d.extracted_chars / 1000).toFixed(1)}k chars` }] : []),
                                ]}
                                to={`/app/documents/${d.id}`}
                                gesture={{ label: "Open document", to: `/app/documents/${d.id}` }}
                                data-testid={`home-doc-${d.id}`}
                              />
                            ))}
                          </div>
                        )}
                      </section>
                    )}

                    {/* Footer "View all" — appears AFTER the cards, inside the scroll box */}
                    {hasItems && currentTab && (
                      <div className="pt-6 mt-6 border-t border-[var(--rule)] flex items-center justify-between">
                        <span className="text-[12px] text-[var(--muted)]">
                          Showing {activeTab === "signals" ? topSignals.length
                                  : activeTab === "briefings" ? topBriefings.length
                                  : newDocs.length} of {totalCount}
                        </span>
                        <Link
                          to={currentTab.viewAllTo}
                          className="akki-gesture text-[13px]"
                          data-testid="home-view-all"
                        >
                          View all {currentTab.label.toLowerCase()} <ArrowRight className="w-3.5 h-3.5" />
                        </Link>
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          </div>
        </div>

        {/* Companion rail */}
        <aside className="hidden lg:block py-8 overflow-y-auto" data-testid="companion-rail">
          <div className="space-y-8">
            <div>
              <p className="akki-overline mb-3">Your portfolio</p>
              <div className="space-y-1 mb-2">
                {contexts.slice(0, 6).map((c) => (
                  <div key={c.id} className={`flex items-center gap-2 px-2 py-1.5 rounded-sm ${c.id === contextId ? "bg-[var(--cream-deep)]" : ""}`}>
                    <Layers className={`w-3 h-3 shrink-0 ${c.id === contextId ? "text-[var(--accent)]" : "text-[var(--muted)]"}`} />
                    <span className={`text-[13px] truncate ${c.id === contextId ? "text-[var(--ink)] font-medium" : "text-[var(--deep)]"}`}>{c.name}</span>
                  </div>
                ))}
              </div>
              <Link to="/app/contexts" className="akki-gesture text-[13px] ml-2">
                My portfolio <ArrowRight className="w-3 h-3" />
              </Link>
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
              </div>
            </div>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}

function EmptySlot({ icon: Icon, copy, cta }) {
  return (
    <div className="bg-white border border-dashed border-[var(--rule)] rounded-lg p-6 flex items-center gap-5">
      <div className="w-10 h-10 bg-[var(--cream-deep)] rounded-md flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4 text-[var(--muted)]" strokeWidth={1.5} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[13.5px] text-[var(--deep)]">{copy}</p>
      </div>
      {cta && (
        <Link to={cta.to} className="akki-gesture text-[13px] shrink-0">
          {cta.label} <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      )}
    </div>
  );
}
