/**
 * News stub — Phase H.1 placeholder for /app/news.
 *
 * The real news/world-feed surface lands in H.3 (will reuse the
 * /api/news Patch 21 backend). For now this is a friendly
 * "Coming soon" page that the "Read more →" link on the Portfolio
 * Landing routes to, so the click flow is wired end-to-end.
 */
import React from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import { Newspaper, ArrowLeft } from "lucide-react";

export default function NewsStub() {
  return (
    <AppShell>
      <div className="akki-w-medium px-8 pt-16 pb-20" data-testid="news-stub">
        <p className="akki-overline mb-3 flex items-center gap-2">
          <Newspaper className="w-3 h-3 text-[var(--accent)]" /> News
        </p>
        <h1
          className="akki-greeting"
          style={{ fontSize: "32px" }}
          data-testid="news-stub-h1"
        >
          The world around you.
        </h1>
        <p className="akki-meta mt-2 max-w-2xl">
          A curated, regionally-tuned news feed for the boards and
          companies in your portfolio.
        </p>

        <div
          className="mt-10 bg-white border border-dashed border-[var(--rule)] rounded-md px-6 py-16 text-center"
          data-testid="news-stub-empty"
        >
          <p className="text-[12.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
            Coming soon
          </p>
          <p className="text-[13px] text-[var(--muted)] mt-2 max-w-md mx-auto">
            We&rsquo;re wiring the live feed in Phase H.3. Until then,
            head back to your portfolio.
          </p>
        </div>

        <div className="mt-6">
          <Link
            to="/app/companies"
            className="text-[12.5px] text-[var(--accent)] hover:text-[var(--ink)] inline-flex items-center gap-1 no-underline"
            data-testid="news-stub-back"
          >
            <ArrowLeft className="w-3 h-3" /> Back to portfolio
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
