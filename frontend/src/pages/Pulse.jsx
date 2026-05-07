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
import {
  Sparkles, MessageSquare, Send, Bookmark, BookmarkCheck,
  CheckCircle2, ArrowRight, AlertTriangle, TrendingUp, Lightbulb,
  Loader2, Filter, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";

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
function SignalCard({ card, onAction, busyAction }) {
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

  /* Load feed (re-runs when context or filters change) */
  const fetchFeed = async (silent = false) => {
    if (!cid) return;
    if (!silent) setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("type", typeFilter);
      params.set("freshness", Array.from(freshnessSet).join(","));
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
  }, [cid, typeFilter, freshnessSet]);

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
        await api.post(`/contexts/${cid}/pulse/signals/${sigId}/resolve`);
        toast.success("Marked resolved.");
        await fetchFeed(true);
        return;
      }
      if (action === "take-to-solva") {
        const { data } = await api.post(
          `/contexts/${cid}/pulse/signals/${sigId}/take-to-solva`,
        );
        toast.success("Solva session started.");
        if (data?.solva_session_id) {
          navigate(`/app/solva/session/${data.solva_session_id}`);
        }
        return data;
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
              />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
