/**
 * HeroSection — homepage repositioning v1.
 *
 * Hero is now warm-traffic-to-early-access. CTA hierarchy:
 *   1. Apply for early access  → /early-access     (oxblood button, primary)
 *   2. How AKKI thinks         → /about#methodology (text link, secondary)
 *   3. See it live in 60 seconds → /sandbox          (smaller, muted, tertiary)
 *
 * Trust strip lives below the CTAs, no scroll required.
 * Right-rail is image only — no quote, no attribution. Image is hosted
 * locally at /static/marketing/hero-executive.jpeg.
 */
import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export default function HeroSection() {
  return (
    <section className="border-b border-[var(--rule)]" data-testid="landing-hero">
      <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-16 md:py-24 grid md:grid-cols-12 gap-10 md:gap-16 items-start">
        <div className="md:col-span-7">
          <p className="akki-overline mb-7" data-testid="hero-overline">
            AKKI for the people who sit at the top table
          </p>
          <h1
            className="akki-serif text-[40px] sm:text-[54px] md:text-[68px] leading-[1.04] tracking-[-0.02em] text-[var(--ink)] font-normal mb-7"
            data-testid="hero-headline"
          >
            The pack arrives Friday.
            <br />
            Walk in Tuesday prepared.
          </h1>
          <p
            className="akki-serif text-[18px] md:text-[20px] leading-[1.6] text-[var(--deep)] max-w-[56ch] mb-9"
            data-testid="hero-subhead"
          >
            AKKI sits beside you, reading every page of the pack, and surfaces the three things a sharp advisor would flag — with citations to the source paragraphs.
          </p>

          <div className="flex flex-col items-start gap-4" data-testid="hero-cta">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
              <Link to="/early-access" data-testid="hero-primary-cta">
                <Button className="rounded-sm h-12 px-7 text-[14.5px] font-medium tracking-wide shadow-sm bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white">
                  Apply for early access <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
              <Link
                to="/about#methodology"
                className="text-[14px] text-[var(--ink)] hover:text-[var(--accent)] transition-colors inline-flex items-center gap-1.5"
                data-testid="hero-secondary-cta"
              >
                How AKKI thinks <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
            <Link
              to="/sandbox"
              className="text-[12.5px] text-[var(--muted)] hover:text-[var(--ink)] transition-colors inline-flex items-center gap-1.5"
              data-testid="hero-tertiary-cta"
            >
              See it live in 60 seconds <ArrowRight className="w-3 h-3" />
            </Link>
          </div>

          {/* Trust strip — single line, middle-dot separated, below CTAs */}
          <div
            className="mt-10 pt-6 border-t border-[var(--rule)] text-[12.5px] text-[var(--muted)] flex flex-wrap items-center gap-x-3 gap-y-2 leading-relaxed"
            data-testid="hero-trust-strip"
          >
            <span>Bank-grade audit trail</span>
            <span aria-hidden="true" className="text-[var(--muted)]">·</span>
            <span>SOC2-aligned architecture</span>
            <span aria-hidden="true" className="text-[var(--muted)]">·</span>
            <span>Built for listed-company governance</span>
          </div>
        </div>

        {/* Right-rail — image only, locally hosted, sepia/desaturated for editorial register */}
        {/* Phase 13.4 — was `<aside>`; axe's
            `landmark-complementary-is-top-level` rule wants <aside> at
            the top level of the document only. As a quotation panel
            beside the hero this is supplementary content, not
            complementary; <div> is the right semantic. */}
        <div className="md:col-span-5 md:pt-2" data-testid="hero-aside">
          <div
            className="relative overflow-hidden rounded-sm border border-[var(--rule)]"
            data-testid="hero-photo"
          >
            <img
              src="/static/marketing/hero-executive.jpeg"
              alt="An executive reading a board pack at a desk"
              className="w-full h-[360px] md:h-[420px] object-cover"
              style={{ filter: "sepia(0.18) saturate(0.85) contrast(1.04)" }}
              loading="eager"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[var(--cream)]/25 via-transparent to-transparent pointer-events-none" />
          </div>
        </div>
      </div>
    </section>
  );
}
