import React from "react";
import { Link, NavLink } from "react-router-dom";
import Logo from "@/components/brand/Logo";
import { ShieldCheck } from "lucide-react";

const NAV = [
  { to: "/about", label: "About" },
  { to: "/features", label: "Features" },
  { to: "/security", label: "Security" },
  { to: "/blog", label: "Exco360" },
];

export function MarketingHeader() {
  return (
    <header className="sticky top-0 z-30 bg-[var(--cream)]/90 backdrop-blur border-b border-[var(--rule)]">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 h-16 flex items-center gap-8">
        <Link to="/" className="shrink-0" data-testid="marketing-logo">
          <Logo />
        </Link>
        <nav className="hidden md:flex items-center gap-6 ml-2">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `text-[13.5px] transition-colors ${isActive ? "text-[var(--ink)] font-medium" : "text-[var(--deep)] hover:text-[var(--ink)]"}`
              }
              data-testid={`marketing-nav-${n.label.toLowerCase()}`}
            >{n.label}</NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <Link to="/sandbox" className="text-[13px] text-[var(--deep)] hover:text-[var(--ink)] transition-colors hidden sm:inline">
            Try the sandbox
          </Link>
          <Link
            to="/signin"
            className="text-[13px] px-4 py-2 bg-[var(--chrome)] hover:bg-[var(--chrome)]/90 text-white rounded-md transition-colors"
            data-testid="marketing-signin-btn"
          >Sign in</Link>
        </div>
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="border-t border-[var(--rule)] bg-[var(--cream-deep)]/40 mt-20">
      <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-12 grid grid-cols-1 md:grid-cols-4 gap-10">
        <div>
          <Logo />
          <p className="text-[12.5px] text-[var(--deep)] mt-4 leading-relaxed max-w-xs">
            Context-primary intelligence for non-executive directors and operating executives.
          </p>
        </div>
        <div>
          <p className="akki-overline mb-3">Product</p>
          <ul className="space-y-2 text-[13px] text-[var(--deep)]">
            <li><Link to="/features" className="hover:text-[var(--ink)]">Features</Link></li>
            <li><Link to="/security" className="hover:text-[var(--ink)]">Security & Trust</Link></li>
            <li><Link to="/sandbox" className="hover:text-[var(--ink)]">Try the sandbox</Link></li>
            <li><Link to="/signin" className="hover:text-[var(--ink)]">Sign in</Link></li>
          </ul>
        </div>
        <div>
          <p className="akki-overline mb-3">Company</p>
          <ul className="space-y-2 text-[13px] text-[var(--deep)]">
            <li><Link to="/about" className="hover:text-[var(--ink)]">About AKKI</Link></li>
            <li><Link to="/blog" className="hover:text-[var(--ink)]">Exco360 — the series</Link></li>
            <li><a href="mailto:hello@akki.ai" className="hover:text-[var(--ink)]">Contact</a></li>
          </ul>
        </div>
        <div>
          <p className="akki-overline mb-3 flex items-center gap-1.5">
            <ShieldCheck className="w-3 h-3 text-[var(--chrome)]" /> Posture
          </p>
          <ul className="space-y-2 text-[12.5px] text-[var(--deep)] leading-relaxed">
            <li>Synisense-shielded LLM calls</li>
            <li>Context never leaves your account</li>
            <li>Every signal cites its source</li>
            <li>Export or delete on demand</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-[var(--rule)] bg-[var(--cream)]">
        <div className="max-w-[1280px] mx-auto px-6 lg:px-10 py-4 text-[11.5px] text-[var(--muted)] font-mono uppercase tracking-wider flex flex-wrap items-center gap-4">
          <span>© AKKI · Syni.ai 2026</span>
          <span className="ml-auto">Build v4.3 · §12 redesign</span>
        </div>
      </div>
    </footer>
  );
}

export default function MarketingShell({ children }) {
  return (
    <div className="min-h-screen bg-[var(--cream)] flex flex-col">
      <MarketingHeader />
      <main className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  );
}
