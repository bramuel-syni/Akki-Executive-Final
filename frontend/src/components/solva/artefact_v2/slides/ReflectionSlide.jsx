/**
 * Solva v2 — Reflection slide (Slice 2b, 2026-05-29).
 * Element 8 of 15. Layer 5 — exactly 3 reflection questions with the
 * user's verbatim response and the engine's diagnostic interpretation.
 */
import React from "react";
import SlideShell from "../SlideShell";


export default function ReflectionSlide({
  reflection,
  slideNumber,
  totalSlides,
  contextName,
  slideState,
}) {
  if (!reflection) return null;
  const questions = reflection.questions || [];

  return (
    <SlideShell
      kind="reflection"
      number={slideNumber}
      total={totalSlides}
      contextName={contextName}
      slideState={slideState}
      sectionTag="Reflection"
    >
      <div className="flex flex-col">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--muted)] mb-3">
          Layer 5 — Reflection
        </p>
        <h2
          className="akki-serif text-[28px] leading-tight text-[var(--ink)] mb-3 max-w-[680px]"
          data-testid="solva-v2-reflection-title"
        >
          {reflection.title}
        </h2>
        <p className="text-[13px] text-[var(--deep)] leading-relaxed mb-6 max-w-[680px]">
          {reflection.intro_copy}
        </p>

        <ol
          className="space-y-6"
          data-testid="solva-v2-reflection-questions"
        >
          {questions.map((q, idx) => (
            <li
              key={idx}
              className="grid grid-cols-[40px_1fr] gap-x-4"
              data-solva-v2-reflection-question={idx + 1}
              data-testid={`solva-v2-reflection-q-${idx + 1}`}
            >
              <span className="akki-serif text-[24px] leading-none text-[var(--ned-purple)]">
                {String(idx + 1).padStart(2, "0")}
              </span>
              <div>
                <p className="text-[14px] text-[var(--ink)] font-medium leading-snug mb-2">
                  {q.question_text}
                </p>
                {q.user_verbatim_response && (
                  <blockquote
                    className="border-l-2 border-ned-purple/40 pl-3 text-[12.5px] italic text-[var(--deep)] leading-relaxed mb-2"
                    data-testid={`solva-v2-reflection-response-${idx + 1}`}
                  >
                    “{q.user_verbatim_response}”
                  </blockquote>
                )}
                <p
                  className="text-[12.5px] leading-relaxed text-[var(--deep)]"
                  data-testid={`solva-v2-reflection-interp-${idx + 1}`}
                >
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--muted)] mr-1.5">
                    Interpretation ·
                  </span>
                  {q.diagnostic_interpretation}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </SlideShell>
  );
}
