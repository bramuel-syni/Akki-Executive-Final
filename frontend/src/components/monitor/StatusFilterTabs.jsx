/**
 * StatusFilterTabs — shared Monitor status-filter row primitive.
 *
 * Phase Y followup (2026-02 fork-resume) · Monitor status-filter
 * harmonization — extracted from `StrategicGoalsPanel.jsx` so both
 * Monitor surfaces (Strategic Objectives + Tasks/Initiatives) share
 * one rendering contract. The pre-extraction Tasks row used a
 * different visual treatment (chunky `rounded-full` capsules with
 * uppercase labels + brand-accent active background); the user
 * called the Goals row the gold standard and asked Tasks to match.
 *
 * Design contract (locked):
 *  • Container: `flex items-center gap-1 flex-wrap` + `role="tablist"`
 *  • Tab: `inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm
 *          text-[11.5px] transition-colors`
 *  • Active: `bg-[var(--ink)] text-[var(--parchment)]`
 *  • Inactive: `text-[var(--muted)] hover:text-[var(--ink)]
 *               hover:bg-brand-rule/40`
 *    (Wave 4.2.followup.2 compliance — `bg-brand-rule/N` is the
 *    Tailwind-config RGB short name; `bg-[var(--cream-deep)]/N`
 *    silently failed on hover because `--cream-deep` is a hex var.
 *    `brand-rule` = `--graphite-light` = `#B8B6AF`, same color.)
 *  • Count chip: separate inline span, `font-mono text-[10px] px-1
 *                rounded-sm`; active chip = `bg-[var(--parchment)]/20`,
 *                inactive = `text-[var(--muted)]`
 *  • Accessibility: full tablist contract — every tab carries
 *    `role="tab"` + `aria-selected` reflecting active state.
 *
 * The primitive is markup-only; it does not own state. Callers
 * pass `tabs` (key+label pairs), `activeKey`, `onSelect`, and a
 * per-tab `counts` map. The `testIdPrefix` lets each surface
 * preserve its existing testid namespace (`strategic-goals-status-
 * tab-<key>`, `tasks-status-tab-<key>`, ...).
 */
import React from "react";


/**
 * tabs:           [{ key, label }]
 * activeKey:      string (matches one of tabs[i].key)
 * onSelect:       (key) => void
 * counts:         { [key]: number }   (optional — chip hidden if undefined)
 * testIdPrefix:   string (e.g. "strategic-goals-status-tab")
 * ariaLabel:      string (`role="tablist"` accessible label)
 */
export default function StatusFilterTabs({
  tabs,
  activeKey,
  onSelect,
  counts,
  testIdPrefix,
  ariaLabel,
}) {
  return (
    <div
      className="flex items-center gap-1 flex-wrap"
      role="tablist"
      aria-label={ariaLabel}
      data-testid={`${testIdPrefix}-list`}
    >
      {tabs.map((t) => {
        const active = activeKey === t.key;
        const hasCount = counts && typeof counts[t.key] === "number";
        return (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onSelect(t.key)}
            className={[
              "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-[11.5px] transition-colors",
              active
                ? "bg-[var(--ink)] text-[var(--parchment)]"
                : "text-[var(--muted)] hover:text-[var(--ink)] hover:bg-brand-rule/40",
            ].join(" ")}
            data-testid={`${testIdPrefix}-${t.key}`}
          >
            <span>{t.label}</span>
            {hasCount && (
              <span
                className={[
                  "font-mono text-[10px] px-1 rounded-sm",
                  active ? "bg-[var(--parchment)]/20" : "text-[var(--muted)]",
                ].join(" ")}
                data-testid={`${testIdPrefix}-${t.key}-count`}
              >
                {counts[t.key]}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
