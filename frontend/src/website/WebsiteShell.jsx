/**
 * Phase I1 — WebsiteShell wraps every public marketing page.
 * Self-contained styling: no app design tokens are inherited, so
 * the website can be tuned without rippling into the SPA.
 */
import React, { useEffect } from "react";
import WebsiteNav from "./WebsiteNav";
import WebsiteFooter from "./WebsiteFooter";

const PLAUSIBLE_DOMAIN = "akki.syni.ai";

export default function WebsiteShell({ children, title, description, pathname }) {
  // Per-page meta + canonical. Plausible analytics script injected once.
  useEffect(() => {
    if (title) document.title = title;
    let m = document.querySelector('meta[name="description"]');
    if (!m) { m = document.createElement("meta"); m.name = "description"; document.head.appendChild(m); }
    if (description) m.content = description;
    let canon = document.querySelector('link[rel="canonical"]');
    if (!canon) { canon = document.createElement("link"); canon.rel = "canonical"; document.head.appendChild(canon); }
    canon.href = `https://${PLAUSIBLE_DOMAIN}${pathname || window.location.pathname}`;
  }, [title, description, pathname]);

  // Plausible script (idempotent).
  useEffect(() => {
    if (document.getElementById("plausible-script")) return;
    const s = document.createElement("script");
    s.id = "plausible-script";
    s.defer = true;
    s.setAttribute("data-domain", PLAUSIBLE_DOMAIN);
    s.src = "https://plausible.io/js/script.js";
    document.head.appendChild(s);
  }, []);

  return (
    <div className="akki-website min-h-screen flex flex-col" style={{
      background: "#F5EFE6",
      color: "#2A1B1D",
      fontFamily: "Calibri, 'Helvetica Neue', Arial, sans-serif",
      fontSize: "18px",
      lineHeight: 1.65,
    }}>
      <WebsiteNav />
      <main className="flex-1">{children}</main>
      <WebsiteFooter />
    </div>
  );
}
