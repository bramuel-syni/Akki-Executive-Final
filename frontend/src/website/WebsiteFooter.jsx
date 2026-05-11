import React from "react";
import { Link } from "react-router-dom";
import { FOOTER } from "./copy";

/**
 * WebsiteFooter — single restrained band at the foot of every public
 * marketing page. AKKI brand tokens via var(--*) from index.css.
 */
export default function WebsiteFooter() {
  return (
    <footer style={{
      background: "var(--paper)",
      borderTop: "1px solid var(--rule)",
      padding: "40px 32px", marginTop: 80,
    }}>
      <div style={{
        maxWidth: 1200, margin: "0 auto",
        display: "flex", flexWrap: "wrap", gap: 24, alignItems: "center", justifyContent: "space-between",
      }}>
        <p style={{ margin: 0, fontSize: 13, color: "var(--muted)" }}>
          <span style={{ fontFamily: "Georgia, 'Times New Roman', serif", fontWeight: 700, color: "var(--ink)" }}>AKKI</span>
          &nbsp;&middot;&nbsp; A Syni product
        </p>
        <div style={{ display: "flex", gap: 24, fontSize: 13 }}>
          <Link to="/privacy" className="website-link-inline" style={{ color: "var(--muted)" }}>Privacy</Link>
          <Link to="/terms"   className="website-link-inline" style={{ color: "var(--muted)" }}>Terms</Link>
          <Link to="/contact" className="website-link-inline" style={{ color: "var(--muted)" }}>Contact</Link>
        </div>
        <p style={{ margin: 0, fontSize: 13, color: "var(--muted)", fontStyle: "italic" }}>
          {FOOTER.signoff}
        </p>
      </div>
    </footer>
  );
}
