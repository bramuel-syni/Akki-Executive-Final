/**
 * /app/news — Full news page (Phase H.3, 2026-05-26).
 *
 * Was a stub in H.1; now the full page using the shared
 * `<NewsStrip>` component with `limit=20` and the `quality=executive`
 * filter. `Read more →` on the Portfolio Landing routes here.
 *
 * Pagination: the current `/api/news` endpoint accepts `limit` (1-50)
 * but no cursor / page param. We render up to 50 items in a single
 * call today; if the catalog grows we'll add a cursor-style param to
 * the aggregator and infinite-scroll here.
 */
import React from "react";
import { Link } from "react-router-dom";
import AppShell from "@/components/layout/AppShell";
import NewsStrip from "@/components/news/NewsStrip";
import { Newspaper, ArrowLeft } from "lucide-react";

export default function NewsStub() {
  return (
    <AppShell>
      <div className="akki-w-medium px-8 pt-12 pb-20" data-testid="news-stub">
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
          Curated, regionally-tuned news from executive-grade sources.
        </p>

        <div
          className="mt-10 bg-white border border-[var(--rule)] rounded-md px-6 py-6"
          data-testid="news-stub-empty"
        >
          <NewsStrip
            limit={20}
            quality="executive"
            variant="expanded"
            testIdRoot="news-page-strip"
          />
        </div>

        <div className="mt-6">
          <Link
            to="/app"
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
