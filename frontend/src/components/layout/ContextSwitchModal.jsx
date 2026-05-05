/**
 * ContextSwitchModal — Phase A (Memo Item 5).
 *
 * Renders the verbatim memo switch-modal copy on the layer above
 * everything else in the AppShell. The body is taken straight from
 * the server response (`POST /api/me/active-context`); we do NOT
 * compose copy on the client. The button label "Continue" matches
 * memo Item 5.
 *
 * Dismissing the modal calls `dismissSwitchModal()` from AuthContext,
 * which reloads the current page so all on-screen data re-fetches
 * with the new (user, context) role binding.
 */
import React from "react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Building2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export default function ContextSwitchModal() {
  const { pendingSwitchModal, dismissSwitchModal } = useAuth();
  const open = !!pendingSwitchModal;

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) dismissSwitchModal(); }}>
      <DialogContent
        className="max-w-[480px] bg-[var(--cream)] border-[var(--rule)] p-0"
        data-testid="context-switch-modal"
      >
        <div className="px-7 py-5 border-b border-[var(--rule)] bg-white">
          <p className="akki-overline mb-2 flex items-center gap-1.5">
            <Building2 className="w-3 h-3 text-[var(--accent)]" /> Context switched
          </p>
          <DialogTitle
            className="akki-serif text-[20px] font-normal text-[var(--ink)] leading-snug"
            data-testid="context-switch-modal-title"
          >
            {pendingSwitchModal?.title || "You are now in a new context"}
          </DialogTitle>
        </div>
        <div className="px-7 py-6 bg-white">
          <DialogDescription
            className="akki-serif text-[15px] leading-[1.7] text-[var(--deep)]"
            data-testid="context-switch-modal-body"
          >
            {pendingSwitchModal?.body}
          </DialogDescription>
        </div>
        <div className="px-7 py-3 border-t border-[var(--rule)] bg-white flex justify-end">
          <Button
            onClick={dismissSwitchModal}
            className="rounded-sm h-9 text-[13px] px-5"
            data-testid="context-switch-modal-continue"
          >
            Continue
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
