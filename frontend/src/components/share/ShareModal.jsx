/**
 * ShareModal — compose an external share of a signal or briefing.
 *
 * Opens from a StreamCard or a briefing/signal detail view. Creates a row in
 * the `shares` collection; if the recipient email matches an AKKI user, the
 * share lands in their Home-inbox as a "SHARED BY" card. If not, the API
 * logs the email-send intent (actual SMTP delivery comes with §6 Email-in).
 *
 * Design: a quiet, editorial overlay. No garish CTAs; oxblood accent only on
 * the primary Share button. Closes on backdrop/ESC.
 */
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Send, Loader2, Quote as QuoteIcon } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

export default function ShareModal({
  open,
  onClose,
  contextId,
  itemType,          // "signal" | "briefing"
  item,              // the full artefact object (headline/title, etc.)
  defaultMessage,    // optional prefill
}) {
  const [toEmail, setToEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [includeQuote, setIncludeQuote] = useState(true);
  const [deliveryMethod, setDeliveryMethod] = useState("akki_notification");
  const [sending, setSending] = useState(false);

  const itemTitle = (
    itemType === "signal" ? item?.headline :
    itemType === "doc_summary" ? (item?.name || item?.original_filename) :
    itemType === "doc_evolution" ? `Drift in: ${item?.name || item?.original_filename || "document"}` :
    item?.title
  ) || "(untitled)";
  const quote = (itemTitle || "").slice(0, 260);
  const itemKicker = (
    itemType === "signal" ? "Signal" :
    itemType === "doc_summary" ? "Document summary" :
    itemType === "doc_evolution" ? "Document evolution" :
    "Briefing"
  );

  useEffect(() => {
    if (open) {
      setToEmail("");
      setSubject(itemTitle.slice(0, 120));
      const defaultByType =
        itemType === "doc_summary"
          ? `AKKI's read on ${itemTitle}. The TL;DR + the questions worth walking in with.`
          : itemType === "doc_evolution"
          ? `How this report has drifted since the last cycle — the additions, the softening, and the questions to put on the table.`
          : `Sharing this ${itemType} — worth a look.`;
      setMessage(defaultMessage ?? defaultByType);
      setIncludeQuote(true);
      setDeliveryMethod((itemType === "doc_summary" || itemType === "doc_evolution") ? "email" : "akki_notification");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, item?.id]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const canSend = toEmail.trim().length > 3 && /@/.test(toEmail) && !sending;

  const handleSend = async () => {
    if (!canSend) return;
    setSending(true);
    try {
      await api.post(`/contexts/${contextId}/shares`, {
        item_type: itemType,
        item_id: item.id,
        to_email: toEmail.trim(),
        subject: subject.trim(),
        message: message.trim(),
        include_as_quote: includeQuote,
        delivery_method: deliveryMethod,
      });
      toast.success("Share sent.", {
        description: deliveryMethod === "akki_notification"
          ? "They'll see it in their Home stream."
          : "Email stub logged — SMTP delivery ships with email-in integration.",
      });
      onClose?.();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-start md:items-center justify-center p-4 md:p-6"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          data-testid="share-modal"
        >
          <motion.div
            className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="relative bg-[var(--cream)] border border-[var(--rule)] rounded-lg shadow-xl max-w-[720px] w-full p-7 mt-10 md:mt-0"
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 6 }}
            transition={{ duration: 0.25, ease: [0.2, 0.8, 0.2, 1] }}
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-1.5 rounded-sm text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)] transition-colors"
              data-testid="share-modal-close"
            >
              <X className="w-4 h-4" />
            </button>

            <p className="akki-overline mb-2">Share externally</p>
            <h2 className="akki-serif text-[24px] leading-snug mb-1">Send this to someone.</h2>
            <p className="text-[13px] text-[var(--muted)] mb-6">
              They'll see it in their AKKI Home if they're on the platform, or get a message link otherwise.
            </p>

            {/* Quoted item preview */}
            {includeQuote && (
              <div className="bg-white border-l-[3px] border-[var(--accent)] rounded-sm px-4 py-3 mb-5">
                <div className="flex items-start gap-2">
                  <QuoteIcon className="w-3.5 h-3.5 text-[var(--accent)] mt-[3px] shrink-0" strokeWidth={1.8} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] mb-1">
                      {itemKicker} · from {item?.context_name || "this context"}
                    </p>
                    <p className="akki-serif text-[15px] leading-snug text-[var(--ink)]">{quote}</p>
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-4">
              {/* To */}
              <div>
                <label className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-1.5 block">
                  To (email)
                </label>
                <Input
                  value={toEmail}
                  onChange={(e) => setToEmail(e.target.value)}
                  placeholder="colleague@company.com"
                  className="bg-white rounded-md h-10 text-sm border-[var(--rule)]"
                  autoFocus
                  data-testid="share-to-email"
                />
              </div>

              {/* Subject */}
              <div>
                <label className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-1.5 block">
                  Subject
                </label>
                <Input
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="bg-white rounded-md h-10 text-sm border-[var(--rule)]"
                  data-testid="share-subject"
                />
              </div>

              {/* Message */}
              <div>
                <label className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-1.5 block">
                  Your message
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={4}
                  className="w-full bg-white rounded-md text-[13.5px] border border-[var(--rule)] px-3 py-2 resize-none focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)] leading-relaxed"
                  placeholder="A short note for them…"
                  data-testid="share-message"
                />
              </div>

              {/* Toggles row */}
              <div className="flex flex-wrap items-center gap-4 pt-1">
                <label className="flex items-center gap-2 text-[13px] text-[var(--deep)] cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={includeQuote}
                    onChange={(e) => setIncludeQuote(e.target.checked)}
                    className="accent-[var(--accent)]"
                    data-testid="share-include-quote"
                  />
                  Include the item as a quote
                </label>

                <div className="flex items-center gap-2 ml-auto">
                  <span className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted)]">Send via</span>
                  <Select value={deliveryMethod} onValueChange={setDeliveryMethod}>
                    <SelectTrigger className="w-[200px] rounded-md h-9 border-[var(--rule)] bg-white text-[13px]" data-testid="share-delivery-method">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="akki_notification">AKKI notification</SelectItem>
                      <SelectItem value="email">Email</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-2 mt-7 pt-5 border-t border-[var(--rule)]">
              <Button
                variant="ghost"
                onClick={onClose}
                className="text-[var(--muted)] hover:text-[var(--ink)] h-10 px-4"
                data-testid="share-cancel"
              >
                Cancel
              </Button>
              <Button
                onClick={handleSend}
                disabled={!canSend}
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-10 px-5 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="share-submit"
              >
                {sending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
                {sending ? "Sending…" : "Share"}
              </Button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
