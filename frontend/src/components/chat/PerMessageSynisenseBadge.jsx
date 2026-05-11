/**
 * CHAT sprint (2026-05-12) — PerMessageSynisenseBadge.
 *
 * Inline kicker-style label rendered on every AKKI assistant message
 * metadata row. Reads from the batched hook map; renders "N IDENTIFIERS
 * REDACTED" (with singular/zero handling), and on hover surfaces a
 * tooltip listing the three-layer breakdown.
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
  const labelText =
    n === 0
      ? "—"
      : n === 1
      ? "1 IDENTIFIER REDACTED"
      : `${n} IDENTIFIERS REDACTED`;
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
          Layer 1 regex · {lb.regex || 0} · Layer 2 Presidio · {lb.presidio || 0} · Layer 3 fallback · {lb.llm || 0}
        </span>
      )}
    </span>
  );
}
