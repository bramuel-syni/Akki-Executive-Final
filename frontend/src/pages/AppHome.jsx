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
  Layers, Globe, Mail, Clock,
} from "lucide-react";
import ShareModal from "@/components/share/ShareModal";
import SandboxPackDrop from "@/components/sandbox/SandboxPackDrop";
import SandboxTutorial from "@/components/sandbox/SandboxTutorial";
import ObjectiveCheck from "@/components/sandbox/ObjectiveCheck";
import ReviewInboxCard from "@/components/cycle/ReviewInboxCard";
import WorkflowsHub from "@/components/home/WorkflowsHub";
import InSummaryTiles from "@/components/home/InSummaryTiles";
import useDraggableSections from "@/hooks/useDraggableSections";
import { GripVertical, RotateCcw } from "lucide-react";

const CONFIDENCE_LABEL = { high: "High confidence", medium: "Medium confidence", low: "Low confidence" };

function greeting(name) {
  const h = new Date().getHours();
  const g = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  return `${g}, ${name}.`;
}

const HOME_TABS = [
  { key: "signals",   label: "Top signals",    icon: Sparkles,   viewAllTo: "/app/prepare" },
  { key: "briefings", label: "Top briefings",  icon: ScrollText, viewAllTo: "/app/prepare" },
  { key: "documents", label: "New documents",  icon: FileText,   viewAllTo: "/app/workspace" },
  { key: "shared",    label: "Shared with you", icon: Mail,      viewAllTo: null },
];

