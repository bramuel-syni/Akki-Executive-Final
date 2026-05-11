/**
 * Website v7 — Nav (E1).
 *
 * Sticky top, rgba parchment with 8px backdrop blur, 1px graphite-light
 * bottom border, 20px 40px padding. Layout per v7 §4.1:
 *
 *   Left   : wordmark "Akki" → /
 *   Centre : Product · Methodology · Exco360 · Trust
 *   Right  : Sign in (graphite) + Try the sandbox (bordered ink primary)
 *
 * "Product" routes to /what-akki-does (per v7 spec — the product overview
 * page is /what-akki-does, with /pricing and per-product pages reachable
 * from there).
 *
 * Audience pages and contact live in the footer, not the top nav.
 */
import React from "react";
import { Link } from "react-router-dom";

const CENTER_LINKS = [
  { to: "/what-akki-does", label: "Product" },
  { to: "/methodology",    label: "Methodology" },
  { to: "/exco360",        label: "Exco360" },
  { to: "/trust",          label: "Trust" },
];

export default function WebsiteNav() {
  return (
    <header className="nav" data-testid="website-nav">
      <div className="nav-inner">
        <Link to="/" className="nav-wordmark" data-testid="website-nav-wordmark">
          Akki
        </Link>
        <nav className="nav-center" aria-label="Primary">
          {CENTER_LINKS.map((l) => (
            <Link
              key={l.to}
              to={l.to}
              data-testid={`website-nav-${l.to.replace(/^\//, "").replace(/\//g, "-")}`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="nav-right">
          <Link to="/signin" className="nav-signin" data-testid="website-nav-signin">
            Sign in
          </Link>
          <Link to="/sandbox" className="btn-primary" data-testid="website-nav-sandbox-cta">
            Try the sandbox
          </Link>
        </div>
      </div>
    </header>
  );
}
