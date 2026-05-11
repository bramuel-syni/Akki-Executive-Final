/**
 * CycleStatusBadge — v7 palette badge for brief / assignment status.
 *
 * Used on cycle cards (board_status: draft|submitted|shipped) and
 * inbox rows (assignment status: pending|accepted|declined|cancelled).
 * All colours resolve through CSS tokens.
 */
import React from "react";

const TONE = {
  // Brief board_status
  draft:     "text-[var(--muted)] bg-[var(--parchment-soft,var(--parchment))] border-[var(--rule)]",
  submitted: "text-amber-900 bg-amber-50 border-amber-200",
  shipped:   "text-emerald-800 bg-emerald-50 border-emerald-200",
  // Assignment status
  pending:   "text-amber-900 bg-amber-50 border-amber-200",
  accepted:  "text-emerald-800 bg-emerald-50 border-emerald-200",
  declined:  "text-[color:var(--oxblood)] bg-[color:var(--oxblood)]/10 border-[color:var(--oxblood)]/30",
  cancelled: "text-[var(--muted)] bg-[var(--parchment-soft,var(--parchment))] border-[var(--rule)]",
  // Fallback
  active:    "text-emerald-800 bg-emerald-50 border-emerald-200",
};

const LABEL = {
  draft: "Draft",
  submitted: "Submitted for board",
  shipped: "Shipped",
  pending: "Pending",
  accepted: "Accepted",
  declined: "Declined",
  cancelled: "Cancelled",
  active: "Active",
};

export default function CycleStatusBadge({ status, size = "sm", testId }) {
  const key = (status || "draft").toLowerCase();
  const tone = TONE[key] || TONE.draft;
  const sizing = size === "xs"
    ? "text-[10px] px-1.5 py-[1px] tracking-[0.10em]"
    : "text-[10.5px] px-2 py-[2px] tracking-[0.12em]";
  return (
    <span
      data-testid={testId || `status-badge-${key}`}
      className={`inline-block uppercase font-mono rounded-sm border ${tone} ${sizing}`}
    >
      {LABEL[key] || key}
    </span>
  );
}
