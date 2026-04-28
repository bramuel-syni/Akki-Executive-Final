/**
 * RecentActivity — categorised hook on Home.
 *
 * Apr-2026 feedback iter48: "Don't list everything. Group events by type
 * — meetings had, questions answered, etc. Pick 4 to 5 categories. User
 * clicks → goes to a timeline page with more details."
 *
 * Five categories:
 *   1. Briefings & meetings      ← meetings the user is preparing for
 *   2. Questions answered        ← briefs generated (answers to prompts)
 *   3. Signals surfaced          ← risks / opportunities / gaps
 *   4. Documents added           ← new uploads
 *   5. Sent your way             ← shared items + mentions
 *
 * Each card shows: kicker, count, most-recent item title, "View timeline →".
 * Click takes the user to /app/activity?cat={key}.
 */
import React, { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Sparkles, ScrollText, FileText, Mail, MessageCircle, ArrowRight, Globe,
} from "lucide-react";

const CATEGORIES = [
  {
    key: "meetings",
    label: "Briefings & meetings",
    verb: "drafted for you",
    icon: ScrollText,
    tone: "text-[var(--deep)]",
  },
  {
    key: "answers",
    label: "Questions answered",
    verb: "drafted",
    icon: MessageCircle,
    tone: "text-[var(--accent)]",
  },
  {
    key: "signals",
    label: "Signals surfaced",
    verb: "to react to",
    icon: Sparkles,
    tone: "text-[var(--accent)]",
  },
  {
    key: "documents",
    label: "Documents added",
    verb: "to read",
    icon: FileText,
    tone: "text-[var(--deep)]",
  },
  {
    key: "shared",
    label: "Sent your way",
    verb: "from your team",
    icon: Mail,
    tone: "text-[var(--accent)]",
  },
];

function relTime(iso) {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  const ms = Date.now() - t;
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.round(ms / 3_600_000)}h ago`;
  if (ms < 7 * 86_400_000) return `${Math.round(ms / 86_400_000)}d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function RecentActivity({
  signals = [], briefings = [], documents = [], shared = [], briefs = [],
  contexts, hasMultipleContexts, scope, onScopeChange,
}) {
  const navigate = useNavigate();

  const groups = useMemo(() => {
    const byKey = {
      meetings:  briefings.slice().sort((a, b) => new Date(b.created_at || b.published_at) - new Date(a.created_at || a.published_at)),
      answers:   briefs.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),
      signals:   signals.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),
      documents: documents.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),
      shared:    shared.slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)),
    };
    const titleOf = (key, it) =>
      key === "signals"  ? (it.headline || it.title)
      : key === "documents" ? (it.name || it.original_filename)
      : key === "shared" ? (it.item_preview || it.subject || "(no preview)")
      : it.title;
    return CATEGORIES.map((c) => {
      const items = byKey[c.key] || [];
      const latest = items[0];
      return {
        ...c,
        count: items.length,
        latestTitle: latest ? titleOf(c.key, latest) : null,
        latestTs: latest ? (latest.created_at || latest.published_at) : null,
      };
    });
  }, [signals, briefings, documents, shared, briefs]);

  const totalCount = groups.reduce((acc, g) => acc + g.count, 0);

  return (
    <section className="border-t border-[var(--rule)] pt-6 pb-12" data-testid="home-recent-activity">
      <div className="flex items-center mb-4 gap-3">
        <p className="akki-overline">Activity since you last looked</p>
        <span className="text-[11px] text-[var(--muted)] tabular-nums">{totalCount} events</span>
        {hasMultipleContexts && (
          <div
            className="ml-auto inline-flex items-center rounded-sm border border-[var(--rule)] bg-white p-[3px]"
            data-testid="recent-scope-toggle"
          >
            <button
              onClick={() => onScopeChange?.("current")}
              className={`px-2.5 py-1 text-[11px] uppercase tracking-wider rounded-[3px] transition-colors ${
                scope === "current"
                  ? "bg-[var(--cream-deep)] text-[var(--ink)]"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
              data-testid="recent-scope-current"
            >
              This company
            </button>
            <button
              onClick={() => onScopeChange?.("all")}
              className={`px-2.5 py-1 text-[11px] uppercase tracking-wider rounded-[3px] inline-flex items-center gap-1 transition-colors ${
                scope === "all"
                  ? "bg-[var(--accent)] text-white"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
              data-testid="recent-scope-all"
            >
              <Globe className="w-3 h-3" /> All boards
            </button>
          </div>
        )}
      </div>

      {totalCount === 0 ? (
        <div className="bg-white border border-[var(--rule)] rounded-md px-5 py-8 text-center">
          <p className="text-[13px] text-[var(--muted)] italic">
            Nothing new yet. Once AKKI has something to surface — a briefing, a signal, a fresh document — it will line up here in time order.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {groups.map((g) => {
            const Icon = g.icon;
            const empty = g.count === 0;
            return (
              <button
                key={g.key}
                onClick={() => navigate(`/app/activity?cat=${g.key}`)}
                disabled={empty}
                className={`text-left bg-white border rounded-lg p-4 transition-colors flex flex-col h-full group ${
                  empty
                    ? "border-[var(--rule)] opacity-50 cursor-default"
                    : "border-[var(--rule)] hover:border-[var(--accent)]/40 hover:shadow-sm cursor-pointer"
                }`}
                data-testid={`activity-cat-${g.key}`}
              >
                <div className="flex items-start justify-between mb-2">
                  <p className="text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] font-mono leading-tight">
                    {g.label}
                  </p>
                  <Icon className={`w-3.5 h-3.5 ${g.tone} shrink-0`} strokeWidth={1.6} />
                </div>
                <p className="akki-serif text-[28px] text-[var(--ink)] leading-none tabular-nums mb-1">
                  {g.count}
                </p>
                <p className="text-[10.5px] uppercase tracking-wider text-[var(--muted)] mb-3">
                  {g.verb}
                </p>
                <div className="mt-auto">
                  {g.latestTitle ? (
                    <>
                      <p className="text-[11.5px] text-[var(--muted)] line-clamp-2 italic mb-2 leading-snug">
                        Latest: {g.latestTitle}
                      </p>
                      <p className="text-[11px] text-[var(--accent)] inline-flex items-center gap-1 group-hover:underline">
                        View timeline <ArrowRight className="w-3 h-3" />
                      </p>
                    </>
                  ) : (
                    <p className="text-[11px] text-[var(--muted)] italic">Nothing yet</p>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
