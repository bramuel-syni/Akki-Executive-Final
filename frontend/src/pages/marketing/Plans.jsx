import React from "react";
import { Link } from "react-router-dom";
import MarketingShell from "@/components/marketing/MarketingShell";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";

export default function Plans() {
  return (
    <MarketingShell>
      <section
        className="max-w-[820px] mx-auto px-6 lg:px-10 py-20 md:py-28"
        data-testid="plans-page"
      >
        <p className="akki-overline mb-3 text-[var(--accent)]">Plans</p>
        <h1 className="akki-serif text-[44px] sm:text-[56px] leading-[1.05] tracking-tight text-[var(--ink)] mb-8 font-normal">
          Plans
        </h1>
        <p className="akki-serif text-[18px] leading-[1.7] text-[var(--deep)] mb-12 max-w-[60ch]">
          AKKI is in early access. Pricing will be published when we open general
          availability. In the meantime, apply for access below.
        </p>
        <div className="flex justify-center pt-4">
          <Link to="/early-access">
            <Button
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-12 px-7 text-[14px] font-medium"
              data-testid="plans-cta"
            >
              Apply for early access <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Link>
        </div>
      </section>
    </MarketingShell>
  );
}
