/**
 * LeftRail — Chunk 6.5 (2026-05-13).
 *
 * Persistent left-side navigation rail in the Claude-style.
 * Layout, top to bottom:
 *
 *   1. Workspace switcher card  — current workspace + role, click opens
 *      the same context dropdown the old top-bar pill used.
 *   2. Module list              — 9 items, order locked by the chunk
 *      brief: Home, Cycle Manager, Work Studio, Document Journal,
 *      Akki Chat, Monitor, Pulse, Learn, Questions.
 *   3. Recent items             — last 5 surfaces from
 *      /api/me/recent-views (Patch 3 endpoint).
 *   4. User profile + settings  — avatar + name + cog at the bottom.
 *
 * Collapse / expand: toggle button at the rail's top-right. State
 * persists in localStorage as `akki:leftRailCollapsed`. Auto-collapses
 * when the viewport drops below 1100px (matches the Compilation
 * Wizard rail breakpoint); the user's manual preference wins at
 * ≥1100px. No icon-only "click bait" tricks — every icon carries an
 * accessible label via `title` and `aria-label`.
 *
 * v7 palette only (no hex literals). Editorial posture: subtle
 * hovers, no glow, no garish colour. Active route gets the
 * cream-deep background + ink text + accent 3px left bar.
 */
import React, { useEffect, useState, useCallback } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Home, Send, Presentation, BookOpenCheck, MessageCircle, Activity,
  Sparkles, GraduationCap, HelpCircle, Settings, LogOut, ChevronsLeft,
  ChevronsRight, Building2, ChevronDown, CheckCircle2, History,
  ChevronRight,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { isSponsoredContext } from "@/lib/sponsorship";


// 9 modules — order locked by the Chunk 6.5 brief. The first item
// (`/app`) uses `end: true` so it doesn't match every nested route.
const MODULES = [
  { to: "/app",               label: "Home",             icon: Home,            end: true },
  { to: "/app/cycle",         label: "Cycle Manager",    icon: Send },
  { to: "/app/work-studio",   label: "Work Studio",      icon: Presentation },
  { to: "/app/workspace",     label: "Document Journal", icon: BookOpenCheck },
  { to: "/app/chat",          label: "Akki Chat",        icon: MessageCircle },
  { to: "/app/monitor",       label: "Monitor",          icon: Activity },
  { to: "/app/pulse",         label: "Pulse",            icon: Sparkles },
  { to: "/app/learn",         label: "Learn",            icon: GraduationCap },
  { to: "/app/questions",     label: "Questions",        icon: HelpCircle },
];

const STORAGE_KEY = "akki:leftRailCollapsed";
const AUTO_COLLAPSE_BREAKPOINT = 1100;

const ROLE_LABEL = {
  ned: "NED", executive: "Executive", reportee: "Reportee", member: "Member",
};

function readPersistedCollapsed() {
  try {
    if (typeof window === "undefined") return false;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;  // "no preference yet"
    return raw === "1";
  } catch {
    return null;
  }
}

function writePersistedCollapsed(value) {
  try {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
  } catch {
    /* ignore quota errors */
  }
}


