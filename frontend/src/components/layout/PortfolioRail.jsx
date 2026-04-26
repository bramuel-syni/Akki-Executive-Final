import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { CheckCircle2, Layers, Plus, ChevronDown, ChevronUp, Briefcase, User as UserIcon } from "lucide-react";

const CONTEXT_TYPE_LABEL = {
  ned: "NED",
  executive: "Executive",
  exec: "Executive",
  cfo: "CFO",
  ceo: "CEO",
  personal: "Personal",
};

const ROLE_LABEL = {
  ned: "Non-Executive Director",
  executive: "Operating Executive",
};

/**
 * PortfolioRail — permanent right-side rail that shows the user's
 * portfolio of contexts with a green active dot, plus the role they're
 * currently acting as. Replaces the top-bar context/role dropdowns,
 * which the user found non-obvious.
 *
 * Sticky on every /app/* page. Width: 240px on desktop, collapses to a
 * thin strip on narrow screens.
 */
export default function PortfolioRail() {
  const navigate = useNavigate();
  const {
    activeContext, contexts, switchContext,
    activeRole, availableRoles, switchRole,
  } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  // Confirm dialog state — { kind: 'role'|'company', target: <id-or-role>, label }
  const [confirm, setConfirm] = useState(null);

  // Wrap role/company switches behind a confirm dialog so the user knows
  // exactly what they are about to change.
  const requestRoleSwitch = (role) => {
    if (role === activeRole) return;
    setConfirm({
      kind: "role",
      target: role,
      title: `Switching to ${ROLE_LABEL[role] || role}`,
      body: `You're about to switch from ${ROLE_LABEL[activeRole] || activeRole} to ${ROLE_LABEL[role] || role}. The companies in your portfolio will change to those you hold this role on. You'll need to pick a company to continue working.`,
    });
  };

  const requestContextSwitch = (cid, cname) => {
    if (cid === activeContext?.id) return;
    setConfirm({
      kind: "company",
      target: cid,
      title: `Switching company to ${cname}`,
      body: `Everything you see — Home, Monitor, Cycle, Workflows, Documents — will refresh to ${cname}. Your other companies stay sealed and untouched.`,
    });
  };

  const handleConfirm = async () => {
    if (!confirm) return;
    if (confirm.kind === "role") await switchRole(confirm.target);
    else if (confirm.kind === "company") await switchContext(confirm.target);
    setConfirm(null);
  };

  const handleRoleSwitch = requestRoleSwitch;

  const groups = useMemo(() => {
    const g = { personal: [], sponsored: [] };
    // Role-scoped: only show contexts where the user holds the active role.
    // If activeRole='ned', list NED boards; 'executive', list executive
    // contexts. This matches the user's mental model of "my portfolio" =
    // boards I'm NED on, OR companies I run, never the union.
    const filtered = (contexts || []).filter((c) => {
      if (!activeRole) return true;
      // my_role is canonical when present; fall back to context.type prefix
      // ('ned_personal' / 'executive_personal' / 'ned_sponsored' / 'executive_enterprise').
      const role = c.my_role || (c.type || "").split("_")[0];
      return role === activeRole;
    });
    for (const c of filtered) {
      if (c.kind === "sponsored" || c.is_sponsored
          || c.type === "ned_sponsored" || c.type === "executive_enterprise") g.sponsored.push(c);
      else g.personal.push(c);
    }
    return g;
  }, [contexts, activeRole]);

  const activeRoleLabel = activeRole === "ned" ? "Non-Executive Director" : (activeRole?.charAt(0).toUpperCase() + activeRole?.slice(1));

  return (
    <aside
      className={`hidden lg:flex flex-col fixed top-14 right-0 bottom-0 ${collapsed ? "w-12" : "w-[260px]"} bg-[var(--cream-deep)]/40 border-l border-[var(--rule)] transition-[width] duration-200 z-20`}
      data-testid="portfolio-rail"
    >
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="absolute -left-3 top-4 w-6 h-6 rounded-full bg-white border border-[var(--rule)] flex items-center justify-center hover:bg-[var(--cream)] z-30"
        data-testid="portfolio-rail-toggle"
        aria-label={collapsed ? "Expand portfolio rail" : "Collapse portfolio rail"}
      >
        {collapsed ? <ChevronDown className="w-3 h-3 -rotate-90" /> : <ChevronUp className="w-3 h-3 -rotate-90" />}
      </button>

      {collapsed ? (
        <div className="flex flex-col items-center pt-6 gap-3">
          <Briefcase className="w-4 h-4 text-[var(--accent)]" />
          <span className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted)]" style={{ writingMode: "vertical-rl" }}>Portfolio</span>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-5 py-6">
          {/* Acting as block */}
          {availableRoles?.length > 1 && (
            <section className="mb-7" data-testid="rail-acting-as">
              <p className="akki-overline mb-2.5">Acting as</p>
              <div className="flex flex-wrap gap-1.5">
                {availableRoles.map((r) => (
                  <button
                    key={r}
                    onClick={() => handleRoleSwitch(r)}
                    className={`px-2.5 py-1 text-[12px] rounded-full border transition-colors ${activeRole === r ? "bg-[var(--ink)] text-white border-[var(--ink)]" : "bg-white border-[var(--rule)] text-[var(--deep)] hover:border-[var(--accent)]/40"}`}
                    data-testid={`rail-role-${r}`}
                  >
                    {r === "ned" ? "NED" : r === "executive" ? "Exec" : r}
                  </button>
                ))}
              </div>
              <p className="text-[11.5px] text-[var(--muted)] italic mt-2">Currently {activeRoleLabel}.</p>
            </section>
          )}

          {/* Portfolio block */}
          <section data-testid="rail-portfolio">
            <div className="flex items-center justify-between mb-2.5">
              <p className="akki-overline">Your portfolio</p>
              <button
                onClick={() => navigate("/app/contexts")}
                className="text-[11px] text-[var(--accent)] hover:underline"
                data-testid="rail-view-all"
              >View all</button>
            </div>

            {groups.personal.length > 0 && (
              <ul className="space-y-1 mb-4">
                {groups.personal.map((c) => {
                  const isActive = c.id === activeContext?.id;
                  return (
                    <li key={c.id}>
                      <button
                        onClick={() => requestContextSwitch(c.id, c.name)}
                        className={`w-full text-left px-2.5 py-2 rounded-md transition-colors ${isActive ? "bg-white border border-[var(--accent)]/30" : "hover:bg-white"}`}
                        data-testid={`rail-context-${c.id}`}
                      >
                        <div className="flex items-start gap-2">
                          <span
                            className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${isActive ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" : "bg-transparent border border-[var(--muted)]/40"}`}
                            aria-label={isActive ? "Active company" : "Inactive company"}
                            data-testid={`rail-dot-${c.id}`}
                          />
                          <div className="flex-1 min-w-0">
                            <p className={`text-[13px] truncate ${isActive ? "text-[var(--ink)] font-medium" : "text-[var(--deep)]"}`}>{c.name}</p>
                            <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] mt-0.5">{CONTEXT_TYPE_LABEL[c.type] || c.type}</p>
                          </div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}

            {groups.sponsored.length > 0 && (
              <>
                <p className="akki-overline mb-2 text-[var(--accent)] text-[10px]">Sponsored</p>
                <ul className="space-y-1 mb-4">
                  {groups.sponsored.map((c) => {
                    const isActive = c.id === activeContext?.id;
                    return (
                      <li key={c.id}>
                        <button
                          onClick={() => requestContextSwitch(c.id, c.name)}
                          className={`w-full text-left px-2.5 py-2 rounded-md transition-colors ${isActive ? "bg-white border border-[var(--accent)]/30" : "hover:bg-white"}`}
                          data-testid={`rail-context-${c.id}`}
                        >
                          <div className="flex items-start gap-2">
                            <span
                              className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${isActive ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" : "bg-transparent border border-[var(--muted)]/40"}`}
                              data-testid={`rail-dot-${c.id}`}
                            />
                            <div className="flex-1 min-w-0">
                              <p className={`text-[13px] truncate ${isActive ? "text-[var(--ink)] font-medium" : "text-[var(--deep)]"}`}>{c.name}</p>
                              <p className="text-[10px] uppercase tracking-[0.18em] text-[var(--accent)] mt-0.5">{CONTEXT_TYPE_LABEL[c.type] || c.type}</p>
                            </div>
                          </div>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </>
            )}

            <button
              onClick={() => navigate("/app/contexts/new")}
              className="w-full text-left px-2.5 py-2 rounded-md text-[12.5px] text-[var(--accent)] hover:bg-white inline-flex items-center gap-2"
              data-testid="rail-add-context"
            >
              <Plus className="w-3.5 h-3.5" /> Add company
            </button>
          </section>
        </div>
      )}

      {/* Confirm dialog — fires on every role / company switch so the user
          knows exactly what they're about to change. */}
      <AlertDialog open={!!confirm} onOpenChange={(o) => { if (!o) setConfirm(null); }}>
        <AlertDialogContent data-testid="switch-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>{confirm?.title}</AlertDialogTitle>
            <AlertDialogDescription className="text-[13px] leading-relaxed pt-2">
              {confirm?.body}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="switch-confirm-cancel">Stay where I am</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirm}
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90"
              data-testid="switch-confirm-proceed"
            >
              {confirm?.kind === "role" ? "Switch role" : "Switch company"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </aside>
  );
}
