/**
 * ThreePillars — Solve as the dominant feature card, Cross Board Pulse as
 * the secondary. Decks + Reports lives in its own full-width navy band
 * (EnterpriseFeature) below.
 *
 * iter65 design brief: bento-style asymmetric grid. Direct the eye to Solve.
 * Pulse uses the library/books image. Solve uses the desk/ledgers image.
 */
import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Sparkles, ArrowRight, Layers, GitBranch,
} from "lucide-react";

export default function ThreePillars() {
  return (
    <section
      className="border-b border-[var(--rule)] bg-[var(--cream)]"
      data-testid="landing-three-pillars"
    >
      <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28">
        <div className="mb-12 max-w-[44ch]">
          <p className="akki-overline mb-4">Three things AKKI does — without overlap</p>
          <h2 className="akki-serif text-[34px] md:text-[44px] leading-[1.08] tracking-[-0.015em] text-[var(--ink)] font-normal">
            For the board problems no chatbot can answer.
          </h2>
        </div>

        <div className="grid md:grid-cols-12 gap-5 md:gap-6">
          {/* SOLVE — dominant card */}
          <article
            className="md:col-span-8 bg-[var(--ink)] text-[var(--cream)] rounded-sm overflow-hidden flex flex-col"
            data-testid="pillar-solve"
          >
            <div className="relative h-[200px] md:h-[260px] overflow-hidden border-b border-black/40">
              <img
                src="https://images.unsplash.com/photo-1643970118347-e11ad4d48a51?crop=entropy&cs=srgb&fm=jpg&q=85&w=1200"
                alt="Old leather-bound books on a library shelf"
                className="w-full h-full object-cover"
                style={{ filter: "sepia(0.25) saturate(0.85) contrast(1.05) brightness(0.6)" }}
                loading="lazy"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-[var(--ink)] via-[var(--ink)]/60 to-transparent" />
              <div className="absolute bottom-5 left-7 right-7">
                <p className="akki-overline mb-2 text-[var(--accent)] flex items-center gap-1.5">
                  <Sparkles className="w-3 h-3" /> Akki Solve · the strongest feature
                </p>
                <h3 className="akki-serif text-[26px] md:text-[34px] leading-[1.08] tracking-[-0.01em] max-w-[24ch]">
                  Diagnose board-grade problems in one structured pause.
                </h3>
              </div>
            </div>
            <div className="p-7 md:p-9 flex-1 flex flex-col">
              <ol className="space-y-3 mb-7 max-w-[58ch]" data-testid="pillar-solve-stages">
                {[
                  ["Surface", "Name the problem the way a chair would. One sentence."],
                  ["Depth",   "Pressure-test the framing. Akki asks the questions a sharp counterpart would."],
                  ["Synthesis","A diagnosis grounded in 27 anonymised comparable diagnoses across boards and sectors."],
                  ["Lock-in", "Decide what you'll do, what you'll watch, and what you'll walk in with."],
                ].map(([t, b], i) => (
                  <li key={t} className="flex gap-4 items-start">
                    <span className="font-mono text-[10.5px] uppercase tracking-[0.2em] text-[var(--accent)] mt-1.5 min-w-[24px]">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <p className="akki-serif text-[15.5px] text-[var(--cream)]">{t}</p>
                      <p className="text-[12.5px] text-[var(--cream)]/70 leading-relaxed mt-0.5">{b}</p>
                    </div>
                  </li>
                ))}
              </ol>
              <div className="flex flex-wrap gap-3 pt-2 border-t border-[var(--cream)]/15">
                <Link to="/signup?from=solve">
                  <Button
                    className="rounded-sm h-11 px-6 text-[13.5px] tracking-wide bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white"
                    data-testid="solve-session-start"
                  >
                    Start a Solve session <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                </Link>
                <Link to="/solve">
                  <Button
                    variant="outline"
                    className="rounded-sm h-11 px-6 text-[13.5px] bg-transparent hover:bg-[var(--cream)]/10 border-[var(--cream)]/30 text-[var(--cream)]"
                    data-testid="solve-learn-more"
                  >
                    How it works
                  </Button>
                </Link>
              </div>
            </div>
          </article>

          {/* CROSS BOARD PULSE — sidebar card */}
          <article
            className="md:col-span-4 bg-[var(--cream-deep)] rounded-sm overflow-hidden flex flex-col"
            data-testid="pillar-pulse"
          >
            <div className="relative h-[160px] md:h-[180px] overflow-hidden border-b border-[var(--rule)]">
              <img
                src="https://images.unsplash.com/photo-1481627834876-b7833e8f5570?w=900&q=80&auto=format&fit=crop"
                alt="A vast library with books from floor to ceiling"
                className="w-full h-full object-cover"
                style={{ filter: "sepia(0.22) saturate(0.85) contrast(1.05)" }}
                loading="lazy"
              />
            </div>
            <div className="p-6 md:p-7 flex-1 flex flex-col">
              <p className="akki-overline mb-2 text-[var(--accent)] flex items-center gap-1.5">
                <GitBranch className="w-3 h-3" /> Cross Board Pulse
              </p>
              <h3 className="akki-serif text-[22px] md:text-[24px] leading-[1.15] tracking-[-0.01em] text-[var(--ink)] mb-3 max-w-[22ch]">
                For the director sitting on five boards at once.
              </h3>
              <p className="text-[13.5px] leading-relaxed text-[var(--deep)] mb-5 max-w-[36ch]">
                Aggregate signals, themes and risk patterns across every
                board you serve. Catch the systemic risk before any
                individual audit chair does.
              </p>
              <ul className="space-y-2 text-[12.5px] text-[var(--deep)] mb-6 mt-auto" data-testid="pillar-pulse-bullets">
                <li className="flex gap-2"><span className="text-[var(--accent)]">·</span><span>NEDs serving multiple boards</span></li>
                <li className="flex gap-2"><span className="text-[var(--accent)]">·</span><span>Pattern-match across sealed contexts</span></li>
                <li className="flex gap-2"><span className="text-[var(--accent)]">·</span><span>Catch systemic risks early</span></li>
              </ul>
              <Link to="/features#pulse" className="inline-flex items-center gap-1.5 text-[12px] uppercase tracking-[0.16em] text-[var(--accent)] hover:underline" data-testid="pillar-pulse-link">
                See how Pulse works <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </article>

          {/* DECKS + REPORTS preview card — slim full-width below */}
          <article
            className="md:col-span-12 bg-white border border-[var(--rule)] rounded-sm p-6 md:p-7 flex items-center gap-6 flex-wrap"
            data-testid="pillar-decks-preview"
          >
            <div className="shrink-0 w-12 h-12 bg-[var(--cream-deep)] rounded-sm flex items-center justify-center">
              <Layers className="w-5 h-5 text-[var(--accent)]" />
            </div>
            <div className="flex-1 min-w-[260px] max-w-[58ch]">
              <p className="akki-overline mb-1.5 text-[var(--accent)]">
                And the third — Decks + Reports Studio
              </p>
              <p className="akki-serif text-[18px] md:text-[20px] leading-[1.35] text-[var(--ink)]">
                Produce board-grade material with your own data — auto-classified,
                read-tracked, exposure-scored. Try it below.
              </p>
            </div>
            <a
              href="#enterprise"
              className="text-[12.5px] uppercase tracking-[0.16em] text-[var(--accent)] hover:underline shrink-0"
              data-testid="pillar-decks-jump"
            >
              See it ↓
            </a>
          </article>
        </div>
      </div>
    </section>
  );
}
