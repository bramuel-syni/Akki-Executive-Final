import React, { useEffect, useState } from "react";
import { Link, NavLink } from "react-router-dom";

const LINKS = [
  { to: "/why-akki",       label: "Why Akki" },
  { to: "/what-akki-does", label: "What Akki Does" },
  { to: "/trust",          label: "Trust" },
  { to: "/about",          label: "About" },
  { to: "/contact",        label: "Contact" },
];

export default function WebsiteNav() {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <header
      style={{
        position: "sticky", top: 0, zIndex: 50,
        background: "#EDE7D6",
        borderBottom: "1px solid #D8D2C5",
        boxShadow: scrolled ? "0 2px 8px rgba(42,27,29,0.06)" : "none",
        transition: "box-shadow 150ms ease",
      }}
    >
      <div className="akki-website-container" style={{
        maxWidth: 1200, margin: "0 auto", padding: "18px 32px",
        display: "flex", alignItems: "center", gap: 24,
      }}>
        <Link to="/" style={{
          fontFamily: "Georgia, serif", fontSize: 22, fontWeight: 700,
          color: "#0F1419", textDecoration: "none", letterSpacing: "-0.01em",
        }}>
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
              })}
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div style={{ flex: 1 }} />
        <Link
          to="/cohort"
          style={{
            background: "#8B6F3E", color: "#EDE7D6", padding: "10px 18px",
            textDecoration: "none", fontSize: 14, fontWeight: 600,
            borderRadius: 2, letterSpacing: "0.02em",
          }}
          data-testid="website-nav-cohort-btn"
        >
          Request early access
        </Link>
        <Link
          to="/signin"
          style={{ fontSize: 14, color: "#0F1419", textDecoration: "none" }}
        >
          Sign in
        </Link>
      </div>
    </header>
  );
}
