/**
 * CitationChip — `p.14¶3` superscript chip with a hover popover showing
 * the source paragraph excerpt and a "Jump to paragraph" affordance.
 *
 * Props:
 *   reference        — { doc_id, doc_title, page, paragraph_id, paragraph_number }
 *   onJump(paragraph_id) — invoked when the chip is clicked.
 *   paragraphLookup  — optional map paragraph_id -> { text, page, paragraph_number }
 *                      used to render the excerpt in the hover card.
 *   compact          — boolean, true on mobile to render inline `[p.14¶3]`.
 */
import React from "react";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { ArrowUpRight } from "lucide-react";

function labelFor(reference) {
  if (!reference) return "";
  const { page, paragraph_number: pn } = reference;
  if (page && pn) return `p.${page}¶${pn}`;
  if (page) return `p.${page}`;
  return reference.doc_title || "source";
}

export default function CitationChip({
  reference,
  onJump,
  paragraphLookup,
  compact = false,
}) {
  if (!reference) return null;
  const label = labelFor(reference);
  const para =
    reference.paragraph_id && paragraphLookup
      ? paragraphLookup[reference.paragraph_id]
      : null;
  const excerpt = para?.text
    ? (para.text.length > 400 ? `${para.text.slice(0, 400)}…` : para.text)
    : null;

  const handleClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (reference.paragraph_id && onJump) onJump(reference.paragraph_id);
  };

  const baseClass = compact
    ? "inline-flex items-center text-[11px] text-[var(--accent)] hover:underline underline-offset-2 font-mono"
    : "inline-flex items-center text-[10px] text-[var(--accent)] font-mono align-super hover:underline underline-offset-2 ml-0.5";

  return (
    <HoverCard openDelay={200} closeDelay={80}>
      <HoverCardTrigger asChild>
        <button
          type="button"
          className={baseClass}
          onClick={handleClick}
          data-testid={`citation-chip-${reference.paragraph_id || reference.doc_id}`}
          aria-label={`Source: ${reference.doc_title}${reference.page ? `, page ${reference.page}` : ""}${reference.paragraph_number ? `, paragraph ${reference.paragraph_number}` : ""}`}
        >
          {compact ? `[${label}]` : label}
        </button>
      </HoverCardTrigger>
      <HoverCardContent
        side="left"
        sideOffset={6}
        className="w-[320px] border border-[var(--rule)] bg-white shadow-[0_8px_28px_-12px_rgba(15,23,42,0.18)] p-4"
      >
        <p className="akki-overline mb-1.5 text-[var(--muted)]">{reference.doc_title}</p>
        {excerpt ? (
          <p className="akki-serif text-[13.5px] leading-[1.55] text-[var(--ink)] mb-3">{excerpt}</p>
        ) : (
          <p className="text-[12px] italic text-[var(--muted)] mb-3">
            Excerpt unavailable. Citation is page-level for this source.
          </p>
        )}
        {reference.paragraph_id ? (
          <button
            type="button"
            onClick={handleClick}
            className="inline-flex items-center gap-1 text-[12px] text-[var(--accent)] hover:underline underline-offset-2"
          >
            Jump to paragraph <ArrowUpRight className="w-3 h-3" />
          </button>
        ) : null}
      </HoverCardContent>
    </HoverCard>
  );
}
