/**
 * Phase P5.17 (2026-02) — Origin chip.
 *
 * Tiny "📧 From email" pill rendered on rows that carry an
 * `origin.source === "email_akki"` envelope. Renders nothing
 * when origin is null — backward-compat for rows created before
 * the P5.17 envelope was introduced.
 *
 * On click, opens the SourceMessageModal which loads the
 * tenant-scoped preview from
 * GET /api/inbox/messages/{message_id}/preview.
 *
 * Voice-lint-clean copy: "From email" + the confidence band as
 * a tooltip. No imperatives, no banned vocabulary.
 */
import React from "react";

const ORIGIN_LABELS = {
  email_akki: "From email",
};

const CONFIDENCE_TONE = {
  high:   "bg-emerald-50 text-emerald-700 border-emerald-300",
  medium: "bg-amber-50 text-amber-700 border-amber-300",
  low:    "bg-slate-50 text-slate-600 border-slate-300",
};

export function OriginChip({ origin, onClick, testid }) {
  if (!origin || origin.source !== "email_akki") return null;
  const tone =
    CONFIDENCE_TONE[origin.confidence_band] ||
    "bg-slate-50 text-slate-600 border-slate-300";
  const label = ORIGIN_LABELS[origin.source] || origin.source;
  const handler = (e) => {
    e.stopPropagation();
    if (onClick) onClick(origin);
  };
  return (
    <button
      type="button"
      onClick={handler}
      className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm border font-mono ${tone} hover:opacity-80`}
      data-testid={testid || `origin-chip-${origin.source}`}
      title={`${label} — ${origin.confidence_band || "low"} confidence`}
    >
      <span aria-hidden>✉</span>
      <span>{label}</span>
    </button>
  );
}

export default OriginChip;
