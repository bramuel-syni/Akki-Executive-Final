/**
 * AddToWorkStudioModal — T3.1 (2026-05-25).
 *
 * Implements spec §4.A → D5 verbatim. Modal opens when the user
 * clicks "Add to Work Studio" from a Document Journal item. Asks
 * the user to pick one of five artefact types; on submit, POSTs to
 * the new `/api/contexts/{cid}/work-studio/from-document` endpoint
 * and routes per G8 ratified:
 *   • Board Pack + Committee Pack → dedicated page (`/app/work-studio/document/{aid}`)
 *   • Minutes + Deck + Report     → drawer-eligible listing tab with `?pulse=<aid>`
 *
 * Copy is verbatim from the spec:
 *   Title              → "Add to Work Studio"
 *   Supporting text    → "Choose the artefact type for this document."
 *   CTA label          → "Add document ({Type})"  ← Type comes from selection
 *   Success toast      → "Your document has been added to Work Studio as a {Type}."
 *   Failure toast      → "We couldn't add this document to Work Studio. Please try again."
 *
 * Spec-driven DOM rule (T2.3 lesson): all five artefact-type cards
 * render unconditionally; the CTA renders unconditionally and is
 * disabled until a card is selected.
 */
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Loader2, FileText, Presentation, Newspaper, Layers, Briefcase,
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

// Display label (spec verbatim) → backend kind key.
const ARTEFACT_TYPES = [
  { kind: "board_pack",     label: "Board Pack",      icon: Briefcase },
  { kind: "minutes",        label: "Minutes",         icon: Newspaper },
  { kind: "committee_pack", label: "Committee Pack",  icon: Layers },
  { kind: "deck",           label: "Deck",            icon: Presentation },
  { kind: "report",         label: "Report",          icon: FileText },
];

function labelFor(kind) {
  const row = ARTEFACT_TYPES.find((t) => t.kind === kind);
  return row?.label || kind;
}

export default function AddToWorkStudioModal({
  open,
  onOpenChange,
  contextId,
  doc,
  onActionDone,
}) {
  const navigate = useNavigate();
  const [selectedKind, setSelectedKind] = useState("");
  const [working, setWorking] = useState(false);

  // Reset selection when modal opens (a stale selection from a prior
  // open would lie about the user's current intent).
  React.useEffect(() => {
    if (open) setSelectedKind("");
  }, [open]);

  const ctaLabel = selectedKind
    ? `Add document (${labelFor(selectedKind)})`
    : "Add document";

  const onSubmit = async () => {
    if (!selectedKind || !doc?.id || !contextId) return;
    setWorking(true);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/work-studio/from-document`,
        { kind: selectedKind, source_doc_id: doc.id },
      );
      // Verbatim success toast per D5 step 3.
      toast.success(
        `Your document has been added to Work Studio as a ${labelFor(selectedKind)}.`
      );
      onOpenChange?.(false);
      onActionDone?.();
      // G8 routing — server emits a redirect_url that already encodes
      // page-vs-drawer destination; honour it.
      if (data?.redirect_url) {
        navigate(data.redirect_url);
      }
    } catch (e) {
      // Verbatim failure toast per D5 step 3 (failure branch).
      toast.error("We couldn't add this document to Work Studio. Please try again.");
    } finally {
      setWorking(false);
    }
  };

  return (
    <Dialog open={!!open} onOpenChange={(v) => onOpenChange?.(v)}>
      <DialogContent className="rounded-sm max-w-2xl" data-testid="add-to-work-studio-modal">
        <DialogHeader>
          <DialogTitle>Add to Work Studio</DialogTitle>
          <DialogDescription>
            Choose the artefact type for this document.
          </DialogDescription>
        </DialogHeader>
        <div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 py-2"
          data-testid="add-to-work-studio-type-grid"
          role="radiogroup"
          aria-label="Choose artefact type"
        >
          {ARTEFACT_TYPES.map((t) => {
            const Icon = t.icon;
            const active = selectedKind === t.kind;
            return (
              <button
                key={t.kind}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => setSelectedKind(t.kind)}
                disabled={working}
                data-testid={`add-to-work-studio-type-${t.kind}`}
                className={[
                  "flex items-center gap-2 p-3 border rounded-sm text-left transition-colors",
                  active
                    ? "border-[var(--accent)] bg-[var(--accent)]/5 text-[var(--ink)]"
                    : "border-[var(--rule)] text-[var(--ink)] hover:border-[var(--accent)]",
                  "disabled:opacity-50",
                ].join(" ")}
              >
                <Icon className="w-4 h-4 shrink-0 text-[var(--muted)]" strokeWidth={1.7} />
                <span className="text-[13px] akki-serif">{t.label}</span>
              </button>
            );
          })}
        </div>
        <DialogFooter>
          <button
            onClick={() => onOpenChange?.(false)}
            disabled={working}
            className="text-[12.5px] px-3 py-1.5 border border-[var(--rule)] rounded-sm hover:bg-slate-50 disabled:opacity-50"
            data-testid="add-to-work-studio-cancel"
          >
            Cancel
          </button>
          <button
            onClick={onSubmit}
            disabled={working || !selectedKind}
            className="text-[12.5px] px-3 py-1.5 bg-[var(--accent)] text-white rounded-sm hover:opacity-90 disabled:opacity-50 inline-flex items-center gap-1.5"
            data-testid="add-to-work-studio-submit"
          >
            {working && <Loader2 className="w-3 h-3 animate-spin" />}
            {ctaLabel}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
