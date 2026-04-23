import React, { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import Logo from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Home, FileText, Sparkles, GraduationCap,
  Settings, LogOut, ChevronDown, Layers, CheckCircle2, Lock,
  Briefcase, Landmark, Search, ScrollText, Target, Eye,
} from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import MentionInbox from "@/components/collab/MentionInbox";

// v3.0 — Six surfaces (BRD §13)
const NAV = [
  { to: "/app", label: "Home", icon: Home, end: true, ready: true },
  { to: "/app/workspace", label: "Workspace", icon: FileText, module: "M3", ready: true },
  { to: "/app/highlights", label: "Highlights", icon: Sparkles, module: "M5", ready: true },
  { to: "/app/briefings", label: "Briefings", icon: ScrollText, module: "M12", ready: true },
  { to: "/app/simulate", label: "Simulate", icon: Target, module: "M14", ready: true },
  { to: "/app/lens", label: "Lens Room", icon: Eye, module: "M14", ready: true },
  { to: "/app/learn", label: "Learn", icon: GraduationCap, module: "M9", ready: true },
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
      {/* Top chrome — cream, 64px, 1px rule border */}
      <header
        className="bg-[var(--cream)] text-[var(--ink)] border-b border-[var(--rule)] h-16 sticky top-0 z-40 flex items-center px-6 justify-between"
        data-testid="top-header"
      >
        <div className="flex items-center gap-8">
          <Link to="/app" data-testid="header-home-link" className="akki-serif text-[24px] text-[var(--navy)] leading-none tracking-tight">AKKI</Link>
          <div className="hidden md:flex items-center gap-1 text-[10px] tracking-[0.2em] uppercase text-[var(--muted)]">
            <span>Confidential</span>
            <span className="opacity-40">·</span>
            <span className="text-[var(--accent)]">Internal</span>
          </div>
        </div>

        <div className="flex items-center gap-5">
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

          {/* Role switcher (only if dual-capable) */}
          {showRoleSwitcher && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="flex items-center gap-2 px-3 py-1.5 text-sm text-[var(--deep)] hover:bg-[var(--cream-deep)] rounded-md transition-colors"
                  data-testid="role-switcher-btn"
                >
                  <RoleIcon className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
                  <span className="capitalize">{activeRole}</span>
                  <ChevronDown className="w-3.5 h-3.5 text-[var(--muted)]" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 rounded-md">
                <DropdownMenuLabel className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">Acting as</DropdownMenuLabel>
                {availableRoles.map((r) => (
                  <DropdownMenuItem
                    key={r}
                    onClick={() => handleRoleSwitch(r)}
                    className="cursor-pointer flex items-center justify-between"
                    data-testid={`role-switch-${r}`}
                  >
                    <span className="capitalize">{r === "ned" ? "Non-Executive Director" : r}</span>
                    {r === activeRole && <CheckCircle2 className="w-4 h-4 text-[var(--accent)]" />}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {/* Context switcher */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="flex items-center gap-2 px-3 py-1.5 text-[14px] text-[var(--deep)] hover:bg-[var(--cream-deep)] rounded-md transition-colors"
                data-testid="context-switcher-btn"
              >
                <Layers className="w-4 h-4 text-[var(--accent)]" strokeWidth={1.8} />
                <span className="max-w-[200px] truncate">{activeContext?.name || "—"}</span>
                {isSponsored && <span className="text-[9px] uppercase tracking-[0.2em] text-[var(--accent)]">sponsored</span>}
                <ChevronDown className="w-3.5 h-3.5 text-[var(--muted)]" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80 rounded-md">
              <DropdownMenuItem
                className="cursor-pointer"
                onClick={() => navigate("/app/contexts")}
                data-testid="context-portfolio-btn"
              >
                <Layers className="w-4 h-4 mr-2 text-[var(--accent)]" strokeWidth={1.8} />
                <span className="font-medium">View portfolio</span>
                <span className="ml-auto text-[10px] uppercase tracking-wider text-[var(--muted)]">{contexts.length}</span>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {groups.personal.length > 0 && (
                <>
                  <DropdownMenuLabel className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">Personal contexts</DropdownMenuLabel>
                  {groups.personal.map((c) => (
                    <DropdownMenuItem
                      key={c.id}
                      onClick={() => switchContext(c.id)}
                      className="flex items-center justify-between cursor-pointer"
                      data-testid={`context-switch-${c.id}`}
                    >
                      <div className="flex flex-col">
                        <span className="font-medium">{c.name}</span>
                        <span className="text-[10px] uppercase tracking-wider text-[var(--muted)]">
                          {CONTEXT_TYPE_LABEL[c.type] || c.type}
                        </span>
                      </div>
                      {c.id === activeContext?.id && <CheckCircle2 className="w-4 h-4 text-[var(--accent)]" />}
                    </DropdownMenuItem>
                  ))}
                </>
              )}
              {groups.sponsored.length > 0 && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuLabel className="text-[10px] uppercase tracking-[0.2em] text-[var(--accent)]">Sponsored contexts</DropdownMenuLabel>
                  {groups.sponsored.map((c) => (
                    <DropdownMenuItem
                      key={c.id}
                      onClick={() => switchContext(c.id)}
                      className="flex items-center justify-between cursor-pointer"
                      data-testid={`context-switch-${c.id}`}
                    >
                      <div className="flex flex-col">
                        <span className="font-medium">{c.name}</span>
                        <span className="text-[10px] uppercase tracking-wider text-[var(--accent)]">
                          {CONTEXT_TYPE_LABEL[c.type] || c.type}
                        </span>
                      </div>
                      {c.id === activeContext?.id && <CheckCircle2 className="w-4 h-4 text-[var(--accent)]" />}
                    </DropdownMenuItem>
                  ))}
                </>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="cursor-pointer text-[var(--accent)]"
                onClick={() => navigate("/app/contexts/new")}
                data-testid="create-context-btn"
              >
                + Add context →
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

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

      <div className="flex flex-1 min-h-0">
        {/* Left nav rail — cream, 220px, oxblood accent on selected */}
        <aside
          className="hidden md:flex flex-col bg-[var(--cream)] text-[var(--deep)] w-[220px] border-r border-[var(--rule)] pt-6 pb-8 gap-0.5"
          data-testid="left-sidebar"
        >
          <div className="px-5 pb-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]">Surfaces</p>
          </div>
          {NAV.map((item) => {
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
              <NavLink
                key={item.to}
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
                        isActive ? "bg-[var(--accent)] opacity-100" : "opacity-0"
                      }`}
                    />
                    <Icon className="w-4 h-4" strokeWidth={1.8} />
                    <span>{item.label}</span>
                  </>
                )}
              </NavLink>
            );
          })}

          <div className="mt-auto px-5 pt-8">
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
        <main className="flex-1 min-w-0">
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
                You're acting as <strong>{activeRole}</strong> but the current context is for <strong>{activeContext.my_role}</strong>.
                Switch to a matching context from the palette (⌘K) or role-switch again to auto-route.
              </span>
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
    </div>
  );
}