export default function LeftRail() {
  const { account, activeContext, contexts, switchContext, logout } = useAuth();
  const navigate = useNavigate();

  // Manual user preference (null = unset / "use breakpoint default").
  const [userPref, setUserPref] = useState(readPersistedCollapsed);
  // Auto-collapse signal from the viewport.
  const [autoCollapsed, setAutoCollapsed] = useState(false);

  // Resolve effective state. If the user has explicitly chosen a state,
  // that wins at wide viewports. Below the breakpoint we ALWAYS collapse
  // (the rail is unusable at <1100px with full labels).
  const collapsed = autoCollapsed ? true : (userPref ?? false);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const recompute = () => setAutoCollapsed(window.innerWidth < AUTO_COLLAPSE_BREAKPOINT);
    recompute();
    window.addEventListener("resize", recompute);
    return () => window.removeEventListener("resize", recompute);
  }, []);

  const onToggle = useCallback(() => {
    setUserPref((prev) => {
      const next = !(prev ?? collapsed);
      writePersistedCollapsed(next);
      return next;
    });
  }, [collapsed]);

  return (
    <aside
      className={
        "shrink-0 hidden md:flex flex-col bg-[var(--cream)] border-r border-[var(--rule)] " +
        "sticky top-0 h-screen overflow-hidden transition-[width] duration-200 " +
        (collapsed ? "w-[64px]" : "w-[260px]")
      }
      data-testid="left-rail"
      data-collapsed={collapsed ? "1" : "0"}
      aria-label="Primary navigation"
    >
      <div className="flex items-center justify-between px-3 pt-4">
        {!collapsed && (
          <a
            href="/app"
            onClick={(e) => { e.preventDefault(); navigate("/app"); }}
            className="akki-serif text-[18px] text-[var(--navy)] tracking-tight inline-flex items-baseline gap-1.5"
            data-testid="left-rail-brand"
          >
            <span>AKKI</span>
            <span className="akki-serif italic text-[10.5px] text-[var(--muted)]">for Executives</span>
          </a>
        )}
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
          title={collapsed ? "Expand navigation" : "Collapse navigation"}
          className="inline-flex items-center justify-center w-7 h-7 rounded-md text-[var(--muted)] hover:text-[var(--ink)] hover:bg-[var(--cream-deep)] transition-colors"
          data-testid="left-rail-collapse-toggle"
        >
          {collapsed
            ? <ChevronsRight className="w-4 h-4" strokeWidth={1.7} />
            : <ChevronsLeft className="w-4 h-4" strokeWidth={1.7} />}
        </button>
      </div>

      <WorkspaceSwitcher
        collapsed={collapsed}
        activeContext={activeContext}
        contexts={contexts}
        switchContext={switchContext}
        account={account}
      />

      <nav
        className="flex-1 overflow-y-auto overflow-x-hidden py-2 px-2 space-y-0.5"
        aria-label="Modules"
      >
        {MODULES.map((m) => (
          <ModuleNavItem key={m.to} item={m} collapsed={collapsed} />
        ))}

        {!collapsed && <RecentSection />}
      </nav>

      <div className="border-t border-[var(--rule)] px-2 py-2">
        <UserBlock
          collapsed={collapsed}
          account={account}
          onSettings={() => navigate("/app/settings")}
          onSignOut={async () => { await logout(); navigate("/signin"); }}
        />
      </div>
    </aside>
  );
}


// ════════════════════════════════════════════════════════════════════
// Workspace switcher card (top of rail)
// ════════════════════════════════════════════════════════════════════
function WorkspaceSwitcher({ collapsed, activeContext, contexts, switchContext, account }) {
  const navigate = useNavigate();
  if (!activeContext) {
    // Pre-login or pre-context render. Defensive — should not normally hit.
    return null;
  }
  const role = activeContext.my_role || "member";
  const roleLabel = (account?.declared_role === "dual" && role === "executive")
    ? "Executive · NED"
    : (ROLE_LABEL[role] || role);
  const sponsored = isSponsoredContext(activeContext);

  if (collapsed) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="mx-2 mt-3 mb-2 inline-flex items-center justify-center w-10 h-10 rounded-md bg-[var(--cream-deep)] hover:bg-[var(--cream-deep)]/70 text-[var(--ink)] transition-colors"
            aria-label={`Workspace: ${activeContext.name}. Click to switch.`}
            title={`${activeContext.name} · ${roleLabel}`}
            data-testid="left-rail-workspace-switcher"
          >
            <Building2 className="w-4 h-4" strokeWidth={1.7} />
          </button>
        </DropdownMenuTrigger>
        <SwitcherDropdown
          activeContext={activeContext}
          contexts={contexts}
          switchContext={switchContext}
          navigate={navigate}
        />
      </DropdownMenu>
    );
  }

  return (
    <div className="mx-3 mt-3 mb-2">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="w-full text-left rounded-md bg-[var(--cream-deep)] hover:bg-[var(--cream-deep)]/70 border border-[var(--rule)] px-3 py-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
            data-testid="left-rail-workspace-switcher"
          >
            <div className="flex items-center gap-2">
              <Building2 className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" strokeWidth={1.7} />
              <span className="akki-serif text-[13.5px] text-[var(--ink)] truncate flex-1 leading-tight" data-testid="left-rail-workspace-name">
                {activeContext.name || "Untitled workspace"}
              </span>
              <ChevronDown className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" strokeWidth={1.7} />
            </div>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="text-[10px] uppercase tracking-[0.16em] font-mono text-[var(--muted)]" data-testid="left-rail-workspace-role">
                {roleLabel}
              </span>
              {sponsored && (
                <span className="text-[9.5px] uppercase tracking-[0.16em] font-mono text-[var(--accent)]">
                  · Sponsored
                </span>
              )}
            </div>
          </button>
        </DropdownMenuTrigger>
        <SwitcherDropdown
          activeContext={activeContext}
          contexts={contexts}
          switchContext={switchContext}
          navigate={navigate}
        />
      </DropdownMenu>
    </div>
  );
}


