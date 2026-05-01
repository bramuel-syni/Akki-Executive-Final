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
}) {
  if (!item) return null;
  const tone = item.tone || "note";
  const borderClass = BORDER_BY_TONE[tone] || BORDER_BY_TONE.note;
  const toneClass = TONE_WORD_CLASS[tone] || TONE_WORD_CLASS.note;

  return (
    <li
      data-rail-paragraph-id={item.paragraphId || ""}
      data-active={isActive ? "true" : undefined}
      data-testid={`commentary-item-${item.kind}-${item.id}`}
      className={`group relative pl-4 pr-3 py-3.5 bg-white ${borderClass} hover:bg-[var(--cream-deep)]/30 transition-colors data-[active=true]:bg-[var(--cream-deep)]/40 data-[flash=true]:ring-2 data-[flash=true]:ring-[var(--accent)] data-[flash=true]:ring-offset-1 rounded-r-sm`}
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
