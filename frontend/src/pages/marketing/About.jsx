import React from "react";
import { Link } from "react-router-dom";
import MarketingShell from "@/components/marketing/MarketingShell";
import { ArrowRight } from "lucide-react";

const PHASES = [
  {
    name: "Surface",
    body:
      "AKKI starts where you start: with the document in front of you. It reads every page, lifts the claims that matter, and shows you what an experienced advisor would notice on a first pass.",
  },
  {
    name: "Depth",
    body:
      "Then it goes deeper. AKKI compares the new pack to your previous packs, last quarter's minutes, and the strategic goals you've already declared. The patterns it finds are cited back to the paragraphs that raised them.",
  },
  {
    name: "Synthesis",
    body:
      "AKKI composes — a brief, a question, a deck outline, a draft email. Composition uses Claude Opus on Pro plans and Sonnet otherwise. Every composition cites its sources and is checked by a second model before it shows up on your screen.",
  },
  {
    name: "Lock-in",
    body:
      "Nothing AKKI produces is binding until you say so. Drafts wait in your daily review. Approve, edit, or reject. Approvals are signed, hash-chained, and reversible.",
  },
];

const AUDIENCE_CARDS = [
  {
    chip: "For Non-Executive Directors",
    h: "Sitting on five boards at once.",
    body:
      "Each board gets its own sealed context. The Audit pack you read at 7am can't bleed into the Risk pack at 10am. Each pack arrives pre-read with the three things to raise in the room.",
    testid: "audience-ned",
  },
  {
    chip: "For Operating Executives",
    h: "Running the quarter.",
    body:
      "Bring in your management committee. Tag signals by sub-committee. Run scenarios. The Ask panel is a colleague who has read everything and cites the paragraph when you ask.",
    testid: "audience-exec",
  },
];

export default function About() {
  return (
    <MarketingShell>
      <section
        className="max-w-3xl mx-auto px-6 lg:px-10 py-20"
        data-testid="about-page"
      >
        <p className="akki-overline mb-3 text-[var(--accent)]">About AKKI</p>
        <h1 className="akki-serif text-[44px] sm:text-[56px] leading-[1.05] tracking-tight text-[var(--ink)] mb-6 font-normal">
          Built for the colleague the boardroom doesn't have time to be.
        </h1>
        <p className="akki-serif text-[19px] leading-relaxed text-[var(--deep)] mb-10 italic">
          Non-executive directors and operating executives carry a discipline most of the world doesn't see — read the pack, ask the right question, hold management to account, and move on. AKKI is the colleague who reads with them.
        </p>

        <div className="space-y-8 akki-serif text-[16.5px] leading-[1.75] text-[var(--deep)]">
          <p>
            Our founders sat on too many boards where the most useful person in the room was the one who'd read the pack twice and could remember what was said the last six meetings. That person was rarely the one who needed to be asked.
          </p>
          <p>
            AKKI was built to be that colleague — a third party who reads everything, remembers what's been asked, and prepares the executive without taking the floor. It does not replace judgement. It removes the secretarial work that gets in the way of judgement.
          </p>
          <h2 className="akki-serif text-[24px] text-[var(--ink)] font-normal mt-10 mb-3">What we believe</h2>
          <ul className="space-y-4 list-none pl-0">
            <li><strong className="text-[var(--ink)]">Context first, not tenant.</strong> The unit of work is a board, a committee, or an executive's brief. Not a company tenant.</li>
            <li><strong className="text-[var(--ink)]">Receipts before opinions.</strong> Every signal AKKI surfaces cites the page it came from. No exceptions.</li>
            <li><strong className="text-[var(--ink)]">Identity stays identified to you.</strong> Names, emails, and identifiers are masked before any LLM call. Only the executive sees the unmasked output.</li>
            <li><strong className="text-[var(--ink)]">AKKI drafts; the executive decides.</strong> When AKKI sends a question to a reportee, the executive reviewed and approved it first.</li>
          </ul>
          <h2 className="akki-serif text-[24px] text-[var(--ink)] font-normal mt-10 mb-3">Where we operate</h2>
          <p>
            AKKI's signal generation, regulator references, and editorial voice adapt to your jurisdiction. CBK and CMA in Kenya. FCA and PRA in the UK. SEC and OCC in the US. SARB in South Africa. CBN in Nigeria. MAS in Singapore. EBA and ECB in the EU. The board's questions don't change. The regulators do.
          </p>
        </div>
      </section>

      {/* Who AKKI is for — audience cards relocated from homepage */}
      <section
        className="border-t border-[var(--rule)] bg-[var(--cream-deep)]/30"
        data-testid="about-audience"
      >
        <div className="max-w-[1100px] mx-auto px-6 lg:px-10 py-16 md:py-20">
          <p className="akki-overline mb-3">Who AKKI is for</p>
          <h2 className="akki-serif text-[28px] md:text-[40px] leading-[1.1] tracking-[-0.015em] text-[var(--ink)] font-normal mb-10 max-w-[28ch]">
            Built for the rooms where capital decisions are made.
          </h2>
          <div className="grid md:grid-cols-2 gap-6">
            {AUDIENCE_CARDS.map((c) => (
              <article
                key={c.testid}
                className="bg-white border border-[var(--rule)] rounded-sm p-8 md:p-10 flex flex-col"
                data-testid={c.testid}
              >
                <p className="akki-overline mb-4 text-[var(--accent)]">{c.chip}</p>
                <h3 className="akki-serif text-[22px] md:text-[26px] leading-[1.18] text-[var(--ink)] font-normal mb-4 max-w-[28ch]">
                  {c.h}
                </h3>
                <p className="akki-serif text-[15.5px] leading-[1.7] text-[var(--deep)] max-w-[50ch]">
                  {c.body}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Methodology — #methodology anchor target for hero CTA */}
      <section
        id="methodology"
        className="border-t border-[var(--rule)] bg-[var(--cream)] scroll-mt-20"
        data-testid="about-methodology"
      >
        <div className="max-w-[1100px] mx-auto px-6 lg:px-10 py-20 md:py-24">
          <p className="akki-overline mb-3">How AKKI thinks</p>
          <h2 className="akki-serif text-[28px] md:text-[40px] leading-[1.1] tracking-[-0.015em] text-[var(--ink)] font-normal mb-12 max-w-[28ch]">
            Surface, Depth, Synthesis, Lock-in.
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-10">
            {PHASES.map((p, i) => (
              <div key={p.name} className="flex flex-col" data-testid={`methodology-${p.name.toLowerCase()}`}>
                <p className="akki-overline mb-2 text-[var(--muted)]">
                  {String(i + 1).padStart(2, "0")} · {p.name}
                </p>
                <p className="akki-serif text-[16px] leading-[1.7] text-[var(--deep)] max-w-[60ch]">
                  {p.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="max-w-3xl mx-auto px-6 lg:px-10 py-14">
        <div className="pt-10 border-t border-[var(--rule)]">
          <Link
            to="/sandbox"
            className="inline-flex items-center gap-2 text-[15px] text-[var(--accent)] hover:underline"
            data-testid="about-sandbox-cta"
          >
            See it work in 60 seconds <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>
    </MarketingShell>
  );
}
