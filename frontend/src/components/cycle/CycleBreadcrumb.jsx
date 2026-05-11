/**
 * CycleBreadcrumb — Layer 1 nav for inside a cycle.
 *
 * "Cycle Manager > [Cycle Title]". Clicking "Cycle Manager" navigates
 * to the list. Tab state preservation is handled by the parent route
 * via URL query params, so this component is purely cosmetic + click.
 */
import React from "react";
import { Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";


export default function CycleBreadcrumb({ title, status, onLeave }) {
  return (
    <nav
      aria-label="breadcrumb"
      className="flex items-center gap-2 text-[12.5px] font-mono mb-4"
      data-testid="cycle-breadcrumb"
    >
      <Link
        to="/app/cycle"
        onClick={onLeave}
        className="uppercase tracking-[0.12em] text-[var(--muted)] hover:text-[color:var(--oxblood)]"
        data-testid="cycle-breadcrumb-back-link"
      >
        Cycle Manager
      </Link>
      <ChevronRight className="w-3 h-3 text-[var(--muted)]" />
      <span
        className="text-[var(--ink)] truncate max-w-[480px]"
        data-testid="cycle-breadcrumb-title"
      >
        {title || "Untitled cycle"}
      </span>
      {status && status !== "active" && (
        <span
          className="ml-1 text-[10px] uppercase tracking-[0.14em] text-[var(--muted)]"
          data-testid="cycle-breadcrumb-status"
        >
          · {status}
        </span>
      )}
    </nav>
  );
}
