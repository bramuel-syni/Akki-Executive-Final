/**
 * Phase R.5.b (2026-05-27) — Day-16 soft-warning banner.
 *
 * Renders a dismissable banner at the top of every authenticated
 * surface when `useTrialStatus().status === 'soft_warning'` (day 16-21).
 * Dismissable per-session via sessionStorage so it doesn't nag mid-task,
 * but re-appears on next page load until the user opts into early
 * access OR the trial ends.
 *
 * Copy is sourced from the founder-saved `day_16_banner` override
 * via the same `/api/me/copy/{slot}` endpoint the EarlyAccessOptIn
 * page uses. Defaults ship with [FOUNDER:] placeholders that the
 * founder MUST replace via the R.5.b editor before going live.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import useTrialStatus from "@/hooks/useTrialStatus";
import { AlertCircle, X } from "lucide-react";

const STORAGE_KEY = "akki_day16_banner_dismissed_at";
const DEFAULTS = {
  heading: "Your founding-cohort trial ends soon.",
  body:    "[FOUNDER: write one sentence in your voice — what they should do before the trial ends, link to early access, etc. Edit before shipping.]",
};

export default function Day16Banner() {
  const trial = useTrialStatus();
  const [copy, setCopy] = useState(DEFAULTS);
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return Boolean(window.sessionStorage.getItem(STORAGE_KEY));
  });

  // Fetch override copy whenever the banner could show.
  useEffect(() => {
    if (trial.status !== "soft_warning") return undefined;
    let cancelled = false;
    api.get("/me/copy/day_16_banner")
      .then((res) => {
        if (cancelled) return;
        const values = res?.data?.values || {};
        setCopy({
          heading: values.heading || DEFAULTS.heading,
          body:    values.body    || DEFAULTS.body,
        });
      })
      .catch(() => { /* keep defaults */ });
    return () => { cancelled = true; };
  }, [trial.status]);

  if (trial.status !== "soft_warning" || dismissed) return null;

  const handleDismiss = () => {
    setDismissed(true);
    try {
      window.sessionStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch (_) { /* sessionStorage may be unavailable */ }
  };

  return (
    <div
      data-testid="day-16-banner"
      role="status"
      aria-live="polite"
      className="w-full bg-[#FFF6E5] border-b border-[#E5C97A] px-5 py-3 flex items-start gap-3"
    >
      <AlertCircle className="w-4 h-4 text-[#A37500] mt-0.5 flex-shrink-0" aria-hidden />
      <div className="flex-1 min-w-0">
        <p
          data-testid="day-16-banner-heading"
          className="text-[13px] font-medium text-[var(--ink)]"
        >
          {copy.heading}{" "}
          <span className="font-mono text-[11.5px] text-[var(--muted)]">
            (day {trial.day} of {trial.totalDays})
          </span>
        </p>
        <p data-testid="day-16-banner-body" className="text-[12.5px] text-[var(--deep)] mt-0.5">
          {copy.body}
        </p>
        <Link
          to="/app/early-access-opt-in"
          data-testid="day-16-banner-cta"
          className="inline-block mt-1 text-[12px] font-medium text-[var(--ink)] underline hover:text-[var(--accent)]"
        >
          Request early access →
        </Link>
      </div>
      <button
        type="button"
        data-testid="day-16-banner-dismiss"
        onClick={handleDismiss}
        aria-label="Dismiss banner"
        className="text-[var(--muted)] hover:text-[var(--ink)] p-1 -mt-1 -mr-1 transition-colors"
      >
        <X className="w-4 h-4" aria-hidden />
      </button>
    </div>
  );
}
