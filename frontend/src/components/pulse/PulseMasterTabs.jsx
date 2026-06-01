/**
 * Phase P5.15 — Pulse master tabs.
 *
 * Two-pill switcher rendered at the top of every Pulse page.
 * Mirrors the Monitor / Work Studio pattern. Default landing
 * stays on "SIGNALS" (the existing surface, untouched). The
 * "IDEAS BY AKKI" pill links to the new Ideas tab built in P5.15.
 *
 * The active pill is computed from `useLocation().pathname` so
 * the caller doesn't thread state through.
 */
import React from "react";
import { Link, useLocation } from "react-router-dom";

export default function PulseMasterTabs() {
  const { pathname } = useLocation();
  const active = pathname.endsWith("/ideas") ? "ideas" : "signals";
  const pills = [
    { id: "signals", label: "SIGNALS",        to: "/app/pulse" },
    { id: "ideas",   label: "IDEAS BY AKKI",  to: "/app/pulse/ideas" },
  ];
  return (
    <div
      data-testid="pulse-master-tabs"
      className="mb-6 flex items-center gap-2 border-b border-[var(--rule)] pb-3"
    >
      {pills.map((p) => {
        const isActive = active === p.id;
        return (
          <Link
            key={p.id}
            to={p.to}
            data-testid={`pulse-master-tab-${p.id}${isActive ? "-active" : ""}`}
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
