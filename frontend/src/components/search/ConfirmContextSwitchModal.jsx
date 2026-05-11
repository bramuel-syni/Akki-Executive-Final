/**
 * Phase F0.3 — ConfirmContextSwitchModal.
 *
 * Opens when a search result lives in a different tenant than the
 * active one. Names BOTH companies, requires explicit confirmation,
 * writes an audit row, switches the active context, then navigates.
 *
 * Contract — parent owns this component and passes:
 *   pending: { from_context_id, from_context_name,
 *              to_context_id,   to_context_name,
 *              surface, result_id, deep_link, type }
 *   onClose(): close without switching
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Loader2, ArrowRight } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import { toast } from "sonner";

export default function ConfirmContextSwitchModal({ pending, onClose }) {
  const { switchContext } = useAuth();
  const navigate = useNavigate();
  const [working, setWorking] = useState(false);
  const open = !!pending;

  const onConfirm = async () => {
    if (!pending) return;
    setWorking(true);
    try {
      // 1) Write the cross-context-open audit row BEFORE the switch so
      //    failure here is loud, not silent.
      try {
        await api.post(`/search/cross-context-open`, {
          from_context_id: pending.from_context_id,
          to_context_id: pending.to_context_id,
          surface: pending.surface,
          result_id: pending.result_id,
        });
      } catch (e) {
        // Non-fatal — we still let the user open the result, but the
        // observability gap is logged.
        // eslint-disable-next-line no-console
        console.warn("[search] cross-context-open audit failed", e);
      }
      // 2) Perform the actual context switch via the existing
      //    AuthContext helper (silent — no memo modal in this flow).
      await switchContext(pending.to_context_id, {
        fromContextId: pending.from_context_id,
        silent: true,
      });
      // 3) Navigate to the result.
      navigate(pending.deep_link);
      onClose?.();
    } catch (e) {
      toast.error("Couldn't switch company. Try again.");
    } finally {
      setWorking(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose?.()}>
      <DialogContent
        className="rounded-sm max-w-md"
        data-testid="confirm-context-switch-modal"
      >
        <DialogHeader>
          <DialogTitle data-testid="confirm-context-switch-title">
            Open in {pending?.to_context_name}?
          </DialogTitle>
          <DialogDescription className="text-sm text-slate-600 mt-2">
            You are currently in <span className="font-medium text-[var(--ink)]">{pending?.from_context_name}</span>.
            To view this {pending?.type?.toLowerCase() || "item"}, Akki will
            switch your active company to <span className="font-medium text-[var(--ink)]">{pending?.to_context_name}</span>.
            Your work in {pending?.from_context_name} is saved.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="mt-4 flex flex-row justify-end gap-2">
          <button
            onClick={onClose}
            disabled={working}
            data-testid="confirm-context-switch-cancel"
            className="px-3 py-1.5 text-sm rounded-sm border border-[var(--rule)] hover:bg-slate-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={working}
            data-testid="confirm-context-switch-confirm"
            className="px-3 py-1.5 text-sm rounded-sm bg-[var(--accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1.5"
          >
            {working ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ArrowRight className="w-3.5 h-3.5" />}
            Switch and open
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
