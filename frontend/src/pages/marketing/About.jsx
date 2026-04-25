import React from "react";
import { Link } from "react-router-dom";
import MarketingShell from "@/components/marketing/MarketingShell";
import { ArrowRight } from "lucide-react";

export default function About() {
  return (
    <MarketingShell>
      <section className="max-w-3xl mx-auto px-6 lg:px-10 py-20" data-testid="about-page">
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

        <div className="mt-14 pt-10 border-t border-[var(--rule)]">
          <Link to="/sandbox" className="inline-flex items-center gap-2 text-[15px] text-[var(--accent)] hover:underline" data-testid="about-sandbox-cta">
            See it work in 60 seconds <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>
    </MarketingShell>
  );
}
