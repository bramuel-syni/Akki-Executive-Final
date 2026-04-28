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
  Settings, LogOut, ChevronDown, Layers, CheckCircle2, Lock,
  Briefcase, Landmark, Search, ScrollText, Target, Eye, Plus, BookOpenCheck,
  Users, Building2, ShieldCheck, Send, Compass, Activity, MessageCircle,
  Presentation,
} from "lucide-react";
import SandboxBanner from "@/components/sandbox/SandboxBanner";
import SandboxEmailCapture from "@/components/sandbox/SandboxEmailCapture";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import MentionInbox from "@/components/collab/MentionInbox";
import UploadModal from "@/components/upload/UploadModal";
import PortfolioRail from "@/components/layout/PortfolioRail";
import ContinueWithPill from "@/components/layout/ContinueWithPill";

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
const NAV = [
  { to: "/app", label: "Home", icon: Home, end: true, ready: true },
  { to: "/app/workspace", label: "Document Journal", icon: BookOpenCheck, module: "M3", ready: true },
  { to: "/app/chat", label: "Chat", icon: MessageCircle, module: "§15", ready: true },
  { to: "/app/prepare", label: "Prepare", icon: Sparkles, module: "M5+M12", ready: true },
  { to: "/app/decks", label: "Decks", icon: Presentation, module: "§17", ready: true },
  { to: "/app/plays", label: "Workflows", icon: Compass, module: "§13", ready: true,
    roles: ["executive"] },
  { to: "/app/lens", label: "The Lens (POV)", icon: Eye, module: "M14", ready: true },
  { to: "/app/simulate", label: "Test Hypothesis", icon: Target, module: "M14", ready: true },
  { to: "/app/cycle", label: "Reporting Cycle", icon: Send, module: "§12", ready: true,
    roles: ["executive"] },
  { to: "/app/monitor", label: "Monitor", icon: Activity, module: "§4", ready: true },
  { to: "/app/learn", label: "Learn", icon: GraduationCap, module: "M9", ready: true },
  { to: "/app/influence", label: "Influence Map", icon: Compass, module: "§16", ready: true },
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
    const bucket = c.type === "ned_sponsored" || c.type === "executive_enterprise" ? "sponsored" : "personal";
    groups[bucket].push(c);
  });
  return groups;
}

