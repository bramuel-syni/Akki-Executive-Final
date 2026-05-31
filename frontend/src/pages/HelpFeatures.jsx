/**
 * Help page — renders the AKKI Features & Functionality reference.
 *
 * Phase E deliverable. Lazily loaded from /help in App.js. Fetches the
 * markdown body + metadata from `GET /api/help/features` (no auth) and
 * renders it via react-markdown with remark-gfm + rehype-highlight.
 *
 * The page styling follows the website-shell aesthetic (light cream
 * background, serif headings, restrained margins) so it slots in next
 * to the existing /trust + /methodology pages without feeling like an
 * adjacent admin surface.
 */
import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { api } from "@/lib/api";

import { resolveBackendOrigin } from "@/lib/api";
const API_BASE = resolveBackendOrigin();

export default function HelpFeatures() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .get("/help/features")
      .then((res) => {
        if (!cancelled) {
          setData(res.data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const status = err?.response?.status;
          const detail = err?.response?.data?.detail || err?.message || "Failed to load";
          setError(status ? `HTTP ${status} — ${detail}` : detail);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div
      className="min-h-screen bg-[#f5f0e6] text-stone-900"
      data-testid="help-features-page"
    >
      {/* Light header consistent with /trust + /methodology */}
      <header className="border-b border-stone-300/60 bg-[#f5f0e6]/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
          <Link
            to="/"
            className="text-xl font-semibold tracking-tight"
            data-testid="help-features-brand-home"
          >
            Akki
          </Link>
          <nav className="flex items-center gap-6 text-sm text-stone-700">
            <Link to="/what-akki-does" className="hover:text-stone-900">Product</Link>
            <Link to="/methodology" className="hover:text-stone-900">Methodology</Link>
            <Link to="/trust" className="hover:text-stone-900">Trust</Link>
            <Link to="/help" className="font-medium text-stone-900" aria-current="page">Help</Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-6 py-12">
        {/* Status header */}
        <div className="mb-10 border-b border-stone-300/70 pb-6">
          <p className="text-xs uppercase tracking-[0.18em] text-stone-500">Help</p>
          <h1
            className="mt-2 text-4xl sm:text-5xl font-serif font-medium leading-tight text-stone-900"
            data-testid="help-features-title"
          >
            {data?.title || "AKKI — Features & Functionality"}
          </h1>
          {data?.last_modified && (
            <p
              className="mt-3 text-sm text-stone-500"
              data-testid="help-features-last-modified"
            >
              Last updated {new Date(data.last_modified).toLocaleDateString(undefined, {
                year: "numeric", month: "long", day: "numeric",
              })}
              {typeof data.word_count === "number" && (
                <> · {data.word_count.toLocaleString()} words</>
              )}
            </p>
          )}
        </div>

        {/* Content area */}
        {loading && (
          <div
            className="text-stone-500"
            data-testid="help-features-loading"
          >
            Loading the features reference…
          </div>
        )}

        {error && !loading && (
          <div
            className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-800"
            data-testid="help-features-error"
          >
            <strong className="font-semibold">Couldn't load /api/help/features:</strong>{" "}
            {error}
          </div>
        )}

        {data?.markdown && !loading && !error && (
          <article
            className="space-y-5 text-stone-800 leading-7"
            data-testid="help-features-content"
          >
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={{
                h1: () => null,
                h2: ({ children }) => (
                  <h2 className="mt-12 mb-4 text-3xl font-serif font-medium text-stone-900">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="mt-8 mb-3 text-xl font-serif font-medium text-stone-900">
                    {children}
                  </h3>
                ),
                h4: ({ children }) => (
                  <h4 className="mt-6 mb-2 text-base font-semibold text-stone-900">
                    {children}
                  </h4>
                ),
                p: ({ children }) => (
                  <p className="text-stone-800">{children}</p>
                ),
                ul: ({ children }) => (
                  <ul className="ml-6 list-disc space-y-1 text-stone-800">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="ml-6 list-decimal space-y-1 text-stone-800">{children}</ol>
                ),
                li: ({ children }) => <li className="leading-7">{children}</li>,
                strong: ({ children }) => (
                  <strong className="font-semibold text-stone-900">{children}</strong>
                ),
                a: ({ href, children }) => (
                  <a
                    href={href}
                    className="text-stone-700 underline underline-offset-4 hover:text-stone-900"
                    target={href?.startsWith("http") ? "_blank" : undefined}
                    rel={href?.startsWith("http") ? "noopener noreferrer" : undefined}
                  >
                    {children}
                  </a>
                ),
                code: ({ inline, className, children }) =>
                  inline ? (
                    <code className="rounded bg-stone-200/70 px-1.5 py-0.5 font-mono text-sm text-stone-900">
                      {children}
                    </code>
                  ) : (
                    <code className={`block ${className || ""}`}>{children}</code>
                  ),
                pre: ({ children }) => (
                  <pre className="my-4 overflow-x-auto rounded-md bg-stone-900 p-4 text-sm text-stone-100">
                    {children}
                  </pre>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="my-4 border-l-4 border-stone-400 pl-4 italic text-stone-700">
                    {children}
                  </blockquote>
                ),
                hr: () => <hr className="my-10 border-stone-300" />,
                table: ({ children }) => (
                  <div className="my-6 overflow-x-auto">
                    <table className="min-w-full border border-stone-300 text-sm">
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="border border-stone-300 bg-stone-100 px-3 py-2 text-left font-semibold">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="border border-stone-300 px-3 py-2 align-top">{children}</td>
                ),
              }}
            >
              {data.markdown}
            </ReactMarkdown>
          </article>
        )}
      </main>

      <footer className="mt-16 border-t border-stone-300/60">
        <div className="mx-auto flex max-w-5xl flex-col gap-2 px-6 py-8 text-sm text-stone-500 sm:flex-row sm:items-center sm:justify-between">
          <div>© {new Date().getFullYear()} Akki — governance-grade AI for executives.</div>
          <div className="flex gap-4">
            <Link to="/privacy" className="hover:text-stone-700">Privacy</Link>
            <Link to="/terms" className="hover:text-stone-700">Terms</Link>
            <a
              href={`${API_BASE}/api/help/features.md`}
              className="hover:text-stone-700"
              data-testid="help-features-download-md"
            >
              Download .md
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
