import React from "react";
import { Link, NavLink } from "react-router-dom";

/**
 * WebsiteNav — sticky top header for the pre-login marketing site.
 *
 * AKKI brand palette via app design tokens (var(--paper), var(--rule),
 * var(--ink), var(--accent)). Single sticky band, 1px --rule bottom
 * divider, no box-shadow, no scroll-triggered effects.
 *
 * Right cluster: primary oxblood CTA (Request early access → /cohort)
 * + ghost-ink sign-in link. Pricing nav link is intentionally absent
 * (page deleted Phase I1 revision 2).
 */
const LINKS = [
  { to: "/why-akki",       label: "Why Akki" },
  { to: "/what-akki-does", label: "What Akki Does" },
  { to: "/trust",          label: "Trust" },
  { to: "/about",          label: "About" },
  { to: "/contact",        label: "Contact" },
];

export default function WebsiteNav() {
  return (
    <header
      style={{
        position: "sticky", top: 0, zIndex: 50,
        background: "var(--paper)",
        borderBottom: "1px solid var(--rule)",
      }}
    >
      <div className="akki-website-container" style={{
        maxWidth: 1200, margin: "0 auto", padding: "18px 32px",
        display: "flex", alignItems: "center", gap: 24,
      }}>
        <Link to="/" style={{
          fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 22, fontWeight: 700,
          color: "var(--ink)", textDecoration: "none", letterSpacing: "-0.01em",
        }}>
          AKKI
        </Link>
        <nav className="website-nav-links" style={{ display: "flex", gap: 26, marginLeft: 32 }}>
          {LINKS.map(l => (
            <NavLink
              key={l.to}
              to={l.to}
              style={({ isActive }) => ({
                fontSize: 14, color: isActive ? "var(--accent)" : "var(--ink)",
                textDecoration: "none", letterSpacing: "0.02em",
                fontFamily: "Calibri, 'Helvetica Neue', Arial, sans-serif",
                transition: "color 200ms ease",
              })}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ flex: 1 }} />
        <Link
          to="/cohort"
          className="website-cta-primary"
          style={{ padding: "10px 18px", fontSize: 14 }}
          data-testid="website-nav-cohort-btn"
        >
          Request early access
        </Link>
        <Link
          to="/signin"
          style={{
            fontSize: 14, color: "var(--ink)", textDecoration: "none",
            transition: "color 200ms ease",
          }}
          data-testid="website-nav-signin"
        >
          Sign in
        </Link>
      </div>
    </header>
  );
}
