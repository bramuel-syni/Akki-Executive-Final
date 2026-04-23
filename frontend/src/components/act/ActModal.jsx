import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Dialog, DialogContent, DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { api, apiErrorMessage } from "@/lib/api";
import { Mail, ScrollText, ArrowRight, Copy, X } from "lucide-react";

/**
 * ActModal — v4.2 unified composition overlay.
 * Destinations kept minimal per user direction: Message + Add to briefing.
 *
 * Props:
 *   open: bool
 *   onOpenChange: (bool) => void
 *   signal: the signal being acted on
 *   contextId: the active context id
 */
export default function ActModal({ open, onOpenChange, signal, contextId }) {
  const [tab, setTab] = useState("message");
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open || !signal) return;
    // Prefill
    setTab("message");
    setTo("");
    setSubject(`Board-relevant signal: ${signal.headline?.slice(0, 80) || ""}`);
    const citations = (signal.sources || [])
      .map((s, i) => `  [${i + 1}] ${s.doc_name} (data trust: ${s.data_trust || "unrated"})`)
      .join("\n");
    setBody(
      `${signal.headline}\n\n${signal.summary || ""}\n\n` +
      `${citations ? "Sources grounding this signal:\n" + citations + "\n\n" : ""}` +
      `Surfaced by AKKI. Open in context: (your AKKI workspace)\n`
    );
  }, [open, signal]);

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Copy failed — select the text manually.");
    }
  };

  const onSendMessage = () => {
    // No mail provider wired; best-effort: open system mailto + copy body
    const mailto = `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    try {
      window.location.href = mailto;
      toast.success("Opened in your mail client");
      onOpenChange(false);
    } catch {
      copyToClipboard(`To: ${to}\nSubject: ${subject}\n\n${body}`);
      toast.message("Your browser blocked the mailto — the text is copied.");
    }
  };

  const onAddToBriefing = async () => {
    setSubmitting(true);
    try {
      const { data } = await api.post(
        `/contexts/${contextId}/briefings`,
        { signal_ids: [signal.id], title: `Follow-up · ${signal.headline?.slice(0, 60)}` },
        { timeout: 120000 },
      );
      toast.success(`Briefing v${data.version} composed`);
      onOpenChange(false);
      navigate("/app/briefings");
    } catch (e) {
      toast.error(apiErrorMessage(e));
    } finally { setSubmitting(false); }
  };

  if (!signal) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-[720px] p-0 bg-white border border-[var(--rule)] rounded-lg"
        data-testid="act-modal"
      >
        {/* Header — muted cream */}
        <div className="px-6 py-4 bg-[var(--cream)] border-b border-[var(--rule)]">
          <p className="akki-overline mb-1">Act on this signal</p>
          <DialogTitle className="akki-lead leading-snug text-left pr-8" data-testid="act-signal-headline">
            {signal.headline}
          </DialogTitle>
        </div>

        {/* Destination tabs */}
        <div className="px-6 border-b border-[var(--rule)]">
          <div className="flex gap-6">
            <button
              onClick={() => setTab("message")}
              data-selected={tab === "message"}
              className="akki-scope-chip py-3 flex items-center gap-2"
              data-testid="act-tab-message"
            >
              <Mail className="w-3.5 h-3.5" /> Message someone
            </button>
            <button
              onClick={() => setTab("briefing")}
              data-selected={tab === "briefing"}
              className="akki-scope-chip py-3 flex items-center gap-2"
              data-testid="act-tab-briefing"
            >
              <ScrollText className="w-3.5 h-3.5" /> Add to briefing
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="p-6">
          {tab === "message" ? (
            <div className="space-y-4" data-testid="act-message-form">
              <div>
                <label className="akki-overline block mb-1.5">To</label>
                <Input
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                  placeholder="name@company.com"
                  className="rounded-md h-10 border-[var(--rule)] bg-white"
                  type="email"
                  data-testid="act-to-input"
                />
              </div>
              <div>
                <label className="akki-overline block mb-1.5">Subject</label>
                <Input
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="rounded-md h-10 border-[var(--rule)] bg-white"
                  data-testid="act-subject-input"
                />
              </div>
              <div>
                <label className="akki-overline block mb-1.5">Message</label>
                <Textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  className="rounded-md min-h-[180px] border-[var(--rule)] bg-white text-[14px] leading-relaxed"
                  data-testid="act-body-input"
                />
              </div>
              <p className="text-[11px] text-[var(--muted)] italic">
                AKKI opens your mail client pre-filled. No mail leaves the platform; everything is local to your browser.
              </p>
            </div>
          ) : (
            <div className="space-y-4" data-testid="act-briefing-preview">
              <p className="akki-serif text-[15px] leading-relaxed text-[var(--deep)]">
                AKKI will compose a single-item briefing (PDF + DOCX exportable) focused entirely on this signal —
                with an opening paragraph, the evidence, and the one question you should ask in the meeting.
              </p>
              <div className="bg-[var(--cream)] border border-[var(--rule)] rounded-md p-4">
                <p className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2 font-semibold">Signal</p>
                <p className="akki-lead text-[16px] mb-2">{signal.headline}</p>
                <p className="text-[13px] text-[var(--muted)] line-clamp-3">{signal.summary}</p>
              </div>
              {(signal.sources || []).length > 0 && (
                <div>
                  <p className="akki-overline mb-2">Will cite</p>
                  <div className="flex flex-wrap gap-1.5">
                    {signal.sources.map((s) => (
                      <span key={s.doc_id} className="akki-context-chip">{s.doc_name}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-[var(--cream)] border-t border-[var(--rule)] flex items-center justify-between">
          <button
            onClick={() => copyToClipboard(`${signal.headline}\n\n${signal.summary}`)}
            className="text-[13px] text-[var(--muted)] hover:text-[var(--accent)] inline-flex items-center gap-1.5"
            data-testid="act-copy-btn"
          >
            <Copy className="w-3.5 h-3.5" /> Copy text
          </button>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              onClick={() => onOpenChange(false)}
              className="rounded-md text-[var(--muted)] hover:text-[var(--ink)]"
              data-testid="act-cancel-btn"
            >
              Cancel
            </Button>
            {tab === "message" ? (
              <Button
                onClick={onSendMessage}
                disabled={!to || !subject}
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-9 px-4"
                data-testid="act-send-btn"
              >
                <Mail className="w-3.5 h-3.5 mr-2" /> Open in mail <ArrowRight className="w-3.5 h-3.5 ml-2" />
              </Button>
            ) : (
              <Button
                onClick={onAddToBriefing}
                disabled={submitting}
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-md h-9 px-4"
                data-testid="act-compose-briefing-btn"
              >
                {submitting ? "Composing…" : <>Compose briefing <ArrowRight className="w-3.5 h-3.5 ml-2" /></>}
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
