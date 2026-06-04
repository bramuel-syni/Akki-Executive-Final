/**
 * LoadingChecklistModal — Track A Phase 5 (2026-06-04)
 *
 * Replaces the wizard / enhance modal body during an in-flight
 * compile / enhance / compose with a per-step checklist + elapsed
 * timer + run UUID (fig 54).
 *
 * Tightening 2 (2026-06-04 dispatch) — progress step-by-step until
 * the second-to-last step, then HOLD on "Finalising..." until
 * status="complete" arrives. Never lies about the current step:
 * the visible "current" step is either genuinely in flight OR
 * wrapping up — never a stale linear-time guess.
 *
 * Event source: 1.5s polling on
 *   `GET /api/contexts/{cid}/work-studio/exports/{export_id}`
 * (per-row `status` field is the source of truth).
 *
 * Props:
 *   - open: bool
 *   - contextId: string
 *   - exportId: string                  ← the run UUID; displayed
 *   - steps: string[]                   ← labels in order
 *   - onComplete: (export_id) => void   ← fires once status === "complete"
 *   - onError: (error_message) => void  ← fires on status === "failed"
 *   - onClose: () => void               ← user-initiated dismissal (Cancel)
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { CheckCircle2, Circle, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

const POLL_INTERVAL_MS = 1500;

export default function LoadingChecklistModal({
  open,
  contextId,
  exportId,
  steps = [],
  onComplete,
  onError,
  onClose,
}) {
  const [status, setStatus] = useState("running");
  const [elapsed, setElapsed] = useState(0);
  const [stepIndex, setStepIndex] = useState(0);
  const startedAtRef = useRef(null);
  const settledRef = useRef(false);

  // Reset on each open.
  useEffect(() => {
    if (!open) return undefined;
    setStatus("running");
    setStepIndex(0);
    setElapsed(0);
    startedAtRef.current = Date.now();
    settledRef.current = false;
    return undefined;
  }, [open, exportId]);

  // Elapsed-time tick (1Hz).
  useEffect(() => {
    if (!open) return undefined;
    const t = setInterval(() => {
      if (startedAtRef.current) {
        setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000));
      }
    }, 1000);
    return () => clearInterval(t);
  }, [open]);

  // Step progression — Tightening 2:
  //   • Steps 0 → N-2 advance linearly on a per-step interval.
  //   • Step N-1 (Finalising) is reached and HELD until status="complete".
  // The per-step interval is intentionally short (~6s) so the user
  // sees motion early; the final hold absorbs the variable LLM
  // round-trip time without lying.
  useEffect(() => {
    if (!open || steps.length <= 1) return undefined;
    const PER_STEP_MS = 6000;
    const t = setInterval(() => {
      setStepIndex((i) => {
        // Hold on the second-to-last index until status flips.
        if (i >= steps.length - 1) return i;
        return i + 1;
      });
    }, PER_STEP_MS);
    return () => clearInterval(t);
  }, [open, steps.length]);

  // Polling — the row's `status` field is the source of truth.
  useEffect(() => {
    if (!open || !exportId || !contextId) return undefined;
    let cancelled = false;

    const poll = async () => {
      try {
        const r = await api.get(
          `/contexts/${contextId}/work-studio/exports/${exportId}`,
        );
        if (cancelled) return;
        const s = (r.data?.status || "running").toLowerCase();
        setStatus(s);
        if (s === "complete" && !settledRef.current) {
          settledRef.current = true;
          // Jump to last step immediately on completion.
          setStepIndex(steps.length - 1);
          // Track A Phase 5 iter-2 (2026-06-04) — pass BOTH the
          // export_id AND the continue_doc_id back to the parent.
          // The export_id opens the DocumentOverlay (legacy work-
          // studio surface); the continue_doc_id opens the canonical
          // universal DocumentDrawer (the ?doc_id= URL surface used
          // by every other category). Iter-1 only passed exportId,
          // which 404'd against the documents-collection lookup.
          const continueDocId = r.data?.continue_doc_id || null;
          // Brief beat to let the checklist render the final ✓.
          setTimeout(() => {
            if (!cancelled) onComplete && onComplete(exportId, continueDocId);
          }, 400);
        } else if (s === "failed" && !settledRef.current) {
          settledRef.current = true;
          onError && onError(r.data?.error || "Compilation failed.");
        }
      } catch (_e) {
        /* transient errors tolerated — keep polling */
      }
    };

    poll();  // immediate first poll
    const t = setInterval(poll, POLL_INTERVAL_MS);
    return () => { cancelled = true; clearInterval(t); };
  }, [open, exportId, contextId, steps.length, onComplete, onError]);

  const shortRunId = useMemo(
    () => (exportId ? exportId.slice(0, 8).toUpperCase() : ""),
    [exportId],
  );

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) onClose && onClose(); }}>
      <DialogContent
        className="max-w-md p-0 overflow-hidden"
        data-testid="loading-checklist-modal"
      >
        <div className="px-6 pt-5 pb-3 border-b border-[var(--rule)]">
          <DialogTitle className="text-[14px] font-semibold text-slate-900">
            Running the agent cycle
          </DialogTitle>
          <p className="text-[11.5px] text-[var(--muted)] mt-0.5 font-mono uppercase tracking-[0.12em]">
            Run · {shortRunId}
            <span className="mx-2">·</span>
            <span data-testid="loading-checklist-elapsed">{elapsed}s</span>
          </p>
        </div>
        <ul className="px-6 py-4 space-y-2.5" data-testid="loading-checklist-list">
          {steps.map((label, i) => {
            const isLast = i === steps.length - 1;
            const isDone = i < stepIndex || status === "complete";
            const isCurrent = i === stepIndex && !isDone;
            const isPending = i > stepIndex;
            // Tightening 2 — the last step gets a "Finalising..."
            // label override when held; the literal step name appears
            // when complete.
            const displayLabel = (isCurrent && isLast && status !== "complete")
              ? "Finalising…"
              : label;
            return (
              <li
                key={i}
                data-testid={`loading-checklist-step-${i}`}
                data-step-status={isDone ? "complete" : isCurrent ? "current" : "pending"}
                className="flex items-center gap-2.5 text-[13px]"
              >
                {isDone ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                ) : isCurrent ? (
                  <Loader2 className="h-4 w-4 text-slate-700 shrink-0 animate-spin" />
                ) : (
                  <Circle className="h-4 w-4 text-slate-300 shrink-0" />
                )}
                <span className={
                  isDone ? "text-slate-700"
                    : isCurrent ? "text-slate-900 font-medium"
                      : "text-slate-400"
                }>
                  {displayLabel}
                </span>
              </li>
            );
          })}
        </ul>
        {status === "failed" && (
          <div className="px-6 py-3 border-t border-amber-200 bg-amber-50 text-[12px] text-amber-900"
               data-testid="loading-checklist-error">
            The agent cycle did not finish. You can close this and try again.
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export const COMPILE_STEPS = [
  "Reading sources",
  "Drafting structure",
  "Composing narrative",
  "Verifying citations",
  "Finalising format",
];

export const ENHANCE_STEPS = [
  "Reading source",
  "Applying instructions",
  "Rendering output",
];