export default function AppHome() {
  const { account, activeContext, activeRole, contexts } = useAuth();
  const contextId = activeContext?.id;
  const [scope, setScope] = useState("current"); // "current" | "all"
  const [signals, setSignals] = useState([]);
  const [briefings, setBriefings] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [shared, setShared] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("signals");
  const [shareOn, setShareOn] = useState(null);  // signal currently being shared

  const hasMultipleContexts = (contexts?.length || 0) >= 2;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // Shared inbox is always loaded (cross-context)
      const sharedPromise = api.get(`/me/shares/inbox?limit=30`).catch(() => ({ data: [] }));

      if (scope === "all" && hasMultipleContexts) {
        const [agg, sh] = await Promise.all([
          api.get(`/me/home/stream?limit=20`),
          sharedPromise,
        ]);
        setSignals(agg.data?.signals || []);
        setBriefings(agg.data?.briefings || []);
        setDocuments([]); // documents are intentionally scoped to one context
        setShared(sh.data || []);
      } else if (contextId) {
        const [s, b, d, sh] = await Promise.all([
          api.get(`/contexts/${contextId}/signals`),
          api.get(`/contexts/${contextId}/briefings`),
          api.get(`/contexts/${contextId}/documents`),
          sharedPromise,
        ]);
        setSignals(s.data || []);
        setBriefings(b.data || []);
        setDocuments(d.data || []);
        setShared(sh.data || []);
      } else {
        setSignals([]); setBriefings([]); setDocuments([]);
        const sh = await sharedPromise;
        setShared(sh.data || []);
      }
    } catch { /* silent — empty sections render */ }
    finally { setLoading(false); }
  }, [contextId, scope, hasMultipleContexts]);

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
          <p className="akki-overline mb-3">Home · {activeContext?.name || "Your company"}</p>
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
      <div className="h-[calc(100vh-4rem)] max-w-[1100px] mx-auto px-8 grid grid-cols-1 gap-10 overflow-hidden">
        {/* Main — sticky header + scrolling stream */}
        <div className="flex flex-col min-h-0 py-8">
          <div className="mb-6 akki-fade-up shrink-0">
            <p className="akki-overline mb-2 flex items-center gap-2">
              <RoleIcon className="w-3 h-3 text-[var(--accent)]" strokeWidth={2} />
              Acting as {activeRole === "ned" ? "Non-Executive Director" : "Executive"}
            </p>
            <h1 className="akki-greeting">{greeting(firstName)}</h1>

            {/* Iter44 — deliberate context picker as the top action.
                The user shouldn't be auto-dropped into a context without
                a moment of awareness. If they have multiple contexts,
                this row asks them to choose; if they have one, it just
                names where they are with a soft lead into a relevant
                action. Replaces the Apr-2026 metrics strip which was
                duplicating the In-Summary tiles right below it. */}
            <ContextChooser
              contexts={contexts}
              activeContext={activeContext}
              hasMultipleContexts={hasMultipleContexts}
              signals={signals}
              briefings={briefings}
              documents={documents}
            />
          </div>

          <div className="flex-1 min-h-0 flex flex-col overflow-hidden" data-testid="home-sections">
            {/* Sandbox-only: first-run guided tutorial card. Auto-dismisses
                once the user closes it; never re-appears. */}
            <SandboxTutorial contextId={contextId} isSandbox={!!account?.is_sandbox} />

            {/* 24-hour objective follow-up. Only fires after the tutorial
                window has elapsed AND the user captured a Q5 objective. */}
            <ObjectiveCheck contextId={contextId} />

            {/* Sandbox-only: a discreet drop-your-own-pack affordance.
                Pinned — not draggable. */}
            <SandboxPackDrop onSignalsReady={load} />

            <DraggableHomeBoard />

            {/* Stream tabs and cards live below the draggable board.
                Pinned to the bottom of the home so the user always
                lands on what's new without having to scroll past it.*/}

            {/* Tab strip with a quiet scope toggle on the right.
                The 'All boards' toggle only appears when the user has 2+ contexts. */}
            <div className="shrink-0 flex items-center border-b border-[var(--rule)] mb-5 gap-4">
              <div className="flex items-center gap-0" data-testid="home-tabs">
                {HOME_TABS.map((t) => {
                  const Icon = t.icon;
                  const active = activeTab === t.key;
                  const count = t.key === "signals" ? signals.length
                              : t.key === "briefings" ? briefings.length
                              : t.key === "shared" ? shared.length
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

              {hasMultipleContexts && activeTab !== "shared" && (
                <div
                  className="ml-auto inline-flex items-center rounded-sm border border-[var(--rule)] bg-white p-[3px] shrink-0"
                  data-testid="home-scope-toggle"
                >
                  <button
                    onClick={() => setScope("current")}
                    className={`px-2.5 py-1 text-[11.5px] uppercase tracking-wider rounded-[3px] transition-colors ${
                      scope === "current"
                        ? "bg-[var(--cream-deep)] text-[var(--ink)]"
                        : "text-[var(--muted)] hover:text-[var(--ink)]"
                    }`}
                    data-testid="home-scope-current"
                    title={`Show only ${activeContext?.name || "this company"}`}
                  >
                    This company
                  </button>
                  <button
                    onClick={() => setScope("all")}
                    className={`px-2.5 py-1 text-[11.5px] uppercase tracking-wider rounded-[3px] inline-flex items-center gap-1 transition-colors ${
                      scope === "all"
                        ? "bg-[var(--accent)] text-white"
                        : "text-[var(--muted)] hover:text-[var(--ink)]"
                    }`}
                    data-testid="home-scope-all"
                    title="Aggregate across every board and context you're a member of"
                  >
                    <Globe className="w-3 h-3" strokeWidth={2} /> All boards
                  </button>
                </div>
              )}
            </div>

            {/* Scrolling panel — only one active stream visible */}
            <div className="flex-1 min-h-0 overflow-y-auto pr-2 -mr-2 pb-8" data-testid="home-scroll">
              {(() => {
                const currentTab = HOME_TABS.find((t) => t.key === activeTab);
                const hasItems =
                  (activeTab === "signals"   && topSignals.length > 0) ||
                  (activeTab === "briefings" && topBriefings.length > 0) ||
                  (activeTab === "documents" && newDocs.length > 0) ||
                  (activeTab === "shared"    && shared.length > 0);
                const totalCount =
                  activeTab === "signals"   ? signals.length
                  : activeTab === "briefings" ? briefings.length
                  : activeTab === "shared"    ? shared.length
                  : documents.length;
                const aggregated = scope === "all" && hasMultipleContexts;
                return (
                  <>
                    {activeTab === "signals" && (
                      <section data-testid="section-top-signals">
                        {loading ? (
                          <div className="h-24 flex items-center text-[12px] uppercase tracking-widest text-[var(--muted)]">Loading…</div>
                        ) : topSignals.length === 0 ? (
                          aggregated ? (
                            <EmptySlot
                              icon={Sparkles}
                              copy="No signals across any of your boards yet."
                              cta={{ label: "Upload pack", to: "/app/workspace" }}
                            />
                          ) : (
                            <NextBestActionCard />
                          )
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
                                  source={aggregated && s.context_name ? {
                                    label: s.context_name.split(" ")[0].toUpperCase().slice(0, 12),
                                    title: s.context_name,
                                    tone: "context",
                                  } : null}
                                  chips={[
                                    { label: CONFIDENCE_LABEL[s.confidence] || "Medium confidence" },
                                    { label: (s.data_trust || "unrated") + " data" },
                                  ]}
                                  to="/app/prepare"
                                  gesture={{ label: "Open signal", to: "/app/prepare" }}
                                  secondary={[
                                    { label: "Share →", onClick: () => setShareOn(s) },
                                  ]}
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
                              ? { label: "Generate signals", to: "/app/prepare" }
                              : { label: "Compose briefing", to: "/app/prepare" }}
                          />
                        ) : (
                          <div className="space-y-3">
                            {topBriefings.map((b) => (
                              <StreamCard
                                key={b.id}
                                type="briefing"
                                lead={b.title}
                                timestamp={b.created_at}
                                source={aggregated && b.context_name ? {
                                  label: b.context_name.split(" ")[0].toUpperCase().slice(0, 12),
                                  title: b.context_name,
                                  tone: "context",
                                } : null}
                                chips={[
                                  { label: `v${b.version}` },
                                  { label: `${b.items?.length || 0} items` },
                                ]}
                                to="/app/prepare"
                                gesture={{ label: "Open briefing", to: "/app/prepare" }}
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
                            copy={aggregated
                              ? "Switch to a single context to browse its documents."
                              : "Drop a board pack, minute, or report in Workspace to get started."}
                            cta={aggregated
                              ? { label: "Choose a context", to: "/app/manage?tab=companies" }
                              : { label: "Open Workspace", to: "/app/workspace" }}
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

                    {activeTab === "shared" && (
                      <section data-testid="section-shared-with-you">
                        {loading ? null : shared.length === 0 ? (
                          <EmptySlot
                            icon={Mail}
                            copy="Nothing shared with you yet. When a colleague shares a signal or briefing, it lands here."
                            cta={null}
                          />
                        ) : (
                          <div className="space-y-3" data-testid="shared-with-you-list">
                            {shared.map((sh) => (
                              <StreamCard
                                key={sh.id}
                                type={sh.item_type === "briefing" ? "briefing" : "signal"}
                                lead={sh.item_preview || sh.subject || "(no preview)"}
                                timestamp={sh.created_at}
                                source={{
                                  label: `SHARED BY ${(sh.shared_by_name || sh.shared_by_email || "someone").split(" ")[0].toUpperCase()}`,
                                  title: sh.shared_by_email,
                                  tone: "share",
                                }}
                                chips={[
                                  { label: `From ${sh.context_name || "a context"}` },
                                  ...(sh.message ? [{ label: "with a note" }] : []),
                                ]}
                                to={sh.item_type === "briefing" ? "/app/prepare" : "/app/prepare"}
                                gesture={{ label: "Look at this", to: sh.item_type === "briefing" ? "/app/prepare" : "/app/prepare" }}
                                data-testid={`shared-card-${sh.id}`}
                              />
                            ))}
                          </div>
                        )}
                      </section>
                    )}

                    {/* Footer "View all" — appears AFTER the cards, inside the scroll box */}
                    {hasItems && currentTab && currentTab.viewAllTo && (
                      <div className="pt-6 mt-6 border-t border-[var(--rule)] flex items-center justify-between">
                        <span className="text-[12px] text-[var(--muted)]">
                          Showing {activeTab === "signals" ? topSignals.length
                                  : activeTab === "briefings" ? topBriefings.length
                                  : activeTab === "shared" ? shared.length
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

        {/* Companion rail removed — its portfolio + quick-actions content
            now lives in the permanent right-side <PortfolioRail /> + the
            on-page <QuickActions /> tiles. Keeping the grid column
            structure unchanged would cause an empty gutter, so we let the
            main content fill the row instead. */}
      </div>

      <ShareModal
        open={!!shareOn}
        onClose={() => setShareOn(null)}
        contextId={shareOn?.context_id || contextId}
        itemType="signal"
        item={shareOn ? { ...shareOn, context_name: shareOn.context_name || activeContext?.name } : null}
      />
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

/**
 * NextBestActionCard — first-time-account hero. Surfaces the single most
 * valuable action a new user can take (upload a pack, AKKI drafts signals in
 * ~40s) in an editorial-grade card rather than a humble EmptySlot. Addresses
 * the "no clear first step" gap on the real-account home.
 */
function NextBestActionCard() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      className="bg-gradient-to-br from-white to-[var(--cream-deep)] border border-[var(--accent)]/15 rounded-lg p-8 relative overflow-hidden"
      data-testid="home-nba-card"
    >
      <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-[var(--accent)]" />
      <p className="akki-overline mb-3 flex items-center gap-2">
        <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Your next best action
      </p>
      <h3 className="akki-serif text-[24px] font-normal text-[var(--ink)] leading-snug mb-3 max-w-2xl">
        Upload your last board pack. AKKI will surface risks, opportunities, and gaps in about forty seconds.
      </h3>
      <p className="text-[13.5px] text-[var(--deep)] leading-relaxed max-w-2xl mb-6">
        Every signal cites the exact page it came from. Nothing leaves your context without a receipt.
      </p>
      <div className="flex items-center gap-3 flex-wrap">
        <Link
          to="/app/workspace"
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white text-[13.5px] font-medium rounded-md transition-colors"
          data-testid="home-nba-upload"
        >
          <FileText className="w-3.5 h-3.5" strokeWidth={1.8} /> Upload a pack
        </Link>
        <Link
          to="/app/prepare"
          className="inline-flex items-center gap-2 px-4 py-2.5 border border-[var(--rule)] hover:border-[var(--accent)]/40 bg-white text-[13.5px] rounded-md text-[var(--deep)] hover:text-[var(--ink)] transition-colors"
          data-testid="home-nba-generate"
        >
          <Sparkles className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} /> Or generate without uploading
        </Link>
      </div>
      <p className="text-[11.5px] text-[var(--muted)] mt-5 flex items-center gap-2">
        <Clock className="w-3 h-3" /> PDF, DOCX, or TXT · up to 20MB · stays in this context
      </p>
    </motion.div>
  );
}

/**
 * ContextChooser — the deliberate "you are here" moment at the top of
 * Home. Per Apr-2026 user feedback ("don't sign me up to a specific
 * company automatically"):
 *
 *  · If the user has 2+ contexts: present the chooser as the primary
 *    top action so they consciously pick where they're working before
 *    doing anything else. Defaults to the most recently active.
 *  · If the user has exactly 1 context: render a soft-lead line that
 *    NAMES where they are (no surprise) and points them at the most
 *    interesting thing AKKI noticed — not a metrics strip.
 */
function ContextChooser({ contexts, activeContext, hasMultipleContexts, signals, briefings, documents }) {
  const { switchContext } = useAuth();
  const sortedContexts = (contexts || []).slice().sort(
    (a, b) => (a.id === activeContext?.id ? -1 : b.id === activeContext?.id ? 1 : 0),
  );

  // The "soft lead" line for the single-context case — pulls the most
  // interesting thing AKKI has on the user's plate today.
  const softLead = (() => {
    if (signals.length > 0) {
      const top = signals[0];
      return {
        label: "Newest signal worth a look",
        text: top.headline || top.title,
        href: "/app/prepare",
      };
    }
    if (briefings.length > 0) {
      const top = briefings[0];
      return {
        label: "Latest brief on your desk",
        text: top.title,
        href: "/app/prepare",
      };
    }
    if (documents.length > 0) {
      const top = documents[0];
      return {
        label: "Most recent document",
        text: top.name,
        href: `/app/documents/${top.id}`,
      };
    }
    return null;
  })();

  if (hasMultipleContexts) {
    return (
      <div className="mt-5" data-testid="home-context-chooser">
        <p className="akki-overline mb-3 text-[var(--muted)]">
          Where are you working today?
        </p>
        <div className="flex flex-wrap gap-2">
          {sortedContexts.map((c) => {
            const active = c.id === activeContext?.id;
            return (
              <button
                key={c.id}
                onClick={() => !active && switchContext(c.id)}
                className={`px-4 py-2 rounded-md border text-[13px] transition-colors ${
                  active
                    ? "bg-[var(--ink)] text-[var(--cream)] border-[var(--ink)]"
                    : "bg-white text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)] hover:text-[var(--ink)]"
                }`}
                data-testid={`home-context-chooser-${c.id}${active ? "-active" : ""}`}
              >
                <span className="akki-serif">{c.name}</span>
                {active && <span className="text-[10px] uppercase tracking-wider ml-2 opacity-70">Active</span>}
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="mt-3" data-testid="home-soft-lead">
      <p className="akki-meta">
        Working on <strong className="text-[var(--ink)]">{activeContext?.name}</strong>.
      </p>
      {softLead && (
        <Link
          to={softLead.href}
          className="mt-3 inline-flex items-start gap-3 max-w-[640px] group"
          data-testid="home-soft-lead-link"
        >
          <span className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--muted)] mt-1 shrink-0 w-[170px]">
            {softLead.label}
          </span>
          <span className="akki-serif text-[15px] text-[var(--deep)] leading-snug group-hover:text-[var(--accent)] transition-colors line-clamp-2">
            {softLead.text} →
          </span>
        </Link>
      )}
    </div>
  );
}

/**
 * DraggableHomeBoard — wraps the three rearrangeable home sections
 * (InSummaryTiles, WorkflowsHub, ReviewInboxCard) in drag-to-reorder
 * cards. Order is persisted to localStorage per user (akki:section-order:home).
 *
 * Per user feedback (iter34): "The board needs to be moveable / draggable
 * around the page." Sandbox drop and the stream tabs are intentionally
 * pinned (anchor + recency) so the page still has a stable spine.
 */
function DraggableHomeBoard() {
  // Memoise the section list so the hook doesn't see a new array on
  // every render and reset the order on each refresh.
  const sections = useMemo(() => ([
    { key: "summary",   node: <InSummaryTiles />,    label: "In summary" },
    { key: "workflows", node: <WorkflowsHub />,      label: "Workflows" },
    { key: "inbox",     node: <ReviewInboxCard />,   label: "Inbox" },
  ]), []);

  const { items, getDragProps, getHandleProps, reset, draggingKey, overKey } =
    useDraggableSections("home", sections);

  // Hide the reset gesture unless the user has actually reordered
  // anything — keeps the page quiet by default.
  const hasReordered = useMemo(() => {
    const baseline = ["summary", "workflows", "inbox"];
    const current = items.map((s) => s.key);
    return current.join("|") !== baseline.join("|");
  }, [items]);

  return (
    <section data-testid="home-draggable-board" className="mb-1">
      {hasReordered && (
        <div className="flex justify-end mb-1.5">
          <button
            onClick={reset}
            className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] hover:text-[var(--accent)] inline-flex items-center gap-1"
            data-testid="home-board-reset"
            title="Reset card order to the AKKI default"
          >
            <RotateCcw className="w-3 h-3" /> Reset layout
          </button>
        </div>
      )}
      <div className="space-y-0">
        {items.map((it) => (
          <div
            key={it.key}
            {...getDragProps(it.key)}
            data-testid={`home-section-${it.key}`}
            className={`relative group/section transition-all ${
              draggingKey === it.key ? "opacity-40" : ""
            } ${
              overKey === it.key && draggingKey && draggingKey !== it.key
                ? "ring-2 ring-[var(--accent)]/40 ring-offset-2 ring-offset-[var(--cream)] rounded-lg"
                : ""
            }`}
          >
            {/* Drag handle — appears on hover so it never adds visual
                noise when the user is reading. */}
            <div
              {...getHandleProps(it.key)}
              className="absolute left-[-26px] top-3 opacity-0 group-hover/section:opacity-100 transition-opacity cursor-grab active:cursor-grabbing text-[var(--muted)]/50 hover:text-[var(--accent)] p-1 rounded-sm"
              data-testid={`home-section-handle-${it.key}`}
              title={`Drag · ${it.label}`}
            >
              <GripVertical className="w-3.5 h-3.5" />
            </div>
            {it.node}
          </div>
        ))}
      </div>
    </section>
  );
}

