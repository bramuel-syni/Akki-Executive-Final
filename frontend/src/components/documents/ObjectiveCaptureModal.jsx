/**
 * ObjectiveCaptureModal — Phase E.3 (2026-05-26).
 *
 * Fires when the user creates a new Draft via the Drafts tab's
 * "+ New draft" CTA. Captures the document's objective so the
 * Intelligence tab can score adherence:
 *   { goal: required, context: optional, set_at: ISO }
 *
 * Persisted on `documents.objective` via PATCH (Phase E.3 backend).
 *
 * Inputs: open, onOpenChange, onSave({goal, context}).
 */
import React, { useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";


export default function ObjectiveCaptureModal({ open, onOpenChange, onSave }) {
  const [goal, setGoal] = useState("");
  const [context, setContext] = useState("");
  const [saving, setSaving] = useState(false);

  const onSubmit = async () => {
    if (!goal.trim()) return;
    setSaving(true);
    try {
      await onSave({ goal: goal.trim(), context: context.trim() });
      // Clear + close on success.
      setGoal("");
      setContext("");
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="objective-capture-modal">
        <DialogHeader>
          <DialogTitle className="text-[15px]">What&apos;s the goal of this document?</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Goal</p>
            <input
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="What this draft is trying to do…"
              autoFocus
              className="w-full border border-[var(--rule)] rounded-sm px-2 py-1.5 text-[13px] focus:outline-none focus:border-[var(--ink)]"
              data-testid="objective-modal-goal-input"
            />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Context (optional)</p>
            <textarea
              value={context}
              onChange={(e) => setContext(e.target.value)}
              rows={3}
              placeholder="Anything Akki should keep in mind while you draft…"
              className="w-full border border-[var(--rule)] rounded-sm px-2 py-1.5 text-[12.5px] focus:outline-none focus:border-[var(--ink)]"
              data-testid="objective-modal-context-input"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} size="sm" data-testid="objective-modal-cancel">Cancel</Button>
          <Button onClick={onSubmit} disabled={!goal.trim() || saving} size="sm" data-testid="objective-modal-save">
            {saving ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : null}
            Save and start drafting
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
