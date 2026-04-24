/**
 * SandboxEmailCapture — quiet mid-exploration prompt.
 *
 * Surfaces once per sandbox session after ~3 minutes of engaged browsing.
 * Captured emails are stored on sandbox_metadata.prospect_email and a
 * sandbox_pickups record is queued for a 24h drip (SMTP ships with §6).
 *
 * Design: small dismissable card anchored bottom-right, not a full-screen
 * blocker. Never interrupts reading.
 */
import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Mail, Check, Sparkles } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";

// Show after this many seconds of sandbox exploration
const SHOW_AFTER_MS = 180_000;  // 3 minutes
const STORAGE_KEY_DISMISSED = "akki_sandbox_email_capture_dismissed";
const STORAGE_KEY_SUBMITTED = "akki_sandbox_email_capture_submitted";

export default function SandboxEmailCapture() {
  const { account, activeContext } = useAuth();
  const isSandbox = activeContext?.type === "sandbox";
  const alreadyCaptured = Boolean(activeContext?.sandbox_metadata?.prospect_email);
  const [visible, setVisible] = useState(false);
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!isSandbox || alreadyCaptured) return;
    // Respect prior dismissal / submission on this device
    try {
      if (window.localStorage.getItem(STORAGE_KEY_DISMISSED)) return;
      if (window.localStorage.getItem(STORAGE_KEY_SUBMITTED)) return;
    } catch { /* noop */ }
    const h = setTimeout(() => setVisible(true), SHOW_AFTER_MS);
    return () => clearTimeout(h);
  }, [isSandbox, alreadyCaptured]);

  if (!isSandbox || alreadyCaptured) return null;

  const dismiss = () => {
    setVisible(false);
    try { window.localStorage.setItem(STORAGE_KEY_DISMISSED, "1"); } catch { /* noop */ }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setSubmitting(true);
    try {
      await api.post(`/sandbox/contexts/${activeContext.id}/capture-email`, {
        email: email.trim(),
      });
      try { window.localStorage.setItem(STORAGE_KEY_SUBMITTED, "1"); } catch { /* noop */ }
      setDone(true);
      toast.success("Noted — we'll nudge you if you don't come back.");
      setTimeout(() => setVisible(false), 2200);
    } catch (err) {
      toast.error(apiErrorMessage(err, "Couldn't save that — try again."));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.35, ease: [0.2, 0.8, 0.2, 1] }}
          className="fixed bottom-6 right-6 z-40 w-[380px] bg-white border border-[var(--rule)] rounded-lg shadow-2xl overflow-hidden"
          data-testid="sandbox-email-capture"
        >
          {/* Accent rail */}
          <div className="h-[3px] bg-[var(--accent)]" />
          <div className="p-5">
            <div className="flex items-start gap-3 mb-3">
              <div className="w-8 h-8 rounded-full bg-[var(--accent-soft)] flex items-center justify-center shrink-0">
                <Sparkles className="w-3.5 h-3.5 text-[var(--accent)]" strokeWidth={2} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="akki-serif text-[17px] leading-tight text-[var(--ink)]">
                  Want to come back to this?
                </p>
                <p className="text-[12.5px] text-[var(--muted)] mt-1 leading-relaxed">
                  Drop your email — we'll send you a one-click link tomorrow to pick up where you left off.
                </p>
              </div>
              <button
                onClick={dismiss}
                className="p-1 rounded-sm text-[var(--muted)] hover:text-[var(--ink)] transition-colors"
                data-testid="sandbox-email-capture-dismiss"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            {done ? (
              <motion.div
                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="flex items-center gap-2 text-[13px] text-[var(--accent)] mt-3"
              >
                <Check className="w-4 h-4" strokeWidth={2} /> You're on the list.
              </motion.div>
            ) : (
              <form onSubmit={onSubmit} className="flex items-stretch gap-2 mt-3">
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="flex-1 h-10 px-3 text-[13px] rounded-sm border border-[var(--rule)] bg-white focus:outline-none focus:border-[var(--accent)] focus:ring-1 focus:ring-[var(--accent)]"
                  data-testid="sandbox-email-capture-input"
                />
                <button
                  type="submit"
                  disabled={submitting}
                  className="h-10 px-4 rounded-sm bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white text-[13px] font-medium transition-colors disabled:opacity-60"
                  data-testid="sandbox-email-capture-submit"
                >
                  {submitting ? "Saving…" : "Save"}
                </button>
              </form>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
