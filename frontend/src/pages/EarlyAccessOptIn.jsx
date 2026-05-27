/**
 * Phase R.5.a (2026-05-27) — Early-access opt-in page.
 *
 * The ONLY route a hard-locked user (`trial_status === "expired_hard_lock"`)
 * can navigate to inside `/app/*`. All other Gated routes redirect here
 * via `<HardLockGuard>` in App.js.
 *
 * Contract:
 *   - Read trial day via `useTrialStatus` (shows "Trial ended on day {day}").
 *   - Single textarea + CTA.
 *   - POST to `/api/me/early-access-opt-in`. Idempotent — second submission
 *     updates `note` + `updated_at`.
 *   - Founder-fillable copy: header tagline + sign-off carry `[FOUNDER:]`
 *     placeholders. R.5.b in-app editor will let founders edit live.
 *   - Server-side guard does NOT fire here (R.5.a deliberately leaves the
 *     page renderable with placeholders so locked users see *something*
 *     and not a 500). R.5.b adds the founder copy editor — until then,
 *     the placeholders show as a literal nudge to the founder.
 */
import React, { useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";
import { toast } from "sonner";
import useTrialStatus from "@/hooks/useTrialStatus";
import { Loader2, CheckCircle2 } from "lucide-react";

export default function EarlyAccessOptIn() {
  const trial = useTrialStatus();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const res = await api.post("/me/early-access-opt-in", { note: note || null });
      if (res?.data?.ok) {
        setSubmitted(true);
        toast.success("We've noted it — we'll be in touch.");
      }
    } catch (err) {
      toast.error(apiErrorMessage(err) || "Couldn't send. Try again?");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-testid="early-access-opt-in-page"
      className="min-h-screen bg-[var(--cream)] flex items-center justify-center px-4 py-12"
    >
      <div className="max-w-xl w-full">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-4">
          Founding cohort · trial complete
        </p>

        <h1
          data-testid="early-access-opt-in-heading"
          className="akki-serif text-[36px] leading-[1.1] tracking-tight text-[var(--ink)] mb-6"
        >
          Your founding-cohort trial has ended.
        </h1>

        <p className="akki-serif italic text-[16.5px] leading-relaxed text-[var(--deep)] mb-3">
          [FOUNDER: write one short paragraph in your voice explaining
          what early-access means + what happens next. The user is
          locked out of the app until you convert them. Edit before
          shipping to real users.]
        </p>

        {trial.day != null && (
          <p
            data-testid="early-access-opt-in-day-counter"
            className="text-[13.5px] text-[var(--muted)] mb-8"
          >
            Trial ended on day {trial.day} of {trial.totalDays}.
          </p>
        )}

        {submitted ? (
          <div
            data-testid="early-access-opt-in-thanks"
            className="border border-[var(--line)] bg-white px-6 py-5 rounded-sm flex items-start gap-3"
          >
            <CheckCircle2 className="w-5 h-5 text-[var(--accent)] mt-0.5 flex-shrink-0" aria-hidden />
            <div>
              <p className="text-[14px] text-[var(--ink)] font-medium mb-1">
                We&rsquo;ve noted it.
              </p>
              <p className="text-[13px] text-[var(--muted)]">
                [FOUNDER: write one sentence — what happens next in your voice.]
              </p>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <label className="text-[12.5px] text-[var(--deep)]" htmlFor="early-access-note">
              Anything you&rsquo;d like us to know? (optional)
            </label>
            <textarea
              id="early-access-note"
              data-testid="early-access-opt-in-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={1000}
              rows={4}
              placeholder="A thought, a question, or a context cue…"
              className="w-full text-[14px] text-[var(--ink)] border border-[var(--line)] rounded-sm p-3 resize-none focus:outline-none focus:ring-1 focus:ring-[var(--accent)] focus:border-[var(--accent)]"
            />
            <div className="flex items-center justify-between pt-2">
              <span className="text-[10.5px] text-[var(--muted)]">{note.length}/1000</span>
              <button
                type="submit"
                data-testid="early-access-opt-in-submit"
                disabled={busy}
                className="inline-flex items-center gap-2 px-5 py-2.5 text-[13px] font-medium rounded-sm bg-[var(--ink)] text-[var(--cream)] disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition-opacity focus:outline-none focus:ring-2 focus:ring-[var(--accent)] focus:ring-offset-2"
              >
                {busy && <Loader2 className="w-4 h-4 animate-spin" aria-hidden />}
                <span>{busy ? "Sending…" : "Request early access"}</span>
              </button>
            </div>
          </form>
        )}

        <p className="akki-serif italic text-[12.5px] text-[var(--muted)] mt-12">
          [FOUNDER: sign-off line in your voice — one line, your name. Edit before shipping.]
        </p>
      </div>
    </div>
  );
}
