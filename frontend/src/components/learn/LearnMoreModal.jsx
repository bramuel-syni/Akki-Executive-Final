import React, { useMemo } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { ExternalLink, BookOpen, Newspaper, FileText, Video as VideoIcon, Briefcase } from "lucide-react";
import { LEARN_MORE, CONTENT_TYPE_LABEL, TOPIC_LABEL } from "@/lib/learnContent";

const TAB_ICON = {
  news: Newspaper,
  tl_article: FileText,
  video: VideoIcon,
  case_study: Briefcase,
};

/**
 * LearnMoreModal — editor-curated further-reading list for the currently
 * active Learn tab. Filters by the user's selected topic when a match exists;
 * otherwise shows the full tab map. One-click open in a new window.
 */
export default function LearnMoreModal({ open, onOpenChange, tab, topic = "all" }) {
  const tabMap = LEARN_MORE[tab] || {};
  const TabIcon = TAB_ICON[tab] || BookOpen;

  // Prefer the user's topic; always include 'general' as a backdrop.
  const sections = useMemo(() => {
    const ordered = [];
    if (topic !== "all" && tabMap[topic]) {
      ordered.push([topic, tabMap[topic]]);
    }
    if (tabMap.general) {
      ordered.push(["general", tabMap.general]);
    }
    // Fall back: show every other topic if the filter is 'all'
    if (topic === "all") {
      Object.entries(tabMap).forEach(([k, v]) => {
        if (k !== "general" && !ordered.find(([key]) => key === k)) {
          ordered.push([k, v]);
        }
      });
    }
    return ordered;
  }, [tabMap, topic]);

  const total = sections.reduce((n, [, items]) => n + items.length, 0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-[640px] bg-[var(--cream)] border border-[var(--rule)] p-0 overflow-hidden"
        data-testid="learn-more-modal"
      >
        <DialogHeader className="px-7 pt-7 pb-4 border-b border-[var(--rule)] bg-white">
          <div className="flex items-center gap-2 mb-2">
            <TabIcon className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={1.8} />
            <span className="akki-overline">
              Further reading · {CONTENT_TYPE_LABEL[tab] || "Library"}
            </span>
          </div>
          <DialogTitle className="akki-serif text-[22px] font-normal text-[var(--ink)] leading-snug">
            {total} primary sources we'd hand you in person.
          </DialogTitle>
          <DialogDescription className="text-[13px] text-[var(--muted)] leading-relaxed mt-1">
            Not on-demand — these are vetted external references AKKI editors trust.
            {topic !== "all" && (
              <> Filtered for <span className="text-[var(--ink)] font-medium">{TOPIC_LABEL[topic] || topic}</span>.</>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[60vh] overflow-y-auto px-7 py-5 space-y-6" data-testid="learn-more-list">
          {sections.length === 0 ? (
            <div className="py-8 text-center text-[13px] text-[var(--muted)]">
              <BookOpen className="w-7 h-7 mx-auto mb-3 opacity-40" strokeWidth={1.3} />
              No curated further-reading for this category yet.
            </div>
          ) : (
            sections.map(([key, items]) => (
              <div key={key}>
                <p className="akki-overline mb-3">
                  {key === "general" ? "Essentials" : (TOPIC_LABEL[key] || key)}
                </p>
                <ul className="space-y-4">
                  {items.map((ref, i) => (
                    <li key={`${key}-${i}`} className="border-l-2 border-[var(--accent)]/30 pl-4">
                      <a
                        href={ref.url}
                        target="_blank"
                        rel="noreferrer"
                        className="block group"
                        data-testid={`learn-more-ref-${key}-${i}`}
                      >
                        <div className="flex items-start justify-between gap-3 mb-1">
                          <h4 className="akki-serif text-[15.5px] font-normal text-[var(--ink)] leading-snug group-hover:text-[var(--accent)] transition-colors">
                            {ref.title}
                          </h4>
                          <ExternalLink className="w-3.5 h-3.5 mt-1 shrink-0 text-[var(--muted)] group-hover:text-[var(--accent)] transition-colors" strokeWidth={1.8} />
                        </div>
                        <p className="text-[11px] uppercase tracking-wider text-[var(--muted)] mb-1.5 font-mono">
                          {ref.source}
                        </p>
                        {ref.note && (
                          <p className="text-[13px] text-[var(--deep)] leading-relaxed italic">
                            {ref.note}
                          </p>
                        )}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </div>

        <div className="px-7 py-3 border-t border-[var(--rule)] bg-white text-[11.5px] text-[var(--muted)] flex items-center justify-between">
          <span>Sources are re-verified quarterly. Broken link? <span className="text-[var(--accent)]">Ask AKKI to research it.</span></span>
        </div>
      </DialogContent>
    </Dialog>
  );
}
