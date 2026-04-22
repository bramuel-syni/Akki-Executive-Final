import React from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import Logo from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import {
  Home, FileText, Sparkles, MessageSquareText, GraduationCap,
  Settings, LogOut, ChevronDown, Layers, CheckCircle2, Lock,
  Briefcase, Landmark,
} from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// v3.0 — Six surfaces (BRD §13)
const NAV = [
  { to: "/app", label: "Home", icon: Home, end: true, ready: true },
  { to: "/app/workspace", label: "Workspace", icon: FileText, module: "M8", ready: false },
  { to: "/app/highlights", label: "Highlights", icon: Sparkles, module: "M7", ready: false },
  { to: "/app/ask", label: "Ask", icon: MessageSquareText, module: "M7", ready: false },
  { to: "/app/learn", label: "Learn", icon: GraduationCap, module: "M9", ready: false },
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
    <div className="min-h-screen flex flex-col bg-[#FAFBFC]">
      {/* Top navy header */}
      <header
        className="bg-[#0A1F44] text-white border-b border-black/20 h-16 sticky top-0 z-40 flex items-center px-6 justify-between"
        data-testid="top-header"
      >
        <div className="flex items-center gap-8">
          <Link to="/app" data-testid="header-home-link"><Logo inverted /></Link>
          <div className="hidden md:flex items-center gap-1 text-[10px] tracking-[0.25em] uppercase text-white/40">
            <span>Confidential</span>
            <span className="text-white/20">·</span>
            <span className="text-[#C9A961]/80">Internal</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Role switcher (only if dual-capable) */}
          {showRoleSwitcher && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  className="flex items-center gap-2 px-3 py-1.5 text-sm bg-[#193262] hover:bg-[#1f3d73] rounded-sm transition-colors"
                  data-testid="role-switcher-btn"
                >
                  <RoleIcon className="w-4 h-4 text-[#C9A961]" strokeWidth={1.8} />
                  <span className="capitalize">{activeRole}</span>
                  <ChevronDown className="w-3.5 h-3.5 text-white/50" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 rounded-sm">
                <DropdownMenuLabel className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Acting as</DropdownMenuLabel>
                {availableRoles.map((r) => (
                  <DropdownMenuItem
                    key={r}
                    onClick={() => switchRole(r)}
                    className="cursor-pointer flex items-center justify-between"
                    data-testid={`role-switch-${r}`}
                  >
                    <span className="capitalize">{r === "ned" ? "Non-Executive Director" : r}</span>
                    {r === activeRole && <CheckCircle2 className="w-4 h-4 text-[#C9A961]" />}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}

          {/* Context switcher */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="flex items-center gap-2 px-3 py-1.5 text-sm bg-[#193262] hover:bg-[#1f3d73] rounded-sm transition-colors"
                data-testid="context-switcher-btn"
              >
                <Layers className="w-4 h-4 text-[#C9A961]" strokeWidth={1.8} />
                <span className="max-w-[180px] truncate">{activeContext?.name || "—"}</span>
                {isSponsored && <span className="text-[9px] uppercase tracking-[0.2em] text-[#C9A961]/80 ml-1">sponsored</span>}
                <ChevronDown className="w-3.5 h-3.5 text-white/50" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80 rounded-sm">
              {groups.personal.length > 0 && (
                <>
                  <DropdownMenuLabel className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Personal contexts</DropdownMenuLabel>
                  {groups.personal.map((c) => (
                    <DropdownMenuItem
                      key={c.id}
                      onClick={() => switchContext(c.id)}
                      className="flex items-center justify-between cursor-pointer"
                      data-testid={`context-switch-${c.id}`}
                    >
                      <div className="flex flex-col">
                        <span className="font-medium">{c.name}</span>
                        <span className="text-[10px] uppercase tracking-wider text-slate-400">
                          {CONTEXT_TYPE_LABEL[c.type] || c.type}
                        </span>
                      </div>
                      {c.id === activeContext?.id && <CheckCircle2 className="w-4 h-4 text-[#C9A961]" />}
                    </DropdownMenuItem>
                  ))}
                </>
              )}
              {groups.sponsored.length > 0 && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuLabel className="text-[10px] uppercase tracking-[0.2em] text-[#C9A961]">Sponsored contexts</DropdownMenuLabel>
                  {groups.sponsored.map((c) => (
                    <DropdownMenuItem
                      key={c.id}
                      onClick={() => switchContext(c.id)}
                      className="flex items-center justify-between cursor-pointer"
                      data-testid={`context-switch-${c.id}`}
                    >
                      <div className="flex flex-col">
                        <span className="font-medium">{c.name}</span>
                        <span className="text-[10px] uppercase tracking-wider text-[#C9A961]">
                          {CONTEXT_TYPE_LABEL[c.type] || c.type}
                        </span>
                      </div>
                      {c.id === activeContext?.id && <CheckCircle2 className="w-4 h-4 text-[#C9A961]" />}
                    </DropdownMenuItem>
                  ))}
                </>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="cursor-pointer"
                onClick={() => navigate("/app/contexts/new")}
                data-testid="create-context-btn"
              >
                + Add a context
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Account menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="flex items-center gap-2 text-sm pl-3 pr-2 py-1.5 hover:bg-[#193262] rounded-sm transition-colors"
                data-testid="account-menu-btn"
              >
                <div className="w-7 h-7 bg-[#C9A961] text-[#0A1F44] flex items-center justify-center text-xs font-bold rounded-sm">
                  {(account?.name || account?.email || "?").charAt(0).toUpperCase()}
                </div>
                <span className="hidden md:inline max-w-[140px] truncate">{account?.name || account?.email}</span>
                <ChevronDown className="w-3.5 h-3.5 text-white/50" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-64 rounded-sm">
              <div className="px-3 py-3 border-b">
                <p className="text-sm font-medium text-[#0A1F44]">{account?.name}</p>
                <p className="text-xs text-slate-500 truncate">{account?.email}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-[10px] uppercase tracking-wider text-slate-400">Role</span>
                  <span className="text-[10px] uppercase tracking-wider font-medium text-[#0A1F44]">
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
        {/* Left nav */}
        <aside
          className="hidden md:flex flex-col bg-[#0A1F44] text-white/80 w-60 border-r border-[#193262] pt-6 pb-8 gap-0.5"
          data-testid="left-sidebar"
        >
          <div className="px-5 pb-4">
            <p className="text-[10px] uppercase tracking-[0.25em] text-white/30">Surfaces</p>
          </div>
          {NAV.map((item) => {
            const Icon = item.icon;
            if (!item.ready) {
              return (
                <div
                  key={item.to}
                  className="mx-2 flex items-center gap-3 px-3 py-2.5 text-sm text-white/35 cursor-not-allowed border-l-2 border-transparent"
                  data-testid={`nav-${item.label.toLowerCase()}-locked`}
                  title={`Unlocks at ${item.module}`}
                >
                  <Icon className="w-4 h-4" strokeWidth={1.5} />
                  <span>{item.label}</span>
                  <span className="ml-auto text-[9px] uppercase tracking-widest text-white/25 bg-white/5 px-1.5 py-0.5 rounded-sm">
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
                  `mx-2 flex items-center gap-3 px-3 py-2.5 text-sm border-l-2 transition-colors rounded-sm ${
                    isActive
                      ? "bg-[#193262] text-white border-[#C9A961]"
                      : "text-white/70 hover:bg-[#193262]/60 hover:text-white border-transparent"
                  }`
                }
                data-testid={`nav-${item.label.toLowerCase()}`}
              >
                <Icon className="w-4 h-4" strokeWidth={1.8} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}

          <div className="mt-auto px-5 pt-8">
            <p className="text-[10px] uppercase tracking-[0.25em] text-white/30 mb-2">Administration</p>
            <NavLink
              to="/app/settings"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 text-sm border-l-2 transition-colors rounded-sm ${
                  isActive
                    ? "bg-[#193262] text-white border-[#C9A961]"
                    : "text-white/70 hover:bg-[#193262]/60 hover:text-white border-transparent"
                }`
              }
              data-testid="nav-settings"
            >
              <Settings className="w-4 h-4" strokeWidth={1.8} />
              <span>Settings</span>
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
          {isSponsored && (
            <div
              className="flex items-center gap-2 px-8 py-2 bg-[#0A1F44]/5 border-b border-[#C9A961]/30 text-xs text-[#0A1F44]"
              data-testid="sponsored-context-banner"
            >
              <span className="akki-overline">Sponsored context</span>
              <span className="text-slate-500">· Data ownership determined by the sponsoring organisation.</span>
            </div>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
