/**
 * Pulse.jsx — Phase F.1 (MEMO Item 4) — same-context only.
 *
 * Twitter-style signal feed for the active context. Cross-context
 * aggregation is deferred to a separate Privacy Wall lift; this
 * surface deliberately scopes to one context at a time and re-scopes
 * when the user switches context in the topbar.
 *
 * Layout:
 *   • Filter strip at the top (Type + Freshness chips).
 *   • Single-column feed, akki-w-medium width (Phase H token).
 *   • Per-card chip cluster (kind / topic / freshness), headline,
 *     body, action row (Comment · Share · Save · Resolve · Take to
 *     Solva).
 *
 * Restraint copy throughout — banned-word grep clean.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { takeToSolva } from "@/lib/takeToSolva";
import {
  Sparkles, MessageSquare, Send, Bookmark, BookmarkCheck,
  CheckCircle2, ArrowRight, AlertTriangle, TrendingUp, Lightbulb,
  Loader2, Filter, X, Layers, FileText, Lightbulb as Reasoning,
  Network, Inbox, RotateCcw, Eye, EyeOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import { toast } from "sonner";
import AcrossBoardsPanel from "@/components/pulse/AcrossBoardsPanel";

const STATE_TABS = [
  { id: "active",     label: "Active"     },
  { id: "bookmarked", label: "Bookmarked" },
  { id: "resolved",   label: "Resolved"   },
  { id: "archived",   label: "Archived"   },
];

/* ------------------------------------------------------------------ */
/* Constants                                                          */
/* ------------------------------------------------------------------ */
const TYPE_FILTERS = [
  { id: "any",            label: "All" },
  { id: "risk",           label: "Risk" },
  { id: "opportunity",    label: "Opportunity" },
  { id: "recommendation", label: "Recommendation" },
];

const FRESHNESS_FILTERS = [
  { id: "new",                    label: "New" },
  { id: "critical",               label: "Critical" },
  { id: "old-but-unresolved",     label: "Old · unresolved" },
  { id: "nice-to-look-into",      label: "Nice to look into" },
  { id: "for-tracking-purposes",  label: "For tracking" },
  { id: "resolved",               label: "Resolved" },
];

const TYPE_ICON = {
  risk:           AlertTriangle,
  opportunity:    TrendingUp,
  recommendation: Lightbulb,
};

const TOPIC_LABEL = {
  capital:    "Capital",
  succession: "Succession",
  regulatory: "Regulatory",
  cyber:      "Cyber",
  other:      "Other",
};

const FRESHNESS_LABEL = {
  "new":                    "New",
  "critical":               "Critical",
  "old-but-unresolved":     "Old · unresolved",
  "nice-to-look-into":      "Nice to look into",
  "for-tracking-purposes":  "Tracking",
  "resolved":               "Resolved",
};

const FRESHNESS_TONE = {
  "critical":               "bg-[#8B2E2B]/10 text-[#8B2E2B] border-[#8B2E2B]/30",
  "new":                    "bg-emerald-50 text-emerald-800 border-emerald-200",
  "old-but-unresolved":     "bg-amber-50 text-amber-900 border-amber-200",
  "nice-to-look-into":      "bg-sky-50 text-sky-800 border-sky-200",
  "for-tracking-purposes":  "bg-stone-50 text-stone-700 border-stone-200",
  "resolved":               "bg-stone-100 text-stone-500 border-stone-200",
};

