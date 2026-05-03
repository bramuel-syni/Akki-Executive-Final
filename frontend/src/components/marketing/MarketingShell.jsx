/**
 * MarketingShell — wraps inner marketing pages (About, Features, Security,
 * Blog, Plans, Enterprise, EarlyAccess) with the shared MarketingNav +
 * MarketingFooter.
 *
 * Pre-PR this file held its own MarketingHeader / MarketingFooter named
 * exports. They are now consolidated into dedicated components so Landing
 * and SolvaLanding can use them too.
 */
import React from "react";
import MarketingNav from "@/components/marketing/MarketingNav";
import MarketingFooter from "@/components/marketing/MarketingFooter";

export default function MarketingShell({ children }) {
  return (
    <div className="min-h-screen bg-[var(--cream)] flex flex-col">
      <MarketingNav />
      <main className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  );
}