function SwitcherDropdown({ activeContext, contexts, switchContext, navigate }) {
  const groupedPersonal = [];
  const groupedSponsored = [];
  (contexts || []).forEach((c) => {
    if (isSponsoredContext(c)) groupedSponsored.push(c);
    else groupedPersonal.push(c);
  });
  return (
    <DropdownMenuContent
      align="start"
      sideOffset={4}
      className="w-[260px] rounded-md max-h-[480px] overflow-y-auto"
      data-testid="left-rail-workspace-switcher-menu"
    >
      {groupedPersonal.length > 0 && (
        <>
          <DropdownMenuLabel className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)]">
            Your workspaces
          </DropdownMenuLabel>
          {groupedPersonal.map((c) => (
            <SwitcherRow key={c.id} c={c} active={c.id === activeContext?.id} onPick={() => switchContext(c.id)} />
          ))}
        </>
      )}
      {groupedSponsored.length > 0 && (
        <>
          <DropdownMenuSeparator />
          <DropdownMenuLabel className="text-[10.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)]">
            Sponsored
          </DropdownMenuLabel>
          {groupedSponsored.map((c) => (
            <SwitcherRow key={c.id} c={c} active={c.id === activeContext?.id} onPick={() => switchContext(c.id)} />
          ))}
        </>
      )}
      <DropdownMenuSeparator />
      <DropdownMenuItem
        className="cursor-pointer"
        onClick={() => navigate("/app/manage?tab=companies")}
        data-testid="left-rail-workspace-manage"
      >
        Manage workspaces…
      </DropdownMenuItem>
    </DropdownMenuContent>
  );
}


function SwitcherRow({ c, active, onPick }) {
  return (
    <DropdownMenuItem
      onClick={onPick}
      className={"cursor-pointer flex items-start gap-2 " + (active ? "bg-[var(--cream-deep)]" : "")}
      data-testid={`left-rail-workspace-row-${c.id}`}
    >
      <div className="min-w-0 flex-1">
        <p className="text-[13px] text-[var(--ink)] truncate">{c.name || "Untitled"}</p>
        <p className="text-[10.5px] uppercase tracking-[0.14em] font-mono text-[var(--muted)] mt-0.5">
          {ROLE_LABEL[c.my_role] || c.my_role || "—"}
        </p>
      </div>
      {active && <CheckCircle2 className="w-3.5 h-3.5 text-[var(--accent)] mt-1 shrink-0" strokeWidth={2} />}
    </DropdownMenuItem>
  );
}


// ════════════════════════════════════════════════════════════════════
// Single module nav item — handles collapsed (icon-only) + expanded
// ════════════════════════════════════════════════════════════════════
function ModuleNavItem({ item, collapsed }) {
  const Icon = item.icon;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        [
          "relative flex items-center gap-3 rounded-md transition-colors group",
          collapsed ? "px-3 py-2.5 justify-center" : "px-3 py-2",
          isActive
            ? "bg-[var(--cream-deep)] text-[var(--ink)] font-medium"
            : "text-[var(--deep)] hover:bg-[var(--cream-deep)]/60 hover:text-[var(--ink)]",
        ].join(" ")
      }
      data-testid={`left-rail-nav-${item.label.toLowerCase().replace(/\s+/g, "-")}`}
      aria-label={item.label}
      title={collapsed ? item.label : undefined}
    >
      {({ isActive }) => (
        <>
          {isActive && (
            <span
              className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r bg-[var(--accent)]"
              aria-hidden="true"
            />
          )}
          <Icon className="w-4 h-4 shrink-0" strokeWidth={1.75} />
          {!collapsed && (
            <span className="text-[13.5px] leading-tight truncate">{item.label}</span>
          )}
        </>
      )}
    </NavLink>
  );
}


