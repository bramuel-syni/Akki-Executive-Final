/**
 * UpgradeModal — surfaces the "Billing & Subscription — Coming Soon"
 * state when a free-plan user clicks a Pro-gated CTA.
 *
 * Chunk c (2026-05-25): no fake pricing, no checkout, no marketing
 * push. One sentence of honest framing + a direct route to the
 * Coming-Soon billing surface where the Notify-me CTA lives. An
 * optional secondary mailto for users who want a human touch (kept
 * because some Pro-gated CTAs come from board/enterprise prospects).
 *
 * Controlled externally by a parent; exposes a tiny context provider
 * via `openUpgradeModal()` for convenience where passing state down is
 * awkward (HomeV2 offer card, AppShell sidebar). If a consumer renders
 * its own instance inline that still works — the module-level event
 * bus lets any Pro-gated CTA `openUpgradeModal()` without threading
 * props.
 */
import React, { useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Link } from "react-router-dom";

// Tiny pub-sub so any CTA can trigger the singleton modal without prop-
// drilling. The root provider (mounted once at the app level) subscribes
// and flips its `open` state.
const _listeners = new Set();
export function openUpgradeModal(source = "unknown") {
  _listeners.forEach((fn) => {
    try { fn(source); } catch { /* noop */ }
  });
}

// Spec-verbatim copy — must match `routers/billing.py` and
// `components/settings/BillingTab.jsx` exactly.
const COMING_SOON_BODY =
  "We're finalizing our subscription tiers. Your account is fully " +
  "active during this preview period; billing will roll out in a " +
  "future release.";

export default function UpgradeModal({ controlledOpen, onOpenChange }) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState(null);
  const isControlled = typeof controlledOpen === "boolean";
  const actualOpen = isControlled ? controlledOpen : open;

  useEffect(() => {
    const handler = (src) => {
      setSource(src);
      if (isControlled) {
        onOpenChange?.(true);
      } else {
        setOpen(true);
      }
    };
    _listeners.add(handler);
    return () => _listeners.delete(handler);
  }, [isControlled, onOpenChange]);

  const handleOpenChange = (v) => {
    if (isControlled) onOpenChange?.(v);
    else setOpen(v);
  };

  return (
    <Dialog open={actualOpen} onOpenChange={handleOpenChange}>
      <DialogContent
        className="bg-[var(--cream)] max-w-[500px]"
        data-testid="upgrade-modal"
      >
        <DialogHeader>
          <DialogTitle
            className="akki-serif text-[22px] font-normal text-[var(--ink)]"
            data-testid="upgrade-modal-heading"
          >
            Billing & Subscription — Coming Soon
          </DialogTitle>
        </DialogHeader>
        <div className="mt-2">
          <p
            className="text-[14px] text-[var(--muted)] leading-[1.65] mb-5 max-w-[56ch]"
            data-testid="upgrade-modal-body"
          >
            {COMING_SOON_BODY}
          </p>
          {source ? (
            <p
              className="text-[11px] text-[var(--muted)]/80 mb-4 akki-overline tracking-[0.18em]"
              data-testid="upgrade-modal-source"
            >
              REQUESTED FROM · {String(source).toUpperCase()}
            </p>
          ) : null}
          <div className="flex flex-col-reverse md:flex-row gap-3 md:items-center md:justify-end">
            <a
              href="mailto:enterprise@akki.ai?subject=AKKI%20Pro%20-%20interested"
              onClick={() => handleOpenChange(false)}
              className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline text-center md:text-left"
              data-testid="upgrade-modal-talk"
            >
              Talk to the team
            </a>
            <Link
              to="/app/settings/billing"
              onClick={() => handleOpenChange(false)}
              className="akki-overline tracking-[0.16em] text-[11px] text-white bg-[var(--accent)] hover:bg-[var(--accent)]/90 px-4 py-2.5 text-center"
              data-testid="upgrade-modal-billing-cta"
            >
              NOTIFY ME WHEN READY
            </Link>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