export default function AppShell({ children }) {
  const {
    account, activeContext, contexts, switchContext, logout,
    activeRole, availableRoles, switchRole,
  } = useAuth();
  const navigate = useNavigate();

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState("");
  const paletteInputRef = useRef(null);

  // Cmd/Ctrl+K opens the palette
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
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
          `No ${r === "ned" ? "NED" : "Executive"} context yet`,
          { description: "Create or accept an invite to set one up." }
        );
      }
    }
  };

  const mfaOwnerNudge = account && !account.mfa_enabled &&
    activeContext && activeContext.my_sub_role === "admin";

  const groups = groupContexts(contexts);
  const isSponsored = activeContext?.provisioning === "sponsored" ||
    activeContext?.type === "ned_sponsored" ||
    activeContext?.type === "executive_enterprise";

  const showRoleSwitcher = availableRoles.length > 1;
  const roleIcon = activeRole === "ned" ? Landmark : Briefcase;
  const RoleIcon = roleIcon;

  return (
    <div className="min-h-screen flex flex-col bg-[var(--cream)]">
      <SandboxBanner />
      <SandboxEmailCapture />
      {/* Top chrome — cream, 64px, 1px rule border */}
      <header
        className="relative bg-[var(--cream)] text-[var(--ink)] border-b border-[var(--rule)] h-16 sticky top-0 z-40 flex items-center px-6 justify-between"
        data-testid="top-header"
      >
        <div className="flex items-center gap-8">
          <Link to="/app" data-testid="header-home-link" className="flex items-baseline gap-2.5 leading-none">
            <span className="akki-serif text-[24px] text-[var(--navy)] tracking-tight">AKKI</span>
            <span className="hidden sm:inline akki-serif italic text-[13.5px] text-[var(--muted)] tracking-tight" data-testid="brand-subtitle">
              for Executives
            </span>
          </Link>
        </div>
        <div
          className="hidden md:flex absolute left-1/2 -translate-x-1/2 items-center gap-1 text-[10px] tracking-[0.2em] uppercase text-[var(--muted)] pointer-events-none"
          data-testid="trust-badge"
        >
          <span className="text-[var(--accent)]">Internal</span>
          <span className="opacity-40">·</span>
          <span>Secure</span>
          <span className="opacity-40">·</span>
          <span>Confidential</span>
        </div>

        <div className="flex items-center gap-5">
          {/* Continue-with-doc pill — Tier-B persistent thread back to the
              last document the executive opened in QuickResults. Hidden
              on surfaces where it would be redundant. */}
          <ContinueWithPill />

          {/* Cmd+K search */}
          <button
            className="hidden md:flex items-center gap-2 px-3 py-1.5 text-[13px] bg-white hover:bg-[var(--cream-deep)] text-[var(--muted)] rounded-md transition-colors border border-[var(--rule)]"
            onClick={() => setPaletteOpen(true)}
            data-testid="cmdk-launch-btn"
          >
            <Search className="w-3.5 h-3.5" strokeWidth={1.8} />
            <span className="akki-sans">Search</span>
            <kbd className="ml-2 text-[10px] font-mono bg-[var(--cream-deep)] px-1.5 py-0.5 rounded tracking-wider">⌘K</kbd>
          </button>

          {/* Mentions bell — pulls from /mentions endpoint */}
          <MentionInbox />

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

      {/* Permanent right-side portfolio rail — visible on every /app page,
          shows the user's contexts with a green active dot, and exposes
          role switcher inline. Self-positions via fixed; we add right
          padding to the main content below to keep the rail clear. */}
      <PortfolioRail />

      {/* Iter57 — Portfolio rail now defaults collapsed (12px sliver).
          Reclaiming ~250px of horizontal canvas for the main content
          column. The rail still self-positions via fixed; main column
          only reserves 48px (the collapsed sliver), expandable on click. */}
      <div className="flex flex-1 min-h-0 lg:pr-[48px]">
        {/* Left nav rail — cream, 220px, oxblood accent on selected */}
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
              title="Add a document to this context"
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
                    </>
                  )}
                </NavLink>
              </div>
            );
          })}

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
              className="flex items-center gap-2 px-8 py-2 bg-[var(--ink)]/5 border-b border-[var(--accent)]/30 text-xs text-[var(--ink)]"
              data-testid="sponsored-context-banner"
            >
              <span className="akki-overline">Sponsored context</span>
              <span className="text-slate-500">· Data ownership determined by the sponsoring organisation.</span>
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

      {/* Command palette — M1 stub: context switcher; becomes universal search in M7 */}
      <Dialog open={paletteOpen} onOpenChange={setPaletteOpen}>
        <DialogContent className="rounded-sm max-w-xl p-0 overflow-hidden">
          <DialogHeader className="sr-only">
            <DialogTitle>Command palette</DialogTitle>
            <DialogDescription>Switch context or search. Universal search unlocks at M7.</DialogDescription>
          </DialogHeader>
          <div className="flex items-center gap-3 border-b border-[#E1E6ED] px-4 py-3">
            <Search className="w-4 h-4 text-slate-400" strokeWidth={1.8} />
            <input
              ref={paletteInputRef}
              value={paletteQuery}
              onChange={(e) => setPaletteQuery(e.target.value)}
              placeholder="Switch context…  (universal search unlocks at M7)"
              className="flex-1 bg-transparent outline-none text-sm placeholder:text-slate-400"
              data-testid="palette-input"
            />
            <kbd className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-sm">esc</kbd>
          </div>
          <div className="max-h-80 overflow-y-auto py-2">
            <p className="px-4 py-1.5 text-[10px] uppercase tracking-[0.2em] text-slate-400">Contexts</p>
            {contexts
              .filter((c) => !paletteQuery || c.name.toLowerCase().includes(paletteQuery.toLowerCase()))
              .map((c) => {
                const active = c.id === activeContext?.id;
                return (
                  <button
                    key={c.id}
                    onClick={() => { switchContext(c.id); setPaletteOpen(false); }}
                    className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-slate-50 text-left group"
                    data-testid={`palette-switch-${c.id}`}
                  >
                    <div className="flex items-center gap-3">
                      <Layers className={`w-4 h-4 ${active ? "text-[var(--accent)]" : "text-slate-400"}`} strokeWidth={1.6} />
                      <div>
                        <p className="text-sm text-[var(--ink)] font-medium">{c.name}</p>
                        <p className="text-[10px] uppercase tracking-wider text-slate-400">
                          {c.my_role || "member"}
                          {c.provisioning === "sponsored" && <span className="ml-2 text-[var(--accent)]">sponsored</span>}
                        </p>
                      </div>
                    </div>
                    {active && <CheckCircle2 className="w-4 h-4 text-[var(--accent)]" />}
                  </button>
                );
              })}
            <p className="px-4 py-1.5 mt-2 text-[10px] uppercase tracking-[0.2em] text-slate-400">Actions</p>
            <button
              onClick={() => { setPaletteOpen(false); navigate("/app/contexts/new"); }}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 text-left"
              data-testid="palette-new-context-btn"
            >
              <Sparkles className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.6} />
              <span className="text-sm text-[var(--ink)]">Add a context…</span>
            </button>
            <button
              onClick={() => { setPaletteOpen(false); navigate("/app/settings"); }}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 text-left"
              data-testid="palette-settings-btn"
            >
              <Settings className="w-4 h-4 text-slate-400" strokeWidth={1.6} />
              <span className="text-sm text-[var(--ink)]">Open settings</span>
            </button>
          </div>
        </DialogContent>
      </Dialog>

      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploaded={() => {
          toast.success("Added to your Document Journal.");
          // Broadcast so whatever surface is open can re-fetch its doc list
          window.dispatchEvent(new CustomEvent("akki:document-uploaded"));
        }}
      />
    </div>
  );
}
