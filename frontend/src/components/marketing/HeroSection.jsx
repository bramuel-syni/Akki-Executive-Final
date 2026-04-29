/**
 * HeroSection — iter65 redesign per /app/design_guidelines.json.
 *
 * Tightens the value-promise to land within the first viewport. Replaces
 * the multi-bullet rubric with a single sub-head and a single dominant
 * navy CTA (Sandbox = primary conversion driver).
 *
 * Cream/oxblood palette preserved per user direction; navy `#0A1F44`
 * appears only on the primary CTA + the right-hand quote attribution.
 */
import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight, Quote } from "lucide-react";

const NAVY = "#0A1F44";

const HERO_QUOTE = {
  body:
    "I have been on five boards for a decade. AKKI is the first thing that reads a pack the way I would.",
  attribution: "Sitting NED · Kenya · financial services",
};

export default function HeroSection() {
  return (
    <section className="border-b border-[var(--rule)]" data-testid="landing-hero">
      <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28 grid md:grid-cols-12 gap-12 md:gap-16 items-start">
        <div className="md:col-span-8">
          <p className="akki-overline mb-8" data-testid="hero-overline">
            For seasoned and emerging executives and non-executive directors
          </p>
          <h1
            className="akki-serif text-[44px] sm:text-[60px] md:text-[76px] leading-[1.02] tracking-[-0.02em] text-[var(--ink)] font-normal mb-8"
            data-testid="hero-headline"
          >
            AKKI reads the pack
            <br />
            so you can <span className="text-[var(--accent)] italic">read the room.</span>
          </h1>
          <p
            className="akki-serif text-[19px] md:text-[22px] leading-[1.55] text-[var(--deep)] max-w-[44ch] mb-10"
            data-testid="hero-subhead"
          >
            The unified workspace for executives and directors who grow and
            preserve shareholder value — frameworks, mindsets, and tooling
            that pay off in the room.
          </p>

          <div className="flex flex-col items-start gap-5 max-w-md" data-testid="hero-cta">
            <Link to="/sandbox" className="group" data-testid="primary-sandbox-cta">
              <Button
                className="rounded-sm h-14 px-8 text-[15px] font-medium tracking-wide shadow-sm hover:opacity-90"
                style={{ backgroundColor: NAVY, color: "#F7F3EA" }}
              >
                Try AKKI in 60 seconds <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />
              </Button>
            </Link>
            <p className="text-[12.5px] text-[var(--muted)] -mt-2 leading-relaxed">
              Sandbox loaded with sample data for your sector. No signup. 14-day
              workspace, then it deletes itself.
            </p>

            <div className="flex items-center gap-5 pt-3 mt-1 border-t border-[var(--rule)] w-full">
              <Link to="/signin" className="text-[13px] text-[var(--deep)] hover:text-[var(--ink)] transition-colors" data-testid="hero-signin-btn">
                Sign in
              </Link>
              <span className="text-[var(--rule)]">·</span>
              <Link to="/signup" className="text-[13px] text-[var(--deep)] hover:text-[var(--ink)] transition-colors" data-testid="hero-signup-btn">
                Request a team workspace
              </Link>
            </div>
          </div>
        </div>

        {/* Right-hand pull quote — attribution in navy */}
        <aside className="md:col-span-4 md:pt-10 md:border-l md:border-[var(--rule)] md:pl-10">
          <Quote className="w-5 h-5 text-[var(--accent)] mb-4" strokeWidth={1.6} />
          <p
            className="akki-serif italic text-[18px] md:text-[20px] leading-[1.55] text-[var(--deep)] mb-5"
            data-testid="hero-quote"
          >
            "{HERO_QUOTE.body}"
          </p>
          <p
            className="text-[11px] uppercase tracking-[0.2em] font-medium"
            style={{ color: NAVY }}
            data-testid="hero-quote-attribution"
          >
            — {HERO_QUOTE.attribution}
          </p>

          <div
            className="mt-8 relative overflow-hidden rounded-sm border border-[var(--rule)]"
            data-testid="hero-photo"
          >
            <img
              src="https://images.unsplash.com/photo-1723002312141-027f132f62de?crop=entropy&cs=srgb&fm=jpg&q=85&w=900"
              alt="An empty boardroom with leather chairs and afternoon light"
              className="w-full h-[260px] object-cover"
              style={{ filter: "sepia(0.22) saturate(0.85) contrast(1.05)" }}
              loading="lazy"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-[var(--cream)]/30 via-transparent to-transparent pointer-events-none" />
          </div>
          <p className="text-[10.5px] uppercase tracking-[0.18em] text-[var(--muted)] mt-2 italic">
            The room you walk into.
          </p>
        </aside>
      </div>
    </section>
  );
}
