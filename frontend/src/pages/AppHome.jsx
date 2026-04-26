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
import ReviewInboxCard from "@/components/cycle/ReviewInboxCard";
import PlaysInProgressStrip from "@/components/home/PlaysInProgressStrip";
import PlayReadyCards from "@/components/home/PlayReadyCards";
import QuickActions from "@/components/home/QuickActions";
import InSummaryTiles from "@/components/home/InSummaryTiles";

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
      <div className="h-[calc(100vh-4rem)] max-w-[1100px] mx-auto px-8 grid grid-cols-1 gap-10 overflow-hidden">
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
            {/* Sandbox-only: a discreet drop-your-own-pack affordance. Never
                renders outside sandbox contexts. */}
            <SandboxPackDrop onSignalsReady={load} />

            {/* Auto-launched workflows the executive hasn't opened yet. */}
            <PlayReadyCards />

            {/* Workflows in progress — restrained chips back into active flow. */}
            <PlaysInProgressStrip />

            {/* Quick actions — three intent-anchored tiles that ARE the
                workflows (start/resume Board Pack or Pre-Board at a
                contextual stage). */}
            <QuickActions />

            {/* In summary — the numbers the user would scan first thing. */}
            <InSummaryTiles />

            {/* Cross-context review inbox card. */}
            <ReviewInboxCard />

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
                    title={`Show only ${activeContext?.name || "this context"}`}
                  >
                    This context
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
                                  to="/app/highlights"
                                  gesture={{ label: "Open signal", to: "/app/highlights" }}
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
                                source={aggregated && b.context_name ? {
                                  label: b.context_name.split(" ")[0].toUpperCase().slice(0, 12),
                                  title: b.context_name,
                                  tone: "context",
                                } : null}
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
                                to={sh.item_type === "briefing" ? "/app/briefings" : "/app/highlights"}
                                gesture={{ label: "Look at this", to: sh.item_type === "briefing" ? "/app/briefings" : "/app/highlights" }}
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
          to="/app/highlights"
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
