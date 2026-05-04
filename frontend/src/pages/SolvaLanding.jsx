/**
 * SolvaLanding — public marketing landing page for AKKI Solva.
 *
 * Iter58 — first surface. Reachable at /solva from the main landing
 * page "How it works" CTA. Phase 13.1 renamed the product module from
 * "Solve" to "Solva"; the legacy `/solve` URL still routes here via a
 * `<Navigate to="/solva" replace />` alias in `App.js`. `data-testid`
 * attributes retain the `solve-` prefix for screenshot/test fixture
 * stability, identical to the rationale for keeping the `solve_`
 * collection names — internal identifiers, not user-facing copy.
 *
 * The actual Solva module (in-app, behind auth) is at /app/solva.
 */
import React from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import SolvaLandingHero from "@/components/solva/SolvaLanding";
import {
  ArrowRight, Sparkles, MessageCircle, Layers, ShieldCheck, GitBranch,
} from "lucide-react";

const PHASES = [
  {
    n: "01",
    title: "Surface",
    headline: "Name the problem the way a board chair would.",
    body:
      "Most board problems arrive tangled — half-symptom, half-strategy, half-politics. " +
      "Solva starts by asking you to state it in one sentence. Plain. Specific. The " +
      "kind of sentence that earns a follow-up question.",
  },
  {
    n: "02",
    title: "Depth",
    headline: "Pressure-test the framing.",
    body:
      "Solva walks the question, not at it. It asks the questions a sharp counterpart " +
      "would — challenging assumptions, surfacing what's missing, separating cause from " +
      "consequence. You leave depth knowing what you actually need to decide.",
  },
  {
    n: "03",
    title: "Synthesis",
    headline: "A diagnosis grounded in evidence.",
    body:
      "Solva triangulates against comparable diagnoses — across boards, sectors, and " +
      "scale — and writes the diagnosis you can hold up to scrutiny. No bullet stuffing. " +
      "No false confidence. Cited, calm, and short enough to read on a phone.",
  },
  {
    n: "04",
    title: "Lock-in",
    headline: "Decide what changes Monday.",
    body:
      "Three commitments: what you'll do, what you'll watch, and what you'll walk into the " +
      "next conversation with. Solva hands the synthesis back as a brief, a deck, or a " +
      "follow-up cycle for the executives who'll deliver it.",
  },
];

const VS_CHAT = [
  {
    icon: MessageCircle,
    chat: "A chat thread answers the question you ask.",
    solve: "AKKI Solva helps you find the question worth asking.",
  },
  {
    icon: Layers,
    chat: "Each turn stands alone. The thread can drift.",
    solve: "Four phases hold the line. You leave with a diagnosis, not a transcript.",
  },
  {
    icon: GitBranch,
    chat: "No memory of what comparable boards have done.",
    solve: "Triangulation against comparable diagnoses, sector-aware.",
  },
  {
    icon: ShieldCheck,
    chat: "Easy to keep typing. Easy to never decide.",
    solve: "A locked Monday-morning decision, on the record.",
  },
];

