/**
 * §7 Closing CTA — full-bleed band with a low-opacity backdrop image and
 * a single primary button matching the hero CTA copy.
 */
import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export default function ClosingCTA() {
  return (
    <section
      className="relative isolate border-b border-[var(--rule)]"
      data-testid="closing-cta"
    >
      <img
        src="/static/marketing/closing-still.jpeg"
        alt=""
        aria-hidden="true"
        className="absolute inset-0 w-full h-full object-cover -z-10"
        style={{ filter: "sepia(0.18) saturate(0.8) contrast(1.05)" }}
        loading="lazy"
      />
      <div className="absolute inset-0 bg-[var(--cream)]/85 -z-10" aria-hidden="true" />

      <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-24 md:py-32 text-center">
        <h2 className="akki-serif text-[36px] md:text-[56px] leading-[1.08] tracking-[-0.015em] text-[var(--ink)] font-normal mb-10 max-w-[24ch] mx-auto">
          One pack. Sixty seconds. Yours.
        </h2>
        <div className="flex flex-col items-center gap-4">
          <Link to="/early-access" data-testid="closing-primary-cta">
            <Button className="rounded-sm h-12 px-7 text-[14.5px] font-medium tracking-wide shadow-sm bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white">
              Apply for early access <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Link>
          <Link
            to="/sandbox"
            className="text-[12.5px] text-[var(--muted)] hover:text-[var(--ink)] transition-colors inline-flex items-center gap-1.5"
            data-testid="closing-tertiary-cta"
          >
            See it live in 60 seconds <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>
    </section>
  );
}
