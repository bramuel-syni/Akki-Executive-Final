/**
 * TierChip — Phase 15.3 citation chip for Solva v2 grounding tiers.
 *
 * Sibling to `CitationChip` (Phase 11). Reuses the same `HoverCard`
 * primitive and a similar visual treatment so the chip family is
 * consistent. Difference: the reference here is a tier marker on a
 * synthesis claim, not a paragraph anchor.
 *
 * Props:
 *   tier        — one of: corpus | comparable | domain_prior | user_assertion | speculation
 *   band        — Unlikely | Possible | Likely | High-conviction (probability_weighting)
 *   confidence  — integer percentage 0..100
 *   ciLow       — optional, integer percentage; bottom of confidence interval
 *   ciHigh      — optional, integer percentage; top of confidence interval
 *   source      — optional string. For `comparable` tier, the comparable title.
 *
 * Visual:
 *   * Inline, super-text chip aligned to end of the assertive sentence.
 *   * Label = `<band> · <pct>%`  (e.g. "Likely · 65%")
 *   * Hover popover = tier name (capitalised), full interval,
 *     and (when present) the source.
 *   * Colour-coded per tier using the existing palette tokens.
 */
import React from "react";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";

// Token-aligned colours. Keep in sync with index.css palette.
const TIER_STYLES = {
  corpus:         { bg: "#0F1E3A", fg: "white",        label: "Corpus" },        // navy
  comparable:     { bg: "#8B2E2B", fg: "white",        label: "Comparable" },    // oxblood
  domain_prior:   { bg: "#E8E5DC", fg: "#39312A",      label: "Domain prior" },  // cream-deep
  user_assertion: { bg: "#F5F1E6", fg: "#39312A",      label: "User assertion" },// cream
  speculation:    { bg: "transparent", fg: "#6F6A5D",  label: "Speculation",
                    italic: true, border: "1px dashed #C9C2B2" },                // muted italic
};

function bandLabel(band) {
  if (!band) return "";
  return String(band);
}

export default function TierChip({
  tier,
  band,
  confidence,
  ciLow,
  ciHigh,
  source,
  compact = false,
}) {
  if (!tier) return null;
  const style = TIER_STYLES[tier] || TIER_STYLES.domain_prior;
  const pct = Number.isFinite(confidence) ? Math.round(confidence) : null;
  const interval = (Number.isFinite(ciLow) && Number.isFinite(ciHigh))
    ? `${Math.round(ciLow)}–${Math.round(ciHigh)}%`
    : null;

  const labelText = pct != null && band
    ? `${bandLabel(band)} · ${pct}%`
    : (pct != null ? `${pct}%` : style.label);

  const baseClass = compact
    ? "inline-flex items-center text-[10px] font-mono px-1.5 py-[1px] rounded-[2px] ml-1"
    : "inline-flex items-center text-[10px] font-mono px-1.5 py-[1px] rounded-[2px] ml-1 align-baseline";

  const inlineStyle = {
    background: style.bg,
    color: style.fg,
    border: style.border || undefined,
    fontStyle: style.italic ? "italic" : undefined,
    letterSpacing: 0.3,
    whiteSpace: "nowrap",
  };

  return (
    <HoverCard openDelay={150} closeDelay={80}>
      <HoverCardTrigger asChild>
        <button
          type="button"
          className={baseClass}
          style={inlineStyle}
          data-testid={`tier-chip-${tier}`}
          aria-label={`${style.label}${pct != null ? `, confidence ${pct} percent` : ""}${interval ? `, range ${interval}` : ""}${source ? `, source ${source}` : ""}`}
        >
          {labelText}
        </button>
      </HoverCardTrigger>
      <HoverCardContent
        side="top"
        sideOffset={6}
        className="w-[280px] border border-[var(--rule)] bg-white shadow-[0_8px_28px_-12px_rgba(15,23,42,0.18)] p-3.5"
      >
        <p className="akki-overline mb-1.5 text-[var(--muted)]">
          {style.label}
        </p>
        {band && pct != null ? (
          <p className="akki-serif text-[14px] leading-[1.45] text-[var(--ink)] mb-1.5">
            <span className="font-semibold">{bandLabel(band)}</span>
            <span className="text-[var(--muted)]"> · </span>
            <span className="font-semibold">{pct}%</span>
            {interval ? (
              <span className="text-[var(--muted)]"> ({interval})</span>
            ) : null}
          </p>
        ) : null}
        {source ? (
          <p className="text-[12px] text-[var(--muted)] mb-0.5">
            <span className="font-medium text-[var(--ink)]">Source: </span>
            {source}
          </p>
        ) : null}
        <p className="text-[11.5px] text-[var(--muted)] mt-2 leading-[1.4]">
          {tier === "corpus" && "Anchored in your own documents."}
          {tier === "comparable" && "Anchored in a named comparable diagnosis."}
          {tier === "domain_prior" && "Widely-held domain knowledge."}
          {tier === "user_assertion" && "Restating what you said."}
          {tier === "speculation" && "Solva's judgement, not directly grounded."}
        </p>
      </HoverCardContent>
    </HoverCard>
  );
}
