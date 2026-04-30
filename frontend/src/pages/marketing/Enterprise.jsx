/**
 * Public marketing page for /enterprise. Distinct from the protected
 * /app/enterprise interest form (pages/Enterprise.jsx) — that one stays
 * untouched. This page does not wire to the existing interest endpoint.
 */
import React from "react";
import MarketingShell from "@/components/marketing/MarketingShell";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export default function Enterprise() {
  return (
    <MarketingShell>
      <section
        className="max-w-[820px] mx-auto px-6 lg:px-10 py-20 md:py-28"
        data-testid="enterprise-page"
      >
        <p className="akki-overline mb-3 text-[var(--accent)]">Enterprise</p>
        <h1 className="akki-serif text-[36px] sm:text-[48px] leading-[1.1] tracking-tight text-[var(--ink)] mb-8 font-normal max-w-[26ch]">
          AKKI for FTSE-listed corporate development and company secretaries
        </h1>
        <p className="akki-serif text-[18px] leading-[1.7] text-[var(--deep)] mb-10 max-w-[60ch]">
          For corporate development teams and company secretaries operating at
          FTSE-listed scale, with the governance and procurement requirements
          that come with it.
        </p>
        <ul
          className="space-y-3 mb-12 text-[15px] text-[var(--deep)] max-w-[52ch]"
          data-testid="enterprise-bullets"
        >
          <li className="flex gap-3">
            <span className="text-[var(--accent)] shrink-0">·</span>
            <span>SSO via your existing identity provider.</span>
          </li>
          <li className="flex gap-3">
            <span className="text-[var(--accent)] shrink-0">·</span>
            <span>Dedicated environment with regional data residency.</span>
          </li>
          <li className="flex gap-3">
            <span className="text-[var(--accent)] shrink-0">·</span>
            <span>Custom DPA, audit rights, and security review on request.</span>
          </li>
        </ul>
        <a href="mailto:enterprise@akki.ai" className="inline-block" data-testid="enterprise-cta">
          <Button className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-12 px-7 text-[14px] font-medium">
            Contact the team <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </a>
      </section>
    </MarketingShell>
  );
}
