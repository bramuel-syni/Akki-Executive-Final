/**
 * ReviewQueueStrip — vertical (desktop) / horizontal (mobile) strip of
 * pending items shown alongside the focused card. Each item is a
 * dot/line; the current one is emphasised.
 */
import React from "react";

export default function ReviewQueueStrip({ items, currentIndex, onJump, isMobile = false }) {
  if (!items || items.length === 0) return null;
  const orientation = isMobile ? "horizontal" : "vertical";

  if (isMobile) {
    return (
      <div
        className="flex items-center gap-1.5 overflow-x-auto py-2 px-1"
        data-testid="review-strip"
        data-orientation="horizontal"
      >
        {items.map((it, i) => {
          const active = i === currentIndex;
          return (
            <button
              key={it.id}
              type="button"
              onClick={() => onJump && onJump(i)}
              className={`inline-flex items-center justify-center min-w-[26px] h-7 px-1.5 text-[10px] rounded-sm border transition-all duration-150 ${
                active
                  ? "bg-[var(--accent)] text-white border-[var(--accent)]"
                  : "bg-white text-[var(--muted)] border-[var(--rule)] hover:text-[var(--ink)]"
              }`}
              data-strip-item-index={i}
            >
              {i + 1}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <ol
      className="flex flex-col gap-1.5 py-1"
      data-testid="review-strip"
      data-orientation="vertical"
    >
      {items.map((it, i) => {
        const active = i === currentIndex;
        return (
          <li key={it.id}>
            <button
              type="button"
              onClick={() => onJump && onJump(i)}
              className={`group flex items-center gap-2.5 w-full px-2 py-1.5 rounded-sm transition-colors ${
                active ? "bg-[var(--accent)]/10" : "hover:bg-[var(--cream)]/60"
              }`}
              data-strip-item-index={i}
            >
              <span
                className={`w-1 rounded-full transition-all ${
                  active ? "bg-[var(--accent)] h-7" : "bg-[var(--rule)] h-4 group-hover:h-5"
                }`}
              />
              <span
                className={`text-[10.5px] tracking-[0.16em] uppercase truncate ${
                  active ? "text-[var(--accent)]" : "text-[var(--muted)]"
                }`}
              >
                {String(i + 1).padStart(2, "0")} · {it.kind === "briefing" ? "brief" : "inbound"}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
