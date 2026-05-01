/**
 * HomeV2 — Phase 5 / Advisory 1 "river of changes".
 *
 * Mounted when `?home=v2` is present in the URL AND the account is not in
 * sandbox mode (see wrapper in AppHome.jsx). A new user who hasn't
 * finished First Session is already redirected by FirstSessionGuard
 * before we ever render, so we can assume an onboarded (or grandfathered)
 * account here.
 *
 * Desktop layout: 3-column grid  →  [240 · 1fr · 320]
 *   left rail   : condensed context switcher
 *   main column : greeting + Phase-2 CycleStrip + reverse-chronological river
 *   right rail  : "Awaiting you" pinned queue (hides when empty)
 *
 * Mobile (<md) : single column. Right-rail collapses to a Sheet that
 * opens from the bottom when there are pending approvals.
 *
 * No spinners, no emojis, no progress bars, no drag-to-reorder, no tabs.
 * Cream / oxblood / navy, Georgia-serif heads, akki-overline labels.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import CycleStrip from "@/components/cycle/CycleStrip";
import useIsMobile from "@/hooks/useIsMobile";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import {
  FileText, Sparkles, ScrollText, AlertTriangle, TrendingUp, CircleSlash,
  Plus, Copy as CopyIcon, ArrowRight, Inbox, AtSign,
} from "lucide-react";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function greeting(name) {
  const h = new Date().getHours();
  const g = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  return `${g}, ${name}.`;
}

function formatStamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday = d.toDateString() === yesterday.toDateString();
  if (sameDay) {
    return `Today · ${d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false })}`;
  }
  if (isYesterday) return "Yesterday";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// ---------------------------------------------------------------------------
// Left rail — condensed context switcher
// ---------------------------------------------------------------------------
function ContextRail({ activeContextId, onSwitch, streamContexts }) {
  const { contexts } = useAuth();
  const ordered = useMemo(() => {
    if (!contexts || contexts.length === 0) return [];
    const filtered = contexts.filter((c) => c.status !== "archived");
    return filtered.slice().sort((a, b) =>
      (a.id === activeContextId ? -1 : b.id === activeContextId ? 1 : 0)
    );
  }, [contexts, activeContextId]);

  // Count items per context from the current river payload — a proxy for
  // "what's new there" without a separate fetch.
  const countsByCtx = useMemo(() => {
    const m = {};
    (streamContexts || []).forEach((c) => {
      m[c.id] = m[c.id] || 0;
    });
    return m;
  }, [streamContexts]);
  void countsByCtx; // currently decorative; counts TBD in next pass

  return (
    <aside
      className="hidden md:flex flex-col min-w-0 pr-3"
      data-testid="homev2-context-rail"
    >
      <p className="akki-overline text-[10.5px] tracking-[0.22em] text-[var(--muted)] mb-3">
        YOUR BOARDS
      </p>
      <div className="flex flex-col gap-1">
        {ordered.map((c) => {
          const active = c.id === activeContextId;
          const rolePill =
            c.my_role === "ned" ? "NED" : c.my_role === "executive" ? "Exec" : null;
          return (
            <button
              key={c.id}
              type="button"
              onClick={() => !active && onSwitch(c.id)}
              className={`relative text-left px-3 py-2.5 text-[13.5px] rounded-sm transition-colors border border-transparent ${
                active
                  ? "bg-white border-[var(--border,#e2d9cf)]"
                  : "hover:bg-white/60"
              }`}
              data-testid={`homev2-ctx-${c.id}${active ? "-active" : ""}`}
            >
              {active && (
                <span className="absolute left-0 top-1 bottom-1 w-[3px] bg-[var(--accent)] rounded-r" />
              )}
              <div className="flex items-start justify-between gap-2">
                <span className="akki-serif text-[14px] text-[var(--ink)] leading-tight line-clamp-2">
                  {c.name}
                </span>
                {rolePill && (
                  <span className="shrink-0 text-[9.5px] akki-overline tracking-[0.14em] text-[var(--muted)] mt-[3px]">
                    {rolePill}
                  </span>
                )}
              </div>
            </button>
          );
        })}
      </div>
      <div className="mt-4 pt-3 border-t border-[var(--border,#e2d9cf)]">
        <Link
          to="/app/contexts/new"
          className="text-[12px] text-[var(--muted)] hover:text-[var(--accent)] inline-flex items-center gap-1"
          data-testid="homev2-new-context"
        >
          <Plus size={12} /> New context
        </Link>
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Stream cards
// ---------------------------------------------------------------------------
const SIGNAL_ICON = {
  risk: AlertTriangle,
  opportunity: TrendingUp,
  gap: CircleSlash,
};

function RiverCard({ entry }) {
  const { kind, headline, body, href, stamp, context_name, meta_icon: Icon, meta_label } = entry;
  return (
    <Link
      to={href}
      className="block border-l-2 border-transparent hover:border-[var(--accent)] hover:bg-white/60 transition-colors px-4 py-3.5 -mx-4"
      data-testid={`homev2-card-${kind}`}
    >
      <div className="flex items-center gap-3 mb-1">
        {Icon ? (
          <Icon size={13} className="text-[var(--accent)] shrink-0" />
        ) : null}
        <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] truncate">
          {stamp}{context_name ? <span className="opacity-60"> · {context_name}</span> : null}{meta_label ? <span className="opacity-60"> · {meta_label}</span> : null}
        </p>
      </div>
      <p className="akki-serif text-[15px] md:text-[16px] text-[var(--ink)] leading-snug line-clamp-2 mb-0.5">
        {headline}
      </p>
      {body ? (
        <p className="text-[13px] text-[var(--muted)] leading-[1.55] line-clamp-2">
          {body}
        </p>
      ) : null}
    </Link>
  );
}

function buildRiver({ signals, briefings, documents, approvals }) {
  const entries = [];
  (signals || []).forEach((s) => {
    const t = (s.type || "").toLowerCase();
    const Icon = SIGNAL_ICON[t] || Sparkles;
    entries.push({
      kind: "signal_surfaced",
      created_at: s.created_at,
      stamp: formatStamp(s.created_at),
      context_name: s.context_name,
      meta_icon: Icon,
      meta_label: t ? t.charAt(0).toUpperCase() + t.slice(1) : "Signal",
      headline: s.headline || s.title || "Signal surfaced",
      body: s.rationale || s.summary || null,
      href: `/app/prepare?signal=${encodeURIComponent(s.id)}`,
    });
  });
  (briefings || []).forEach((b) => {
    entries.push({
      kind: "briefing_drafted",
      created_at: b.created_at,
      stamp: formatStamp(b.created_at),
      context_name: b.context_name,
      meta_icon: ScrollText,
      meta_label: "Briefing",
      headline: b.title || b.subject || "Briefing drafted",
      body: b.opening_paragraph || b.summary || null,
      href: `/app/prepare?briefing=${encodeURIComponent(b.id)}`,
    });
  });
  (documents || []).forEach((d) => {
    entries.push({
      kind: "document_added",
      created_at: d.created_at,
      stamp: formatStamp(d.created_at),
      context_name: d.context_name,
      meta_icon: FileText,
      meta_label: "Document",
      headline: d.name || "New document",
      body: null,
      href: `/app/documents/${encodeURIComponent(d.id)}`,
    });
  });
  // One summary "awaiting approval" card only — the right rail lists
  // the individual items.
  if ((approvals || []).length > 0) {
    const newest = approvals[0];
    entries.push({
      kind: "awaiting_approval",
      created_at: newest.created_at,
      stamp: formatStamp(newest.created_at),
      context_name: null,
      meta_icon: Inbox,
      meta_label: "Awaiting your review",
      headline: approvals.length === 1
        ? `1 item is waiting on your approval`
        : `${approvals.length} items are waiting on your approval`,
      body: newest.headline ? `Most recent: ${newest.headline}` : null,
      href: "/app/review",
    });
  }
  // Reverse-chron sort by created_at.
  entries.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  return entries;
}

// ---------------------------------------------------------------------------
// Right rail — "Awaiting you"
// ---------------------------------------------------------------------------
function AwaitingRail({ approvals }) {
  if (!approvals || approvals.length === 0) return null;
  return (
    <aside
      className="hidden lg:block pl-4 border-l border-[var(--border,#e2d9cf)]"
      data-testid="homev2-awaiting-rail"
    >
      <p className="akki-overline text-[10.5px] tracking-[0.22em] text-[var(--muted)] mb-3">
        AWAITING YOU
      </p>
      <div className="flex flex-col gap-3">
        {approvals.slice(0, 5).map((a) => (
          <div
            key={`${a.kind}-${a.id}`}
            className="bg-white border border-[var(--border,#e2d9cf)] p-3"
            data-testid={`homev2-awaiting-${a.kind}-${a.id}`}
          >
            <p className="akki-overline text-[9.5px] tracking-[0.18em] text-[var(--muted)] mb-1">
              {a.kind === "inbound_doc" ? "INBOUND DOC" : a.kind.toUpperCase()}
              {a.context_name ? <span className="opacity-60"> · {a.context_name}</span> : null}
            </p>
            <p className="akki-serif text-[13.5px] text-[var(--ink)] leading-snug line-clamp-2 mb-2">
              {a.headline}
            </p>
            <Link
              to="/app/review"
              className="akki-overline tracking-[0.16em] text-[10.5px] text-[var(--accent)] hover:underline underline-offset-2 inline-flex items-center gap-1"
            >
              REVIEW <ArrowRight size={10} />
            </Link>
          </div>
        ))}
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
function EmptyState() {
  const [addr, setAddr] = useState(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get("/inbound/address");
        if (!cancelled) setAddr(data.address);
      } catch { /* noop */ }
    })();
    return () => { cancelled = true; };
  }, []);

  const copy = async () => {
    if (!addr) return;
    try {
      await navigator.clipboard.writeText(addr);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast.message("Couldn't copy — select and copy manually.");
    }
  };

  return (
    <div
      className="bg-white border border-[var(--border,#e2d9cf)] p-6 md:p-8"
      data-testid="homev2-empty-state"
    >
      <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-3">
        THE RIVER
      </p>
      <h2 className="akki-serif text-[22px] md:text-[26px] text-[var(--ink)] font-normal leading-snug mb-3">
        AKKI is reading your materials.
      </h2>
      <p className="text-[14px] text-[var(--muted)] leading-[1.6] mb-5 max-w-[55ch]">
        Nothing&apos;s landed since you were last here. Forward a board pack to
        your inbox and we&apos;ll begin.
      </p>
      {addr ? (
        <div
          className="flex items-center gap-2 bg-[var(--cream)] border border-[var(--border,#e2d9cf)] px-3 py-2 max-w-[640px]"
          data-testid="homev2-empty-inbound"
        >
          <code className="text-[13px] md:text-[14px] font-mono text-[var(--ink)] break-all flex-1">
            {addr}
          </code>
          <button
            type="button"
            onClick={copy}
            className="text-[11px] akki-overline tracking-[0.16em] text-[var(--muted)] hover:text-[var(--ink)] flex items-center gap-1"
          >
            <CopyIcon size={12} />
            {copied ? "COPIED" : "COPY"}
          </button>
        </div>
      ) : (
        <p className="text-[12px] text-[var(--muted)]">Your inbound address will appear here shortly.</p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function HomeV2() {
  const { account, activeContext, activeContextId, switchContext } = useAuth();
  const isMobile = useIsMobile();
  const [data, setData] = useState({
    signals: [], briefings: [], documents: [], approvals: [], contexts: [], next_cursor: null,
  });
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [mentions, setMentions] = useState([]);
  const [approvalsSheetOpen, setApprovalsSheetOpen] = useState(false);

  // Initial fetch. Keep it simple — the unmount-leak risk is minor and
  // the mountedRef guard was leaking a stale `false` between StrictMode
  // mount cycles, which pinned the loading spinner on.
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const { data: stream } = await api.get("/me/home/stream?limit=30");
        if (!active) return;
        setData(stream || {});
      } catch {
        if (active) {
          setData({ signals: [], briefings: [], documents: [], approvals: [], contexts: [], next_cursor: null });
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    (async () => {
      try {
        const { data: mens } = await api.get("/me/mentions", { timeout: 5000 });
        if (!active) return;
        setMentions(Array.isArray(mens) ? mens : (mens?.items || []));
      } catch {
        if (active) setMentions([]);
      }
    })();
    return () => { active = false; };
  }, []);

  const loadMore = useCallback(async () => {
    if (!data.next_cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const { data: page } = await api.get(
        `/me/home/stream?limit=30&cursor=${encodeURIComponent(data.next_cursor)}`
      );
      setData((prev) => ({
        ...prev,
        signals: [...(prev.signals || []), ...(page.signals || [])],
        briefings: [...(prev.briefings || []), ...(page.briefings || [])],
        documents: [...(prev.documents || []), ...(page.documents || [])],
        // approvals are always the live 5 — ignore older pages
        contexts: page.contexts || prev.contexts,
        next_cursor: page.next_cursor || null,
      }));
    } finally {
      setLoadingMore(false);
    }
  }, [data.next_cursor, loadingMore]);

  const river = useMemo(() => buildRiver(data), [data]);
  const firstName = (account?.name || "there").split(" ")[0];

  const mainWide = !data.approvals || data.approvals.length === 0;
  const gridCols = mainWide ? "lg:grid-cols-[240px_1fr]" : "lg:grid-cols-[240px_1fr_320px]";

  return (
    <AppShell>
      <div
        className="min-h-[calc(100vh-4rem)] bg-[var(--cream)] px-4 md:px-8 py-6 md:py-10"
        data-testid="homev2-page"
      >
        <div className="max-w-[1240px] mx-auto">
          {/* Greeting + Phase-2 CycleStrip (the load-bearing contract) */}
          <div className="mb-5 md:mb-7">
            <h1 className="akki-serif text-[26px] md:text-[32px] leading-[1.15] text-[var(--ink)] font-normal">
              {greeting(firstName)}
            </h1>
            {activeContextId ? (
              <div className="mt-4">
                <CycleStrip contextId={activeContextId} isMobile={isMobile} />
              </div>
            ) : null}
          </div>

          {/* Mobile-only: "awaiting you" pill that opens a sheet */}
          {isMobile && data.approvals && data.approvals.length > 0 ? (
            <button
              type="button"
              onClick={() => setApprovalsSheetOpen(true)}
              className="mb-4 w-full bg-white border border-[var(--border,#e2d9cf)] px-4 py-3 text-left flex items-center justify-between"
              data-testid="homev2-awaiting-pill"
            >
              <span className="akki-overline text-[10.5px] tracking-[0.22em] text-[var(--accent)]">
                {data.approvals.length} AWAITING YOUR REVIEW
              </span>
              <ArrowRight size={14} className="text-[var(--muted)]" />
            </button>
          ) : null}

          <div className={`grid grid-cols-1 ${gridCols} gap-6 md:gap-8`}>
            <ContextRail
              activeContextId={activeContextId}
              onSwitch={switchContext}
              streamContexts={data.contexts}
            />

            {/* Main column */}
            <main className="min-w-0" data-testid="homev2-river">
              <div className="flex items-baseline justify-between mb-4">
                <div>
                  <p className="akki-overline text-[10.5px] tracking-[0.22em] text-[var(--muted)] mb-1">
                    WHAT&apos;S CHANGED
                  </p>
                  <p className="text-[12.5px] italic text-[var(--muted)]">
                    Since you were last here.
                  </p>
                </div>
                <Link
                  to="/app"
                  className="akki-overline tracking-[0.16em] text-[10.5px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline"
                  data-testid="homev2-back-to-v1"
                >
                  Back to classic home →
                </Link>
              </div>

              {loading ? (
                <p
                  className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] animate-pulse py-10"
                  data-testid="homev2-loading"
                >
                  Reading the river…
                </p>
              ) : river.length === 0 ? (
                <EmptyState />
              ) : (
                <div
                  className="flex flex-col divide-y divide-[var(--border,#e2d9cf)]/60"
                  data-testid="homev2-river-list"
                >
                  {river.map((e, i) => (
                    <RiverCard key={`${e.kind}-${e.created_at}-${i}`} entry={e} />
                  ))}
                </div>
              )}

              {/* Mentions inlined as a tail block — one-line each, only if
                  we got any from /me/mentions. Kept discreet so the river
                  stays the focal element. */}
              {mentions && mentions.length > 0 ? (
                <div className="mt-8 pt-5 border-t border-[var(--border,#e2d9cf)]">
                  <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-2">
                    MENTIONS
                  </p>
                  <ul className="space-y-1.5" data-testid="homev2-mentions">
                    {mentions.slice(0, 5).map((m, i) => (
                      <li key={m.id || i} className="flex items-start gap-2 text-[13px] text-[var(--muted)]">
                        <AtSign size={12} className="mt-[4px] shrink-0 opacity-70" />
                        <span className="truncate">
                          {m.summary || m.comment_preview || m.body || "You were mentioned."}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              {/* Load-older */}
              {data.next_cursor ? (
                <div className="pt-6">
                  <button
                    type="button"
                    onClick={loadMore}
                    disabled={loadingMore}
                    className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline disabled:opacity-50"
                    data-testid="homev2-load-more"
                  >
                    {loadingMore ? "Reading older items…" : "Load older →"}
                  </button>
                </div>
              ) : null}
            </main>

            <AwaitingRail approvals={data.approvals} />
          </div>
        </div>
      </div>

      {/* Mobile approvals sheet */}
      <Sheet open={approvalsSheetOpen} onOpenChange={setApprovalsSheetOpen}>
        <SheetContent side="bottom" className="bg-[var(--cream)]">
          <SheetHeader>
            <SheetTitle className="akki-serif text-[18px] font-normal text-[var(--ink)]">
              Awaiting your review
            </SheetTitle>
          </SheetHeader>
          <div className="mt-3 flex flex-col gap-3">
            {(data.approvals || []).slice(0, 5).map((a) => (
              <div
                key={`sheet-${a.kind}-${a.id}`}
                className="bg-white border border-[var(--border,#e2d9cf)] p-3"
              >
                <p className="akki-overline text-[9.5px] tracking-[0.18em] text-[var(--muted)] mb-1">
                  {a.kind === "inbound_doc" ? "INBOUND DOC" : a.kind.toUpperCase()}
                  {a.context_name ? <span className="opacity-60"> · {a.context_name}</span> : null}
                </p>
                <p className="akki-serif text-[13.5px] text-[var(--ink)] leading-snug mb-2">
                  {a.headline}
                </p>
                <Link
                  to="/app/review"
                  className="akki-overline tracking-[0.16em] text-[10.5px] text-[var(--accent)] inline-flex items-center gap-1"
                >
                  REVIEW <ArrowRight size={10} />
                </Link>
              </div>
            ))}
          </div>
        </SheetContent>
      </Sheet>
    </AppShell>
  );
}
