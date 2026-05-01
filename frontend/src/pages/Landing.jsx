/*
 * Homepage repositioning v1 — see /docs/homepage-positioning-v1.md
 *
 * Rejected hero headline candidates (kept for recoverability):
 *   — "Your next board meeting starts before you open the pack." (literal register)
 *   — "280 pages on Friday. Three questions on Tuesday." (sharp register)
 *
 * Selected: "The pack arrives Friday. Walk in Tuesday prepared." (editorial)
 *
 * Section order is the v1 contract:
 *   §1 Hero · §2 60-second proof · §3 Sharpest use case · §4 Trust
 *   §5 Voice · (no §6 — price dropped at v1) · §7 Closing CTA
 */
import React from "react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";
import HeroSection from "@/components/marketing/HeroSection";
import SixtySecondProof from "@/components/marketing/SixtySecondProof";
import SharpestUseCase from "@/components/marketing/SharpestUseCase";
import Exco360Voice from "@/components/marketing/Exco360Voice";
import ClosingCTA from "@/components/marketing/ClosingCTA";
import { Check } from "lucide-react";

const TRUST_ITEMS = [
  {
    h: "Every claim, cited",
    b: "Every line AKKI writes is traceable to a source paragraph. Hover to see where it came from. Click to open the document at that page.",
  },
  {
    h: "Receipts, not whispers",
    b: "Every AI exchange is logged, hash-chained, and exportable as a verifiable ZIP. Your interactions are receipts, reviewable by internal audit.",
  },
  {
    h: "Classified before it leaves your screen",
    b: "AKKI classifies every artefact — public, internal, confidential, or restricted — and enforces that classification on share. Nothing leaves your board without a label.",
  },
];

export default function Landing() {
  return (
    <div
      className="min-h-screen bg-[var(--cream)] text-[var(--ink)] flex flex-col"
      data-testid="landing-page"
    >
      {/* Shared masthead */}
      <MarketingNav />

      {/* §1 Hero */}
      <HeroSection />

      {/* §2 60-second proof */}
      <SixtySecondProof />

      {/* §3 Sharpest use case */}
      <SharpestUseCase />

      {/* §4 Trust — reused 3-up layout, replaced copy */}
      <section
        className="border-b border-[var(--rule)] bg-[var(--cream)]"
        data-testid="trust-section"
      >
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-16 md:py-24">
          <p className="akki-overline mb-3">The conditions of trust</p>
          <h2 className="akki-serif text-[28px] md:text-[40px] leading-[1.1] tracking-[-0.015em] text-[var(--ink)] font-normal mb-12 max-w-[24ch]">
            What listed-company governance requires
          </h2>
          <div className="grid md:grid-cols-3 gap-8 md:gap-0 md:divide-x divide-[var(--rule)]">
            {TRUST_ITEMS.map((item, i) => (
              <div
                key={item.h}
                className="md:px-8 first:md:pl-0 last:md:pr-0"
                data-testid={`trust-strip-${i}`}
              >
                <Check
                  className="w-4 h-4 text-[var(--accent)] mb-3"
                  strokeWidth={2.2}
                />
                <p className="akki-serif text-[19px] leading-snug text-[var(--ink)] mb-2 max-w-[28ch]">
                  {item.h}
                </p>
                <p className="text-[13.5px] text-[var(--deep)] leading-[1.7]">
                  {item.b}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* §5 Voice */}
      <Exco360Voice />

      {/* §7 Closing CTA (no §6) */}
      <ClosingCTA />

      {/* Shared footer */}
      <MarketingFooter />
    </div>
  );
}
