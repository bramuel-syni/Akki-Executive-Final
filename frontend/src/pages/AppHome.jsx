/**
 * AppHome — dispatcher (Phase I.1 update, 2026-05-27).
 *
 *   /app  →
 *     • If account.declared_role is undeclared       → HomeUndeclared
 *     • Else, if there is NO active context          → ContextPortfolio (Portfolio Landing)
 *     • Else                                         → CompanyHome (active-context home, Phase I.1)
 *
 * Phase H.5 (2026-05-27): `/app` is the canonical landing route. The
 * legacy `/app/portfolio`, `/app/companies`, `/app/contexts` routes
 * all 301-redirect to `/app` (see App.js). Home1 is archived.
 *
 * Phase I.1 (2026-05-27): the active-context branch now routes to
 * `CompanyHome` (the new design). The legacy `Home2.jsx` will be
 * archived in Phase I.6 once I.2–I.5 wire all data sources.
 *
 * The FirstSessionGuard in App.js still bounces brand-new accounts to
 * /app/first-session before they reach this dispatcher.
 */
import React from "react";
import { useAuth } from "@/contexts/AuthContext";
import ContextPortfolio from "@/pages/ContextPortfolio";
import CompanyHome from "@/pages/CompanyHome";
import HomeUndeclared from "@/pages/home/HomeUndeclared";

export default function AppHome() {
  const { account, activeContext } = useAuth();
  const role = (account?.declared_role || "undeclared").toLowerCase();

  if (role === "undeclared") return <HomeUndeclared />;
  if (!activeContext) return <ContextPortfolio />;
  return <CompanyHome />;
}