/* ------------------------------------------------------------------ */
/* Tiny chip primitive                                                */
/* ------------------------------------------------------------------ */
function Chip({ children, tone = "default", testid }) {
  const cls = tone === "default"
    ? "bg-white text-[var(--ink)] border-[var(--rule)]"
    : tone;
  return (
    <span
      className={`inline-flex items-center text-[10.5px] uppercase tracking-[0.12em] font-mono px-2 py-0.5 rounded-full border ${cls}`}
      data-testid={testid}
    >
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Per-card                                                           */
/* ------------------------------------------------------------------ */
function SignalCard({ card, onAction, busyAction, onOpenDrawer }) {
  const TypeIcon = TYPE_ICON[card.surface_type] || Lightbulb;
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");
  const isResolved = !!card.actions_summary?.resolved || card.freshness === "resolved";
  const saved = !!card.actions_summary?.my_saved;

  const submitComment = async () => {
    if (!comment.trim()) return;
    await onAction("comment", card.id, { note: comment.trim() });
    setComment("");
    setShowComment(false);
  };

  return (
    <article
      className={`border border-[var(--rule)] bg-white rounded-md px-5 py-4 mb-3 ${isResolved ? "opacity-70" : ""}`}
      data-testid={`pulse-card-${card.id}`}
    >
      {/* Phase H3 (2026-05-11) — clicking the card body opens the drawer.
          Button-class elements inside the action row still stopPropagation. */}
      <button
        type="button"
        onClick={() => onOpenDrawer?.(card)}
        className="block w-full text-left"
        data-testid={`pulse-card-open-${card.id}`}
      >
      {/* Chip cluster */}
      <div className="flex flex-wrap items-center gap-1.5 mb-2" data-testid={`pulse-card-chips-${card.id}`}>
        <Chip
          tone={card.surface_type === "risk"
            ? "bg-[#8B2E2B]/10 text-[#8B2E2B] border-[#8B2E2B]/30"
            : card.surface_type === "opportunity"
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : "bg-sky-50 text-sky-800 border-sky-200"}
          testid={`pulse-card-chip-type-${card.id}`}
        >
          <TypeIcon className="w-3 h-3 mr-1" strokeWidth={1.7} />
          {card.surface_type}
        </Chip>
        <Chip testid={`pulse-card-chip-topic-${card.id}`}>
          {TOPIC_LABEL[card.topic_class] || card.topic_class}
        </Chip>
        <Chip
          tone={FRESHNESS_TONE[card.freshness] || "default"}
          testid={`pulse-card-chip-freshness-${card.id}`}
        >
          {FRESHNESS_LABEL[card.freshness] || card.freshness}
        </Chip>
        {typeof card.confidence === "number" && (
          <Chip testid={`pulse-card-chip-confidence-${card.id}`}>
            confidence {Math.round(card.confidence * 100)}%
          </Chip>
        )}
        {typeof card.confidence === "string" && card.confidence && (
          <Chip
            tone={card.confidence === "low" ? "bg-slate-50 text-slate-600 border-slate-200" : "default"}
            testid={`pulse-card-chip-confidence-tier-${card.id}`}
          >
            {card.confidence}
          </Chip>
        )}
        {card.merge_count > 1 && (
          <Chip
            tone="bg-amber-50 text-amber-800 border-amber-200"
            testid={`pulse-card-chip-merge-${card.id}`}
          >
            ×{card.merge_count} merged
          </Chip>
        )}
      </div>

      {/* Headline + body */}
      <h2 className="akki-serif text-[16px] text-[var(--ink)] leading-snug mb-1" data-testid={`pulse-card-headline-${card.id}`}>
        {card.headline}
      </h2>
      {card.summary && (
        <p className="text-[13px] text-[var(--ink)] leading-[1.65] mb-3" data-testid={`pulse-card-summary-${card.id}`}>
          {card.summary}
        </p>
      )}
      </button>

      {/* Action row */}
      <div className="flex flex-wrap gap-1 items-center pt-2 border-t border-[var(--rule)] mt-2" data-testid={`pulse-card-actions-${card.id}`}>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => setShowComment((v) => !v)}
          disabled={busyAction === `comment:${card.id}`}
          className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] h-7 px-2"
          data-testid={`pulse-action-comment-${card.id}`}
        >
          <MessageSquare className="w-3.5 h-3.5 mr-1" strokeWidth={1.7} />
          Comment{card.actions_summary?.comments_count ? ` (${card.actions_summary.comments_count})` : ""}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => onAction("share", card.id)}
          disabled={busyAction === `share:${card.id}`}
          className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] h-7 px-2"
          data-testid={`pulse-action-share-${card.id}`}
        >
          <Send className="w-3.5 h-3.5 mr-1" strokeWidth={1.7} />
          Share{card.actions_summary?.shares_count ? ` (${card.actions_summary.shares_count})` : ""}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => onAction("save", card.id)}
          disabled={busyAction === `save:${card.id}`}
          className={`text-[12px] hover:text-[var(--ink)] h-7 px-2 ${saved ? "text-[var(--accent)]" : "text-[var(--muted)]"}`}
          data-testid={`pulse-action-save-${card.id}`}
          aria-pressed={saved}
        >
          {saved
            ? <BookmarkCheck className="w-3.5 h-3.5 mr-1" strokeWidth={1.7} />
            : <Bookmark className="w-3.5 h-3.5 mr-1" strokeWidth={1.7} />}
          {saved ? "Saved" : "Save"}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => onAction("resolve", card.id)}
          disabled={isResolved || busyAction === `resolve:${card.id}`}
          className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] h-7 px-2 disabled:opacity-50"
          data-testid={`pulse-action-resolve-${card.id}`}
        >
          <CheckCircle2 className="w-3.5 h-3.5 mr-1" strokeWidth={1.7} />
          {isResolved ? "Resolved" : "Mark resolved"}
        </Button>
        <span className="flex-1" />
        <Button
          type="button"
          size="sm"
          onClick={() => onAction("take-to-solva", card.id)}
          disabled={busyAction === `take-to-solva:${card.id}`}
          className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12px] h-7 px-3"
          data-testid={`pulse-action-take-to-solva-${card.id}`}
        >
          {busyAction === `take-to-solva:${card.id}`
            ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
            : <ArrowRight className="w-3.5 h-3.5 mr-1" />}
          Take to Solva
        </Button>
      </div>

      {/* Inline comment composer */}
      {showComment && (
        <div className="mt-3 pt-3 border-t border-[var(--rule)]" data-testid={`pulse-card-comment-form-${card.id}`}>
          <Textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Add a private note on this signal."
            className="rounded-sm min-h-[64px] text-[13px]"
          />
          <div className="flex justify-end gap-2 mt-2">
            <Button size="sm" variant="ghost" onClick={() => { setShowComment(false); setComment(""); }} className="text-[12px]">
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={submitComment}
              disabled={!comment.trim() || busyAction === `comment:${card.id}`}
              className="bg-[var(--accent)] hover:bg-[var(--accent-dark)] text-white text-[12px]"
            >
              Save note
            </Button>
          </div>
        </div>
      )}
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                               */
/* ------------------------------------------------------------------ */
export default function Pulse() {
  const navigate = useNavigate();
  const { activeContext } = useAuth();
  const cid = activeContext?.id;

  const [cards, setCards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyAction, setBusyAction] = useState(null);

  const [typeFilter, setTypeFilter] = useState("any");
  // Default per brief: New + Critical.
  const [freshnessSet, setFreshnessSet] = useState(new Set(["new", "critical"]));
  // Phase H3 (2026-05-11) — Phase G.4 frontend wiring.
  const [stateTab, setStateTab] = useState("active");   // active|bookmarked|resolved|archived
  const [showLow, setShowLow] = useState(false);        // surface confidence='low'
  const [drawerCard, setDrawerCard] = useState(null);   // currently-open signal in side drawer

  /* Load feed (re-runs when context or filters change) */
  const fetchFeed = async (silent = false) => {
    if (!cid) return;
    if (!silent) setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("type", typeFilter);
      params.set("freshness", Array.from(freshnessSet).join(","));
      // Phase H3 — pipe state + show_low to the backend feed.
      params.set("state", stateTab);
      if (showLow) params.set("show_low", "true");
      const { data } = await api.get(`/contexts/${cid}/pulse/feed?${params.toString()}`);
      setCards(data?.cards || []);
      setError(null);
    } catch (e) {
      setError(apiErrorMessage(e));
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    fetchFeed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cid, typeFilter, freshnessSet, stateTab, showLow]);

  const toggleFreshness = (id) => {
    setFreshnessSet((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      // Don't allow zero filters — fall back to default.
      if (next.size === 0) return new Set(["new", "critical"]);
      return next;
    });
  };

  /* Action dispatcher — optimistic UI for save, then re-fetch for truth */
  const onAction = async (action, sigId, payload) => {
    if (!cid) return;
    setBusyAction(`${action}:${sigId}`);
    try {
      // Optimistic update for save
      if (action === "save") {
        setCards((prev) => prev.map((c) =>
          c.id === sigId
            ? { ...c, actions_summary: {
                ...(c.actions_summary || {}),
                my_saved: !c.actions_summary?.my_saved,
              } }
            : c));
      }
      if (action === "comment") {
        const { data } = await api.post(
          `/contexts/${cid}/pulse/signals/${sigId}/comment`, payload || {},
        );
        setCards((prev) => prev.map((c) => c.id === sigId
          ? { ...c, actions_summary: {
              ...(c.actions_summary || {}),
              comments_count: (c.actions_summary?.comments_count || 0) + 1,
            } }
          : c));
        toast.success("Note saved.");
        return data;
      }
      if (action === "share") {
        // Phase F.1 — share writes an empty-recipients row (a track of
        // intent). The deeper share-to-people UX lands with C.x later.
        const { data } = await api.post(
          `/contexts/${cid}/pulse/signals/${sigId}/share`, { recipients: [] },
        );
        setCards((prev) => prev.map((c) => c.id === sigId
          ? { ...c, actions_summary: {
              ...(c.actions_summary || {}),
              shares_count: (c.actions_summary?.shares_count || 0) + 1,
            } }
          : c));
        toast.success("Share intent recorded.");
        return data;
      }
      if (action === "save") {
        const { data } = await api.post(
          `/contexts/${cid}/pulse/signals/${sigId}/save`,
        );
        // Reconcile from server truth.
        setCards((prev) => prev.map((c) => c.id === sigId
          ? { ...c, actions_summary: {
              ...(c.actions_summary || {}),
              my_saved: !!data?.saved,
            } }
          : c));
        return data;
      }
      if (action === "resolve") {
        await api.post(`/contexts/${cid}/pulse/signals/${sigId}/resolve`, payload || {});
        toast.success("Marked resolved.");
        await fetchFeed(true);
        return;
      }
      if (action === "unresolve") {
        await api.post(`/contexts/${cid}/pulse/signals/${sigId}/unresolve`);
        toast.success("Returned to Active.");
        await fetchFeed(true);
        return;
      }
      if (action === "bookmark") {
        await api.post(`/contexts/${cid}/pulse/signals/${sigId}/bookmark`);
        toast.success("Bookmarked.");
        await fetchFeed(true);
        return;
      }
      if (action === "unbookmark") {
        await api.post(`/contexts/${cid}/pulse/signals/${sigId}/unbookmark`);
        toast.success("Removed from bookmarks.");
        await fetchFeed(true);
        return;
      }
      if (action === "take-to-solva") {
        // Phase F.2.A — universal journey via takeToSolva helper.
        // Lands the user on the Solva framing surface with the
        // signal's text pre-populated in the textarea instead of
        // server-creating a session before they've framed.
        takeToSolva({ navigate, kind: "signal", id: sigId });
        return;
      }
    } catch (e) {
      toast.error(apiErrorMessage(e));
      // Rollback the optimistic save flip if it failed.
      if (action === "save") await fetchFeed(true);
    } finally {
      setBusyAction(null);
    }
  };

  if (!cid) {
    return (
      <AppShell>
        <div className="akki-w-medium px-8 py-12 text-[var(--muted)]">
          Pick a workspace to see its Pulse.
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="akki-w-medium px-8 py-10" data-testid="pulse-page">
        <p className="akki-overline mb-2 flex items-center gap-2">
          <Sparkles className="w-3 h-3 text-[var(--accent)]" /> Pulse · {activeContext.name}
        </p>
        <h1 className="akki-greeting mb-1">Signals worth your attention.</h1>
        <p className="akki-meta mb-6 max-w-2xl">
          Risks, opportunities, and recommendations surfaced from <strong className="text-[var(--ink)]">{activeContext.name}</strong>. Use the chips below to refine.
        </p>

        {/* Phase H3 (2026-05-11) — Phase G.4 lifecycle tab strip.
            Switch sets ?state= on the feed query. Each tab refetches. */}
        <div className="flex items-center gap-0.5 mb-4 border-b border-[var(--rule)]" data-testid="pulse-state-tabs">
          {STATE_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setStateTab(t.id)}
              data-testid={`pulse-tab-${t.id}${stateTab === t.id ? "-active" : ""}`}
              aria-pressed={stateTab === t.id}
              className={`px-3 py-2 text-[13px] akki-sans -mb-px border-b-2 transition-colors ${
                stateTab === t.id
                  ? "text-[var(--accent)] border-[var(--accent)]"
                  : "text-[var(--muted)] hover:text-[var(--ink)] border-transparent"
              }`}
            >
              {t.label}
            </button>
          ))}
          <span className="flex-1" />
          {/* Show low toggle — G.2 confidence floor */}
          <button
            type="button"
            onClick={() => setShowLow((v) => !v)}
            data-testid="pulse-show-low-toggle"
            aria-pressed={showLow}
            className="text-[12px] px-2.5 py-1.5 text-[var(--muted)] hover:text-[var(--ink)] inline-flex items-center gap-1.5"
            title={showLow ? "Hiding low-confidence signals" : "Show low-confidence signals"}
          >
            {showLow ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            {showLow ? "Show all" : "Hide low confidence"}
          </button>
        </div>

        {/* Filter strip */}
        <div className="border border-[var(--rule)] bg-white rounded-md px-4 py-3 mb-5 space-y-3" data-testid="pulse-filters">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="akki-overline text-[var(--muted)] mr-1 inline-flex items-center gap-1">
              <Filter className="w-3 h-3" /> Type
            </span>
            {TYPE_FILTERS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTypeFilter(t.id)}
                className={`text-[11.5px] px-2.5 py-1 rounded-full border transition-colors ${
                  typeFilter === t.id
                    ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                    : "bg-white text-[var(--ink)] border-[var(--rule)] hover:border-[var(--accent)]"
                }`}
                data-testid={`pulse-filter-type-${t.id}${typeFilter === t.id ? "-active" : ""}`}
                aria-pressed={typeFilter === t.id}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="akki-overline text-[var(--muted)] mr-1">Freshness</span>
            {FRESHNESS_FILTERS.map((f) => {
              const active = freshnessSet.has(f.id);
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => toggleFreshness(f.id)}
                  className={`text-[11.5px] px-2.5 py-1 rounded-full border transition-colors ${
                    active
                      ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                      : "bg-white text-[var(--ink)] border-[var(--rule)] hover:border-[var(--accent)]"
                  }`}
                  data-testid={`pulse-filter-freshness-${f.id}${active ? "-active" : ""}`}
                  aria-pressed={active}
                >
                  {f.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Feed */}
        {error && (
          <p className="text-[12.5px] text-amber-900 bg-amber-50 border border-amber-100 rounded-sm px-3 py-2 mb-3">{error}</p>
        )}
        {loading && (
          <div className="py-16 text-center">
            <Loader2 className="w-4 h-4 mx-auto animate-spin text-[var(--accent)]" />
          </div>
        )}
        {!loading && cards.length === 0 && (
          <div className="py-16 text-center" data-testid="pulse-empty">
            <p className="akki-serif text-[18px] text-[var(--ink)] mb-1">No signals match these filters.</p>
            <p className="akki-meta text-[var(--muted)]">Try adding more freshness chips above.</p>
          </div>
        )}
        {!loading && cards.length > 0 && (
          <div data-testid="pulse-feed">
            {cards.map((card) => (
              <SignalCard
                key={card.id}
                card={card}
                onAction={onAction}
                busyAction={busyAction}
                onOpenDrawer={setDrawerCard}
              />
            ))}
          </div>
        )}

        {/* Phase E.0.3 — Cross-board metadata patterns. Sits UNDER
            the same-context feed (per spec). Reads only metadata —
            never source-board name, never source-artefact links. */}
        <div className="mt-8">
          <AcrossBoardsPanel contextId={cid} />
        </div>
      </div>
      {/* Phase H3 (2026-05-11) — Phase G.4 drill-down drawer.
          5 sections (Storyline / Source / Reasoning / Related Context
          / Comments) + a 6-button action footer. */}
      <SignalDrawer
        card={drawerCard}
        contextId={cid}
        onClose={() => setDrawerCard(null)}
        onAction={async (action, sigId, payload) => {
          await onAction(action, sigId, payload);
          // Re-pull the card with updated state so the drawer reflects.
          // The feed has been refetched; find the updated card.
          if (drawerCard) {
            const updated = (cards || []).find((c) => c.id === drawerCard.id);
            setDrawerCard(updated || null);
          }
        }}
        busyAction={busyAction}
      />
    </AppShell>
  );
}


/* ───────────────────────────────────────────────────────────────
 * Phase H3 (2026-05-11) — SignalDrawer (Phase G.4 right-side drawer).
 *
 * 5 sections:
 *   1. Storyline           — headline, body, confidence, last_merged_at
 *   2. Source              — provenance (doc / monitor goal / pipeline)
 *   3. Reasoning           — signals.reasoning field (verbatim)
 *   4. Related Context     — cross-board metadata matches (if any)
 *   5. Comments            — existing comment composer/list
 *
 * 6 actions in footer:
 *   Resolve | Unresolve | Bookmark | Unbookmark | Save | Take to Solva
 * ─────────────────────────────────────────────────────────────── */
function SignalDrawer({ card, contextId, onClose, onAction, busyAction }) {
  const navigate = useNavigate();
  const [related, setRelated] = useState(null);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [commentDraft, setCommentDraft] = useState("");
  const [submittingComment, setSubmittingComment] = useState(false);

  useEffect(() => {
    if (!card || !contextId) return;
    let alive = true;
    setRelatedLoading(true);
    (async () => {
      try {
        const { data } = await api.get(
          `/contexts/${contextId}/pulse/across-boards?window_days=30&min_other_boards=1&limit=10`,
        );
        if (alive) setRelated(data);
      } catch {
        /* drawer renders without related section */
      } finally {
        if (alive) setRelatedLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [card, contextId]);

  if (!card) return null;
  const state = (card.state || card.status || "active").toLowerCase();
  const isResolved = state === "resolved" || !!card.actions_summary?.resolved;
  const isBookmarked = state === "bookmarked" || !!card.bookmarked_at;

  const handleComment = async () => {
    const text = commentDraft.trim();
    if (!text) return;
    setSubmittingComment(true);
    try {
      await onAction("comment", card.id, { text });
      setCommentDraft("");
    } finally {
      setSubmittingComment(false);
    }
  };

  return (
    <Sheet open={!!card} onOpenChange={(v) => !v && onClose?.()}>
      <SheetContent side="right" className="w-full sm:max-w-xl flex flex-col p-0" data-testid="pulse-signal-drawer">
        <SheetHeader className="px-6 py-4 border-b border-[var(--rule)]">
          <SheetTitle className="akki-serif text-[18px] text-[var(--ink)] leading-snug pr-8" data-testid="pulse-drawer-title">
            {card.headline || "(untitled)"}
          </SheetTitle>
          <SheetDescription className="sr-only">Signal details and actions.</SheetDescription>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
          <section data-testid="pulse-drawer-storyline">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] akki-sans mb-2">Storyline</p>
            {card.summary && (
              <p className="text-[13.5px] text-[var(--ink)] leading-[1.65] mb-3">{card.summary}</p>
            )}
            <div className="flex flex-wrap gap-2 text-[11px] text-[var(--muted)]">
              {card.confidence != null && (
                <span className="px-2 py-0.5 bg-slate-50 border border-slate-200 rounded-sm" data-testid="pulse-drawer-confidence">
                  confidence: {typeof card.confidence === "number" ? `${Math.round(card.confidence * 100)}%` : card.confidence}
                </span>
              )}
              {card.merge_count > 1 && (
                <span className="px-2 py-0.5 bg-amber-50 border border-amber-200 rounded-sm text-amber-800">
                  ×{card.merge_count} merged
                </span>
              )}
              {card.created_at && (
                <span className="px-2 py-0.5">
                  created {new Date(card.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                </span>
              )}
              {card.last_merged_at && (
                <span className="px-2 py-0.5">
                  last merged {new Date(card.last_merged_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                </span>
              )}
            </div>
          </section>

          <section data-testid="pulse-drawer-source">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] akki-sans mb-2">Source</p>
            {(card.references && card.references.length > 0) ? (
              <ul className="space-y-1.5">
                {card.references.slice(0, 6).map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-[12px] text-[var(--ink)]">
                    <FileText className="w-3.5 h-3.5 mt-0.5 text-[var(--muted)]" strokeWidth={1.7} />
                    <span>{r.label || r.doc_name || r.title || r.doc_id || "(reference)"}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[12px] text-[var(--muted)] italic">No source attributions recorded.</p>
            )}
          </section>

          <section data-testid="pulse-drawer-reasoning">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] akki-sans mb-2">Reasoning</p>
            {card.reasoning ? (
              <p className="text-[12.5px] text-[var(--ink)] leading-[1.6] whitespace-pre-wrap">{card.reasoning}</p>
            ) : (
              <p className="text-[12px] text-[var(--muted)] italic">No reasoning recorded for this signal.</p>
            )}
          </section>

          <section data-testid="pulse-drawer-related">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] akki-sans mb-2">Related context</p>
            {relatedLoading ? (
              <p className="text-[12px] text-[var(--muted)] italic">Looking across boards…</p>
            ) : (related?.patterns?.length || 0) === 0 ? (
              <p className="text-[12px] text-[var(--muted)] italic">No cross-board matches in window.</p>
            ) : (
              <ul className="space-y-1.5">
                {(related?.patterns || []).slice(0, 5).map((p, i) => (
                  <li key={i} className="flex items-start gap-2 text-[12px] text-[var(--ink)]">
                    <Network className="w-3.5 h-3.5 mt-0.5 text-[var(--muted)]" strokeWidth={1.7} />
                    <span>
                      <span className="font-medium">{p.signature_kind}</span>: {p.signature_value}
                      <span className="text-[var(--muted)] ml-1">— seen on {p.other_boards_count} other board{p.other_boards_count === 1 ? "" : "s"}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section data-testid="pulse-drawer-comments">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] akki-sans mb-2">Comments</p>
            <div className="space-y-2 mb-3">
              {(card.comments || []).length === 0 && (
                <p className="text-[12px] text-[var(--muted)] italic">No comments yet.</p>
              )}
              {(card.comments || []).map((c) => (
                <div key={c.id} className="border border-[var(--rule)] rounded-sm px-3 py-2 bg-[var(--cream)]/30">
                  <p className="text-[12.5px] text-[var(--ink)] leading-[1.55] whitespace-pre-wrap">{c.note}</p>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--muted)] mt-1">
                    {c.created_at ? new Date(c.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : ""}
                  </p>
                </div>
              ))}
            </div>
            <div className="flex flex-col gap-2">
              <Textarea
                value={commentDraft}
                onChange={(e) => setCommentDraft(e.target.value)}
                placeholder="Add a private note…"
                className="text-[13px] min-h-[60px]"
                data-testid="pulse-drawer-comment-input"
              />
              <div className="flex justify-end">
                <Button
                  size="sm"
                  onClick={handleComment}
                  disabled={!commentDraft.trim() || submittingComment}
                  className="bg-[var(--accent)] text-white hover:opacity-90"
                  data-testid="pulse-drawer-comment-submit"
                >
                  {submittingComment ? <Loader2 className="w-3 h-3 mr-1 animate-spin" /> : <Send className="w-3 h-3 mr-1" />}
                  Post
                </Button>
              </div>
            </div>
          </section>
        </div>

        <div className="border-t border-[var(--rule)] px-4 py-3 flex flex-wrap gap-2 bg-[var(--cream)]/30" data-testid="pulse-drawer-footer">
          {!isResolved ? (
            <button
              onClick={() => onAction("resolve", card.id, {})}
              disabled={busyAction === card.id}
              data-testid="pulse-drawer-action-resolve"
              className="text-[12px] px-3 py-1.5 border border-[var(--rule)] rounded-sm hover:border-[var(--accent)] inline-flex items-center gap-1.5"
            >
              <CheckCircle2 className="w-3.5 h-3.5" /> Resolve
            </button>
          ) : (
            <button
              onClick={() => onAction("unresolve", card.id)}
              disabled={busyAction === card.id}
              data-testid="pulse-drawer-action-unresolve"
              className="text-[12px] px-3 py-1.5 border border-[var(--rule)] rounded-sm hover:border-[var(--accent)] inline-flex items-center gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Unresolve
            </button>
          )}
          {!isBookmarked ? (
            <button
              onClick={() => onAction("bookmark", card.id)}
              disabled={busyAction === card.id}
              data-testid="pulse-drawer-action-bookmark"
              className="text-[12px] px-3 py-1.5 border border-[var(--rule)] rounded-sm hover:border-[var(--accent)] inline-flex items-center gap-1.5"
            >
              <Bookmark className="w-3.5 h-3.5" /> Bookmark
            </button>
          ) : (
            <button
              onClick={() => onAction("unbookmark", card.id)}
              disabled={busyAction === card.id}
              data-testid="pulse-drawer-action-unbookmark"
              className="text-[12px] px-3 py-1.5 border border-[var(--rule)] rounded-sm hover:border-[var(--accent)] inline-flex items-center gap-1.5"
            >
              <BookmarkCheck className="w-3.5 h-3.5" /> Unbookmark
            </button>
          )}
          <button
            onClick={() => onAction("save", card.id)}
            disabled={busyAction === card.id}
            data-testid="pulse-drawer-action-save"
            className="text-[12px] px-3 py-1.5 border border-[var(--rule)] rounded-sm hover:border-[var(--accent)] inline-flex items-center gap-1.5"
          >
            <Inbox className="w-3.5 h-3.5" /> Save
          </button>
          <button
            onClick={async () => {
              try {
                const { data } = await api.post(`/contexts/${contextId}/pulse/signals/${card.id}/take-to-solva`);
                if (data?.session_id) navigate(`/app/solva/session/${data.session_id}`);
                else navigate("/app/solva");
              } catch {
                takeToSolva({
                  navigate, submodule: "seek_clarity",
                  seed: { kind: "signal", id: card.id, headline: card.headline },
                });
              }
            }}
            disabled={busyAction === card.id}
            data-testid="pulse-drawer-action-take-to-solva"
            className="ml-auto text-[12px] px-3 py-1.5 bg-[var(--accent)] text-white rounded-sm hover:opacity-90 inline-flex items-center gap-1.5"
          >
            <Sparkles className="w-3.5 h-3.5" /> Take to Solva
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