export default function SolvaLanding() {
  return (
    <div className="min-h-screen bg-[var(--cream)] text-[var(--ink)]" data-testid="solve-landing">
      {/* Header — shared MarketingNav */}
      <MarketingNav />

      {/* Phase 13.4 — wrap all sections in a <main> landmark so axe's
          region rule passes and the doc carries the required single
          <main>. */}
      <main>
        {/* Phase B.4 — Solva landing hero. The 4-tile picker + sample
            input mirrors the in-app surface so prospects see exactly
            the experience they'd get post-signin. Submit button is a
            sign-in CTA in marketing variant. */}
        <section className="border-b border-[var(--rule)] bg-[var(--warm-white)]" aria-label="Solva landing hero">
          <div className="max-w-[1280px] mx-auto">
            <SolvaLandingHero variant="marketing" />
          </div>
        </section>
        {/* Hero */}
        <section className="border-b border-[var(--rule)]" aria-labelledby="solva-hero-h1">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28 grid md:grid-cols-12 gap-10 items-end">
          <div className="md:col-span-8">
            <p className="akki-overline mb-6 text-[var(--accent)] flex items-center gap-1.5">
              <Sparkles className="w-3 h-3" /> Akki Solva · structured pause for board-grade problems
            </p>
            <h1 id="solva-hero-h1" className="akki-serif text-[44px] md:text-[64px] leading-[1.04] tracking-[-0.018em] font-normal text-[var(--ink)] max-w-[18ch]">
              For the board problems that don't have tidy answers.
            </h1>
            <p className="akki-serif text-[18px] md:text-[20px] leading-[1.65] text-[var(--deep)] mt-7 max-w-[58ch]">
              The cost of moving without a diagnosis is rarely on the dashboard. It shows up
              quietly — a CEO who can't be told the board is uncertain, a strategy refresh
              that lands six months late, a succession plan that becomes an emergency.
              Solva gives you the structured pause those decisions actually deserve.
            </p>
            <div className="flex flex-wrap gap-3 mt-9">
              <Link to="/signup?from=solva">
                <Button className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-12 px-7 text-[14px]" data-testid="solve-hero-cta">
                  Try Akki Solva <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
              <a href="#how" className="inline-flex items-center text-[14px] text-[var(--deep)] hover:text-[var(--accent)] underline-offset-4 hover:underline">
                See the framework →
              </a>
            </div>
          </div>
          <div className="md:col-span-4">
            <p className="akki-overline mb-3">Built for</p>
            <ul className="space-y-2 text-[14px] text-[var(--deep)]">
              <li>NEDs sitting on multiple boards.</li>
              <li>Audit and risk committee chairs.</li>
              <li>ExCos rebuilding strategy.</li>
              <li>Founders preparing for governance scrutiny.</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Four phases */}
      <section id="how" className="border-b border-[var(--rule)] bg-[var(--cream-deep)]/30">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20">
          <div className="max-w-[58ch] mb-14">
            <p className="akki-overline mb-3">The framework</p>
            <h2 className="akki-serif text-[32px] md:text-[44px] leading-[1.08] tracking-[-0.012em] font-normal">
              Four phases. One diagnosis. No drift.
            </h2>
          </div>
          <ol className="grid md:grid-cols-2 gap-x-12 gap-y-12">
            {PHASES.map((p) => (
              <li key={p.n} className="border-l border-[var(--rule)] pl-6" data-testid={`solve-phase-${p.n}`}>
                <p className="font-mono text-[10.5px] uppercase tracking-[0.22em] text-[var(--accent)] mb-2">
                  Phase {p.n}
                </p>
                <h3 className="akki-serif text-[22px] text-[var(--ink)] mb-2">{p.title}</h3>
                <p className="akki-serif text-[15.5px] leading-snug text-[var(--ink)] mb-3 max-w-[42ch]">
                  {p.headline}
                </p>
                <p className="text-[13.5px] leading-[1.75] text-[var(--deep)] max-w-[58ch]">
                  {p.body}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* vs Chat */}
      <section className="border-b border-[var(--rule)] bg-[var(--ink)] text-[var(--cream)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20">
          <div className="max-w-[60ch] mb-14">
            {/* Phase 13.4 — `text-[var(--accent)]` on navy ink lands at
                ≈ 4.4:1, fails AA small-text 4.5:1. Replaced with the
                lightened cream/85 used elsewhere in the dark band. */}
            <p className="akki-overline mb-3 text-[var(--cream)]/85">Why not just chat</p>
            <h2 className="akki-serif text-[32px] md:text-[44px] leading-[1.08] tracking-[-0.012em] font-normal">
              Chat is brilliant for clarity. Solva is built for decision.
            </h2>
          </div>
          <div className="grid md:grid-cols-2 gap-8" data-testid="solve-vs-chat">
            {VS_CHAT.map((row) => (
              <div key={row.solve} className="bg-[var(--cream)]/[0.05] border border-[var(--cream)]/15 rounded-sm p-6">
                {/* Icon stays accent — large enough (16px) and on dark
                    via aria-hidden gets a contrast pass at the
                    non-text-element 3:1 threshold. */}
                <row.icon className="w-4 h-4 text-[var(--accent)] mb-3" strokeWidth={1.7} aria-hidden="true" />
                <p className="text-[12.5px] uppercase tracking-[0.16em] text-[var(--cream)]/50 mb-1.5">A chat thread</p>
                <p className="text-[14.5px] text-[var(--cream)]/80 mb-4">{row.chat}</p>
                {/* Same Phase 13.4 contrast bump as the section overline. */}
                <p className="text-[12.5px] uppercase tracking-[0.16em] text-[var(--cream)]/85 mb-1.5">Akki Solva</p>
                <p className="text-[14.5px] text-[var(--cream)]">{row.solve}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-b border-[var(--rule)]">
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-28 text-center">
          <p className="akki-overline mb-6">Try it</p>
          <h2 className="akki-serif text-[36px] md:text-[56px] leading-[1.08] tracking-[-0.015em] font-normal mb-6 max-w-[28ch] mx-auto">
            Bring Solva a problem you've been carrying.
          </h2>
          <p className="akki-serif text-[17px] leading-[1.7] text-[var(--muted)] max-w-[56ch] mx-auto mb-10">
            One session is fifteen to thirty minutes. The diagnosis is yours to keep.
            We'll be in your inbox the moment a slot opens.
          </p>
          <div className="flex flex-wrap justify-center gap-4">
            <Link to="/signup?from=solva">
              <Button className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-12 px-7 text-[14px]" data-testid="solve-cta-final">
                Request access <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link to="/signin">
              <Button variant="outline" className="bg-transparent border-[var(--rule)] text-[var(--deep)] hover:bg-[var(--cream-deep)] rounded-sm h-12 px-7 text-[14px]">
                Sign in
              </Button>
            </Link>
          </div>
        </div>
      </section>
      </main>

      <MarketingFooter />
    </div>
  );
}
