/**
 * DailyReview — Phase 3 (Advisory 4, Phase A).
 *
 * The load-bearing modality. A focused queue across the user's contexts:
 *   - Inbound docs awaiting triage
 *   - Briefings awaiting review (status=active, not yet read)
 *
 * Layout (per /app/docs/ux-advisories-v1.md):
 *   - Top-left: count badge "1 of N awaiting your review"
 *   - Top-right: "Done for today" link → /app
 *   - Centre: single ReviewItemCard
 *   - Bottom: 3 actions — Approve (oxblood), Edit (navy outline), Reject (muted)
 *   - Right side: ReviewQueueStrip (vertical desktop, horizontal mobile)
 *
 * Keyboard:
 *   ⏎ approve · e edit · x reject · ↑↓/j/k navigate · esc exit
 *   Disabled while focus is in input / textarea / contentEditable.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Edit3, Keyboard, Loader2 } from "lucide-react";
import { toast } from "sonner";
import AppShell from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import useReviewQueue from "@/hooks/useReviewQueue";
import useIsMobile from "@/hooks/useIsMobile";
import { apiErrorMessage } from "@/lib/api";
import ReviewItemCard from "@/components/review/ReviewItemCard";
import ReviewQueueStrip from "@/components/review/ReviewQueueStrip";

function isTypingTarget(target) {
  if (!target) return false;
  const tag = (target.tagName || "").toUpperCase();
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable === true) return true;
  // `[contenteditable=true]` is also covered by isContentEditable, but
  // some Radix portals set the attribute without isContentEditable until
  // the next tick — belt-and-braces.
  if (typeof target.getAttribute === "function" && target.getAttribute("contenteditable") === "true") return true;
  return false;
}

export default function DailyReview() {
  const navigate = useNavigate();
  const isMobile = useIsMobile();
  const { items, totalPending, loading, error, acting, refetch, approve, reject, edit } =
    useReviewQueue();

  const [currentIndex, setCurrentIndex] = useState(0);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectOpen, setRejectOpen] = useState(false);
  const [editSheetOpen, setEditSheetOpen] = useState(false);
  const [editPayload, setEditPayload] = useState(null);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const editIframeRef = useRef(null);
  const pageRef = useRef(null);

  // Ref-backed mirrors of the overlay flags so our global keydown handler
  // can always read the latest value — React's effect cleanup/re-register
  // cycle can lag behind a rapidly opened Radix overlay, which leaves the
  // closure with stale `editSheetOpen=false` at the moment the user
  // presses Escape. Refs sidestep that race.
  const rejectOpenRef = useRef(false);
  const editSheetOpenRef = useRef(false);
  const shortcutsOpenRef = useRef(false);
  useEffect(() => { rejectOpenRef.current = rejectOpen; }, [rejectOpen]);
  useEffect(() => { editSheetOpenRef.current = editSheetOpen; }, [editSheetOpen]);
  useEffect(() => { shortcutsOpenRef.current = shortcutsOpen; }, [shortcutsOpen]);

  // Auto-focus the page container on mount so global keyboard shortcuts
  // fire even before the user has clicked anywhere. This was the v1.3
  // FAIL — focus landed on Radix trigger buttons which captured Enter
  // natively, re-opening popovers instead of approving.
  useEffect(() => {
    if (pageRef.current) {
      try { pageRef.current.focus({ preventScroll: true }); } catch (_) { /* noop */ }
    }
  }, []);

  // Refocus the page container whenever an overlay closes so subsequent
  // keystrokes don't get swallowed by the trigger button that opened it.
  useEffect(() => {
    if (!rejectOpen && !editSheetOpen && !shortcutsOpen) {
      // Defer one tick so Radix has finished its own focus restoration.
      const t = window.setTimeout(() => {
        if (pageRef.current) {
          try { pageRef.current.focus({ preventScroll: true }); } catch (_) { /* noop */ }
        }
      }, 0);
      return () => window.clearTimeout(t);
    }
    return undefined;
  }, [rejectOpen, editSheetOpen, shortcutsOpen]);

  const current = items[currentIndex] || null;

  // Keep currentIndex within bounds when the queue shrinks.
  useEffect(() => {
    if (items.length === 0) {
      setCurrentIndex(0);
    } else if (currentIndex >= items.length) {
      setCurrentIndex(Math.max(0, items.length - 1));
    }
  }, [items, currentIndex]);

  const handleApprove = useCallback(async () => {
    if (!current || acting) return;
    try {
      await approve(current);
      // Stay at the same index — the just-approved item was removed, so
      // the next item slides into this slot. Optimistic local removal in
      // the hook handles that.
      toast.success("Approved.");
    } catch (err) {
      if (err?.response?.status === 409) {
        toast.error("Already actioned. Refreshing the queue.");
      } else {
        toast.error(apiErrorMessage(err, "AKKI couldn’t complete the approval."));
      }
      await refetch();
    }
  }, [current, acting, approve, refetch]);

  const submitReject = useCallback(async () => {
    if (!current || acting) return;
    setRejectOpen(false);
    try {
      await reject(current, rejectReason || undefined);
      setRejectReason("");
      toast.success("Rejected.");
    } catch (err) {
      if (err?.response?.status === 409) {
        toast.error("Already actioned. Refreshing the queue.");
      } else {
        toast.error(apiErrorMessage(err, "AKKI couldn’t complete the rejection."));
      }
      await refetch();
    }
  }, [current, acting, reject, rejectReason, refetch]);

  const handleEdit = useCallback(async () => {
    if (!current || acting) return;
    try {
      const data = await edit(current);
      // Briefings → open the existing prepare flow in a Sheet overlay.
      // Inbound docs → in-card form (handled in a follow-up; we surface
      // a toast for now since the routing knobs are not yet wired into
      // the card UI itself).
      if (data?.inline) {
        toast.message("Edit inline coming next pass — for now, approve or reject.");
        return;
      }
      if (data?.edit_url) {
        setEditPayload({ url: data.edit_url, item: current });
        setEditSheetOpen(true);
      }
    } catch (err) {
      toast.error(apiErrorMessage(err, "AKKI couldn’t open the editor."));
    }
  }, [current, acting, edit]);

  // Keyboard shortcuts.
  useEffect(() => {
    const onKey = (e) => {
      if (isTypingTarget(e.target)) return;
      // Read overlay state from refs — state closures can lag behind a
      // Radix overlay that has just opened on the same key-press cycle.
      const anyOverlayOpen =
        rejectOpenRef.current || editSheetOpenRef.current || shortcutsOpenRef.current;

      // Esc always takes precedence. If an overlay is open, let Radix close
      // it (its DismissableLayer listens for Esc natively) — we swallow the
      // event here so we don't also navigate. If nothing is open, navigate
      // home.
      if (e.key === "Escape") {
        if (anyOverlayOpen) return;
        e.preventDefault();
        navigate("/app");
        return;
      }

      // Every other shortcut is disabled while an overlay is open so that
      // keystrokes inside the edit/reject UI (typing, tabbing) aren't
      // hijacked.
      if (anyOverlayOpen) return;

      if (!current) return;

      switch (e.key) {
        case "Enter":
          e.preventDefault();
          handleApprove();
          break;
        case "e":
          e.preventDefault();
          handleEdit();
          break;
        case "x":
          e.preventDefault();
          setRejectOpen(true);
          break;
        case "ArrowDown":
        case "j":
          e.preventDefault();
          setCurrentIndex((i) => Math.min(items.length - 1, i + 1));
          break;
        case "ArrowUp":
        case "k":
          e.preventDefault();
          setCurrentIndex((i) => Math.max(0, i - 1));
          break;
        default:
          break;
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [current, items.length, handleApprove, handleEdit, navigate]);

  const headline = useMemo(() => {
    if (loading) return null;
    if (items.length === 0) return null;
    return `${currentIndex + 1} of ${items.length} awaiting your review`;
  }, [items.length, currentIndex, loading]);

  if (loading) {
    return (
      <AppShell>
        <div className="min-h-[60vh] flex items-center justify-center bg-[var(--cream)]">
          <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] animate-pulse">
            Reading the queue…
          </p>
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell>
        <div className="min-h-[60vh] flex flex-col items-center justify-center bg-[var(--cream)] px-6">
          <p className="akki-serif text-[18px] text-[var(--ink)] mb-3 text-center max-w-[40ch]">
            {error}
          </p>
          <button
            type="button"
            onClick={refetch}
            className="text-[12px] text-[var(--accent)] hover:underline underline-offset-2"
          >
            Try again
          </button>
        </div>
      </AppShell>
    );
  }

  if (items.length === 0) {
    // Empty state — single panel, editorial copy, single CTA.
    return (
      <AppShell>
        <div
          className="min-h-[70vh] flex items-center justify-center bg-[var(--cream)] px-6"
          data-testid="review-empty"
        >
          <div className="max-w-[440px] text-center">
            <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-3">
              Daily Review
            </p>
            <h1 className="akki-serif text-[28px] md:text-[32px] leading-[1.2] text-[var(--ink)] font-normal mb-4">
              Nothing’s awaiting you.
            </h1>
            <p className="akki-meta mb-6">
              AKKI will show you items here when something’s drafted, ingested, or
              extracted. Head back to your workspace, or wait — AKKI’s working on
              the cycle.
            </p>
            <Link
              to="/app"
              className="inline-flex items-center gap-1.5 text-[13px] text-[var(--accent)] hover:underline underline-offset-2"
              data-testid="review-empty-back"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Back to home
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div
        ref={pageRef}
        tabIndex={-1}
        className="min-h-[calc(100vh-4rem)] bg-[var(--cream)] px-4 md:px-8 py-6 md:py-10 outline-none focus:outline-none"
        data-testid="daily-review-page"
      >
        <div className="max-w-[1200px] mx-auto">
          {/* Header */}
          <div className="flex items-center justify-between mb-4 md:mb-6">
            <p
              className="akki-overline text-[10.5px] tracking-[0.22em] text-[var(--muted)]"
              data-testid="review-count-headline"
            >
              {headline}
            </p>
            <Link
              to="/app"
              className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline"
              data-testid="review-done-for-today"
            >
              Done for today
            </Link>
          </div>

          {/* Mobile strip on top */}
          {isMobile ? (
            <ReviewQueueStrip
              items={items}
              currentIndex={currentIndex}
              onJump={setCurrentIndex}
              isMobile
            />
          ) : null}

          {/* Body */}
          <div className="grid grid-cols-1 md:grid-cols-[1fr_180px] gap-4 md:gap-6">
            <div>
              <ReviewItemCard item={current} />

              {/* Action footer */}
              <div
                className={`mt-5 ${isMobile ? "flex flex-col gap-2.5" : "flex items-center justify-end gap-3"}`}
                data-testid="review-actions"
              >
                {/* Reject (muted, in popover for confirm + reason) */}
                <Popover open={rejectOpen} onOpenChange={setRejectOpen}>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      className={`text-[12px] text-[var(--muted)] hover:text-[var(--ink)] hover:underline underline-offset-2 ${
                        isMobile ? "w-full py-3" : "px-3 py-2"
                      }`}
                      data-testid="review-reject-btn"
                      disabled={acting}
                    >
                      Reject {!isMobile ? <kbd className="ml-1 text-[10px] text-[var(--muted)]">x</kbd> : null}
                    </button>
                  </PopoverTrigger>
                  <PopoverContent
                    side={isMobile ? "top" : "bottom"}
                    align="end"
                    className="w-[320px] bg-white border-[var(--rule)] p-4"
                    data-testid="review-reject-popover"
                  >
                    <p className="akki-overline text-[10px] tracking-[0.22em] mb-2">Reject</p>
                    <p className="text-[12px] text-[var(--muted)] mb-3 leading-[1.5]">
                      Optional reason — kept for the audit trail. The sender isn’t notified.
                    </p>
                    <Textarea
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="e.g. duplicate of last week’s pack"
                      maxLength={200}
                      className="text-[13px] mb-3"
                    />
                    <div className="flex items-center justify-end gap-2">
                      <Button variant="ghost" size="sm" onClick={() => setRejectOpen(false)}>
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        onClick={submitReject}
                        disabled={acting}
                        className="bg-[var(--ink)] text-white hover:opacity-90"
                        data-testid="review-reject-submit"
                      >
                        {acting ? "Rejecting…" : "Reject"}
                      </Button>
                    </div>
                  </PopoverContent>
                </Popover>

                {/* Edit (navy outline) */}
                <Button
                  variant="outline"
                  onClick={handleEdit}
                  disabled={acting}
                  className={`border-[var(--navy)] text-[var(--navy)] hover:bg-[var(--navy)]/5 ${
                    isMobile ? "w-full justify-center h-11" : ""
                  }`}
                  data-testid="review-edit-btn"
                >
                  <Edit3 className="w-3.5 h-3.5 mr-1.5" />
                  Edit {!isMobile ? <kbd className="ml-1 text-[10px] text-[var(--muted)]">e</kbd> : null}
                </Button>

                {/* Approve (oxblood, primary) */}
                <Button
                  onClick={handleApprove}
                  disabled={acting}
                  className={`bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white akki-overline tracking-[0.16em] text-[11px] ${
                    isMobile ? "w-full justify-center h-11" : "h-9 px-4"
                  }`}
                  data-testid="review-approve-btn"
                >
                  {acting ? (
                    <span className="inline-flex items-center gap-1.5">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" /> Saving…
                    </span>
                  ) : (
                    <>
                      Approve {!isMobile ? <kbd className="ml-1.5 text-[10px] opacity-80">↵</kbd> : null}
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* Desktop strip on right */}
            {!isMobile ? (
              <aside className="hidden md:block bg-white border border-[var(--rule)] rounded-sm p-3 sticky top-6 self-start">
                <p className="akki-overline text-[10px] tracking-[0.22em] text-[var(--muted)] mb-2 px-2">
                  Queue
                </p>
                <ReviewQueueStrip
                  items={items}
                  currentIndex={currentIndex}
                  onJump={setCurrentIndex}
                />
              </aside>
            ) : null}
          </div>

          {/* Shortcuts hint (desktop only) */}
          {!isMobile ? (
            <Popover open={shortcutsOpen} onOpenChange={setShortcutsOpen}>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="fixed bottom-4 right-4 inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm bg-white border border-[var(--rule)] text-[10.5px] tracking-[0.16em] uppercase text-[var(--muted)] hover:text-[var(--ink)]"
                  data-testid="review-shortcuts-btn"
                >
                  <Keyboard className="w-3 h-3" /> Shortcuts
                </button>
              </PopoverTrigger>
              <PopoverContent side="top" align="end" className="w-[260px] bg-white border-[var(--rule)] p-4">
                <p className="akki-overline text-[10px] tracking-[0.22em] mb-2">Keyboard</p>
                <ul className="text-[12.5px] text-[var(--ink)] space-y-1.5">
                  <li className="flex justify-between"><span>Approve</span><kbd className="text-[var(--muted)]">↵</kbd></li>
                  <li className="flex justify-between"><span>Edit</span><kbd className="text-[var(--muted)]">e</kbd></li>
                  <li className="flex justify-between"><span>Reject</span><kbd className="text-[var(--muted)]">x</kbd></li>
                  <li className="flex justify-between"><span>Navigate</span><kbd className="text-[var(--muted)]">↑ ↓ / j k</kbd></li>
                  <li className="flex justify-between"><span>Exit</span><kbd className="text-[var(--muted)]">esc</kbd></li>
                </ul>
              </PopoverContent>
            </Popover>
          ) : null}
        </div>

        {/* Edit Sheet (briefings only — opens the existing prepare flow inline) */}
        <Sheet open={editSheetOpen} onOpenChange={(v) => { setEditSheetOpen(v); if (!v) refetch(); }}>
          <SheetContent
            side={isMobile ? "bottom" : "right"}
            className={`bg-white border-[var(--rule)] p-0 ${
              isMobile ? "h-[88vh]" : "w-full sm:max-w-[640px] md:max-w-[820px]"
            }`}
            data-testid="review-edit-sheet"
          >
            <SheetHeader className="px-5 py-3 border-b border-[var(--rule)] text-left">
              <SheetTitle className="akki-serif text-[16px] font-normal">
                Edit briefing
              </SheetTitle>
              <SheetDescription className="text-[11px] text-[var(--muted)]">
                Save inside the editor; close this panel when you’re done.
              </SheetDescription>
            </SheetHeader>
            {editPayload?.url ? (
              <iframe
                ref={editIframeRef}
                src={editPayload.url}
                title="Edit briefing"
                className="w-full"
                style={{ height: isMobile ? "calc(88vh - 60px)" : "calc(100vh - 60px)" }}
              />
            ) : null}
          </SheetContent>
        </Sheet>
      </div>
    </AppShell>
  );
}
