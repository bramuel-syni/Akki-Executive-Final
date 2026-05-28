/**
 * Wave 1.4 (2026-05-27) — Universal back button.
 *
 * Lives at the top-left of the page content area, above the H1.
 * Uses `useNavigate(-1)` (router history) so the destination is
 * whatever the user last visited, not a hard-coded link.
 *
 * Auto-hide rules:
 *   1. If current route is a top-level route (no useful "back"
 *      destination — Home, Sign-in, Landing, first-session intake,
 *      early-access opt-in), the button does not render.
 *   2. If the browser history has no prior entry (the user landed
 *      directly on this URL with no prior navigation), the button
 *      does not render. `window.history.length` is the conservative
 *      check — a single-entry history means there's nothing to go
 *      back to within the SPA session.
 *
 * Visual: monochrome chevron + "Back" label, muted, matches the
 * existing "Back to Portfolio" affordance used in CompanyHome.
 */
import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

// Routes that DO NOT show a back button. Match exact path or
// startswith for nested first-session/early-access flows.
//
// Item 6 redo (2026-02 fork-resume) — extended to include the 4
// top-level app surfaces that carry the sign-in-style side-panel
// hairline divider. The divider must touch the top horizontal nav
// rule with zero gap; the back-slot wrapper (with px-8 pt-4) was
// adding 51px of dead space above the page content even when the
// page is logically top-level. These 4 are reached via primary nav,
// not via deep navigation — back button adds no value here.
const TOP_LEVEL_ROUTES = [
  "/",
  "/sign-in",
  "/sign-up",
  "/app",
  "/app/portfolio",
  "/app/contexts",
  "/app/companies",
  "/app/first-session",
  "/app/early-access-opt-in",
  "/app/work-studio",
  "/app/task-manager",
];

function isTopLevelRoute(pathname) {
  if (TOP_LEVEL_ROUTES.includes(pathname)) return true;
  // Trim trailing slash for tolerance.
  const trimmed = pathname.replace(/\/$/, "");
  return TOP_LEVEL_ROUTES.includes(trimmed);
}

export default function BackButton({ className = "", testId = "back-button" }) {
  const navigate = useNavigate();
  const location = useLocation();

  if (isTopLevelRoute(location.pathname)) return null;
  // history.length === 1 means this is a direct/cold landing; no
  // useful back destination.
  if (typeof window !== "undefined" && window.history.length <= 1) return null;

  return (
    <button
      type="button"
      onClick={() => navigate(-1)}
      data-testid={testId}
      className={
        "inline-flex items-center gap-1.5 text-[12.5px] text-[var(--muted)] " +
        "hover:text-[var(--ink)] transition-colors mb-4 " +
        className
      }
    >
      <ArrowLeft className="w-3.5 h-3.5" strokeWidth={1.8} aria-hidden="true" />
      <span>Back</span>
    </button>
  );
}
