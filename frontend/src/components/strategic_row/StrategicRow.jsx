/**
 * Phase Y / Decision 2 (2026-02 fork-resume) — Shared row primitive.
 *
 * The Monitor Strategic Objectives row vocabulary, extracted into a
 * reusable component so Task Manager cards (and any future entity
 * surface) consume the same primitive. Locks visual consistency
 * across Monitor and Task Manager permanently.
 *
 * Slots:
 *   - categoryChip            : ReactNode — left-most chip (e.g. REVENUE)
 *   - statusChip              : ReactNode — chip beside title (e.g. AT RISK)
 *   - title                   : string    — primary heading
 *   - rightSideScores         : Array<{label, value, barClass, narrative, testId}>
 *                                          1–2 score bars on the right
 *                                          (Performance + Probability on Monitor;
 *                                           Readiness on Task cards)
 *   - metadataChildren        : ReactNode — inline metadata row contents
 *                                          (count, target, reassessed, owner avatars, etc.)
 *   - description             : string?   — optional 2-line italic description
 *   - onClick                 : fn        — row click handler
 *   - testId                  : string    — root data-testid
 *   - isLast                  : bool      — suppress bottom border on last row
 *
 * Visual rules locked:
 *   - Top row: category chip + title + status chip on a single line,
 *     left-justified, with the score bars right-anchored.
 *   - Metadata row: same gap rhythm, narrative tucks under each score bar.
 *   - Description: optional, italic, 2-line clamp, muted.
 *   - Hover: cream-deep tint, cursor pointer when onClick provided.
 *
 * IMPORTANT — Wave 4.2.followup.2 compliance: any color tokens must
 * be either CSS-var direct (`var(--rule)`) or Tailwind-config short
 * names (`bg-ned-purple/N`). NEVER `bg-[var(--ned-purple)]/N`.
 */
import React from "react";


/**
 * ScoreBar — extracted from StrategicGoalsPanel for shared use.
 * value: 0-100 or null (renders "—" + dashed empty bar).
 *
 * Selector contract (locked 2026-02 fork-resume):
 *   - data-scorebar="true"      — generic ScoreBar marker
 *   - data-scorebar-kind="<lowercase-label>" — semantic kind (e.g.
 *     "readiness", "performance", "probability"). Allows cross-
 *     surface testid-agnostic probes that don't depend on the
 *     row-id suffix.
 *   - data-testid=<testId>      — caller-supplied per-row testid
 *     (e.g. "task-card-readiness-<id>")
 */
export function ScoreBar({ label, value, barClass, testId }) {
  const empty = value === null || value === undefined;
  const pct = empty ? 0 : Math.max(0, Math.min(100, value));
  const kind = (label || "").toLowerCase().replace(/\s+/g, "-");
  return (
    <div
      className="w-[150px]"
      data-testid={testId}
      data-scorebar="true"
      data-scorebar-kind={kind}
    >
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-[9.5px] uppercase tracking-wider text-[var(--muted)]">
          {label}
        </span>
        <span
          className={`akki-serif text-[14px] leading-none ${
            empty ? "text-[var(--muted)]" : "text-[var(--ink)]"
          }`}
        >
          {empty ? "—" : `${pct}%`}
        </span>
      </div>
      <div
        className={`h-1.5 rounded-sm w-full ${
          empty
            ? "border border-dashed border-[var(--rule)]"
            : "bg-[var(--cream-deep)]"
        } overflow-hidden`}
      >
        {!empty && (
          <div
            className={`h-full ${barClass}`}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  );
}


export default function StrategicRow({
  categoryChip = null,
  statusChip   = null,
  title,
  rightSideScores = [],
  metadataChildren = null,
  description = null,
  onClick = null,
  testId,
  isLast = false,
}) {
  const clickable = typeof onClick === "function";

  const handleKey = (e) => {
    if (!clickable) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick(e);
    }
  };

  return (
    <div
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onClick={clickable ? onClick : undefined}
      onKeyDown={clickable ? handleKey : undefined}
      className={`px-5 py-3.5 ${
        !isLast ? "border-b border-[var(--rule)]" : ""
      } ${
        clickable
          ? "cursor-pointer hover:bg-brand-rule/30 focus:outline-none focus:bg-brand-rule/40"
          : ""
      }`}
      data-testid={testId}
      data-strategic-row="true"
    >
      {/* TOP ROW — single line. Title block flexes left; scores anchor right. */}
      <div className="flex items-center gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {categoryChip}
            <h3 className="text-[14.5px] text-[var(--ink)] font-medium truncate">
              {title}
            </h3>
            {statusChip}
          </div>
        </div>

        {rightSideScores.length > 0 && (
          <div
            className="flex items-center gap-6 shrink-0"
            data-strategic-row-scores="true"
          >
            {rightSideScores.map((s, i) => (
              <ScoreBar
                key={s.testId || `${s.label}-${i}`}
                label={s.label}
                value={s.value}
                barClass={s.barClass}
                testId={s.testId}
              />
            ))}
          </div>
        )}
      </div>

      {/* METADATA ROW — count, target, owner, reassessed... + narrative under each bar. */}
      {(metadataChildren || rightSideScores.some((s) => s.narrative)) && (
        <div className="flex items-center gap-4 mt-2">
          <div className="flex-1 min-w-0">
            <div
              className="flex items-center gap-x-4 gap-y-1 text-[11.5px] text-[var(--deep)] flex-wrap"
              data-strategic-row-metadata="true"
            >
              {metadataChildren}
            </div>
          </div>
          {rightSideScores.some((s) => s.narrative) && (
            <div className="flex items-center gap-6 shrink-0">
              {rightSideScores.map((s, i) => (
                <p
                  key={`narr-${s.testId || i}`}
                  className="akki-serif italic text-[11px] text-[var(--muted)] w-[150px] truncate text-left"
                  title={s.narrative || ""}
                >
                  {s.narrative || ""}
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {description && (
        <p
          className="text-[12px] text-[var(--muted)] italic mt-2 leading-relaxed line-clamp-2"
          data-strategic-row-description="true"
        >
          {description}
        </p>
      )}
    </div>
  );
}
