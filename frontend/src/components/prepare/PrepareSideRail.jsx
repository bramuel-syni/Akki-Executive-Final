/**
 * PrepareSideRail — the right-side history dock on /app/prepare.
 *
 * Apr-2026 user request: "Have a list dock on the right with all listings
 * of past minutes, generated briefs, signals. The list changes based on
 * the tab click — if you click Signals, it shows past signals filterable
 * by topic or timeline."
 *
 * Behaviour:
 *  - Sticks to the right column on lg+ viewports (collapses below the
 *    main content on smaller screens).
 *  - Header swaps with the active tab — "Past briefs" / "Past signals" /
 *    "Past minutes" (Minutes is Tier-C; we render an empty-state stub so
 *    the structure is in place for when minutes ship).
 *  - Two filter rows: TIMELINE (last 7d · last 30d · all) and TOPIC
 *    (free-text contains-match against title / kind / type).
 *  - Spacing follows the page's editorial rhythm: 24px column gap, items
 *    separated by hairline rules, tabular-nums dates.
 */
import React, { useMemo, useState } from "react";
import { Search, Clock, ScrollText, Activity, FileText } from "lucide-react";
import { Input } from "@/components/ui/input";

const TIMELINE_OPTS = [
  { id: "7d",  label: "7d",  ms: 7  * 24 * 3600 * 1000 },
  { id: "30d", label: "30d", ms: 30 * 24 * 3600 * 1000 },
  { id: "all", label: "All", ms: null },
];

function formatDate(d) {
  if (!d) return "";
  const dt = new Date(d);
  const now = new Date();
  const sameYear = dt.getFullYear() === now.getFullYear();
  return dt.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  });
}

export default function PrepareSideRail({ tab, briefs, signals, loadingBriefs, loadingSignals, onOpenBrief, onOpenSignal }) {
  const [topic, setTopic] = useState("");
  const [timeline, setTimeline] = useState("30d");

  const config = useMemo(() => {
    if (tab === "brief") {
      return {
        title: "Past briefs",
        icon: ScrollText,
        items: briefs,
        loading: loadingBriefs,
        onOpen: onOpenBrief,
        emptyText: "No briefs yet — generate one and it appears here.",
        renderItem: (it) => ({ title: it.title, kicker: it.kind, ts: it.created_at, raw: it }),
        searchHay: (it) => `${it.title || ""} ${it.kind || ""} ${it.objective || ""}`.toLowerCase(),
      };
    }
    if (tab === "signals") {
      return {
        title: "Past signals",
        icon: Activity,
        items: signals,
        loading: loadingSignals,
        onOpen: onOpenSignal,
        emptyText: "No signals yet — generate some and they appear here.",
        renderItem: (it) => ({
          title: it.headline || it.title,
          kicker: it.type || it.tone,
          ts: it.created_at,
          raw: it,
        }),
        searchHay: (it) => `${it.headline || ""} ${it.title || ""} ${it.type || ""} ${it.summary || ""}`.toLowerCase(),
      };
    }
    return {
      title: "Past minutes",
      icon: FileText,
      items: [],
      loading: false,
      onOpen: () => {},
      emptyText: "Minutes are coming soon. They'll be a first-class doc type so AKKI can anchor cycles and decisions to them.",
      renderItem: () => ({ title: "", kicker: "", ts: null, raw: null }),
      searchHay: () => "",
    };
  }, [tab, briefs, signals, loadingBriefs, loadingSignals, onOpenBrief, onOpenSignal]);

  const filtered = useMemo(() => {
    const tl = TIMELINE_OPTS.find((t) => t.id === timeline);
    const cutoff = tl?.ms ? Date.now() - tl.ms : 0;
    const q = topic.trim().toLowerCase();
    return (config.items || [])
      .filter((it) => {
        if (cutoff && it.created_at) {
          const t = new Date(it.created_at).getTime();
          if (t < cutoff) return false;
        }
        if (q && !config.searchHay(it).includes(q)) return false;
        return true;
      });
  }, [config, topic, timeline]);

  const Icon = config.icon;

  return (
    <aside
      className="bg-white border border-[var(--rule)] rounded-md flex flex-col self-start lg:sticky lg:top-6 max-h-[calc(100vh-7rem)]"
      data-testid="prepare-side-rail"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--rule)]">
        <div className="flex items-center gap-2 mb-3">
          <Icon className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
          <p className="akki-overline">{config.title}</p>
          <span className="ml-auto text-[11px] text-[var(--muted)] tabular-nums">
            {config.loading ? "—" : `${filtered.length}`}
          </span>
        </div>

        {/* Topic search */}
        <div className="relative mb-2">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-[var(--muted)]" />
          <Input
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Filter by topic…"
            className="h-8 pl-8 text-[12.5px] bg-[var(--cream-deep)]/30 border-[var(--rule)] focus:border-[var(--accent)]"
            data-testid="prepare-rail-topic"
          />
        </div>

        {/* Timeline chips */}
        <div className="flex items-center gap-1.5">
          <Clock className="w-3 h-3 text-[var(--muted)] mr-1" />
          {TIMELINE_OPTS.map((opt) => {
            const active = timeline === opt.id;
            return (
              <button
                key={opt.id}
                onClick={() => setTimeline(opt.id)}
                className={`px-2 py-0.5 rounded-sm text-[11px] border transition-colors ${
                  active
                    ? "bg-[var(--ink)] text-[var(--cream)] border-[var(--ink)]"
                    : "bg-white text-[var(--deep)] border-[var(--rule)] hover:border-[var(--accent)]"
                }`}
                data-testid={`prepare-rail-timeline-${opt.id}${active ? "-active" : ""}`}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto" data-testid="prepare-rail-list">
        {config.loading ? (
          <p className="px-4 py-6 text-center text-[12px] text-[var(--muted)] italic">Loading…</p>
        ) : filtered.length === 0 ? (
          <p className="px-4 py-6 text-center text-[12px] text-[var(--muted)] italic max-w-[260px] mx-auto leading-snug">
            {config.emptyText}
          </p>
        ) : (
          <ul className="divide-y divide-[var(--rule)]">
            {filtered.map((it) => {
              const r = config.renderItem(it);
              return (
                <li key={it.id} data-testid={`prepare-brief-history-${it.id}`}>
                  <button
                    onClick={() => config.onOpen?.(r.raw || it)}
                    className="w-full text-left px-4 py-2.5 hover:bg-[var(--cream-deep)]/30 transition-colors group"
                    data-testid={`prepare-rail-item-${it.id}`}
                  >
                    <div className="flex items-baseline gap-2">
                      <span className="text-[10px] uppercase tracking-wider text-[var(--accent)] font-mono shrink-0">
                        {r.kicker}
                      </span>
                      <span className="text-[10.5px] text-[var(--muted)] tabular-nums ml-auto">
                        {formatDate(r.ts)}
                      </span>
                    </div>
                    <p className="akki-serif text-[13.5px] text-[var(--ink)] leading-snug mt-0.5 line-clamp-2 group-hover:text-[var(--accent)] transition-colors">
                      {r.title}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
