/**
 * NewsStrip — shared news-list component (Phase H.3, 2026-05-26).
 *
 * Used by:
 *   • Portfolio Landing  "The world around you" section (limit ≈ 5)
 *   • /app/news full page                              (limit ≈ 20)
 *   • Home1 "What's moving in your world"              (limit ≈ 5, legacy)
 *
 * Lifted from `pages/home/Home1.jsx` and made composable. Wraps a
 * single fetch + render contract from `/api/news` so we don't
 * duplicate the request across surfaces.
 *
 * The aggregator (services/news_aggregator.py) populates `news_items`
 * via an asyncio task started at app boot. If the collection is
 * empty (cold start), this component renders an editorial fallback
 * line.
 */
import React, { useEffect, useState } from "react";
import api from "@/api";

const REGION_LABELS = {
  GB: "United Kingdom", US: "United States", KE: "Kenya",
  IN: "India",          HK: "Hong Kong",     NG: "Nigeria",
  AE: "United Arab Emirates", SG: "Singapore", ZA: "South Africa",
  GLOBAL: "global executive newsrooms",
};

export default function NewsStrip({
  limit = 5,
  quality = null,             // "executive" | null
  variant = "compact",        // "compact" | "expanded"
  testIdRoot = "news-strip",
  items: itemsProp = null,    // optional pre-fetched items (skips internal fetch)
  loading: loadingProp = false,
  regionApplied: regionAppliedProp = null,
  showRegionLabel = true,
}) {
  const [items, setItems]               = useState(itemsProp || []);
  const [regionApplied, setRegionApp]   = useState(regionAppliedProp);
  const [loading, setLoading]           = useState(itemsProp === null);

  const externalControl = itemsProp !== null;

  useEffect(() => {
    if (externalControl) {
      setItems(itemsProp);
      setRegionApp(regionAppliedProp);
      setLoading(loadingProp);
      return;
    }
    setLoading(true);
    const params = { limit };
    if (quality) params.quality = quality;
    api.get("/news", { params })
      .then(({ data }) => {
        setItems(data?.items || []);
        setRegionApp(data?.region_applied || null);
      })
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [limit, quality, itemsProp, loadingProp, regionAppliedProp]);

  return (
    <div data-testid={testIdRoot}>
      {regionApplied && regionApplied !== "GLOBAL" && REGION_LABELS[regionApplied] && (
        <p
          className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)] mb-3"
          data-testid={`${testIdRoot}-region-label`}
        >
          Curated for {REGION_LABELS[regionApplied]}
        </p>
      )}

      {loading ? (
        <p className="akki-meta italic" data-testid={`${testIdRoot}-loading`}>
          Loading…
        </p>
      ) : items.length === 0 ? (
        <p className="akki-meta italic" data-testid={`${testIdRoot}-empty`}>
          News updating — check back shortly.
        </p>
      ) : (
        <ul
          className={
            variant === "expanded"
              ? "space-y-5"
              : "space-y-3 max-h-[480px] overflow-y-auto pr-2 akki-thin-scroll"
          }
          data-testid={`${testIdRoot}-list`}
        >
          {items.map((n) => (
            <li
              key={n.id}
              className="border-b border-[var(--rule)] pb-3 last:border-b-0"
              data-testid={`${testIdRoot}-item-${n.id}`}
            >
              <div className="flex items-baseline gap-2 mb-1">
                <span className="text-[10.5px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]">
                  {n.source}
                </span>
                <span className="text-[10.5px] font-mono text-[var(--muted)]">·</span>
                <span className="text-[10.5px] font-mono text-[var(--muted)]">
                  {new Date(n.published_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                </span>
              </div>
              <a
                href={n.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`akki-serif ${
                  variant === "expanded" ? "text-[17px]" : "text-[15px]"
                } text-[var(--ink)] leading-snug hover:text-[var(--accent)] no-underline block`}
              >
                {n.title}
              </a>
              {n.summary && (
                <p className="text-[12.5px] text-[var(--muted)] leading-snug mt-1">
                  {n.summary}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
