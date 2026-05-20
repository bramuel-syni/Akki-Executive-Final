/**
 * ReadingRail — right-hand commentary panel (desktop only).
 *
 * Receives a flat list of normalised commentary items. Renders the
 * "AKKI’s commentary" header + the items, calls down into <CommentaryItem>.
 * Independent vertical scroll — the parent grid pins height.
 */
import React from "react";
import CommentaryItem from "@/components/reading/CommentaryItem";

export default function ReadingRail({
  items,
  loading = false,
  activeParagraphId,
  flashedRailIds = new Set(),
  onJump,
  paragraphLookup,
  onGenerateSignals,
  canGenerateSignals = false,
  generatingSignals = false,
  signalsStatusMessage = "",
}) {
  const empty = !loading && items.length === 0;

  return (
    <aside
      className="hidden md:flex md:flex-col bg-white border-l border-[var(--rule)] overflow-hidden"
      data-testid="reading-rail"
    >
      <div className="px-4 py-4 border-b border-[var(--rule)]">
        <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)]">
          AKKI’s commentary
        </p>
        <p className="text-[11px] text-[var(--muted)] mt-1">
          {loading
            ? "Comparing across documents…"
            : items.length === 0
              ? "Nothing surfaced yet"
              : `${items.length} note${items.length === 1 ? "" : "s"}`}
        </p>
      </div>
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="px-4 py-8 text-[12px] italic text-[var(--muted)]">
            Comparing across documents…
          </div>
        ) : null}
        {empty ? (
          <div
            className="px-4 py-8 text-[13px] italic text-[var(--muted)] leading-[1.55]"
            data-testid="reading-rail-empty"
          >
            <p>AKKI hasn’t surfaced anything from this document yet.</p>
            {canGenerateSignals && onGenerateSignals ? (
              <button
                type="button"
                onClick={onGenerateSignals}
                disabled={generatingSignals}
                className="mt-3 text-[12px] text-[var(--accent)] hover:underline underline-offset-2 not-italic disabled:opacity-60 disabled:cursor-wait"
                data-testid="reading-rail-generate-signals"
              >
                {generatingSignals ? "Generating signals…" : "Generate signals →"}
              </button>
            ) : null}
            {/* QA-2026-05-16-007 (2026-05-18) — long-running status line. */}
            {generatingSignals && signalsStatusMessage ? (
              <p
                className="mt-3 text-[12px] text-[var(--muted)] italic"
                data-testid="reading-rail-signals-status"
              >
                {signalsStatusMessage}
              </p>
            ) : null}
          </div>
        ) : null}
        {!loading && !empty ? (
          <ul className="divide-y divide-[var(--rule)]">
            {items.map((item) => (
              <CommentaryItem
                key={`${item.kind}-${item.id}`}
                item={item}
                onJump={onJump}
                paragraphLookup={paragraphLookup}
                isActive={Boolean(
                  activeParagraphId &&
                    item.paragraphId &&
                    activeParagraphId === item.paragraphId,
                )}
                isFlashing={Boolean(item.paragraphId && flashedRailIds.has(item.paragraphId))}
              />
            ))}
          </ul>
        ) : null}
      </div>
    </aside>
  );
}
