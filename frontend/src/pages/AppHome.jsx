import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import AppShell from "@/components/layout/AppShell";
import StreamCard from "@/components/stream/StreamCard";
import { useAuth } from "@/contexts/AuthContext";
import CycleStrip from "@/components/cycle/CycleStrip";
import useIsMobile from "@/hooks/useIsMobile";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  ArrowRight, FileText, Sparkles, ScrollText, Landmark, Briefcase,
  Layers, Globe, Mail, Clock,
  GripVertical, RotateCcw,
} from "lucide-react";
import ShareModal from "@/components/share/ShareModal";
import SandboxPackDrop from "@/components/sandbox/SandboxPackDrop";
import SandboxSampleDoc from "@/components/sandbox/SandboxSampleDoc";
import SandboxTutorial from "@/components/sandbox/SandboxTutorial";
import ObjectiveCheck from "@/components/sandbox/ObjectiveCheck";
import ReviewInboxCard from "@/components/cycle/ReviewInboxCard";
import WorkflowsHub from "@/components/home/WorkflowsHub";
import InSummaryTiles from "@/components/home/InSummaryTiles";
import RecentActivity from "@/components/home/RecentActivity";
import useDraggableSections from "@/hooks/useDraggableSections";

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
  const { account, activeContext, activeRole, contexts, availableRoles } = useAuth();
  const contextId = activeContext?.id;
  const isMobile = useIsMobile();
  const [scope, setScope] = useState("current"); // "current" | "all"
  const [signals, setSignals] = useState([]);
  const [briefings, setBriefings] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [shared, setShared] = useState([]);
  const [briefs, setBriefs] = useState([]);
  const [loading, setLoading] = useState(true);
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
        const [s, b, d, sh, bf] = await Promise.all([
          api.get(`/contexts/${contextId}/signals`),
          api.get(`/contexts/${contextId}/briefings`),
          api.get(`/contexts/${contextId}/documents`),
          sharedPromise,
          api.get(`/contexts/${contextId}/briefs?limit=50`).catch(() => ({ data: { items: [] } })),
        ]);
        setSignals(s.data || []);
        setBriefings(b.data || []);
        setDocuments(d.data || []);
        setShared(sh.data || []);
        setBriefs(bf.data?.items || []);
      } else {
        setSignals([]); setBriefings([]); setDocuments([]); setBriefs([]);
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
            <Link to="/app/first-session">
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
      {/* Fixed-height page: only inner content column scrolls.
          (Apr-2026 fix: removed overflow-hidden which was clipping the
          Workflows hub Quick Actions on narrow viewports.) */}
      <div className="min-h-[calc(100vh-4rem)] max-w-[1100px] mx-auto px-8 grid grid-cols-1 gap-10">
        {/* Main — sticky header + scrolling stream */}
        <div className="flex flex-col min-h-0 py-8">
          <div className="mb-6 akki-fade-up shrink-0">
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
              activeRole={activeRole}
              availableRoles={availableRoles}
            />
            {/* Cycle strip — Phase 2, Advisory 6. Pinned below the
                greeting/chooser, above the section board. */}
            {contextId ? (
              <div className="mt-6">
                <CycleStrip contextId={contextId} isMobile={isMobile} />
              </div>
            ) : null}
          </div>

          <div className="flex-1 min-h-0 flex flex-col overflow-hidden" data-testid="home-sections">
            {/* Sandbox-only: first-run guided tutorial card. Auto-dismisses
                once the user closes it; never re-appears. */}
            <SandboxTutorial contextId={contextId} isSandbox={!!account?.is_sandbox} />

            {/* 24-hour objective follow-up. Only fires after the tutorial
                window has elapsed AND the user captured a Q5 objective. */}
            <ObjectiveCheck contextId={contextId} />

            {/* Sandbox-only: AKKI proactively prepares a sample board pack
                the prospect can accept with one click. Sits ABOVE the
                drop-your-own affordance — most prospects won't have a
                real pack handy on first visit. (Apr-2026 user request.) */}
            <SandboxSampleDoc onAccepted={load} />

            {/* Sandbox-only: a discreet drop-your-own-pack affordance.
                Pinned — not draggable. */}
            <SandboxPackDrop onSignalsReady={load} />

            <DraggableHomeBoard />

            {/* Stream tabs and cards live below the draggable board.
                Pinned to the bottom of the home so the user always
                lands on what's new without having to scroll past it.*/}

            {/* Recent activity hook — a single chronological feed that
                replaces the old four-tab summary repeater. Pulls from the
                same fetched lists; no extra API calls. */}
            <RecentActivity
              signals={signals}
              briefings={briefings}
              documents={documents}
              shared={shared}
              briefs={briefs}
              contexts={contexts}
              hasMultipleContexts={hasMultipleContexts}
              scope={scope}
              onScopeChange={setScope}
            />
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
function ContextChooser({ contexts, activeContext, hasMultipleContexts, signals, briefings, documents, activeRole, availableRoles }) {
  const { switchContext, switchRole } = useAuth();

  // Role isolation: only show contexts where the user holds the *current*
  // active role. Switching role swaps the visible portfolio entirely.
  const roleScopedContexts = (contexts || []).filter(
    (c) => !c.my_role || c.my_role === activeRole
  );
  const sortedContexts = roleScopedContexts.slice().sort(
    (a, b) => (a.id === activeContext?.id ? -1 : b.id === activeContext?.id ? 1 : 0),
  );

  // Counts per role for the editorial intro line.
  const nedCount = (contexts || []).filter((c) => c.my_role === "ned" && c.status !== "archived").length;
  const execCount = (contexts || []).filter((c) => c.my_role === "executive" && c.status !== "archived").length;

  const intro = (() => {
    if (nedCount && execCount) {
      return `You work in ${nedCount + execCount} ${(nedCount + execCount) === 1 ? "company" : "companies"}. ${nedCount} as NED and ${execCount} as Executive. Where would you like to start?`;
    }
    if (nedCount) return `You sit on ${nedCount} ${nedCount === 1 ? "board" : "boards"} as NED. Where would you like to start?`;
    if (execCount) return `You operate in ${execCount} ${execCount === 1 ? "company" : "companies"} as Executive. Where would you like to start?`;
    return "Where are you working today?";
  })();

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

  // Always render the role toggle when the user holds both roles. This
  // is the "single source of truth" for the role lens — switching here
  // re-anchors the whole experience (see AuthContext.switchRole).
  const showRoleToggle = (availableRoles || []).length >= 2;

  if (hasMultipleContexts || showRoleToggle) {
    return (
      <div className="mt-5" data-testid="home-context-chooser">
        {showRoleToggle && (
          <div className="mb-4 flex items-center gap-2" data-testid="home-role-toggle">
            <span className="akki-overline text-[var(--muted)] mr-1">Acting as</span>
            {availableRoles.includes("ned") && (
              <button
                onClick={() => activeRole !== "ned" && switchRole("ned")}
                className={`px-3 py-1 rounded-full text-[12.5px] border transition-colors ${
                  activeRole === "ned"
                    ? "bg-[var(--ink)] text-[var(--cream)] border-[var(--ink)]"
                    : "bg-white text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)]"
                }`}
                data-testid={`home-role-ned${activeRole === "ned" ? "-active" : ""}`}
              >
                NED
              </button>
            )}
            {availableRoles.includes("executive") && (
              <button
                onClick={() => activeRole !== "executive" && switchRole("executive")}
                className={`px-3 py-1 rounded-full text-[12.5px] border transition-colors ${
                  activeRole === "executive"
                    ? "bg-[var(--ink)] text-[var(--cream)] border-[var(--ink)]"
                    : "bg-white text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)]"
                }`}
                data-testid={`home-role-executive${activeRole === "executive" ? "-active" : ""}`}
              >
                Exec
              </button>
            )}
          </div>
        )}

        <p className="akki-overline mb-3 text-[var(--muted)]" data-testid="home-chooser-intro">
          {intro}
        </p>
        {sortedContexts.length === 0 ? (
          <p className="text-[13px] text-[var(--muted)] italic">
            No companies as {activeRole === "ned" ? "NED" : "Executive"} yet. Add one from the right rail.
          </p>
        ) : (
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
        )}
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

