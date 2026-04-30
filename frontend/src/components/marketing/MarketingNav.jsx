/**
 * MarketingNav — shared top nav for the public marketing surface.
 *
 * Replaces three previous nav implementations:
 *   - inline nav in pages/Landing.jsx (lines 120-166 pre-PR)
 *   - MarketingHeader inside components/marketing/MarketingShell.jsx
 *   - inline nav in pages/SolveLanding.jsx (lines 87-112 pre-PR)
 *
 * Logged-out CTA: "Apply for early access" -> /early-access
 * Logged-in: replaces Sign in + CTA with "Go to workspace" -> /app
 *
 * No new design tokens. cream/oxblood/navy palette preserved.
 */
import React from "react";
import { Link, NavLink } from "react-router-dom";
import Logo from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { ArrowRight } from "lucide-react";

const NAV_ITEMS = [
  { to: "/features", label: "Product" },
  { to: "/about#methodology", label: "Methodology" },
  { to: "/blog", label: "Exco360" },
];

export default function MarketingNav() {
  // useAuth may legitimately be undefined on routes mounted outside the
  // AuthProvider; guard with `|| {}` so this nav stays renderable in
  // any context (e.g. storybook, error boundaries).
  const { account } = useAuth() || {};
  const isAuthed = !!account;

  return (
    <header
      className="sticky top-0 z-30 bg-[var(--cream)]/90 backdrop-blur border-b border-[var(--rule)]"
      data-testid="marketing-nav"
    >
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 h-16 flex items-center gap-8">
        <Link to="/" className="shrink-0" aria-label="AKKI home" data-testid="marketing-nav-logo">
          <Logo />
        </Link>

        <nav className="hidden md:flex items-center gap-6 ml-2" aria-label="Primary">
          {NAV_ITEMS.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `text-[13.5px] transition-colors ${
                  isActive
                    ? "text-[var(--ink)] font-medium"
                    : "text-[var(--deep)] hover:text-[var(--ink)]"
                }`
              }
              data-testid={`marketing-nav-${n.label.toLowerCase()}`}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {isAuthed ? (
            <Link to="/app" data-testid="marketing-nav-workspace">
              <Button className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-9 px-4 text-[13px] font-medium">
                Go to workspace <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
              </Button>
            </Link>
          ) : (
            <>
              <Link
                to="/signin"
                className="text-[13px] text-[var(--deep)] hover:text-[var(--ink)] transition-colors px-3 py-1.5"
                data-testid="marketing-nav-signin"
              >
                Sign in
              </Link>
              <Link to="/early-access" data-testid="marketing-nav-cta">
                <Button className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-sm h-9 px-4 text-[13px] font-medium">
                  Apply for early access <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                </Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
