import React, { useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog";
import { Mail, Send, X, Check, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

/**
 * Share a Studio artefact (deck or briefing) with an external reader
 * via a tracked email link. The recipient's click increments the
 * document's exposure score — so the executive knows who actually
 * read the material before the next meeting.
 *
 * Usage:
 *   <ShareArtefactModal
 *     open={open} onOpenChange={setOpen}
 *     contextId={cid} kind="deck" artefactId={deck.id}
 *     artefactTitle={deck.title}
 *     sensitivityLabel={deck.sensitivity?.label}
 *     onShared={() => refreshEngagement()}
 *   />
 */
export default function ShareArtefactModal({
  open, onOpenChange, contextId, kind, artefactId,
  artefactTitle, sensitivityLabel, onShared,
}) {
  const [toName, setToName] = useState("");
  const [toEmail, setToEmail] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // { ok, to_email, email_mode } | null

  const reset = () => {
    setToName(""); setToEmail(""); setMessage("");
    setResult(null); setBusy(false);
  };

  const close = (v) => {
    if (!v) reset();
    onOpenChange?.(v);
  };

  const submit = async (e) => {
    e?.preventDefault();
    if (!toEmail.includes("@")) {
      toast.error("Please enter a valid email address.");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/studio/${kind}/${artefactId}/share-email`,
        { to_email: toEmail.trim(), to_name: toName.trim() || null, message: message.trim() || null },
      );
      setResult(data);
      onShared?.(data);
      toast.success(
        data.email_mode === "sent"
          ? "Shared — the recipient will get an email with a tracked link."
          : "Share recorded. Email provider isn't configured — copy the tracked link below.",
      );
    } catch (err) {
      toast.error(apiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent
        className="bg-[var(--cream)] max-w-lg p-0 border-[var(--rule)]"
        data-testid="share-artefact-modal"
      >
        <DialogHeader className="px-6 pt-6 pb-3 border-b border-[var(--rule)]">
          <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--accent)] mb-1">
            Share with the chair
          </p>
          <DialogTitle className="akki-serif text-[22px] text-[var(--ink)] font-normal leading-tight">
            {artefactTitle || "Your document"}
          </DialogTitle>
          <DialogDescription className="text-[12.5px] text-[var(--muted)] mt-1">
            Send a tracked link. When they open it, we log the read and bump your exposure score.
            {sensitivityLabel ? (
              <span className="ml-1.5 text-[var(--accent)] uppercase tracking-[0.14em] text-[10px]">
                · {sensitivityLabel}
              </span>
            ) : null}
          </DialogDescription>
        </DialogHeader>

        {!result && (
          <form onSubmit={submit} className="px-6 py-5 space-y-4" data-testid="share-artefact-form">
            <div>
              <Label htmlFor="share-to-name" className="text-[11.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
                Recipient name (optional)
              </Label>
              <Input
                id="share-to-name"
                value={toName}
                onChange={(e) => setToName(e.target.value)}
                placeholder="e.g. Chair Mwangi"
                className="mt-1.5 bg-white border-[var(--rule)]"
                data-testid="share-to-name-input"
              />
            </div>
            <div>
              <Label htmlFor="share-to-email" className="text-[11.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
                Email
              </Label>
              <Input
                id="share-to-email"
                type="email"
                required
                value={toEmail}
                onChange={(e) => setToEmail(e.target.value)}
                placeholder="chair@example.com"
                className="mt-1.5 bg-white border-[var(--rule)]"
                data-testid="share-to-email-input"
              />
            </div>
            <div>
              <Label htmlFor="share-message" className="text-[11.5px] uppercase tracking-[0.14em] text-[var(--muted)]">
                Note (optional)
              </Label>
              <Textarea
                id="share-message"
                rows={3}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="For your read ahead of Thursday."
                className="mt-1.5 bg-white border-[var(--rule)] resize-none"
                data-testid="share-message-input"
              />
            </div>
            <div className="pt-2 flex items-center justify-between gap-3">
              <p className="text-[11px] text-[var(--muted)] italic leading-relaxed">
                Link expires in 14 days. The recipient's visit is recorded against this document.
              </p>
              <div className="flex items-center gap-2 shrink-0">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => close(false)}
                  className="border-[var(--rule)]"
                  data-testid="share-artefact-cancel"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={busy || !toEmail.includes("@")}
                  className="bg-[var(--accent)] hover:bg-[var(--accent-deep)] text-white"
                  data-testid="share-artefact-submit"
                >
                  {busy ? "Sending…" : <><Send className="w-3.5 h-3.5 mr-1.5" /> Share</>}
                </Button>
              </div>
            </div>
          </form>
        )}

        {result && (
          <div className="px-6 py-6" data-testid="share-artefact-success">
            <div className="flex items-start gap-3">
              {result.email_mode === "sent" ? (
                <Check className="w-5 h-5 text-emerald-700 mt-0.5 shrink-0" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
              )}
              <div className="min-w-0">
                <p className="akki-serif text-[17px] text-[var(--ink)] leading-snug">
                  {result.email_mode === "sent"
                    ? `Email sent to ${result.to_email}.`
                    : `Share recorded — email delivery wasn't available.`}
                </p>
                <p className="text-[12.5px] text-[var(--muted)] mt-1 leading-relaxed">
                  The exposure score on this {kind} will update the moment they open it.
                  You'll see them in the readers strip once the click lands.
                </p>
                {result.tracked_url && (
                  <div className="mt-4 p-3 bg-[var(--cream-deep)]/40 border border-[var(--rule)] rounded-sm">
                    <p className="text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] mb-1.5">
                      Copy this tracked link
                    </p>
                    <code className="block text-[11px] break-all text-[var(--deep)]">
                      {result.tracked_url}
                    </code>
                  </div>
                )}
              </div>
            </div>
            <div className="mt-5 flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={reset}
                className="border-[var(--rule)]"
                data-testid="share-artefact-send-another"
              >
                <Mail className="w-3.5 h-3.5 mr-1.5" /> Share with someone else
              </Button>
              <Button
                type="button"
                onClick={() => close(false)}
                className="bg-[var(--ink)] hover:bg-black text-white"
                data-testid="share-artefact-done"
              >
                Done
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