// ════════════════════════════════════════════════════════════════════
// Recent items section — fetches /me/recent-views
// ════════════════════════════════════════════════════════════════════
function RecentSection() {
  const [items, setItems] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let dead = false;
    api.get("/me/recent-views", { params: { limit: 5 } })
      .then(({ data }) => { if (!dead) { setItems(data?.items || []); setLoaded(true); } })
      .catch(() => { if (!dead) { setItems([]); setLoaded(true); } });
    return () => { dead = true; };
  }, []);

  if (loaded && items.length === 0) return null;

  return (
    <div className="mt-4 pt-4 border-t border-[var(--rule)]" data-testid="left-rail-recent-section">
      <p className="px-3 pb-1.5 text-[10px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] flex items-center gap-1.5">
        <History className="w-3 h-3" strokeWidth={1.7} />
        Recent
      </p>
      <ul className="space-y-0.5">
        {items.slice(0, 5).map((it, idx) => (
          <li key={`${it.surface_path || idx}-${idx}`}>
            <button
              type="button"
              onClick={() => navigate(it.surface_path)}
              className="w-full text-left px-3 py-1.5 rounded-md text-[12.5px] text-[var(--deep)] hover:bg-[var(--cream-deep)]/60 hover:text-[var(--ink)] transition-colors flex items-center gap-1.5"
              data-testid={`left-rail-recent-${idx}`}
              title={it.label || it.surface_path}
            >
              <ChevronRight className="w-3 h-3 text-[var(--muted)] shrink-0" strokeWidth={1.7} />
              <span className="truncate">{it.label || it.surface_path || "Untitled"}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}


// ════════════════════════════════════════════════════════════════════
// User block (bottom of rail) — avatar + name + settings cog
// ════════════════════════════════════════════════════════════════════
function UserBlock({ collapsed, account, onSettings, onSignOut }) {
  const initials = (account?.name || account?.email || "?").charAt(0).toUpperCase();
  if (collapsed) {
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-[var(--navy)] text-white font-bold text-[12px] hover:opacity-90 transition-opacity mx-auto"
            data-testid="left-rail-user-avatar"
            aria-label={account?.name || account?.email || "Account"}
            title={account?.name || account?.email || "Account"}
          >
            {initials}
          </button>
        </DropdownMenuTrigger>
        <UserDropdownContent account={account} onSettings={onSettings} onSignOut={onSignOut} />
      </DropdownMenu>
    );
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="w-full flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-[var(--cream-deep)]/60 transition-colors text-left"
          data-testid="left-rail-user-block"
        >
          <div className="w-8 h-8 rounded-full bg-[var(--navy)] text-white inline-flex items-center justify-center font-bold text-[12px] shrink-0">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[12.5px] text-[var(--ink)] truncate" data-testid="left-rail-user-name">{account?.name || "—"}</p>
            <p className="text-[10.5px] text-[var(--muted)] truncate">{account?.email || ""}</p>
          </div>
          <Settings className="w-3.5 h-3.5 text-[var(--muted)] shrink-0" strokeWidth={1.7} />
        </button>
      </DropdownMenuTrigger>
      <UserDropdownContent account={account} onSettings={onSettings} onSignOut={onSignOut} />
    </DropdownMenu>
  );
}


function UserDropdownContent({ account, onSettings, onSignOut }) {
  return (
    <DropdownMenuContent align="start" sideOffset={6} className="w-56 rounded-md">
      <div className="px-3 py-2 border-b border-[var(--rule)]">
        <p className="text-sm font-medium text-[var(--ink)]">{account?.name}</p>
        <p className="text-xs text-[var(--muted)] truncate">{account?.email}</p>
      </div>
      <DropdownMenuItem className="cursor-pointer" onClick={onSettings} data-testid="left-rail-user-settings">
        <Settings className="w-4 h-4 mr-2" /> Settings
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem className="cursor-pointer text-red-600" onClick={onSignOut} data-testid="left-rail-user-signout">
        <LogOut className="w-4 h-4 mr-2" /> Sign out
      </DropdownMenuItem>
    </DropdownMenuContent>
  );
}
