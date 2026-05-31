/**
 * Website v7 — Footer (E3).
 *
 * Four-column grid (brand spans 2 cols mobile), padding 60/40/40,
 * column headings 11px oxblood, links 14px ink, bottom rule mono 11px
 * graphite. Verbatim sequence per v7 §4.10.
 */
import React from "react";
import { Link } from "react-router-dom";

const PRODUCT = [
  ["Solva",            "/solva"],
  ["Akki Chat",        "/akki-chat"],
  ["Work Studio",      "/work-studio"],
  ["Cycle Manager",    "/cycle-manager"],
  ["Monitor",          "/monitor"],
  ["Pulse",            "/pulse"],
  ["Document Journal", "/document-journal"],
];
const READING = [
  ["Methodology",         "/methodology"],
  ["Exco360",             "/exco360"],
  ["Trust & Sovereignty", "/trust"],
  ["Early access",        "/cohort"],
];
const STUDIO = [
  ["Syni.ai", "https://syni.ai"],
  ["About",   "/about"],
  ["Contact", "/contact"],
];

export default function WebsiteFooter() {
  return (
    <footer className="footer" data-testid="website-footer">
      <div className="footer-inner">
        <div className="footer-brand footer-col">
          <Link to="/" className="footer-brand-wordmark" data-testid="footer-wordmark">Akki <span className="footer-brand-wordmark-tail">for&nbsp;Executives</span></Link>
          <p className="footer-tagline">
            A workspace for executives running serious operations. From Syni.ai, Nairobi.
          </p>
        </div>
        <div className="footer-col">
          <p className="footer-col-heading">Product</p>
          <ul>
            {PRODUCT.map(([label, to]) => (
              <li key={to}><Link to={to} data-testid={`footer-product-${to.replace(/^\//, "")}`}>{label}</Link></li>
            ))}
          </ul>
        </div>
        <div className="footer-col">
          <p className="footer-col-heading">Reading</p>
          <ul>
            {READING.map(([label, to]) => (
              <li key={to}><Link to={to} data-testid={`footer-reading-${to.replace(/^\//, "")}`}>{label}</Link></li>
            ))}
          </ul>
        </div>
        <div className="footer-col">
          <p className="footer-col-heading">Studio</p>
          <ul>
            {STUDIO.map(([label, to]) => {
              const external = to.startsWith("http");
              return (
                <li key={to}>
                  {external ? (
                    <a href={to} target="_blank" rel="noopener noreferrer" data-testid={`footer-studio-external`}>{label}</a>
                  ) : (
                    <Link to={to} data-testid={`footer-studio-${to.replace(/^\//, "")}`}>{label}</Link>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
      <div className="footer-bottom">
        <span>© {new Date().getFullYear()} Syni.ai · Nairobi · Built for people who read before they buy.</span>
        <span>
          <Link to="/privacy" style={{ marginRight: 12 }} data-testid="footer-privacy">Privacy</Link>
          <Link to="/terms" data-testid="footer-terms">Terms</Link>
        </span>
      </div>
    </footer>
  );
}
