/**
 * UpgradeModal — opens when a free-plan user clicks a Pro-gated CTA.
 *
 * No fake pricing, no comparison table, no feature-matrix. One sentence,
 * two CTAs: mailto enterprise, or go to /plans. Radix Dialog, cream
 * surface, Georgia-serif heading.
 *
 * Controlled externally by a parent; exposes a tiny context provider
 * via `openUpgradeModal()` for convenience where passing state down is
 * awkward (right now: HomeV2 offer card). If a consumer renders its own
 * instance inline that still works — the module-level event bus lets
 * any Pro-gated CTA `openUpgradeModal()` without threading props.
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
      <DialogContent className="bg-[var(--cream)] max-w-[500px]" data-testid="upgrade-modal">
        <DialogHeader>
          <DialogTitle className="akki-serif text-[22px] font-normal text-[var(--ink)]">
            AKKI Pro
          </DialogTitle>
        </DialogHeader>
        <div className="mt-2">
          <p className="text-[14px] text-[var(--muted)] leading-[1.65] mb-5 max-w-[56ch]">
            Run depth analyses, generate decks with the deeper model, get
            longer Solve sessions. Pricing is on request — talk to us.
          </p>
          {source ? (
            <p className="text-[11px] text-[var(--muted)]/80 mb-4 akki-overline tracking-[0.18em]" data-testid="upgrade-modal-source">
              REQUESTED FROM · {String(source).toUpperCase()}
            </p>
          ) : null}
          <div className="flex flex-col-reverse md:flex-row gap-3 md:items-center md:justify-end">
            <Link
              to="/plans"
              onClick={() => handleOpenChange(false)}
              className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline-offset-2 hover:underline text-center md:text-left"
              data-testid="upgrade-modal-plans"
            >
              Go to Plans
            </Link>
            <a
              href="mailto:enterprise@akki.ai?subject=AKKI%20Pro%20-%20interested"
              onClick={() => handleOpenChange(false)}
              className="akki-overline tracking-[0.16em] text-[11px] text-white bg-[var(--accent)] hover:bg-[var(--accent)]/90 px-4 py-2.5 text-center"
              data-testid="upgrade-modal-talk"
            >
              TALK TO THE TEAM
            </a>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
