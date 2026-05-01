/**
 * §3 “The sharpest use case” — Friday’s 280-page pack → Tuesday’s 2-page brief.
 * Two image+label+body columns, single text-link CTA below.
 */
import React from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

function Column({ src, alt, overline, overlineTone, body, testid }) {
  return (
    <article className="flex flex-col" data-testid={testid}>
      <div className="relative overflow-hidden rounded-sm border border-[var(--rule)] aspect-square">
        <img
          src={src}
          alt={alt}
          className="w-full h-full object-cover"
          style={{ filter: "sepia(0.18) saturate(0.85) contrast(1.04)" }}
          loading="lazy"
        />
      </div>
      <p
        className={`akki-overline mt-6 mb-3 ${overlineTone === "accent" ? "text-[var(--accent)]" : "text-[var(--muted)]"}`}
      >
        {overline}
      </p>
      <p className="akki-serif text-[16px] leading-[1.7] text-[var(--deep)] max-w-[52ch]">
        {body}
      </p>
    </article>
  );
}

export default function SharpestUseCase() {
  return (
    <section
      className="border-b border-[var(--rule)] bg-[var(--cream)]"
      data-testid="sharpest-use-case"
    >
      <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28">
        <p className="akki-overline mb-3">One weekend, one outcome</p>
        <h2 className="akki-serif text-[28px] md:text-[42px] leading-[1.1] tracking-[-0.015em] text-[var(--ink)] font-normal mb-14 max-w-[28ch]">
          The 280 pages you were sent. The two pages that matter.
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-10 md:gap-14">
          <Column
            src="/static/marketing/friday-pack.jpeg"
            alt="A thick board pack on a desk on Friday evening"
            overline="Friday, 5:47pm."
            overlineTone="muted"
            body="Seven committee papers. A KPI dashboard three cycles behind. A new-investment proposal buried in appendix four. A full minute-set from October. Board Tuesday morning."
            testid="sharpest-friday"
          />
          <Column
            src="/static/marketing/tuesday-brief.jpeg"
            alt="A two-page printed brief on a desk on Tuesday morning"
            overline="Tuesday, 07:15am."
            overlineTone="accent"
            body="Two pages. Three questions worth asking, each linked to the paragraph that raised them. The committee papers that confirm themselves sit in a footnote. The one that doesn't is the first bullet."
            testid="sharpest-tuesday"
          />
        </div>

        <div className="mt-14 text-center">
          <Link
            to="/sandbox"
            className="inline-flex items-center gap-1.5 text-[13.5px] text-[var(--accent)] hover:underline underline-offset-4"
            data-testid="sharpest-cta"
          >
            See it live in 60 seconds <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
