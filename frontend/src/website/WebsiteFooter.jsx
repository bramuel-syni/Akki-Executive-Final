import React from "react";
import { Link } from "react-router-dom";
import { FOOTER } from "./copy";

export default function WebsiteFooter() {
  return (
    <footer style={{
      background: "#FAF7F2",
      borderTop: "1px solid #D5C9B6",
      padding: "28px 32px",
      marginTop: 60,
    }}>
      <div style={{
        maxWidth: 1200, margin: "0 auto", display: "flex",
        alignItems: "center", justifyContent: "space-between",
        gap: 24, flexWrap: "wrap",
      }}>
        <p style={{ margin: 0, fontSize: 13, color: "#6B6B6B" }}>
          <span style={{ fontFamily: "Georgia, serif", fontWeight: 700, color: "#2A1B1D" }}>AKKI</span>
          {" "}· © {new Date().getFullYear()} Akki Limited
        </p>
        <nav style={{ display: "flex", gap: 24, fontSize: 13 }}>
          <Link to="/privacy" style={{ color: "#6B6B6B", textDecoration: "none" }}>Privacy</Link>
          <Link to="/terms" style={{ color: "#6B6B6B", textDecoration: "none" }}>Terms</Link>
          <Link to="/contact" style={{ color: "#6B6B6B", textDecoration: "none" }}>Contact</Link>
        </nav>
        <p style={{ margin: 0, fontSize: 13, color: "#6B6B6B", fontStyle: "italic" }}>
          {FOOTER.signoff}
        </p>
      </div>
    </footer>
  );
}
