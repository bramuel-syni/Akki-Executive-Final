/**
 * §5 Voice — three Exco360 pull-quotes. Live data fetched from
 * GET /api/blog/posts (returns published posts only).
 *
 * Per spec: prefer post.dek for the pull-quote; fall back to first sentence
 * of post.body capped at 180 chars (no mid-sentence cut). If fewer than 3
 * published posts exist, render whatever is available and console.warn().
 * No placeholder fallback text.
 *
 * Body is excluded from the list endpoint, so we fetch the individual post
 * by slug only when its dek is missing.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Quote, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";

function firstSentenceCapped(body, cap = 180) {
  const text = (body || "").replace(/\s+/g, " ").trim();
  if (!text) return "";
  const slice = text.length <= cap ? text : text.slice(0, cap);
  // Prefer the last full stop within the cap so we don't cut mid-sentence.
  const lastStop = Math.max(slice.lastIndexOf(". "), slice.lastIndexOf(".\n"));
  if (lastStop > 40) return slice.slice(0, lastStop + 1).trim();
  // Otherwise return the slice unchanged — spec says no ellipsis.
  return slice.trim();
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return "";
  }
}

export default function Exco360Voice() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get("/blog/posts?limit=10");
        const list = Array.isArray(r.data?.posts) ? r.data.posts : [];
        const top = list.slice(0, 3);

        // Enrich each post with a quote: dek first, then first sentence of body.
        const enriched = await Promise.all(
          top.map(async (p) => {
            let quote = (p.dek || "").trim();
            if (!quote && p.slug) {
              try {
                const single = await api.get(`/blog/posts/${p.slug}`);
                quote = firstSentenceCapped(single.data?.body, 180);
              } catch {
                /* ignore — leave quote blank */
              }
            }
            return { ...p, _quote: quote };
          }),
        );

        if (cancelled) return;

        // Drop posts where we still have no quote text — spec says no placeholder.
        const final = enriched.filter((p) => p._quote);
        if (final.length < 3) {
          // eslint-disable-next-line no-console
          console.warn(
            `[Exco360Voice] Only ${final.length} published post(s) with usable quotes — expected 3.`,
          );
        }
        setPosts(final);
      } catch (err) {
        if (cancelled) return;
        // eslint-disable-next-line no-console
        console.warn("[Exco360Voice] Failed to load Exco360 posts:", err?.message || err);
        setPosts([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section
      className="border-b border-[var(--rule)] bg-[var(--cream-deep)]/40"
      data-testid="exco360-voice"
    >
      <div className="max-w-[1280px] mx-auto px-6 md:px-12 py-20 md:py-24">
        <p className="akki-overline mb-3">From Exco360</p>
        <h2 className="akki-serif text-[28px] md:text-[40px] leading-[1.1] tracking-[-0.015em] text-[var(--ink)] font-normal mb-3 max-w-[26ch]">
          From the editorial side
        </h2>
        <p className="akki-serif text-[16px] leading-[1.7] text-[var(--deep)] max-w-[64ch] mb-14">
          Our weekly column on what AI is doing to governance — and what it should not.
        </p>

        {posts.length > 0 && (
          <div
            className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-10"
            data-testid="exco360-quotes"
          >
            {posts.map((p) => (
              <Link
                key={p.slug}
                to={`/blog/${p.slug}`}
                className="group block"
                data-testid={`exco360-quote-${p.slug}`}
              >
                <article className="flex flex-col h-full">
                  <Quote
                    className="w-5 h-5 text-[var(--accent)] mb-4"
                    strokeWidth={1.5}
                    aria-hidden="true"
                  />
                  <p className="akki-serif text-[17px] md:text-[18px] leading-[1.55] text-[var(--ink)] mb-6 group-hover:text-[var(--accent)] transition-colors">
                    {p._quote}
                  </p>
                  <div className="mt-auto pt-4 border-t border-[var(--rule)]">
                    <p className="akki-serif italic text-[15px] text-[var(--deep)] leading-snug mb-1.5">
                      {p.title}
                    </p>
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      {p.kicker && (
                        <span className="akki-overline text-[var(--muted)]">{p.kicker}</span>
                      )}
                      {p.kicker && p.published_at && (
                        <span aria-hidden="true" className="text-[var(--rule)]">·</span>
                      )}
                      {p.published_at && (
                        <span className="akki-overline text-[var(--muted)]">
                          {formatDate(p.published_at)}
                        </span>
                      )}
                    </div>
                  </div>
                </article>
              </Link>
            ))}
          </div>
        )}

        {!loading && posts.length === 0 && (
          <p
            className="text-[13px] text-[var(--muted)] italic"
            data-testid="exco360-empty"
          >
            New issues are in preparation.
          </p>
        )}

        <div className="mt-14">
          <Link
            to="/blog"
            className="inline-flex items-center gap-1.5 text-[13.5px] text-[var(--accent)] hover:underline underline-offset-4"
            data-testid="exco360-cta"
          >
            Read Exco360 <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
