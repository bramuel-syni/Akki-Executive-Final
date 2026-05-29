/**
 * Solva v2 — Cover slide (Slice 2a, 2026-05-29).
 * Element 1 of 15. Method tag + title + prepared_for + method + inputs_range.
 */
import React from "react";
import SlideShell from "../SlideShell";


export default function CoverSlide({
  cover,
  slideNumber,
  totalSlides,
  contextName,
}) {
  if (!cover) return null;
  return (
    <SlideShell
      kind="cover"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      sectionTag="Cover"
    >
      <div className="flex flex-col h-full">
        {/* Method tag — canonical "SOLVE · SESSION OUTPUT · CONFIDENTIAL" */}
        <div
          className="font-mono text-[11px] uppercase tracking-[0.32em] text-[var(--ink)] mb-12"
          data-testid="solva-v2-cover-method-tag"
        >
          {cover.method_tag}
        </div>

        {/* Title — the session's framing one-liner */}
        <h1
          className="akki-serif text-[44px] leading-[1.15] text-[var(--ink)] mb-8 max-w-[760px]"
          data-testid="solva-v2-cover-title"
        >
          {cover.title}
        </h1>

        {/* Hairline */}
        <div className="w-24 h-px bg-[var(--rule)] mb-8" />

        {/* Prepared for + subject + method + inputs_range */}
        <dl className="grid grid-cols-[140px_1fr] gap-y-3 gap-x-6 text-[12.5px] mb-8 max-w-[640px]">
          <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] pt-0.5">
            Prepared for
          </dt>
          <dd className="text-[var(--ink)]" data-testid="solva-v2-cover-prepared-for">
            {cover.prepared_for}
          </dd>

          <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] pt-0.5">
            Subject
          </dt>
          <dd className="text-[var(--ink)]" data-testid="solva-v2-cover-subject">
            {cover.subject}
          </dd>

          <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] pt-0.5">
            Method
          </dt>
          <dd className="text-[var(--ink)]" data-testid="solva-v2-cover-method">
            {cover.method}
          </dd>

          <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] pt-0.5">
            Inputs
          </dt>
          <dd className="text-[var(--ink)]" data-testid="solva-v2-cover-inputs-range">
            {cover.inputs_range}
          </dd>

          <dt className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-[var(--muted)] pt-0.5">
            Date
          </dt>
          <dd className="text-[var(--ink)] font-mono" data-testid="solva-v2-cover-date">
            {cover.date_str}
          </dd>
        </dl>
      </div>
    </SlideShell>
  );
}
