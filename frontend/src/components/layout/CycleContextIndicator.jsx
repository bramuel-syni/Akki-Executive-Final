/**
 * CycleContextIndicator — Phase 13.3 top-right context surface.
 *
 * Sits inside the AppShell primary nav row. Shows the user's currently
 * active context (board / company seat) with their role on it, and
 * lets them switch between any contexts they belong to via a
 * dropdown. The dropdown reuses the auth context's `switchContext`
 * method, so the switch propagates everywhere the active context is
 * read (Cycle Manager, Monitor, Work Studio, etc).
 *
 * Editorial: serif label for the context name (board-level identity),
 * mono caps for the role line (governance metadata convention used
 * across AKKI). One accent dot to mark the active row in the dropdown
 * — the rest stays cream/oxblood-restrained per UI/UX brief (max two
 * accent uses per screen).
 */
import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Building2, ChevronDown, CheckCircle2, Plus, Briefcase, Landmark } from "lucide-react";
import { isSponsoredContext } from "@/lib/sponsorship";

const ROLE_LABEL = {
  ned: "NED",
  executive: "Executive",
  reportee: "Reportee",
  member: "Member",
};

export default function CycleContextIndicator() {
  const { activeContext, contexts, switchContext } = useAuth();
  const navigate = useNavigate();

  if (!activeContext) {
    return (
      <button
        type="button"
        onClick={() => navigate("/app/contexts/new")}
        className="hidden md:flex items-center gap-2 px-3 h-9 text-[13px] text-[var(--muted)] hover:text-[var(--ink)] border border-[var(--rule)] rounded-md hover:bg-[var(--cream-deep)] transition-colors"
        data-testid="cycle-context-indicator-empty"
      >
        <Plus className="w-3.5 h-3.5" />
        Add a context
      </button>
    );
  }

  const role = activeContext.my_role || "member";
  const RoleIcon = role === "ned" ? Landmark : Briefcase;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="hidden md:flex items-center gap-2 px-3 h-9 text-[13px] text-[var(--ink)] border border-[var(--rule)] rounded-md hover:bg-[var(--cream-deep)] transition-colors max-w-[260px]"
          data-testid="cycle-context-indicator"
          aria-label="Switch active context"
        >
          <RoleIcon className="w-3.5 h-3.5 text-[var(--deep)]" strokeWidth={1.7} />
          <span className="akki-serif truncate">{activeContext.name}</span>
          <span className="text-[9.5px] uppercase tracking-[0.18em] font-mono text-[var(--muted)] ml-1 shrink-0">
            {ROLE_LABEL[role] || role}
          </span>
          <ChevronDown className="w-3 h-3 text-[var(--muted)]" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-72 rounded-md" data-testid="cycle-context-menu">
        <DropdownMenuLabel className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)] font-mono">
          Your contexts
        </DropdownMenuLabel>
        {(contexts || []).map((c) => {
          const active = c.id === activeContext.id;
          return (
            <DropdownMenuItem
              key={c.id}
              onClick={async () => {
                if (active) return;
                try {
                  await switchContext(c.id, { fromContextId: activeContext.id });
                  // Modal opens via AppShell; on dismiss the page reloads.
                } catch (e) {
                  // Defensive — server-side validation refused the
                  // switch (e.g. membership revoked between page load
                  // and click). The api.js interceptor has already
                  // emitted akki:rbac-error; we just stop here.
                  // eslint-disable-next-line no-console
                  console.warn("[switcher] switch refused:", e?.response?.data || e);
                }
              }}
              className="cursor-pointer flex items-center gap-2 py-2"
              data-testid={`cycle-context-switch-${c.id}`}
            >
              <Building2 className={`w-3.5 h-3.5 ${active ? "text-[var(--accent)]" : "text-[var(--muted)]"}`} />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] text-[var(--ink)] truncate">{c.name}</p>
                <p className="text-[10px] uppercase tracking-[0.16em] text-[var(--muted)] font-mono">
                  {ROLE_LABEL[c.my_role] || c.my_role || "member"}
                  {isSponsoredContext(c) && (
                    <span className="ml-1.5 text-[var(--accent)]">· sponsored</span>
                  )}
                </p>
              </div>
              {active && <CheckCircle2 className="w-3.5 h-3.5 text-[var(--accent)] shrink-0" />}
            </DropdownMenuItem>
          );
        })}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => navigate("/app/contexts/new")} className="cursor-pointer text-[13px]">
          <Plus className="w-3.5 h-3.5 mr-2" />
          Add a new context
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => navigate("/app/manage")} className="cursor-pointer text-[13px]">
          <Building2 className="w-3.5 h-3.5 mr-2" />
          Manage my contexts
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
