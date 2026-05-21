import React, { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
// Note: framer-motion was removed from this file iter50 — the staggered
// nav entrance caused a first-paint flash and added zero value after the
// initial visit. Plain divs render instantly.
import { useAuth } from "@/contexts/AuthContext";
import Logo from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Home, FileText, Sparkles, GraduationCap,
  Layers,
  Settings, LogOut, ChevronDown, CheckCircle2, Lock,
  Briefcase, Landmark, Search, ScrollText, Target, Eye, Plus, BookOpenCheck,
  Users, Building2, ShieldCheck, Send, Compass, Activity, MessageCircle,
  Presentation, Menu, X, Keyboard,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import MentionInbox from "@/components/collab/MentionInbox";
// QA-2026-05-16-009 (Chunk 15) — ReviewBadge import removed; the
// top-bar bell affordance was deleted. Component file kept at
// `@/components/layout/ReviewBadge.jsx` for forensic reference and
// potential future re-introduction; nothing in this file imports it.
import UploadModal from "@/components/upload/UploadModal";
// Patch 27 — PortfolioRail removed entirely.
import { isSponsoredContext } from "@/lib/sponsorship";
import ContinueWithPill from "@/components/layout/ContinueWithPill";
import ProPill from "@/components/depth/ProPill";
import { openUpgradeModal } from "@/components/depth/UpgradeModal";
import useDepthStatus from "@/hooks/useDepthStatus";
import TrustPanel from "@/components/governance/TrustPanel";
// Phase 13.3 — primary 8-item top nav, cycle context indicator, keyboard
// shortcuts. The legacy left-rail nav is no longer rendered (the brief
// said "Replace current nav with..."). Routes still exist; users land on
// them via the top nav, the command palette (⌘K), or direct URL.
import CycleContextIndicator from "@/components/layout/CycleContextIndicator";
import ContextSwitchModal from "@/components/layout/ContextSwitchModal";
import useKeyboardShortcuts from "@/hooks/useKeyboardShortcuts";
import KeyboardHelp from "@/components/layout/KeyboardHelp";
// Phase F0 — Universal Search replaces the F0.0 hijack where Cmd+K
// opened a company switcher disguised as search. The company switcher
// is now its own affordance (CompanySwitcherDialog) mounted alongside.
import UniversalSearchDialog from "@/components/search/UniversalSearchDialog";
import ConfirmContextSwitchModal from "@/components/search/ConfirmContextSwitchModal";
import CompanySwitcherDialog from "@/components/layout/CompanySwitcherDialog";


// Phase 13.3 — primary 8-item top nav. Order locked per UI/UX brief.
// "Pulse" is the Phase 14 surface; Phase 13.3 ships an honest holding
// page so users discover it during 13.x without 404'ing. "Work Studio"
// is a new unified entry hub, not a rebuild — it lists in-flight
// briefings/decks/reports across the active context.
//
// Phase 1 (2026-05-05) — "Document Journal" added to the primary nav.
// The page itself is `pages/Workspace.jsx` mounted at `/app/workspace`
// and was already shipped end-to-end (lists every doc the user can
// see, opens the M.2 in-app body modal, renders the Phase 1 backfilled
// `journal_commentary` inline). It just had no entry in the rendered
// top nav — only in the dead `NAV` array below — so testers couldn't
// find it. Inserted between Home and Chat so document workflows are
// adjacent to the home stream.
const TOP_NAV = [
  { to: "/app",               label: "Home",          end: true },
  // Phase E (MEMO Item 1, D-006) — "Document Journal" slot collapsed
  // to whitespace; entry-point lives on the Home page as the
  // `AllDocumentsButton` instead. Route /app/workspace still works
  // and renders the new journal listing + drawer pattern.
  { to: "/app/chat",          label: "Chat" },
  { to: "/app/solva",         label: "Solva" },
  { to: "/app/work-studio",   label: "Work Studio" },
  { to: "/app/cycle",         label: "Cycle Manager" },
  { to: "/app/monitor",       label: "Monitor" },
  { to: "/app/pulse",         label: "Pulse" },
  { to: "/app/learn",         label: "Learn" },
];

// Legacy left-rail surfaces. The arrays are retained because some
// existing code paths (depth gating, lookup helpers) still reference
// them; the rendering of the left aside has been removed in Phase 13.3.
// v3.0 — surfaces (BRD §13). The `roles` field scopes a nav entry
// to the role(s) that actually use it. Omit `roles` for surfaces both
// roles share. NEDs don't run reporting cycles on boards they sit on;
// they consume briefings + signals + monitor.
//
// Apr-2026 reorder + renames per user feedback:
//   The Lens → "The Lens (POV)"  ·  Simulate → "Test Hypothesis"
//   Cycle → "Reporting Cycle"
// Document Journal kept in primary nav as the doc surface (omitted from
// the user's explicit list but high-usage).
//
// Phase 6 / v1.6 — Lens / Simulate / Monitor / Influence Map pulled out
// into DEPTH_NAV and rendered beneath the base nav, only when the user's
// corpus threshold is met (see `useDepthStatus`). Routes stay URL-
// accessible regardless.
const NAV = [
  { to: "/app", label: "Home", icon: Home, end: true, ready: true },
  { to: "/app/workspace", label: "Document Journal", icon: BookOpenCheck, module: "M3", ready: true },
  { to: "/app/chat", label: "Chat", icon: MessageCircle, module: "§15", ready: true },
  { to: "/app/solva", label: "Solva", icon: Layers, module: "§18", ready: true,
    badge: "Preview" },
  // M.4: /app/prepare and /app/decks redirect-aliases retired. Direct
  // links to the canonical surfaces (Cycle Manager + Work Studio).
  { to: "/app/cycle?tab=briefs", label: "Boardpack", icon: ScrollText, module: "M3+M12", ready: true },
  { to: "/app/work-studio?view=decks", label: "Decks + Reports", icon: Presentation, module: "§17", ready: true },
  { to: "/app/cycle", label: "Reporting Cycle", icon: Send, module: "§12", ready: true,
    roles: ["executive"] },
  { to: "/app/learn", label: "Learn", icon: GraduationCap, module: "M9", ready: true },
];

// Depth surfaces — hidden until corpus threshold (3 docs OR 1 briefing)
// is crossed. The `pro` flag tells the shell to render a ProPill next to
// the nav label for free-plan users. URL routes stay accessible either
// way (bookmarks don't break).
const DEPTH_NAV = [
  { to: "/app/lens", label: "The Lens (POV)", icon: Eye, module: "M14", pro: true },
  { to: "/app/simulate", label: "Test Hypothesis", icon: Target, module: "M14", pro: true },
  { to: "/app/monitor", label: "Monitor", icon: Activity, module: "§4" },
  { to: "/app/influence", label: "Influence Map", icon: Compass, module: "§16" },
];

// Housekeeping shortcuts — surfaced just below Learn for low-ceremony access.
// Both deep-link to /app/manage and activate the matching tab.
const MANAGE_NAV = [
  { to: "/app/manage?tab=team", label: "Manage my team", icon: Users, match: "/app/manage" },
  { to: "/app/manage?tab=companies", label: "Manage my companies", icon: Building2, match: "/app/manage" },
];

const CONTEXT_TYPE_LABEL = {
  ned_personal: "NED · Personal",
  ned_sponsored: "NED · Sponsored",
  executive_personal: "Executive · Personal",
  executive_enterprise: "Executive · Enterprise",
};

function groupContexts(contexts) {
  const groups = { personal: [], sponsored: [] };
  contexts.forEach((c) => {
    groups[isSponsoredContext(c) ? "sponsored" : "personal"].push(c);
  });
  return groups;
}

export default function AppShell({ children }) {
  const {
    account, activeContext, contexts, switchContext, logout,
    activeRole, availableRoles, switchRole,
  } = useAuth();
  const navigate = useNavigate();
  const { status: depthStatus } = useDepthStatus();
  const depthEligible = !!depthStatus?.eligible;
  const isProPlan = (account?.plan || "free") !== "free";
  const [trustOpen, setTrustOpen] = useState(false);

  // CHAT sprint (2026-05-12) — surfaces nested inside AppShell (e.g.
  // Chat → AuditDialog) can request opening the Trust Panel by
  // dispatching the global event `akki:open-trust-panel`. No prop drilling.
  useEffect(() => {
    const handler = () => setTrustOpen(true);
    window.addEventListener("akki:open-trust-panel", handler);
    return () => window.removeEventListener("akki:open-trust-panel", handler);
  }, []);

  const [paletteOpen, setPaletteOpen] = useState(false);  // legacy state — kept only as a no-op fallback for any stale callers
  const [uploadOpen, setUploadOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState("");
  const paletteInputRef = useRef(null);
  // Phase F0 — when a search result lives in a foreign tenant, we
  // route it through the ConfirmContextSwitchModal. The search dialog
  // dispatches the candidate row up via `onCrossContextRequest`.
  const [searchPending, setSearchPending] = useState(null);
  // Phase 13.3 — keyboard help overlay + mobile drawer state.
  const [helpOpen, setHelpOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Phase 13.3 — global keyboard shortcuts hook (⌘K / ⌘J / ⌘S / ?).
  // Phase F0 — Cmd+K now opens UniversalSearchDialog. The dialog
  // listens for `akki:open-search`; the keyboard hook still fires
  // that event. We DO NOT mount the F0.0 hijack here anymore.
  useKeyboardShortcuts({ openHelp: () => setHelpOpen(true) });
  useEffect(() => {
    // Phase F0 — `akki:open-palette` no longer toggles a stub dialog
    // owned by AppShell. UniversalSearchDialog listens for both
    // `akki:open-search` (canonical) and `akki:open-palette` (legacy
    // alias) directly. We keep this listener as a defensive no-op
    // setter so `paletteOpen` state doesn't go stale — but it does
    // NOT control any visible UI.
    const onPaletteOpen = () => setPaletteOpen((v) => !v);
    window.addEventListener("akki:open-palette", onPaletteOpen);
    return () => window.removeEventListener("akki:open-palette", onPaletteOpen);
  }, []);

  // Phase M.1 — Home Quick Action cards and any other entry point
  // dispatches `akki:open-upload-modal` to open the shared UploadModal
  // owned by AppShell. Single modal instance, multiple triggers.
  useEffect(() => {
    const onOpenUpload = () => setUploadOpen(true);
    window.addEventListener("akki:open-upload-modal", onOpenUpload);
    return () => window.removeEventListener("akki:open-upload-modal", onOpenUpload);
  }, []);

  useEffect(() => {
    if (paletteOpen) setTimeout(() => paletteInputRef.current?.focus(), 50);
    else setPaletteQuery("");
  }, [paletteOpen]);

  // Role/context mismatch nudge
  const mismatched =
    activeRole && activeContext?.my_role &&
    activeRole !== activeContext.my_role &&
    // don't nag for 'reportee' since it's a different axis
    (activeRole === "ned" || activeRole === "executive") &&
    (activeContext.my_role === "ned" || activeContext.my_role === "executive");

  const handleRoleSwitch = (r) => {
    switchRole(r);
    // If current context doesn't match the new role, try to find one that does
    if (activeContext && activeContext.my_role !== r) {
      const match = contexts.find((c) => c.my_role === r);
      if (match) {
        switchContext(match.id);
        toast.success(`Switched to ${match.name} for your ${r === "ned" ? "NED" : "Executive"} role`);
      } else {
        toast.message(
          `No ${r === "ned" ? "NED" : "Executive"} company yet`,
          { description: "Create or accept an invite to set one up." }
        );
      }
    }
  };

  const mfaOwnerNudge = account && !account.mfa_enabled &&
    activeContext && activeContext.my_sub_role === "admin";

  const groups = groupContexts(contexts);
  const isSponsored = isSponsoredContext(activeContext);

  const showRoleSwitcher = availableRoles.length > 1;
  const roleIcon = activeRole === "ned" ? Landmark : Briefcase;
  const RoleIcon = roleIcon;

  return (
    <div className="min-h-screen flex flex-col bg-[var(--cream)]">
      {/* M.4: legacy SandboxBanner / SandboxEmailCapture removed —
          no live context now carries type='sandbox' (Sandbox v2 is
          pre-auth at /sandbox). */}
      {/* Top chrome — cream, 64px, 1px rule border. 2-region flex: left
          (logo + brand subtitle) / right (palette + nav controls).
          Phase 15.2: relocated the "Internal · Secure · Confidential"
          trust badge OUT of the top-bar centre and into the secondary
          nav row to the right of "Learn". The top bar centre is now
          intentionally empty so the AKKI logo + "for Executives" sit
          alone on the left, cleaner editorial spacing. */}
      <header
        className="bg-[var(--cream)] text-[var(--ink)] border-b border-[var(--rule)] h-16 sticky top-0 z-40 flex items-center gap-4 px-6 justify-between"
        data-testid="top-header"
      >
        {/* LEFT — logo */}
        <div className="flex items-center gap-8 flex-shrink-0">
          <Link to="/app" data-testid="header-home-link" className="flex items-baseline gap-2.5 leading-none">
            <span className="akki-serif text-[24px] text-[var(--navy)] tracking-tight">AKKI</span>
            <span className="hidden sm:inline akki-serif italic text-[13.5px] text-[var(--muted)] tracking-tight" data-testid="brand-subtitle">
              for Executives
            </span>
          </Link>
        </div>

        <div className="flex items-center gap-5 flex-shrink-0">
          {/* Continue-with-doc pill — Tier-B persistent thread back to the
              last document the executive opened in QuickResults. Hidden
              on surfaces where it would be redundant. */}
          <ContinueWithPill />

          {/* Cmd+K search — Phase F0: now opens UniversalSearchDialog,
              NOT the company switcher. Dispatching `akki:open-search`
              keeps AppShell free of the modal state.
              Phase-tidy 2026-05: widened from content-natural (~145px)
              to 280px @ md and 340px @ xl so the primary nav affordance
              reads as primary, not as an afterthought next to the bell.
              On viewports < md the button is hidden — Cmd+K still works. */}
          <button
            className="hidden md:flex md:w-[280px] xl:w-[340px] items-center gap-2 px-3 py-1.5 text-[13px] bg-white hover:bg-[var(--cream-deep)] text-[var(--muted)] rounded-md transition-colors border border-[var(--rule)]"
            onClick={() => window.dispatchEvent(new CustomEvent("akki:open-search"))}
            data-testid="cmdk-launch-btn"
          >
            <Search className="w-3.5 h-3.5 flex-shrink-0" strokeWidth={1.8} />
            <span className="akki-sans">Search</span>
            <kbd className="ml-auto text-[10px] font-mono bg-[var(--cream-deep)] px-1.5 py-0.5 rounded tracking-wider flex-shrink-0">⌘K</kbd>
          </button>

          {/* Mentions bell — pulls from /mentions endpoint */}
          <MentionInbox />

          {/* QA-2026-05-16-009 (2026-05-21, Chunk 15) — Daily Review bell
              REMOVED from the top bar. The QA author flagged the
              notification-bell sub-page reachable from this affordance
              for removal. The underlying /app/review route remains
              intact (direct URL access still works) — only the
              top-bar surface is gone, matching the verbatim spec
              "Remove the page below. User gets to this page by clicking
              on the bell icon on the top bar". A future cleanup can
              decide whether to remove the /app/review route + DailyReview
              page entirely if no other entry path consumes them. */}
          {/* Phase 13.3 — Cycle context indicator. Shows the active
              context + role; click opens a dropdown of all the user's
              contexts and switches scope. Hidden below md to keep the
              mobile header tidy; the mobile drawer surfaces it via the
              avatar menu instead. */}
          <CycleContextIndicator />

          {/* Phase M.1 → Chunk 6.5-REVISED (2026-05-13, Task A) —
              "Documents" button replaces the legacy `+` add-document
              icon. Routes to the Document Journal — same destination
              as the "All documents" CTA on Home 1 and Home 2. The
              upload modal (which the legacy `+` used to open
              directly) still surfaces from Home 1 / Home 2's
              "+ Add document" buttons, the workspace journal page
              itself, and the global `akki:open-upload-modal` event
              other surfaces can dispatch. We keep the event listener
              mounted in this shell so nothing breaks. */}
          <button
            type="button"
            onClick={() => navigate("/app/workspace")}
            className="inline-flex items-center gap-1.5 h-8 px-2.5 text-[12.5px] text-[var(--deep)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)] rounded-md transition-colors"
            aria-label="Open Document Journal"
            data-testid="topbar-documents-btn"
            title="Open Document Journal"
          >
            <BookOpenCheck className="w-4 h-4" strokeWidth={1.7} />
            <span className="hidden sm:inline">Documents</span>
          </button>

          {/* Phase 13.3 — discoverable shortcut overlay trigger. Press ?
              keyboard-side achieves the same; this gives mouse users a
              way to find the shortcuts list without trying random keys. */}
          <button
            type="button"
            onClick={() => setHelpOpen(true)}
            className="hidden md:inline-flex items-center justify-center w-8 h-8 text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)] rounded-md transition-colors"
            aria-label="Keyboard shortcuts"
            data-testid="keyboard-help-btn"
            title="Keyboard shortcuts (?)"
          >
            <Keyboard className="w-4 h-4" strokeWidth={1.7} />
          </button>

          {/* Phase 13.3 — mobile hamburger. Opens the slide-out drawer
              with the same 8 nav items below 1024px. */}
          <button
            type="button"
            onClick={() => setMobileNavOpen(true)}
            className="lg:hidden inline-flex items-center justify-center w-9 h-9 text-[var(--ink)] hover:bg-[var(--cream-deep)] rounded-md transition-colors"
            aria-label="Open navigation"
            data-testid="mobile-nav-trigger"
          >
            <Menu className="w-5 h-5" strokeWidth={1.7} />
          </button>

          {/* Role + context have moved to the permanent right-side
              PortfolioRail (more discoverable, indicates active context
              with a green dot). The top bar now stays minimal. */}

          {/* Account avatar */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="flex items-center gap-2 text-sm pl-2 pr-2 py-1 hover:bg-[var(--cream-deep)] rounded-md transition-colors"
                data-testid="account-menu-btn"
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
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--muted)]">Role</span>
                  <span className="text-[10px] uppercase tracking-wider font-medium text-[var(--deep)]">
                    {account?.declared_role === "dual"
                      ? "NED + Executive"
                      : account?.declared_role === "undeclared"
                        ? "Not declared"
                        : account?.declared_role}
                  </span>
                </div>
              </div>
              <DropdownMenuItem
                onClick={() => navigate("/app/settings")}
                className="cursor-pointer"
                data-testid="nav-settings-menu"
              >
                <Settings className="w-4 h-4 mr-2" /> Settings
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => navigate("/app/security")}
                className="cursor-pointer"
                data-testid="nav-security-menu"
              >
                <Lock className="w-4 h-4 mr-2" /> Account security
              </DropdownMenuItem>
              {/* Phase 7 / v1.7 — Trust panel entrypoint. Lives in the user
                  menu only (never the left rail) — system-utility feel. */}
              <DropdownMenuItem
                onClick={() => setTrustOpen(true)}
                className="cursor-pointer"
                data-testid="nav-trust-menu"
              >
                <ShieldCheck className="w-4 h-4 mr-2" /> Trust
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={async () => { await logout(); navigate("/signin"); }}
                className="cursor-pointer text-red-600"
                data-testid="logout-menu-btn"
              >
                <LogOut className="w-4 h-4 mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Phase 13.3 — primary 8-item top nav row. Sits directly under
          the existing 64px header. 64px tall, accent underline on
          active (never background fill), Georgia for labels per UI/UX
          brief. Hidden below 1024px (lg:flex) — mobile uses the
          hamburger drawer instead. */}
      <nav
        className="hidden lg:flex items-stretch h-[64px] bg-[var(--cream)] border-b border-[var(--rule)] sticky top-[64px] z-40"
        data-testid="primary-top-nav"
        aria-label="Primary"
      >
        <div className="max-w-[1400px] w-full mx-auto px-6 flex items-stretch gap-0">
          {TOP_NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              data-testid={`top-nav-${n.label.toLowerCase().replace(/\s+/g, "-")}`}
              className={({ isActive }) =>
                `akki-serif px-5 inline-flex items-center text-[14px] border-b-2 -mb-px transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cream)] ${
                  isActive
                    ? "border-[var(--accent)] text-[var(--ink)] font-medium"
                    : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
          {/* Phase 15.2 — classification chip relocated from the top bar
              centre slot into the nav row, right-anchored beside Learn.
              Now interactive: click navigates to /app/security (Trust
              Panel). Tooltip explains what the three labels mean. */}
          <button
            type="button"
            onClick={() => navigate("/app/security")}
            className="ml-auto self-center flex items-center gap-1 text-[10px] tracking-[0.2em] uppercase text-[var(--muted)] pl-4 pr-1 hover:text-[var(--ink)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--cream)] cursor-pointer"
            data-testid="trust-badge"
            aria-label="Open Trust & Governance panel"
            title="This session is classified INTERNAL. Transport is SECURE (TLS). Content is CONFIDENTIAL by default. Click for the full trust summary."
          >
            <span className="text-[var(--accent)]">Internal</span>
            <span className="opacity-40">·</span>
            <span>Secure</span>
            <span className="opacity-40">·</span>
            <span>Confidential</span>
          </button>
        </div>
      </nav>

      {/* Phase 13.3 — mobile slide-out drawer. Same 8 items, full-height
          on the right. Backdrop closes on click outside. */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" data-testid="mobile-nav-drawer">
          <div
            className="absolute inset-0 bg-[var(--ink)]/30"
            onClick={() => setMobileNavOpen(false)}
          />
          <aside className="absolute right-0 top-0 bottom-0 w-[280px] bg-[var(--cream)] border-l border-[var(--rule)] py-4 px-2 flex flex-col">
            <div className="flex items-center justify-between px-3 pb-2 mb-2 border-b border-[var(--rule)]">
              <p className="akki-overline">Navigation</p>
              <button
                type="button"
                onClick={() => setMobileNavOpen(false)}
                aria-label="Close navigation"
                className="w-8 h-8 inline-flex items-center justify-center text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)] rounded-md"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            {TOP_NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                onClick={() => setMobileNavOpen(false)}
                className={({ isActive }) =>
                  `akki-serif px-4 py-3 text-[15px] rounded-md mx-1 transition-colors border-l-2 ${
                    isActive
                      ? "border-[var(--accent)] text-[var(--ink)] bg-[var(--cream-deep)]/40 font-medium"
                      : "border-transparent text-[var(--deep)] hover:bg-[var(--cream-deep)]/40 hover:text-[var(--ink)]"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </aside>
        </div>
      )}

      {/* Patch 27 — PortfolioRail removed entirely. The workspace
          switcher in the top bar is now the single canonical way to
          switch contexts; the right-side rail was redundant and
          visually intrusive (user feedback). Home 1 portfolio chips
          (`/app/portfolio`) remain the explicit portfolio surface for
          multi-company navigation.
          Main content now flows full-width to the outer gutter — no
          `pr-[48px]` reservation. */}
      <div className="flex flex-1 min-h-0">
        {/* (Phase 13.3) Left nav rail intentionally not rendered. The
            <aside> tree below stays for code-archaeology reference but
            is now wrapped in a `false` guard. */}
        {false && (
        <aside
          className="hidden md:flex flex-col bg-[var(--cream)] text-[var(--deep)] w-[220px] border-r border-[var(--rule)] pt-6 pb-8 gap-0.5"
          data-testid="left-sidebar"
        >
          {/* Primary action — upload to Document Journal. Styled to feel like
              Google Drive's "+ New" button: oxblood pill, sits above nav,
              never recedes into the surface list. */}
          <div className="px-4 pb-4">
            <button
              onClick={() => setUploadOpen(true)}
              className="w-full flex items-center justify-center gap-2 bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white rounded-full h-10 px-4 shadow-sm transition-all text-[13px] font-medium"
              data-testid="sidebar-upload-btn"
              title="Add a document to this company"
            >
              <Plus className="w-4 h-4" strokeWidth={2.4} />
              Add document
            </button>
          </div>
          <div className="px-5 pb-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">Surfaces</p>
          </div>
          {NAV
            .filter((item) => !item.roles || item.roles.includes(activeRole))
            .map((item, idx) => {
            const Icon = item.icon;
            if (!item.ready) {
              return (
                <div
                  key={item.to}
                  className="mx-2 flex items-center gap-3 px-3 py-2.5 text-[14px] text-[var(--muted)]/70 cursor-not-allowed rounded-sm"
                  data-testid={`nav-${item.label.toLowerCase()}-locked`}
                  title={`Unlocks at ${item.module}`}
                >
                  <Icon className="w-4 h-4" strokeWidth={1.5} />
                  <span>{item.label}</span>
                  <span className="ml-auto text-[9px] uppercase tracking-widest text-[var(--muted)]/60 bg-[var(--cream-deep)] px-1.5 py-0.5 rounded-sm">
                    {item.module}
                  </span>
                </div>
              );
            }
            return (
              <div key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `group mx-2 relative flex items-center gap-3 px-3 py-2.5 text-[14px] transition-colors rounded-sm ${
                      isActive
                        ? "bg-[var(--cream-deep)] text-[var(--ink)] font-medium"
                        : "text-[var(--deep)] hover:bg-[var(--cream-deep)] hover:text-[var(--ink)]"
                    }`
                  }
                  data-testid={`nav-${item.label.toLowerCase()}`}
                >
                  {({ isActive }) => (
                    <>
                      <span
                        className={`absolute left-0 top-1 bottom-1 w-[3px] rounded-r transition-opacity ${
                          isActive ? "bg-[var(--chrome)] opacity-100" : "opacity-0"
                        }`}
                      />
                      <Icon className="w-4 h-4" strokeWidth={1.8} />
                      <span>{item.label}</span>
                      {item.badge && (
                        <span
                          className="ml-auto text-[9px] uppercase tracking-[0.16em] px-1.5 py-0.5 rounded-sm bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/25"
                          data-testid={`nav-${item.label.toLowerCase()}-badge`}
                        >
                          {item.badge}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              </div>
            );
          })}

          {/* Phase 6 / v1.6 — Depth disclosure. Lens / Simulate / Monitor /
              Influence Map hidden until the user crosses the corpus
              threshold (3 docs OR 1 briefing). Once eligible, the four
              items appear under a "DEPTH" divider. Pro-gated items (Lens,
              Simulate) render a ProPill to the right of the label for
              free-plan users; clicking the link for a Pro item on the
              free plan intercepts the navigation and opens the upgrade
              modal instead. Routes remain URL-accessible regardless. */}
          {depthEligible && (
            <>
              <div className="px-5 pt-6 pb-2" data-testid="nav-depth-section">
                <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">Depth</p>
              </div>
              {DEPTH_NAV.map((item) => {
                const Icon = item.icon;
                const proBlocked = item.pro && !isProPlan;
                return (
                  <div key={item.to}>
                    <NavLink
                      to={item.to}
                      onClick={(e) => {
                        if (proBlocked) {
                          e.preventDefault();
                          openUpgradeModal(`nav-${item.label}`);
                        }
                      }}
                      className={({ isActive }) =>
                        `group mx-2 relative flex items-center gap-3 px-3 py-2.5 text-[14px] transition-colors rounded-sm ${
                          isActive
                            ? "bg-[var(--cream-deep)] text-[var(--ink)] font-medium"
                            : "text-[var(--deep)] hover:bg-[var(--cream-deep)] hover:text-[var(--ink)]"
                        }`
                      }
                      data-testid={`nav-depth-${item.label.toLowerCase()}`}
                    >
                      {({ isActive }) => (
                        <>
                          <span
                            className={`absolute left-0 top-1 bottom-1 w-[3px] rounded-r transition-opacity ${
                              isActive ? "bg-[var(--chrome)] opacity-100" : "opacity-0"
                            }`}
                          />
                          <Icon className="w-4 h-4" strokeWidth={1.8} />
                          <span>{item.label}</span>
                          {item.pro && !isProPlan && (
                            <ProPill className="ml-auto" />
                          )}
                        </>
                      )}
                    </NavLink>
                  </div>
                );
              })}
            </>
          )}

          {/* Housekeeping — sits below Learn, same accent treatment, labelled
              as a secondary block so it doesn't compete with the six core
              surfaces. Both items deep-link to /app/manage with the matching
              tab. */}
          <div className="px-5 pt-6 pb-2">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">Housekeeping</p>
          </div>
          {MANAGE_NAV.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) => {
                    // Match on pathname since query-string tabs are sibling targets.
                    const active = isActive || (typeof window !== "undefined" && window.location.pathname === item.match);
                    return `group mx-2 relative flex items-center gap-3 px-3 py-2.5 text-[14px] transition-colors rounded-sm ${
                      active
                        ? "bg-[var(--cream-deep)] text-[var(--ink)] font-medium"
                        : "text-[var(--deep)] hover:bg-[var(--cream-deep)] hover:text-[var(--ink)]"
                    }`;
                  }}
                  data-testid={`nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
                >
                  {() => {
                    const active = typeof window !== "undefined" &&
                      window.location.pathname === item.match &&
                      window.location.search.includes(item.to.split("?")[1] || "");
                    return (
                      <>
                        <span
                          className={`absolute left-0 top-1 bottom-1 w-[3px] rounded-r transition-opacity ${
                            active ? "bg-[var(--chrome)] opacity-100" : "opacity-0"
                          }`}
                        />
                        <Icon className="w-4 h-4" strokeWidth={1.8} />
                        <span>{item.label}</span>
                      </>
                    );
                  }}
                </NavLink>
              </div>
            );
          })}

          <div className="mt-auto px-5 pt-8">
            {(() => {
              const t = activeContext?.type;
              const isPersonal = t === "ned_personal" || t === "executive_personal";
              if (!isPersonal) return null;
              return (
                <NavLink
                  to="/app/enterprise"
                  className="block mb-3 px-3 py-2.5 rounded-sm border border-[var(--accent)]/30 bg-[var(--accent)]/[0.04] hover:bg-[var(--accent)]/[0.08] transition-colors"
                  data-testid="nav-enterprise-upsell"
                >
                  <div className="text-[10px] uppercase tracking-[0.18em] text-[var(--accent)] font-medium">
                    Akki for Enterprise
                  </div>
                  <div className="text-[12px] text-[var(--deep)] mt-0.5 leading-snug">
                    Sponsored seats, audit-grade exports, SSO →
                  </div>
                </NavLink>
              );
            })()}
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] mb-2">Administration</p>
            <NavLink
              to="/app/settings"
              className={({ isActive }) =>
                `relative flex items-center gap-3 px-3 py-2.5 text-[14px] transition-colors rounded-sm ${
                  isActive
                    ? "bg-[var(--cream-deep)] text-[var(--ink)] font-medium"
                    : "text-[var(--deep)] hover:bg-[var(--cream-deep)] hover:text-[var(--ink)]"
                }`
              }
              data-testid="nav-settings"
            >
              {({ isActive }) => (
                <>
                  <span className={`absolute left-0 top-1 bottom-1 w-[3px] rounded-r transition-opacity ${isActive ? "bg-[var(--accent)] opacity-100" : "opacity-0"}`} />
                  <Settings className="w-4 h-4" strokeWidth={1.8} />
                  <span>Settings</span>
                </>
              )}
            </NavLink>
          </div>
        </aside>
        )}

        {/* Main content */}
        <main className="flex-1 min-w-0 flex flex-col min-h-[calc(100vh-4rem)]">
          {mfaOwnerNudge && (
            <div
              className="flex items-center justify-between px-8 py-2.5 bg-amber-50/70 border-b border-amber-200 text-amber-900 text-xs"
              data-testid="mfa-owner-nudge"
            >
              <span>
                <strong className="font-semibold">Security recommended:</strong> Enable MFA to protect your account and this context.
              </span>
              <Button
                size="sm" variant="outline"
                className="rounded-sm h-7 border-amber-300 text-amber-900 hover:bg-amber-100"
                onClick={() => navigate("/app/security")}
                data-testid="enable-mfa-nudge-btn"
              >
                Enable MFA
              </Button>
            </div>
          )}
          {mismatched && (
            <div
              className="flex items-center gap-3 px-8 py-2 bg-[var(--ink)]/5 border-b border-[var(--ink)]/20 text-xs text-[var(--ink)]"
              data-testid="role-mismatch-banner"
            >
              <span className="akki-overline">Heads up</span>
              <span className="text-slate-600">
                You're acting as <strong>{activeRole}</strong> but <strong>{activeContext.name}</strong> is a <strong>{activeContext.my_role === "ned" ? "NED" : "Executive"}</strong> context.
              </span>
              <button
                type="button"
                onClick={() => {
                  const target = activeContext.my_role;
                  switchRole(target);
                  toast.success(`Now acting as ${target === "ned" ? "NED" : "Executive"} on ${activeContext.name}.`);
                }}
                className="ml-auto inline-flex items-center gap-1.5 px-3 py-1 text-[11.5px] font-medium bg-[var(--chrome)] text-white hover:bg-[var(--chrome)]/90 rounded-sm transition-colors"
                data-testid="role-mismatch-fix-btn"
              >
                Act as {activeContext.my_role === "ned" ? "NED" : "Executive"}
              </button>
            </div>
          )}
          {isSponsored && (
            <div
              className="flex items-center gap-2 px-8 py-2 bg-[var(--ink)]/5 border-b border-[var(--accent)]/30 text-xs text-[var(--muted)]"
              data-testid="sponsored-context-banner"
            >
              <span>Sponsored. Your data stays with the sponsoring company.</span>
            </div>
          )}
          {children}

          {/* Trust footer — low-weight, persistent line that reinforces
              AKKI's data posture on every page. Editorial mono, muted tone,
              reads like a masthead colophon rather than marketing copy. */}
          <footer
            className="border-t border-[var(--rule)] bg-[var(--cream-deep)]/60 px-8 py-3 mt-auto flex flex-wrap items-center gap-x-5 gap-y-1 text-[10.5px] text-[var(--muted)] font-mono uppercase tracking-wider"
            data-testid="trust-footer"
          >
            <span className="inline-flex items-center gap-1.5 text-[var(--deep)]">
              <ShieldCheck className="w-3 h-3 text-[var(--chrome)]" strokeWidth={2} />
              Synisense-shielded
            </span>
            <span>· Your data never leaves this account</span>
            <span className="hidden md:inline">· Every signal cites its source</span>
            <button
              type="button"
              onClick={() => navigate("/app/settings?tab=trust")}
              className="ml-auto hover:text-[var(--ink)] transition-colors cursor-pointer bg-transparent border-0 p-0 m-0 font-mono uppercase tracking-wider text-[10.5px] text-[var(--muted)]"
              data-testid="trust-footer-link"
            >
              Trust centre →
            </button>
          </footer>
        </main>
      </div>

      {/* Phase F0 — Universal Search.
          • UniversalSearchDialog listens for `akki:open-search` (canonical)
            and `akki:open-palette` (legacy alias). Opened by the top-nav
            "Search ⌘K" button and the global Cmd+K keyboard shortcut.
          • Cross-context result clicks bubble up via onCrossContextRequest;
            ConfirmContextSwitchModal names BOTH companies before any
            tenant switch happens — no silent hijack.
          • CompanySwitcherDialog is the moved F0.0 hijack body, now reachable
            only via `akki:open-company-switcher` (Cmd+Shift+K) and is
            independent of the search input. The day-to-day affordance to
            switch company remains the CycleContextIndicator dropdown above. */}
      <UniversalSearchDialog onCrossContextRequest={(row) => setSearchPending({
        from_context_id: activeContext?.id,
        from_context_name: activeContext?.name,
        to_context_id: row.context_id,
        to_context_name: row.context_name,
        surface: row.surface,
        result_id: row.id,
        deep_link: row.deep_link,
        type: row.type,
      })} />
      <ConfirmContextSwitchModal pending={searchPending} onClose={() => setSearchPending(null)} />
      <CompanySwitcherDialog />

      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={(doc) => {
          toast.success("Added to your Document Journal.");
          // Broadcast so whatever surface is open can re-fetch its doc list
          window.dispatchEvent(new CustomEvent("akki:document-uploaded"));
          // Phase M.1 — route the user straight to the Reading Viewer
          // for the new doc so the upload feels finished, not "where did
          // it go?". UploadModal already calls onClose() before this.
          if (doc?.id) {
            navigate(`/app/documents/${doc.id}`);
          }
        }}
      />

      {/* Phase 7 / v1.7 — Trust panel. Mounted once at the shell level so
          it persists across menu opens/closes. */}
      <TrustPanel open={trustOpen} onOpenChange={setTrustOpen} />

      {/* Phase 13.3 — keyboard shortcut help overlay. Toggled via ? key
          (handled by useKeyboardShortcuts) and the inline keyboard
          button in the header (mouse path). */}
      <KeyboardHelp open={helpOpen} onOpenChange={setHelpOpen} />

      {/* Phase A (Memo Item 5) — verbatim memo switch-modal. Mounted
          here so it can render over any /app surface without coupling
          to a specific page. Driven by AuthContext.pendingSwitchModal. */}
      <ContextSwitchModal />
    </div>
  );
}
