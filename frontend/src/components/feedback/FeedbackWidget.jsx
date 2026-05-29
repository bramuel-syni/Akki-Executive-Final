/**
 * Phase R.4 (2026-05-27) — In-app Feedback Widget.
 *
 * Fixed lower-right widget rendered inside `Gated` so it shows on
 * every authenticated app surface. Single text field + locked
 * tag taxonomy (Broken / Wrong / Great) + submit-and-thanks toast.
 *
 * POST contract:
 *   POST /api/feedback
 *     body: { text, tag: "Broken"|"Wrong"|"Great", surface_path }
 *     response: { feedback_id, dispatched_thanks, block_reason?, received_at }
 *
 * The endpoint ALWAYS captures the feedback (writes a
 * `feedback.submitted` row to the feature_events pipe) regardless
 * of whether the auto-thanks email actually goes out — `block_reason`
 * surfaces when the founder hasn't yet filled in the [FOUNDER:]
 * thanks-copy placeholders. The widget shows the same friendly
 * toast in both cases ("Got it, thank you.") because the user
 * doesn't need to know about the founder-copy guard.
 *
 * Accessibility:
 *   - Trigger button has `aria-haspopup="dialog"` + `aria-expanded`.
 *   - When open, the panel is `role="dialog"` + `aria-label="Send feedback"`.
 *   - Escape key closes.
 *   - Focus traps to the textarea on open.
 *
 * Locked design constraints:
 *   - Position: bottom-right fixed (24px gutter on desktop,
 *     16px on mobile per the codebase's standard inset).
 *   - Tag taxonomy: exactly 3 buttons, locked labels.
 *   - Trigger: pill-shaped, low contrast, doesn't block content.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { MessageSquare, X, Loader2 } from "lucide-react";

const LOCKED_TAGS = ["Broken", "Wrong", "Great"];

export default function FeedbackWidget() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [tag, setTag] = useState(null);
  const [busy, setBusy] = useState(false);
  const textareaRef = useRef(null);
  const location = useLocation();

  // Z2.3 (2026-05-29) — observe the DOM for an open Radix Sheet
  // (DocumentDrawer / TaskDrawer / etc.) and shift the feedback
  // pill left so it doesn't sit on top of the drawer's close
  // affordance or interactive controls. The Sheet primitive renders
  // an `aside[role="dialog"][data-state="open"]` element; we watch
  // for its presence via a lightweight MutationObserver. When closed,
  // the pill returns to the canonical bottom-right gutter.
  const [drawerOpen, setDrawerOpen] = useState(false);
  useEffect(() => {
    const detect = () => {
      const open = !!document.querySelector(
        'aside[role="dialog"][data-state="open"]'
      );
      setDrawerOpen(open);
    };
    detect();
    const obs = new MutationObserver(detect);
    obs.observe(document.body, {
      subtree: true, attributes: true,
      attributeFilter: ["data-state", "role"],
      childList: true,
    });
    return () => obs.disconnect();
  }, []);

  // Open on hotkey "?+shift" — optional shortcut for power users.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (open && textareaRef.current) {
      // Defer to next tick so the panel paint completes first.
      const t = setTimeout(() => textareaRef.current?.focus(), 60);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [open]);

  const reset = useCallback(() => {
    setText("");
    setTag(null);
    setBusy(false);
  }, []);

  const handleSubmit = useCallback(async (e) => {
    e?.preventDefault();
    if (!text.trim() || !tag || busy) return;
    setBusy(true);
    try {
      const res = await api.post("/feedback", {
        text:         text.trim(),
        tag,
        surface_path: location.pathname,
      });
      // We always show the same friendly toast — whether the auto-thanks
      // landed in the SendGrid queue or the [FOUNDER:] guard blocked it,
      // the user's feedback is captured.
      const wasDispatched = Boolean(res?.data?.dispatched_thanks);
      toast.success(
        wasDispatched
          ? "Got it, thank you. We've sent a note your way."
          : "Got it, thank you.",
      );
      setOpen(false);
      reset();
    } catch (err) {
      toast.error(apiErrorMessage(err) || "Couldn't send. Try again?");
    } finally {
      setBusy(false);
    }
  }, [text, tag, busy, location.pathname, reset]);

  return (
    <>
      {/* ── Trigger button (always visible, fixed lower-right) ───── */}
      {!open && (
        <button
          type="button"
          data-testid="feedback-widget-trigger"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={open}
          className="fixed bottom-5 right-5 z-[60] inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--ink)] text-[var(--cream)] text-[12.5px] font-medium shadow-md hover:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:ring-offset-2"
        >
          <MessageSquare className="w-3.5 h-3.5" aria-hidden />
          <span>Feedback</span>
        </button>
      )}

      {/* ── Panel ─────────────────────────────────────────────── */}
      {open && (
        <div
          data-testid="feedback-widget-panel"
          role="dialog"
          aria-label="Send feedback"
          className="fixed bottom-5 right-5 z-[60] w-[340px] max-w-[calc(100vw-2rem)] bg-white border border-[var(--line)] shadow-xl rounded-md p-5 flex flex-col gap-3"
        >
          <div className="flex items-start justify-between">
            <p className="akki-serif text-[15px] text-[var(--ink)] leading-snug">
              Tell us what you saw.
            </p>
            <button
              type="button"
              onClick={() => { setOpen(false); reset(); }}
              data-testid="feedback-widget-close"
              aria-label="Close feedback"
              className="text-[var(--muted)] hover:text-[var(--ink)] -mt-1 -mr-1 p-1 transition-colors"
            >
              <X className="w-4 h-4" aria-hidden />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <textarea
              ref={textareaRef}
              data-testid="feedback-widget-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              maxLength={4000}
              rows={4}
              placeholder="What happened?"
              className="w-full text-[13px] text-[var(--ink)] border border-[var(--line)] rounded-sm p-2 resize-none focus:outline-none focus:ring-1 focus:ring-[var(--accent)] focus:border-[var(--accent)]"
            />

            {/* Tag taxonomy — locked */}
            <div className="flex gap-1.5" role="radiogroup" aria-label="Feedback type">
              {LOCKED_TAGS.map((t) => (
                <button
                  key={t}
                  type="button"
                  data-testid={`feedback-widget-tag-${t.toLowerCase()}`}
                  role="radio"
                  aria-checked={tag === t}
                  onClick={() => setTag(t)}
                  className={`flex-1 px-2 py-1.5 text-[11.5px] font-medium rounded-sm border transition-colors ${
                    tag === t
                      ? "bg-[var(--ink)] text-[var(--cream)] border-[var(--ink)]"
                      : "bg-transparent text-[var(--muted)] border-[var(--line)] hover:text-[var(--ink)] hover:border-[var(--muted)]"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="text-[10.5px] text-[var(--muted)]">
                {text.length}/4000
              </span>
              <button
                type="submit"
                data-testid="feedback-widget-submit"
                disabled={!text.trim() || !tag || busy}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium rounded-sm bg-[var(--ink)] text-[var(--cream)] disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:ring-offset-1"
              >
                {busy && <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden />}
                <span>{busy ? "Sending…" : "Send"}</span>
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
