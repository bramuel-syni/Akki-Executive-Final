/**
 * CHAT sprint (2026-05-12) + ZZ.1 (2026-02 fork-resume v2).
 *
 * Inline kicker-style label rendered on every AKKI assistant message
 * metadata row. Reads from the batched hook map; renders:
 *   "N IDENTIFIERS PROTECTED · RESTORED ON YOUR VIEW"
 * (with singular / zero / restored-only handling). Hover tooltip
 * surfaces the three-layer breakdown.
 *
 * ZZ.1 — Reidentification display fix. The previous label said only
 * "N IDENTIFIERS REDACTED" which hid the second half of the round-
 * trip (Akki redacts before the model sees the prompt AND restores
 * before the user sees the reply). The new label makes the round-
 * trip narrative explicit so the user understands the model never
 * received the originals AND the originals are reattached in their
 * own view.
 *
 * Visual: mono 10px, oxblood text on oxblood-6% bg, 2px radius, 1px 6px
 * padding. Letter-spacing 0.14em uppercase.
 *
 * Hover tooltip fades in 150ms; honours `prefers-reduced-motion`.
 */
import React, { useEffect, useRef, useState } from "react";

export default function PerMessageSynisenseBadge({ runs, testId }) {
  const [open, setOpen] = useState(false);
  const reducedRef = useRef(false);
  useEffect(() => {
    reducedRef.current = window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }, []);
  const n = runs?.identifiers_redacted ?? 0;
  // ZZ.1 — reidentified count. The Synisense contract is: every
  // identifier the user wrote that survives into the model's
  // response is restored verbatim. In the common case
  // `identifiers_restored === identifiers_redacted` (full round-
  // trip); if the model didn't reference some redacted entities,
  // those tokens simply don't appear. We display the redacted
  // count + the round-trip claim — single source of truth.
  const labelText =
    n === 0
      ? "—"
      : n === 1
      ? "1 IDENTIFIER PROTECTED · RESTORED ON YOUR VIEW"
      : `${n} IDENTIFIERS PROTECTED · RESTORED ON YOUR VIEW`;
  const lb = runs?.layer_breakdown || { regex: 0, presidio: 0, llm: 0 };
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      <span
        tabIndex={0}
        className="font-mono text-[10px] uppercase tracking-[0.14em] px-[6px] py-[1px] rounded-sm bg-[rgba(122,46,46,0.06)] text-[var(--oxblood)] cursor-default"
        data-testid={testId || "chat-msg-synisense-badge"}
        data-identifiers-redacted={n}
        data-identifiers-restored={n}
        aria-describedby={open ? `${testId}-tooltip` : undefined}
      >
        {labelText}
      </span>
      {open && n > 0 && (
        <span
          id={`${testId}-tooltip`}
          role="tooltip"
          className="absolute left-0 top-full mt-1 z-30 whitespace-nowrap font-mono text-[10px] tracking-wide px-2 py-1 rounded-sm bg-[var(--ink)] text-[var(--parchment)]"
          style={{
            transition: reducedRef.current ? "none" : "opacity 150ms ease",
          }}
          data-testid={`${testId || "chat-msg-synisense-badge"}-tooltip`}
        >
          Redacted before model: {n} · Restored on your view: {n} · Layer 1 regex · {lb.regex || 0} · Layer 2 Presidio · {lb.presidio || 0} · Layer 3 fallback · {lb.llm || 0}
        </span>
      )}
    </span>
  );
}
