/**
 * TopBar — Chunk 6.5 (2026-05-13).
 *
 * Slimmed top chrome that lives to the right of the LeftRail. From
 * left to right:
 *
 *   - Breadcrumb           (computed from the current route)
 *   - Global Cmd+K search  (existing UniversalSearchDialog trigger)
 *   - Bell / mentions      (existing MentionInbox component)
 *   - Daily review badge   (existing ReviewBadge component)
 *   - Add document         (Hero Doc Action — opens the existing
 *                           UploadModal via the global event)
 *   - Keyboard help        (?, opens KeyboardHelp)
 *   - Account avatar       (legacy menu — Settings / Security / Trust /
 *                           Sign out). Note: the LeftRail user-block
 *                           is now the primary surface for the same
 *                           three items, but the avatar menu stays
 *                           because power users reach for the top
 *                           bar reflexively.
 *
 * The workspace switcher is INTENTIONALLY removed from this bar — the
 * LeftRail now owns that affordance. The Trust classification chip is
 * intentionally removed; it lives on the Trust panel + footer instead.
 *
 * No v7 hex literals. 64px tall, cream background, single rule border
 * underneath. Matches the previous header height so /app/cycle's
 * Layer 1 breadcrumb (Patch CM v2) stays aligned.
 */
import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Search, Plus, Keyboard, ChevronRight,
  Settings, Lock, ShieldCheck, LogOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/contexts/AuthContext";
import MentionInbox from "@/components/collab/MentionInbox";
import ReviewBadge from "@/components/layout/ReviewBadge";
import ContinueWithPill from "@/components/layout/ContinueWithPill";


// Static breadcrumb map for the 9 modules + a few high-traffic
// sub-routes. Dynamic sub-paths (like `/app/cycle/:cycleId/...`)
// derive a "Cycle Manager" root from the longest prefix match.
const BREADCRUMB_ROOTS = [
  { match: "/app/cycle",         label: "Cycle Manager" },
  { match: "/app/work-studio",   label: "Work Studio" },
  { match: "/app/workspace",     label: "Document Journal" },
  { match: "/app/documents",     label: "Document Journal" },
  { match: "/app/chat",          label: "Akki Chat" },
  { match: "/app/solva",         label: "Solva" },
  { match: "/app/monitor",       label: "Monitor" },
  { match: "/app/pulse",         label: "Pulse" },
  { match: "/app/learn",         label: "Learn" },
  { match: "/app/questions",     label: "Questions" },
  { match: "/app/settings",      label: "Settings" },
  { match: "/app/security",      label: "Account security" },
  { match: "/app/manage",        label: "Manage" },
  { match: "/app/portfolio",     label: "Portfolio" },
  { match: "/app/studio/composer", label: "Composer" },
  { match: "/app/decks",         label: "Decks" },
];


function computeBreadcrumb(pathname) {
  // Always start with Home.
  const segments = [{ to: "/app", label: "Home", end: true }];
  if (pathname === "/app" || pathname === "/app/") return segments;

  // Longest-prefix match. The Cycle Manager has nested cycle IDs that
  // should not surface their UUID in the breadcrumb — we collapse
  // them to "Cycle Manager" only.
  const match = BREADCRUMB_ROOTS
    .filter((r) => pathname === r.match || pathname.startsWith(r.match + "/") || pathname.startsWith(r.match + "?"))
    .sort((a, b) => b.match.length - a.match.length)[0];
  if (match) {
    segments.push({ to: match.match, label: match.label, end: false });
  }
  return segments;
}


