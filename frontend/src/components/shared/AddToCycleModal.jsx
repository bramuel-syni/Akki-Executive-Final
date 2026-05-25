/**
 * AddToCycleModal — T3.2 (2026-05-25).
 *
 * Shared Select-Cycle-only modal that posts a document contribution
 * to the active context's cycle, conforming to G1 ratified (spec
 * §4.A → D6 + §6 G1). Extracted from `DocumentRoutingActions.jsx`
 * so both that component and the cross-surface `HandoffActions.jsx`
 * (document-kind branch) use the same modal and the same wire format.
 *
 * Wire format (G1 verbatim):
 *   POST /api/contexts/{cid}/cycle/contributions?cycle_id=<selected>
 *   body = { cycle_id, kind: "document", source_doc_id, title }
 *
 * Failure handling: status-aware human-readable toasts for 400 / 422 /
 * 423; the verbatim D6 fallback for anything else.
 *
 * Success: navigates to `/app/cycle?attached=<cycleId>` so the
 * Cycle Manager listing pulses the destination card.
 *
 * Spec-driven DOM rule (T2.3 lesson): every spec-required section
 * inside the modal emits DOM unconditionally; only its internal
 * content is data-conditional (loading vs error vs empty vs list).
 */
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Loader2, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const CYCLE_SELECTABLE_STATUSES = ["active", "draft"];

export default function AddToCycleModal({
  open,
  onOpenChange,
  contextId,
  doc,
  onActionDone,
}) {
  const navigate = useNavigate();
  const [working, setWorking] = useState(false);
  const [cycles, setCycles] = useState(null);      // null=loading, [...]=loaded
  const [selectedCycleId, setSelectedCycleId] = useState("");
  const [cyclesError, setCyclesError] = useState(null);

  useEffect(() => {
    if (!open || !contextId) return;
    let alive = true;
    setCycles(null);
    setCyclesError(null);
    setSelectedCycleId("");
    (async () => {
      try {
        const [activeResp, draftResp] = await Promise.all([
          api.get(`/contexts/${contextId}/cycles`, { params: { status: "active", page_size: 60 } }),
          api.get(`/contexts/${contextId}/cycles`, { params: { status: "draft",  page_size: 60 } }),
        ]);
        if (!alive) return;
        const merged = [
          ...((activeResp.data?.cycles) || []),
          ...((draftResp.data?.cycles)  || []),
        ];
        setCycles(merged);
      } catch (e) {
        if (!alive) return;
        setCyclesError(true);
        setCycles([]);
      }
    })();
    return () => { alive = false; };
  }, [open, contextId]);

  const onAttach = async () => {
    if (!selectedCycleId) return;
    setWorking(true);
    const cycle = (cycles || []).find((c) => c.id === selectedCycleId);
    const cycleName = cycle?.title || "the cycle";
    try {
      const payload = {
        cycle_id: selectedCycleId,
        kind: "document",
        source_doc_id: doc?.id,
        title: doc?.name || "Document",
      };
      await api.post(
        `/contexts/${contextId}/cycle/contributions?cycle_id=${encodeURIComponent(selectedCycleId)}`,
        payload,
      );
      toast.success(`Your document has been added to Cycle Manager in ${cycleName}.`);
      onOpenChange?.(false);
      onActionDone?.();
      navigate(`/app/cycle?attached=${encodeURIComponent(selectedCycleId)}`);
    } catch (e) {
      const status = e?.response?.status;
      if (status === 423) {
        toast.error("This cycle is locked and can't accept new contributions.");
      } else if (status === 422) {
        toast.error("This document can't be added — required details are missing.");
      } else if (status === 400) {
        toast.error("This document can't be added to the selected cycle.");
      } else {
        toast.error("We couldn't add this document to the cycle. Please try again.");
      }
    } finally {
      setWorking(false);
    }
  };

  return (
    <Dialog open={!!open} onOpenChange={(v) => onOpenChange?.(v)}>
      <DialogContent className="rounded-sm max-w-lg" data-testid="add-to-cycle-modal">
        <DialogHeader>
          <DialogTitle>Add to Cycle</DialogTitle>
          <DialogDescription>
            Choose which cycle this document contributes to.
          </DialogDescription>
        </DialogHeader>
        <div className="py-2">
          <label
            htmlFor="add-to-cycle-select"
            className="block text-[11.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5"
          >
            Select cycle
          </label>
          {cycles === null ? (
            <p className="text-[12px] text-slate-500 italic py-2" data-testid="add-to-cycle-loading">
              Loading cycles…
            </p>
          ) : cyclesError ? (
            <p className="text-[12px] text-red-700 py-2" data-testid="add-to-cycle-error">
              Couldn't load your cycles. Please try again.
            </p>
          ) : cycles.length === 0 ? (
            <p className="text-[12px] text-slate-500 italic py-2" data-testid="add-to-cycle-empty">
              You have no active or draft cycles. Create one from the Cycle Manager first.
            </p>
          ) : (
            <select
              id="add-to-cycle-select"
              value={selectedCycleId}
              onChange={(e) => setSelectedCycleId(e.target.value)}
              disabled={working}
              data-testid="add-to-cycle-select"
              className="w-full text-[13px] px-3 py-2 border border-[var(--rule)] rounded-sm bg-white text-[var(--ink)] focus:outline-none focus:border-[var(--accent)]"
            >
              <option value="">— Choose a cycle —</option>
              {cycles.map((c) => (
                <option key={c.id} value={c.id} data-testid={`add-to-cycle-option-${c.id}`}>
                  {c.title}
                  {CYCLE_SELECTABLE_STATUSES.includes((c.status || "").toLowerCase())
                    ? ` (${(c.status || "").toLowerCase()})`
                    : ""}
                </option>
              ))}
            </select>
          )}
        </div>
        <DialogFooter>
          <button
            onClick={() => onOpenChange?.(false)}
            className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm hover:bg-slate-50"
            data-testid="add-to-cycle-cancel"
          >
            Cancel
          </button>
          <button
            onClick={onAttach}
            disabled={working || !selectedCycleId}
            className="text-[12.5px] px-3 py-1.5 bg-[var(--accent)] text-white rounded-sm hover:opacity-90 disabled:opacity-50 inline-flex items-center gap-1.5"
            data-testid="add-to-cycle-attach"
          >
            {working ? <Loader2 className="w-3 h-3 animate-spin" /> : <ArrowRight className="w-3 h-3" />}
            Attach to cycle
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
