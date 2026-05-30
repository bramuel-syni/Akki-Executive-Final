/**
 * Wiki page — Phase P1 γ (2026-02).
 *
 * Replaces the legacy /help single-markdown page with a multi-article
 * wiki: sidebar nav grouped by category, fuzzy search across all
 * article bodies, markdown rendering of the selected article with
 * breadcrumb. Article content lives in src/website/wiki/content/**.md
 * and is indexed in src/website/wiki/index.js (compile-time manifest).
 *
 * Admin-only articles are filtered server-side from the auth context:
 * we read `account.is_superadmin` from AuthContext and surface the
 * Admin category only when true.
 *
 * Route: /help/:slug? (slug optional — defaults to the first non-admin
 * article in alphabetical category order).
 */
import React, { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import Fuse from "fuse.js";
import { useAuth } from "@/contexts/AuthContext";
import { ARTICLES, categoriesFor, findArticle } from "@/website/wiki";

export default function Wiki() {
  const { slug: routeSlug } = useParams();
  const navigate = useNavigate();
  const { account } = useAuth();
  const isAdmin = account?.is_superadmin === true;

  const articles = useMemo(
    () => ARTICLES.filter((a) => !a.adminOnly || isAdmin),
    [isAdmin]
  );
  const grouped = useMemo(() => categoriesFor(isAdmin), [isAdmin]);

  // Default to the first article when no slug is in the URL.
  const slug = routeSlug || articles[0]?.slug || "";
  const article = findArticle(slug, isAdmin);

  // Fuzzy search.
  const [query, setQuery] = useState("");
  const fuse = useMemo(
    () =>
      new Fuse(articles, {
        keys: [
          { name: "title", weight: 2 },
          { name: "category", weight: 1 },
          { name: "body", weight: 1 },
        ],
        threshold: 0.4,
        ignoreLocation: true,
        minMatchCharLength: 2,
      }),
    [articles]
  );
  const searchResults = useMemo(() => {
    const q = query.trim();
    if (!q) return null;
    return fuse.search(q).slice(0, 10).map((r) => r.item);
  }, [query, fuse]);

  // If the route slug doesn't exist (or is admin-only and we're not),
  // bounce to the default article.
  useEffect(() => {
    if (routeSlug && !article && articles.length > 0) {
      navigate(`/help/${articles[0].slug}`, { replace: true });
    }
  }, [routeSlug, article, articles, navigate]);

  return (
    <div className="min-h-screen bg-[var(--cream)] text-[var(--ink)]" data-testid="wiki-page">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <button
          type="button"
          data-testid="wiki-back-btn"
          onClick={() => {
            if (window.history.length > 1) window.history.back();
            else window.location.assign("/");
          }}
          className="inline-flex items-center gap-1.5 mb-6 px-2.5 py-1.5 text-[12.5px] text-[var(--deep)] hover:text-[var(--ink)] border border-[var(--cream-deep)] hover:border-[var(--ink)] rounded-sm transition-colors"
          aria-label="Back"
        >
          <span aria-hidden="true">←</span><span>Back</span>
        </button>

        <header className="mb-8" data-testid="wiki-header">
          <h1 className="text-3xl font-serif text-[var(--ink)]">Help & wiki</h1>
          <p className="text-[14px] text-[var(--deep)] mt-1">
            How Akki works, what each surface does, and how to use it.
          </p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-[260px,1fr] gap-8">
          <aside data-testid="wiki-sidebar" className="border-r border-[var(--cream-deep)] pr-6">
            <input
              type="search"
              placeholder="Search articles…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              data-testid="wiki-search-input"
              className="w-full px-3 py-2 text-[13px] border border-[var(--cream-deep)] bg-white rounded-sm mb-6 focus:outline-none focus:border-[var(--ink)]"
            />
            {searchResults !== null ? (
              <div data-testid="wiki-search-results">
                <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] mb-2">
                  Search results
                </p>
                {searchResults.length === 0 ? (
                  <p className="text-[13px] text-[var(--deep)]">No matches.</p>
                ) : (
                  <ul className="space-y-1">
                    {searchResults.map((a) => (
                      <li key={a.slug}>
                        <Link
                          to={`/help/${a.slug}`}
                          className="block px-2 py-1.5 text-[13px] text-[var(--deep)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)] rounded-sm transition-colors"
                          data-testid={`wiki-search-result-${a.slug}`}
                          onClick={() => setQuery("")}
                        >
                          {a.title}
                          <span className="block text-[10px] text-[var(--muted)] mt-0.5">{a.category}</span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ) : (
              <nav data-testid="wiki-nav">
                {Object.entries(grouped).map(([cat, items]) => (
                  <div key={cat} className="mb-6">
                    <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] mb-2">{cat}</p>
                    <ul className="space-y-1">
                      {items.map((a) => (
                        <li key={a.slug}>
                          <Link
                            to={`/help/${a.slug}`}
                            className={`block px-2 py-1.5 text-[13px] rounded-sm transition-colors ${
                              a.slug === slug
                                ? "bg-[var(--cream-deep)] text-[var(--ink)] font-medium"
                                : "text-[var(--deep)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)]"
                            }`}
                            data-testid={`wiki-nav-${a.slug}`}
                          >
                            {a.title}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </nav>
            )}
          </aside>

          <main data-testid="wiki-article-shell">
            {!article ? (
              <p className="text-[14px] text-[var(--deep)]">Article not found.</p>
            ) : (
              <article data-testid={`wiki-article-${article.slug}`}>
                <nav className="text-[11px] text-[var(--muted)] mb-4" aria-label="Breadcrumb" data-testid="wiki-breadcrumb">
                  <Link to="/help" className="hover:text-[var(--ink)]">Help</Link>
                  <span className="mx-1.5">/</span>
                  <span>{article.category}</span>
                  <span className="mx-1.5">/</span>
                  <span className="text-[var(--ink)]">{article.title}</span>
                </nav>
                <div className="prose prose-sm max-w-none wiki-article-body" data-testid="wiki-article-body">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    rehypePlugins={[rehypeHighlight]}
                  >
                    {article.body}
                  </ReactMarkdown>
                </div>
              </article>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