export default function TopBar({ onOpenUpload, onOpenHelp, onOpenTrust }) {
  const { account, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const crumbs = computeBreadcrumb(location.pathname);

  return (
    <header
      className="h-16 sticky top-0 z-30 bg-[var(--cream)] border-b border-[var(--rule)] flex items-center px-5 gap-4"
      data-testid="topbar"
    >
      {/* Breadcrumb — left-anchored, editorial mono caps */}
      <nav
        className="min-w-0 flex items-center gap-1.5 flex-1"
        aria-label="Breadcrumb"
        data-testid="topbar-breadcrumb"
      >
        {crumbs.map((c, idx) => (
          <React.Fragment key={c.to}>
            {idx > 0 && <ChevronRight className="w-3 h-3 text-[var(--muted)] shrink-0" strokeWidth={1.7} />}
            <Link
              to={c.to}
              className={
                "akki-serif text-[14px] leading-none truncate transition-colors " +
                (idx === crumbs.length - 1
                  ? "text-[var(--ink)] font-medium"
                  : "text-[var(--muted)] hover:text-[var(--ink)]")
              }
              data-testid={`topbar-breadcrumb-${idx}`}
            >
              {c.label}
            </Link>
          </React.Fragment>
        ))}
      </nav>

      {/* Continue-with-doc pill — Tier-B persistent thread (unchanged
          from the old header). Hidden when there's no continue target. */}
      <ContinueWithPill />

      {/* Cmd+K launch — same dispatch as before. */}
      <button
        type="button"
        onClick={() => window.dispatchEvent(new CustomEvent("akki:open-search"))}
        className="hidden md:flex md:w-[240px] lg:w-[300px] items-center gap-2 px-3 py-1.5 text-[13px] bg-white hover:bg-[var(--cream-deep)] text-[var(--muted)] rounded-md transition-colors border border-[var(--rule)]"
        data-testid="topbar-global-search"
        aria-label="Open search (Cmd+K)"
      >
        <Search className="w-3.5 h-3.5 flex-shrink-0" strokeWidth={1.8} />
        <span className="akki-sans">Search</span>
        <kbd className="ml-auto text-[10px] font-mono bg-[var(--cream-deep)] px-1.5 py-0.5 rounded tracking-wider flex-shrink-0">⌘K</kbd>
      </button>

      <MentionInbox />
      <ReviewBadge />

      {/* Hero Doc Action — Add Document (Patch 2A). The button stays
          where users learned to find it; the modal mount stays on the
          shell. */}
      <button
        type="button"
        onClick={onOpenUpload}
        className="inline-flex items-center justify-center w-8 h-8 text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)] rounded-md transition-colors"
        aria-label="Add a document"
        title="Add a document"
        data-testid="topbar-add-document-btn"
      >
        <Plus className="w-4 h-4" strokeWidth={2} />
      </button>

      <button
        type="button"
        onClick={onOpenHelp}
        className="hidden md:inline-flex items-center justify-center w-8 h-8 text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)] rounded-md transition-colors"
        aria-label="Keyboard shortcuts"
        title="Keyboard shortcuts (?)"
        data-testid="topbar-keyboard-help-btn"
      >
        <Keyboard className="w-4 h-4" strokeWidth={1.7} />
      </button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            className="flex items-center gap-2 text-sm px-1.5 py-1 hover:bg-[var(--cream-deep)] rounded-md transition-colors"
            data-testid="topbar-account-menu-btn"
            aria-label="Account menu"
          >
            <div className="w-7 h-7 bg-[var(--navy)] text-white flex items-center justify-center text-xs font-bold rounded-full">
              {(account?.name || account?.email || "?").charAt(0).toUpperCase()}
            </div>
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64 rounded-md">
          <div className="px-3 py-3 border-b border-[var(--rule)]">
            <p className="text-sm font-medium text-[var(--ink)]">{account?.name}</p>
            <p className="text-xs text-[var(--muted)] truncate">{account?.email}</p>
          </div>
          <DropdownMenuItem onClick={() => navigate("/app/settings")} className="cursor-pointer" data-testid="topbar-nav-settings">
            <Settings className="w-4 h-4 mr-2" /> Settings
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => navigate("/app/security")} className="cursor-pointer" data-testid="topbar-nav-security">
            <Lock className="w-4 h-4 mr-2" /> Account security
          </DropdownMenuItem>
          <DropdownMenuItem onClick={onOpenTrust} className="cursor-pointer" data-testid="topbar-nav-trust">
            <ShieldCheck className="w-4 h-4 mr-2" /> Trust
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onClick={async () => { await logout(); navigate("/signin"); }}
            className="cursor-pointer text-red-600"
            data-testid="topbar-logout-btn"
          >
            <LogOut className="w-4 h-4 mr-2" /> Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
