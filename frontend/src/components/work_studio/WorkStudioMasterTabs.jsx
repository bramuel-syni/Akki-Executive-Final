/**
 * Phase P5.14 — Work Studio master tabs.
 *
 * Two-pill switcher rendered at the top of every Work Studio page.
 * Mirrors the Monitor pill-tab pattern visible at
 * `pages/Monitor.jsx` ("STRATEGIC OBJECTIVES" / "TASKS"). Default
 * landing is "GENERATE DOCUMENTS" — the existing WorkStudio
 * surface. The "ANALYZE" pill links to the new Analyze tab built
 * in P5.14.
 *
 * The active pill is computed from `useLocation().pathname` so the
 * caller doesn't need to thread state through.
 */
import React from "react";
import { Link, useLocation } from "react-router-dom";

export default function WorkStudioMasterTabs() {
  const { pathname } = useLocation();
  const active = pathname.endsWith("/analyze") ? "analyze" : "generate";
  const pills = [
    { id: "generate", label: "GENERATE DOCUMENTS", to: "/app/work-studio" },
    { id: "analyze",  label: "ANALYZE",            to: "/app/work-studio/analyze" },
  ];
  return (
    <div
      data-testid="work-studio-master-tabs"
      className="mb-6 flex items-center gap-2 border-b border-[var(--rule)] pb-3"
    >
      {pills.map((p) => {
        const isActive = active === p.id;
        return (
          <Link
            key={p.id}
            to={p.to}
            data-testid={`ws-master-tab-${p.id}${isActive ? "-active" : ""}`}
            aria-current={isActive ? "page" : undefined}
            className={`px-4 py-1.5 rounded-full text-[11px] tracking-[0.14em] uppercase transition-colors ${
              isActive
                ? "bg-[color:var(--oxblood)] text-white"
                : "border border-[var(--rule)] text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            {p.label}
          </Link>
        );
      })}
    </div>
  );
}
