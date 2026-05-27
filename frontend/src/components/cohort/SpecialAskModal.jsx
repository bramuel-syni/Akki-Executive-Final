/**
 * Phase R.5.b.2 (2026-05-27) — Special-ask modal.
 *
 * Renders inside `Gated` (alongside Day16Banner + FeedbackWidget)
 * but only when `useTrialStatus().special_ask_surface === true`.
 * The backend sets that flag when the user is on day 14+ AND
 * `cohort_special_asks` row status is still `pending`.
 *
 * Three fields:
 *   - referral_name  (required, enables Save)
 *   - referral_email (required, enables Save)
 *   - case_study_consent (optional checkbox)
 *   - testimonial_text (optional)
 *
 * "Remind me later" closes the modal for the session but does NOT
 * change the row's status — the modal re-surfaces on next session.
 *
 * Copy is sourced from the founder's `special_ask` slot override
 * via the same `/api/me/special-ask` GET that returns the row.
 * Defaults ship with `[FOUNDER:]` placeholders that the founder MUST
 * replace via the R.5.b copy editor before going live — but per the
 * R.4 semantic divergence, the modal STILL surfaces with placeholders
 * so the user experience doesn't break for founder copy lag.
 */
import React, { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import useTrialStatus from "@/hooks/useTrialStatus";
import { X, Send, Loader2 } from "lucide-react";

const SESSION_DISMISS_KEY = "akki_special_ask_dismissed_at";

export default function SpecialAskModal() {
  const trial = useTrialStatus();
  const [open, setOpen] = useState(false);
  const [copy, setCopy] = useState({
    modal_heading: "Before you go — one ask.",
    modal_body:    "",
  });
  const [refName, setRefName] = useState("");
  const [refEmail, setRefEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [testimonial, setTestimonial] = useState("");
  const [busy, setBusy] = useState(false);

  // Open the modal when the day-14 trigger flag is up + we haven't
  // dismissed this session.
  useEffect(() => {
    if (!trial.refresh) return;  // hook not yet initialised
    const dismissed = (typeof window !== "undefined")
      ? window.sessionStorage.getItem(SESSION_DISMISS_KEY)
      : null;
    const shouldOpen = Boolean(
      // backend flag — only true when day >= 14 AND row.status === 'pending'
      trial.specialAskSurface && !dismissed,
    );
    if (shouldOpen && !open) {
      setOpen(true);
      // Load existing row + copy
      api.get("/me/special-ask")
        .then((res) => {
          const row = res?.data?.row || {};
          const c   = res?.data?.copy || {};
          if (c.modal_heading) setCopy({ modal_heading: c.modal_heading, modal_body: c.modal_body || "" });
          setRefName(row.referral_name || "");
          setRefEmail(row.referral_email || "");
          setConsent(Boolean(row.case_study_consent));
          setTestimonial(row.testimonial_text || "");
          // Emit surface-ack so the funnel records this surfacing.
          api.post("/me/special-ask/surface-ack").catch(() => {});
        })
        .catch(() => { /* keep defaults */ });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trial.specialAskSurface]);

  const canSave = refName.trim().length > 0 && refEmail.trim().length > 0;

  const handleSave = useCallback(async (e) => {
    e?.preventDefault();
    if (!canSave || busy) return;
    setBusy(true);
    try {
      const res = await api.post("/me/special-ask", {
        referral_name:      refName.trim(),
        referral_email:     refEmail.trim(),
        case_study_consent: consent,
        testimonial_text:   testimonial.trim() || null,
      });
      const status = res?.data?.status || "unknown";
      toast.success(status === "complete"
        ? "Thank you — we'll be in touch."
        : "Got it, thank you.");
      setOpen(false);
      // Mark session-dismissed so it doesn't immediately re-open.
      try { window.sessionStorage.setItem(SESSION_DISMISS_KEY, String(Date.now())); } catch (_) { /* noop */ }
      trial.refresh?.();
    } catch (err) {
      toast.error(apiErrorMessage(err) || "Couldn't save. Try again?");
    } finally {
      setBusy(false);
    }
  }, [canSave, busy, refName, refEmail, consent, testimonial, trial]);

  const handleRemindLater = useCallback(async () => {
    try {
      await api.post("/me/special-ask/dismiss");
    } catch (_) { /* fire-and-forget */ }
    try { window.sessionStorage.setItem(SESSION_DISMISS_KEY, String(Date.now())); } catch (_) { /* noop */ }
    setOpen(false);
  }, []);

  if (!open) return null;

  return (
    <div
      data-testid="special-ask-modal-overlay"
      role="dialog"
      aria-label="Founding cohort — special ask"
      aria-modal="true"
      className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4"
    >
      <div
        data-testid="special-ask-modal"
        className="bg-[var(--cream)] border border-[var(--line)] rounded-sm shadow-xl max-w-[520px] w-full max-h-[90vh] overflow-y-auto p-7"
      >
        <div className="flex items-start justify-between mb-2">
          <p className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)]">
            Founding cohort &middot; day {trial.day} of {trial.totalDays}
          </p>
          <button
            type="button"
            data-testid="special-ask-modal-close"
            onClick={handleRemindLater}
            aria-label="Close modal"
            className="text-[var(--muted)] hover:text-[var(--ink)] p-1 -mt-1 -mr-1"
          >
            <X className="w-4 h-4" aria-hidden />
          </button>
        </div>

        <h2 className="akki-serif text-[24px] leading-tight text-[var(--ink)] mb-3">
          {copy.modal_heading}
        </h2>
        <p
          data-testid="special-ask-modal-body"
          className="akki-serif italic text-[14px] leading-relaxed text-[var(--deep)] mb-5"
        >
          {copy.modal_body}
        </p>

        <form onSubmit={handleSave} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="sa-ref-name" className="text-[12px] font-medium text-[var(--deep)]">
              Referral name <span className="text-[#7A2F2F]">*</span>
            </label>
            <input
              id="sa-ref-name"
              type="text"
              data-testid="special-ask-referral-name"
              value={refName}
              onChange={(e) => setRefName(e.target.value)}
              maxLength={200}
              placeholder="A name you trust"
              className="border border-[var(--line)] rounded-sm px-3 py-2 text-[13px] text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="sa-ref-email" className="text-[12px] font-medium text-[var(--deep)]">
              Referral email <span className="text-[#7A2F2F]">*</span>
            </label>
            <input
              id="sa-ref-email"
              type="email"
              data-testid="special-ask-referral-email"
              value={refEmail}
              onChange={(e) => setRefEmail(e.target.value)}
              maxLength={200}
              placeholder="their work email"
              className="border border-[var(--line)] rounded-sm px-3 py-2 text-[13px] text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            />
          </div>

          <label className="flex items-start gap-2 mt-2 text-[12.5px] text-[var(--deep)] cursor-pointer">
            <input
              type="checkbox"
              data-testid="special-ask-case-study-consent"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-0.5"
            />
            <span>I&rsquo;m open to being part of a brief case study.</span>
          </label>

          <div className="flex flex-col gap-1.5 mt-1">
            <label htmlFor="sa-testimonial" className="text-[12px] font-medium text-[var(--deep)]">
              Testimonial <span className="text-[var(--muted)] font-normal">(optional)</span>
            </label>
            <textarea
              id="sa-testimonial"
              data-testid="special-ask-testimonial"
              value={testimonial}
              onChange={(e) => setTestimonial(e.target.value)}
              maxLength={4000}
              rows={3}
              placeholder="One sentence — feel free to leave blank."
              className="border border-[var(--line)] rounded-sm px-3 py-2 text-[13px] text-[var(--ink)] resize-none focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            />
          </div>

          <div className="flex items-center justify-between gap-3 mt-3">
            <button
              type="button"
              data-testid="special-ask-remind-later"
              onClick={handleRemindLater}
              className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline"
            >
              Remind me later
            </button>
            <button
              type="submit"
              data-testid="special-ask-submit"
              disabled={!canSave || busy}
              className="inline-flex items-center gap-2 px-4 py-2 text-[12.5px] font-medium rounded-sm bg-[var(--ink)] text-[var(--cream)] disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
            >
              {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
              {busy ? "Sending…" : "Send"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
