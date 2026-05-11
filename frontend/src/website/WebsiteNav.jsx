import React from "react";
import { Link, NavLink } from "react-router-dom";

/**
 * Phase J.2 — WebsiteNav per the new Website Experience Architecture v1.
 *
 * Strict 6-link spec, left to right:
 *   1. AKKI wordmark (home)
 *   2. Product (→ product overview hub)
 *   3. Methodology
 *   4. Exco360
 *   5. Sign in   (graphite, right-aligned, quiet)
 *   6. Try the sandbox   (bordered ink, right-most, NEW site-wide primary CTA)
 *
 * No mega-menus, no dropdowns, no nested nav. Audience pages (For
 * Executives / For NEDs / For Organisations) and Trust / Cohort /
 * About / Contact live in the footer, not the top nav.
 */
const LINKS = [
  { to: "/product",     label: "Product" },
  { to: "/methodology", label: "Methodology" },
  { to: "/exco360",     label: "Exco360" },
];

export default function WebsiteNav() {
  return (
    <header
      style={{
        position: "sticky", top: 0, zIndex: 50,
        background: "#EDE7D6",
        borderBottom: "1px solid #D8D2C5",
      }}
    >
      <div style={{
        maxWidth: 1200, margin: "0 auto", padding: "18px 32px",
        display: "flex", alignItems: "center", gap: 24,
      }}>
        <Link to="/" style={{
          fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 22, fontWeight: 700,
          color: "#0F1419", textDecoration: "none", letterSpacing: "-0.01em",
        }} data-testid="website-nav-wordmark">
          AKKI
        </Link>
        <nav className="website-nav-links" style={{ display: "flex", gap: 26, marginLeft: 32 }}>
          {LINKS.map(l => (
            <NavLink
              key={l.to}
              to={l.to}
              style={({ isActive }) => ({
                fontSize: 14, color: isActive ? "#8B6F3E" : "#0F1419",
                textDecoration: "none", letterSpacing: "0.02em",
                fontFamily: "Calibri, 'Helvetica Neue', Arial, sans-serif",
                transition: "color 180ms ease",
              })}
              data-testid={`website-nav-${l.to.replace(/^\//, "")}`}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ flex: 1 }} />
        <Link
          to="/signin"
          style={{
            fontSize: 14, color: "#6B7480", textDecoration: "none",
            transition: "color 180ms ease", letterSpacing: "0.02em",
          }}
          data-testid="website-nav-signin"
        >
          Sign in
        </Link>
        <Link
          to="/sandbox"
          style={{
            background: "transparent", color: "#0F1419", padding: "10px 18px",
            textDecoration: "none", fontSize: 14, fontWeight: 600,
            border: "1px solid #0F1419", borderRadius: 2, letterSpacing: "0.03em",
            transition: "border-color 180ms ease, color 180ms ease",
          }}
          data-testid="website-nav-sandbox-cta"
        >
          Try the sandbox
        </Link>
      </div>
    </header>
  );
}
