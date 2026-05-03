/*
 * Features page — the homepage's three-pillar structure (Solva, Cross-Board
 * Pulse, Work Studio) lives here, alongside the live sensitivity demo. Per
 * the homepage rules doc, three pillars are not homepage real estate at v1.
 */
import React from "react";
import MarketingShell from "@/components/marketing/MarketingShell";
import ThreePillars from "@/components/marketing/ThreePillars";
import EnterpriseFeature from "@/components/marketing/EnterpriseFeature";

export default function Features() {
  return (
    <MarketingShell>
      <section
        className="border-b border-[var(--rule)] bg-[var(--cream)]"
        data-testid="features-page"
      >
        <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-16 md:py-24">
          <p className="akki-overline mb-3 text-[var(--accent)]">Product</p>
          <h1
            className="akki-serif text-[40px] sm:text-[52px] leading-[1.08] tracking-[-0.018em] text-[var(--ink)] mb-7 font-normal max-w-[24ch]"
            data-testid="features-h1"
          >
            What AKKI is, in three pieces
          </h1>
          <p className="akki-serif text-[18px] leading-[1.7] text-[var(--deep)] max-w-[64ch]">
            AKKI organises around three working surfaces — Solva, Cross-Board
            Pulse, and the Work Studio for decks and reports. Each is editorially
            distinct. Together they are how AKKI fits into a board cycle.
          </p>
        </div>
      </section>

      {/* Three pillars (Solva / Pulse / Work Studio) */}
      <ThreePillars />

      {/* Enterprise feature — live sensitivity demo */}
      <EnterpriseFeature />
    </MarketingShell>
  );
}
