/**
 * MarketingFooter — flat link row for the public marketing surface.
 *
 * Replaces:
 *   - colophon in pages/Landing.jsx (lines 326-337 pre-PR)
 *   - 4-column footer inside components/marketing/MarketingShell.jsx
 *
 * Status / Terms / Privacy intentionally hidden until those pages exist.
 */
import React from "react";
import { Link } from "react-router-dom";

const LINKS = [
  { label: "Plans", href: "/plans", external: false },
  { label: "Security", href: "/security", external: false },
  { label: "Enterprise", href: "/enterprise", external: false },
  { label: "About", href: "/about", external: false },
  { label: "Contact", href: "mailto:hello@akki.ai", external: true },
  { label: "RSS", href: "/api/blog/rss", external: true },
];

export default function MarketingFooter() {
  return (
    <footer
      className="border-t border-[var(--rule)] bg-[var(--cream)] mt-12"
      data-testid="marketing-footer"
    >
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-10">
        <nav
          className="flex flex-wrap items-center gap-x-5 gap-y-3 text-[13px] text-[var(--deep)]"
          aria-label="Footer"
          data-testid="marketing-footer-links"
        >
          {LINKS.map((l, i) => (
            <React.Fragment key={l.label}>
              {l.external ? (
                <a
                  href={l.href}
                  className="hover:text-[var(--ink)] transition-colors"
                  data-testid={`marketing-footer-${l.label.toLowerCase()}`}
                >
                  {l.label}
                </a>
              ) : (
                <Link
                  to={l.href}
                  className="hover:text-[var(--ink)] transition-colors"
                  data-testid={`marketing-footer-${l.label.toLowerCase()}`}
                >
                  {l.label}
                </Link>
              )}
              {i < LINKS.length - 1 && (
                <span className="text-[var(--muted)]" aria-hidden="true">·</span>
              )}
            </React.Fragment>
          ))}
        </nav>
        <p
          className="mt-6 text-[11px] uppercase tracking-[0.2em] text-[var(--muted)]"
          data-testid="marketing-footer-colophon"
        >
          © AKKI · Syni.ai 2026 · Confidential · by invitation
        </p>
      </div>
    </footer>
  );
}
