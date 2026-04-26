import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { CheckCircle2, Layers, Plus, ChevronDown, ChevronUp, Briefcase, User as UserIcon } from "lucide-react";

const CONTEXT_TYPE_LABEL = {
  ned: "NED",
  executive: "Executive",
  exec: "Executive",
  cfo: "CFO",
  ceo: "CEO",
  personal: "Personal",
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

  const handleRoleSwitch = switchRole;

  const groups = useMemo(() => {
    const g = { personal: [], sponsored: [] };
    for (const c of contexts || []) {
      if (c.kind === "sponsored" || c.is_sponsored) g.sponsored.push(c);
      else g.personal.push(c);
    }
    return g;
  }, [contexts]);

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
                        onClick={() => switchContext(c.id)}
                        className={`w-full text-left px-2.5 py-2 rounded-md transition-colors ${isActive ? "bg-white border border-[var(--accent)]/30" : "hover:bg-white"}`}
                        data-testid={`rail-context-${c.id}`}
                      >
                        <div className="flex items-start gap-2">
                          <span
                            className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${isActive ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" : "bg-transparent border border-[var(--muted)]/40"}`}
                            aria-label={isActive ? "Active context" : "Inactive context"}
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
                          onClick={() => switchContext(c.id)}
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
              <Plus className="w-3.5 h-3.5" /> Add context
            </button>
          </section>
        </div>
      )}
    </aside>
  );
}
