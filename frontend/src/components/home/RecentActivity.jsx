/**
 * RecentActivity — single editorial timeline that replaces the four-tab
 * "Top signals · Top briefings · New documents · Shared with you" block
 * the user said was duplicating the In-Summary tiles above.
 *
 * Apr-2026 user feedback: "Below the workflow dock we are repeating the
 * summary, can you recommend something that will be a good hook?"
 *
 * What this is: a chronological "what's happened since you last looked"
 * feed. We merge signals + briefings + documents + shared items into one
 * timeline, dedup by timestamp, and present them with a typed chip + a
 * verb-led headline. Items click through to their respective surfaces.
 *
 * Why it's not "summary": each row is an EVENT, not a count. Numbers live
 * in the InSummary tiles. Verbs and headlines live here.
 */
import React, { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Sparkles, ScrollText, FileText, Mail, ArrowRight, Globe,
} from "lucide-react";

const TYPE_META = {
  signal: { icon: Sparkles, label: "Signal", verb: "surfaced", to: "/app/prepare", tone: "text-[var(--accent)]" },
  briefing: { icon: ScrollText, label: "Briefing", verb: "drafted", to: "/app/prepare", tone: "text-[var(--deep)]" },
  document: { icon: FileText, label: "Document", verb: "added", to: null, tone: "text-[var(--deep)]" },
  shared: { icon: Mail, label: "Shared", verb: "sent your way", to: "/app/prepare", tone: "text-[var(--accent)]" },
};

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

export default function RecentActivity({ signals, briefings, documents, shared, contexts, hasMultipleContexts, scope, onScopeChange }) {
  const ctxName = (id) => (contexts || []).find((c) => c.id === id)?.name;

  const events = useMemo(() => {
    const arr = [];
    (signals || []).forEach((s) =>
      arr.push({
        id: `sg-${s.id}`,
        kind: "signal",
        title: s.headline || s.title,
        ts: s.created_at,
        context_id: s.context_id,
        context_name: s.context_name,
        meta: s.type || s.tone,
        to: "/app/prepare",
      })
    );
    (briefings || []).forEach((b) =>
      arr.push({
        id: `br-${b.id}`,
        kind: "briefing",
        title: b.title,
        ts: b.created_at || b.published_at,
        context_id: b.context_id,
        context_name: b.context_name,
        to: "/app/prepare",
      })
    );
    (documents || []).forEach((d) =>
      arr.push({
        id: `dc-${d.id}`,
        kind: "document",
        title: d.name || d.original_filename,
        ts: d.created_at,
        context_id: d.context_id,
        context_name: d.context_name,
        to: `/app/documents/${d.id}`,
      })
    );
    (shared || []).forEach((sh) =>
      arr.push({
        id: `sh-${sh.id}`,
        kind: "shared",
        title: sh.item_preview || sh.subject || "(no preview)",
        ts: sh.created_at,
        context_id: sh.context_id,
        context_name: sh.context_name,
        meta: `from ${(sh.shared_by_name || sh.shared_by_email || "someone").split(" ")[0]}`,
        to: "/app/prepare",
      })
    );
    return arr
      .filter((e) => e.title && e.ts)
      .sort((a, b) => new Date(b.ts) - new Date(a.ts));
  }, [signals, briefings, documents, shared]);

  const visible = events.slice(0, 8);

  if (visible.length === 0) {
    return (
      <section className="border-t border-[var(--rule)] pt-6 pb-12" data-testid="home-recent-activity">
        <p className="akki-overline mb-2">Activity since you last looked</p>
        <p className="text-[13px] text-[var(--muted)] italic">
          Nothing new yet. Once AKKI has something to surface, it will line up here in time order.
        </p>
      </section>
    );
  }

  return (
    <section className="border-t border-[var(--rule)] pt-6 pb-12" data-testid="home-recent-activity">
      <div className="flex items-center mb-4 gap-3">
        <p className="akki-overline">Activity since you last looked</p>
        <span className="text-[11px] text-[var(--muted)] tabular-nums">{visible.length} events</span>
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

      <ul className="bg-white border border-[var(--rule)] rounded-md divide-y divide-[var(--rule)]" data-testid="recent-activity-list">
        {visible.map((e) => {
          const m = TYPE_META[e.kind];
          const Icon = m.icon;
          const ctx = e.context_name || ctxName(e.context_id);
          const showCtx = scope === "all" && hasMultipleContexts;
          const Inner = (
            <div className="flex items-start gap-3 px-5 py-3.5 hover:bg-[var(--cream-deep)]/30 transition-colors group">
              <Icon className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${m.tone}`} strokeWidth={1.8} />
              <div className="flex-1 min-w-0">
                <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] mb-0.5 flex items-center gap-2">
                  <span className={m.tone}>{m.label} {m.verb}</span>
                  {e.meta && <span className="italic normal-case tracking-normal">· {e.meta}</span>}
                  {showCtx && ctx && (
                    <span className="ml-auto akki-overline text-[var(--muted)]/80">{ctx}</span>
                  )}
                </p>
                <p className="akki-serif text-[14.5px] text-[var(--ink)] leading-snug line-clamp-2 group-hover:text-[var(--accent)] transition-colors">
                  {e.title}
                </p>
              </div>
              <span className="text-[11px] text-[var(--muted)] tabular-nums shrink-0 mt-1">
                {relTime(e.ts)}
              </span>
            </div>
          );
          return (
            <li key={e.id}>
              {e.to ? (
                <Link to={e.to} className="block" data-testid={`recent-event-${e.kind}-${e.id}`}>{Inner}</Link>
              ) : (
                <div data-testid={`recent-event-${e.kind}-${e.id}`}>{Inner}</div>
              )}
            </li>
          );
        })}
      </ul>

      <div className="flex justify-end mt-3">
        <Link to="/app/prepare" className="akki-gesture text-[12.5px]" data-testid="recent-view-all">
          See more in Prepare <ArrowRight className="w-3 h-3 inline ml-1" />
        </Link>
      </div>
    </section>
  );
}
