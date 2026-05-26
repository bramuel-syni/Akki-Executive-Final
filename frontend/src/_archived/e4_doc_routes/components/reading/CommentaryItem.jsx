/**
 * CommentaryItem — a single rail entry. Source can be a signal, an Ask
 * answer, or a briefing item. The component is dumb-on-purpose: the
 * parent (ReadingRail) does the data shaping and passes the normalised
 * `item` object.
 *
 * Item shape:
 *   {
 *     id,
 *     kind: "signal" | "ask" | "briefing",
 *     tone: "risk" | "gap" | "opportunity" | "note",  // signals only; else "note"
 *     toneWord: "RISK" | "GAP" | "OPP" | "NOTE",
 *     headline,
 *     body,
 *     reference,           // primary citation reference (CitationChip-shaped)
 *     paragraphId,         // shorthand for reference.paragraph_id; used for sync
 *     allReferences,       // optional, for multi-cite items
 *   }
 */
import React from "react";
import CitationChip from "@/components/reading/CitationChip";

const BORDER_BY_TONE = {
  risk: "border-l-[3px] border-l-red-600",
  gap: "border-l-[3px] border-l-amber-600",
  opportunity: "border-l-[3px] border-l-emerald-600",
  note: "border-l-[3px] border-l-[var(--navy)]",
};

const TONE_WORD_CLASS = {
  risk: "text-red-700",
  gap: "text-amber-700",
  opportunity: "text-emerald-700",
  note: "text-[var(--navy)]",
};

export default function CommentaryItem({
  item,
  onJump,
  paragraphLookup,
  isActive = false,
  isFlashing = false,
}) {
  if (!item) return null;
  const tone = item.tone || "note";
  const borderClass = BORDER_BY_TONE[tone] || BORDER_BY_TONE.note;
  const toneClass = TONE_WORD_CLASS[tone] || TONE_WORD_CLASS.note;

  // Flash visuals: tint + ring + shadow + subtle scale so it actually
  // reads as a flash, not a near-invisible border accent. Driven by the
  // React `isFlashing` prop (lifted from useReadingScrollSync). The
  // `data-flash` attribute is also set as a fallback for any consumer
  // that prefers attribute selectors.
  const flashClass =
    "bg-[var(--accent)]/20 ring-2 ring-[var(--accent)] ring-offset-2 ring-offset-white shadow-[0_6px_24px_-4px_rgba(165,42,42,0.5)] scale-[1.015]";

  return (
    <li
      data-rail-paragraph-id={item.paragraphId || ""}
      data-active={isActive ? "true" : undefined}
      data-flash={isFlashing ? "true" : undefined}
      data-testid={`commentary-item-${item.kind}-${item.id}`}
      className={`group relative pl-4 pr-3 py-3.5 ${borderClass} hover:bg-[var(--cream-deep)]/30 transition-all duration-200 data-[active=true]:bg-[var(--cream-deep)]/40 rounded-r-sm ${
        isFlashing ? flashClass : "bg-white"
      }`}
    >
      <div className="flex items-baseline justify-between gap-2 mb-1">
        <span className={`akki-overline text-[10px] tracking-[0.18em] ${toneClass}`}>
          {item.toneWord}
        </span>
        {item.reference ? (
          <CitationChip
            reference={item.reference}
            onJump={onJump}
            paragraphLookup={paragraphLookup}
          />
        ) : null}
      </div>
      <p className="akki-serif italic text-[14px] leading-[1.4] text-[var(--ink)] mb-1.5">
        {item.headline}
      </p>
      {item.body ? (
        <p className="text-[12.5px] leading-[1.55] text-[var(--muted)] line-clamp-3">
          {item.body}
        </p>
      ) : null}
    </li>
  );
}
