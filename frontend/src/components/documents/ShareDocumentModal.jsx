/**
 * ShareDocumentModal — Phase E.3 (2026-05-26).
 *
 * Ports the legacy electronic-tracking implementation
 * (`backend/routers/document_engagement.py`) into the Universal
 * Document Drawer's 5th CTA. NO new tracking infrastructure invented;
 * everything wires to:
 *
 *   POST /api/contexts/{cid}/documents/{did}/share
 *        — send email + record a `document_shares` row
 *   GET  /api/contexts/{cid}/documents/{did}/engagement
 *        — returns view_count, unique_readers, share_count, latest events
 *
 * Revoke / expiry flow uses the existing `/api/shares/{share_id}` routes
 * surfaced by `routers/shares.py`.
 *
 * Inputs: docId, docTitle, contextId, open, onOpenChange.
 */
import React, { useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import { Send, Eye, RotateCcw, Loader2 } from "lucide-react";


export default function ShareDocumentModal({
  open, onOpenChange, docId, docTitle, contextId,
}) {
  const [recipients, setRecipients] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [engagement, setEngagement] = useState(null);
  const [engLoading, setEngLoading] = useState(false);

  useEffect(() => {
    if (!open || !docId) return;
    setEngLoading(true);
    api.get(`/contexts/${contextId}/documents/${docId}/engagement`)
      .then(({ data }) => setEngagement(data))
      .catch(() => setEngagement(null))
      .finally(() => setEngLoading(false));
  }, [open, docId, contextId]);

  const onSend = async () => {
    const list = recipients.split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
    if (list.length === 0) {
      toast.error("Add at least one recipient email.");
      return;
    }
    setSending(true);
    try {
      await api.post(`/contexts/${contextId}/documents/${docId}/share`, {
        recipient_emails: list,
        message: message.trim() || null,
      });
      toast.success(`Shared with ${list.length} recipient${list.length === 1 ? "" : "s"}.`);
      // Refresh engagement.
      const { data } = await api.get(`/contexts/${contextId}/documents/${docId}/engagement`);
      setEngagement(data);
      setRecipients("");
      setMessage("");
    } catch (e) { toast.error(apiErrorMessage(e)); }
    finally { setSending(false); }
  };

  const onRevoke = async (shareId) => {
    if (!shareId) return;
    try {
      await api.post(`/shares/${shareId}/revoke`);
      const { data } = await api.get(`/contexts/${contextId}/documents/${docId}/engagement`);
      setEngagement(data);
      toast.success("Share revoked.");
    } catch (e) { toast.error(apiErrorMessage(e)); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="document-share-modal">
        <DialogHeader>
          <DialogTitle className="text-[15px]">Share document</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Document</p>
            <p className="text-[13px] text-[var(--ink)] truncate" data-testid="share-modal-doc-title">{docTitle}</p>
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Recipients</p>
            <input
              value={recipients}
              onChange={(e) => setRecipients(e.target.value)}
              placeholder="alice@example.com, bob@example.com"
              className="w-full border border-[var(--rule)] rounded-sm px-2 py-1.5 text-[12.5px] focus:outline-none focus:border-[var(--ink)]"
              data-testid="share-modal-recipients"
            />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-1.5">Message (optional)</p>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              rows={3}
              className="w-full border border-[var(--rule)] rounded-sm px-2 py-1.5 text-[12.5px] focus:outline-none focus:border-[var(--ink)]"
              data-testid="share-modal-message"
            />
          </div>
          <div className="border-t border-[var(--rule)] pt-3 mt-3">
            <p className="text-[11px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mb-2">Engagement</p>
            {engLoading ? (
              <p className="text-[11.5px] text-[var(--muted)] inline-flex items-center gap-1.5">
                <Loader2 className="w-3 h-3 animate-spin" /> Loading…
              </p>
            ) : engagement ? (
              <div className="space-y-1 text-[12px]">
                <p data-testid="share-modal-engagement-views"><Eye className="w-3 h-3 inline mr-1.5" />{engagement.view_count || 0} views · {engagement.unique_readers || 0} readers</p>
                <p data-testid="share-modal-engagement-shares"><Send className="w-3 h-3 inline mr-1.5" />{engagement.share_count || 0} prior shares</p>
                {(engagement.shares || []).slice(0, 5).map((s) => (
                  <div key={s.id} className="flex items-center gap-2 text-[11.5px] text-[var(--muted)]" data-testid="share-modal-share-row">
                    <span className="truncate flex-1">{(s.recipient_emails || []).join(", ")}</span>
                    {s.status === "delivered" && !s.revoked_at && (
                      <button onClick={() => onRevoke(s.id)} className="text-[var(--muted)] hover:text-[color:var(--oxblood)] inline-flex items-center gap-1" data-testid="share-modal-revoke-btn">
                        <RotateCcw className="w-3 h-3" /> Revoke
                      </button>
                    )}
                    {s.revoked_at && (
                      <span className="text-[10px] uppercase tracking-[0.14em] font-mono text-[color:var(--oxblood)]">revoked</span>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[11.5px] italic text-[var(--muted)]" data-testid="share-modal-engagement-empty">No engagement data yet.</p>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} size="sm" data-testid="share-modal-cancel">
            Close
          </Button>
          <Button onClick={onSend} disabled={sending} size="sm" data-testid="share-modal-send">
            {sending ? <Loader2 className="w-3 h-3 animate-spin mr-1.5" /> : <Send className="w-3 h-3 mr-1.5" />}
            Send share
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
