/**
 * Phase Y (2026-05-27) — First-login onboarding briefs modal.
 *
 * Renders a 6-slide deck on the first authenticated /app/* load per
 * account. Slides: Welcome → Surfaces → How to use → Tell us →
 * Data safety → Get started.
 *
 * Open condition: backend `/api/me/onboarding-briefs` returns
 * `shown_at: null`. The user can: (a) navigate Prev/Next through the
 * 6 slides, (b) Skip at any time, or (c) Get started on the final
 * slide. Both Skip and Get started POST `/api/me/onboarding-briefs/complete`
 * which stamps `onboarding_briefs_shown_at` so the modal never
 * re-surfaces.
 *
 * R.4 semantic-divergence rule: slide bodies are rendered as-is even
 * if they contain `[FOUNDER:` placeholders — UX is never broken.
 *
 * Visual: matches the Claude reference — serif title, sober body,
 * thin progress indicator at the top.
 */
import React, { useEffect, useState, useCallback } from "react";
import { ArrowLeft, ArrowRight, X } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

export default function OnboardingBriefsModal() {
  const { account } = useAuth();
  const [open, setOpen]     = useState(false);
  const [slides, setSlides] = useState([]);
  const [idx, setIdx]       = useState(0);
  const [closing, setClosing] = useState(false);

  // Load briefs once per session. If `shown_at` is null AND we have
  // slides, open the modal.
  useEffect(() => {
    if (!account?.id) return;
    let dead = false;
    (async () => {
      try {
        const { data } = await api.get("/me/onboarding-briefs");
        if (dead) return;
        if (!data?.shown_at && Array.isArray(data?.slides) && data.slides.length) {
          setSlides(data.slides);
          setOpen(true);
        }
      } catch { /* noop */ }
    })();
    return () => { dead = true; };
  }, [account?.id]);

  const finish = useCallback(async () => {
    if (closing) return;
    setClosing(true);
    try { await api.post("/me/onboarding-briefs/complete"); } catch { /* noop */ }
    setOpen(false);
    setClosing(false);
  }, [closing]);

  if (!open || slides.length === 0) return null;

  const slide   = slides[idx];
  const isFirst = idx === 0;
  const isLast  = idx === slides.length - 1;

  return (
    <div
      className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/40 backdrop-blur-sm px-4"
      data-testid="onboarding-briefs-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-briefs-title"
    >
      <div
        className="w-full max-w-xl bg-[var(--parchment)] border border-[var(--rule)] rounded-sm shadow-xl"
        data-testid="onboarding-briefs-modal"
      >
        {/* Progress indicator + close */}
        <div className="flex items-center justify-between px-6 pt-5 pb-3 border-b border-[var(--rule)]">
          <div className="flex items-center gap-1.5" data-testid="onboarding-briefs-progress">
            {slides.map((_, i) => (
              <span
                key={i}
                className={
                  "h-1 rounded-full transition-all " +
                  (i === idx
                    ? "w-6 bg-[var(--ink)]"
                    : i < idx
                      ? "w-4 bg-[var(--ink)]/40"
                      : "w-4 bg-[var(--rule)]")
                }
                aria-hidden="true"
              />
            ))}
          </div>
          <button
            type="button"
            onClick={finish}
            className="text-[var(--muted)] hover:text-[var(--ink)] transition-colors"
            data-testid="onboarding-briefs-skip"
            aria-label="Skip onboarding"
          >
            <X className="w-4 h-4" strokeWidth={1.7} />
          </button>
        </div>

        {/* Slide body */}
        <div className="px-8 py-10" data-testid={`onboarding-briefs-slide-${slide.id}`}>
          <h2
            id="onboarding-briefs-title"
            className="akki-serif text-[28px] text-[var(--ink)] mb-4 leading-tight"
            data-testid="onboarding-briefs-slide-title"
          >
            {slide.title}
          </h2>
          <p
            className="text-[14.5px] text-[var(--deep)] leading-relaxed whitespace-pre-line"
            data-testid="onboarding-briefs-slide-body"
          >
            {slide.body}
          </p>
        </div>

        {/* Footer nav */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-[var(--rule)] bg-[var(--cream-deep)]/30">
          <button
            type="button"
            onClick={() => setIdx((i) => Math.max(0, i - 1))}
            disabled={isFirst}
            className={
              "inline-flex items-center gap-1.5 text-[12.5px] px-3 py-1.5 rounded-sm transition-colors " +
              (isFirst
                ? "text-[var(--muted)]/40 cursor-not-allowed"
                : "text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)]")
            }
            data-testid="onboarding-briefs-prev"
          >
            <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.7} /> Back
          </button>

          <span className="text-[11.5px] text-[var(--muted)] font-mono" data-testid="onboarding-briefs-step">
            {idx + 1} of {slides.length}
          </span>

          {isLast ? (
            <button
              type="button"
              onClick={finish}
              className="inline-flex items-center gap-1.5 text-[12.5px] px-4 py-1.5 rounded-sm bg-[var(--ink)] text-[var(--parchment)] hover:bg-[var(--ink)]/90 transition-colors"
              data-testid="onboarding-briefs-get-started"
            >
              Get started <ArrowRight className="w-3.5 h-3.5" strokeWidth={1.7} />
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setIdx((i) => Math.min(slides.length - 1, i + 1))}
              className="inline-flex items-center gap-1.5 text-[12.5px] px-3 py-1.5 rounded-sm bg-[var(--ink)] text-[var(--parchment)] hover:bg-[var(--ink)]/90 transition-colors"
              data-testid="onboarding-briefs-next"
            >
              Next <ArrowRight className="w-3.5 h-3.5" strokeWidth={1.7} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
