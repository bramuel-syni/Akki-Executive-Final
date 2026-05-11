/**
 * Website v7 — WebsiteShell.
 *
 * Wraps every public marketing page. Loads v7 CSS, injects per-page
 * meta + canonical, and lazy-injects Plausible analytics with
 * data-domain="akki.syni.ai". Self-contained: imports no app design
 * tokens.
 *
 * A9 — IntersectionObserver wired here drives the .section-reveal
 * class. Honours prefers-reduced-motion.
 *
 * Sandbox + sign-in routes inherit the same v7 palette via
 * sandbox/style.css (separate file) and the legacy app shell
 * respectively — this shell is NOT mounted on those routes.
 */
import React, { useEffect } from "react";
import WebsiteNav from "./WebsiteNav";
import WebsiteFooter from "./WebsiteFooter";
import "./style.css";

const PLAUSIBLE_DOMAIN = "akki.syni.ai";
const OG_IMAGE = "/static/media/home-hero.webp";

export default function WebsiteShell({ children, title, description, pathname, ogImage }) {
  // Per-page meta + canonical.
  useEffect(() => {
    if (title) document.title = title;
    const setMeta = (name, content) => {
      if (!content) return;
      let m = document.querySelector(`meta[name="${name}"]`);
      if (!m) { m = document.createElement("meta"); m.name = name; document.head.appendChild(m); }
      m.content = content;
    };
    const setProperty = (prop, content) => {
      if (!content) return;
      let m = document.querySelector(`meta[property="${prop}"]`);
      if (!m) { m = document.createElement("meta"); m.setAttribute("property", prop); document.head.appendChild(m); }
      m.content = content;
    };
    setMeta("description", description);
    setProperty("og:title", title || "");
    setProperty("og:description", description || "");
    setProperty("og:image", ogImage || OG_IMAGE);
    setProperty("og:url", `https://${PLAUSIBLE_DOMAIN}${pathname || window.location.pathname}`);
    setProperty("og:type", "website");
    setMeta("twitter:card", "summary_large_image");
    setMeta("twitter:title", title || "");
    setMeta("twitter:description", description || "");
    setMeta("twitter:image", ogImage || OG_IMAGE);
    let canon = document.querySelector('link[rel="canonical"]');
    if (!canon) { canon = document.createElement("link"); canon.rel = "canonical"; document.head.appendChild(canon); }
    canon.href = `https://${PLAUSIBLE_DOMAIN}${pathname || window.location.pathname}`;
  }, [title, description, pathname, ogImage]);

  // Plausible script — load once.
  useEffect(() => {
    if (document.getElementById("plausible-script")) return;
    const s = document.createElement("script");
    s.id = "plausible-script";
    s.defer = true;
    s.setAttribute("data-domain", PLAUSIBLE_DOMAIN);
    s.src = "https://plausible.io/js/script.js";
    document.head.appendChild(s);
  }, []);

  // A9 — IntersectionObserver for .section-reveal.
  useEffect(() => {
    const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    // Arm the hero stagger animation (A8) once the shell has mounted.
    // We do this in a rAF so the browser registers the keyframes from
    // an unrendered base state — guarantees the first paint sees the
    // animation, NOT a flash of final content.
    requestAnimationFrame(() => {
      document.querySelectorAll(".akki-website").forEach((el) => el.classList.add("reveal-armed"));
    });
    const targets = document.querySelectorAll(".section-reveal");
    if (reduced) {
      targets.forEach((el) => el.classList.add("in-view"));
      return undefined;
    }
    const obs = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("in-view");
          obs.unobserve(e.target);
        }
      });
    }, { threshold: 0.05, rootMargin: "0px 0px -80px 0px" });
    targets.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, [children]);

  return (
    <div className="akki-website">
      <WebsiteNav />
      <main>{children}</main>
      <WebsiteFooter />
    </div>
  );
}
