/**
 * CommentaryDrawer — mobile bottom-sheet variant of the rail.
 *
 * Triggered by a fixed bottom-right button "Commentary (N)". Slides up
 * from the bottom using the existing Radix Sheet primitive. Same item
 * shape as ReadingRail — the inner list reuses CommentaryItem so the
 * styling stays consistent.
 */
import React, { useState } from "react";
import { MessageSquare } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetTrigger } from "@/components/ui/sheet";
import CommentaryItem from "@/components/reading/CommentaryItem";

export default function CommentaryDrawer({
  items,
  onJump,
  paragraphLookup,
  onGenerateSignals,
  canGenerateSignals = false,
}) {
  const [open, setOpen] = useState(false);
  const count = items.length;
  const handleJump = (paragraphId) => {
    if (onJump) onJump(paragraphId);
    setOpen(false);
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          type="button"
          className="md:hidden fixed bottom-5 right-4 z-[60] inline-flex items-center gap-2 px-4 py-2.5 rounded-full bg-[var(--navy)] text-white text-[12px] uppercase tracking-[0.18em] shadow-[0_6px_22px_-8px_rgba(10,31,68,0.55)]"
          data-testid="commentary-drawer-trigger"
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Commentary ({count})
        </button>
      </SheetTrigger>
      <SheetContent
        side="bottom"
        className="max-h-[85vh] overflow-hidden p-0 bg-white border-t border-[var(--rule)]"
        data-testid="commentary-drawer"
      >
        <SheetHeader className="px-5 py-4 border-b border-[var(--rule)] text-left">
          <SheetTitle className="akki-serif text-[16px] font-normal text-[var(--ink)]">
            AKKI’s commentary
          </SheetTitle>
          <SheetDescription className="text-[11px] text-[var(--muted)]">
            {count === 0
              ? "Nothing surfaced yet"
              : `${count} note${count === 1 ? "" : "s"} on this document`}
          </SheetDescription>
        </SheetHeader>
        <div className="overflow-y-auto max-h-[calc(85vh-72px)]">
          {count === 0 ? (
            <div className="px-5 py-8 text-[13px] italic text-[var(--muted)] leading-[1.55]">
              <p>AKKI hasn’t surfaced anything from this document yet.</p>
              {canGenerateSignals && onGenerateSignals ? (
                <button
                  type="button"
                  onClick={onGenerateSignals}
                  className="mt-3 text-[12px] text-[var(--accent)] hover:underline underline-offset-2 not-italic"
                >
                  Generate signals →
                </button>
              ) : null}
            </div>
          ) : (
            <ul className="divide-y divide-[var(--rule)]">
              {items.map((item) => (
                <CommentaryItem
                  key={`${item.kind}-${item.id}`}
                  item={item}
                  onJump={handleJump}
                  paragraphLookup={paragraphLookup}
                />
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
