/**
 * AppHome — dispatcher (Phase H.1 update, 2026-05-26).
 *
 *   /app  →
 *     • If account.declared_role is undeclared       → HomeUndeclared
 *     • Else, if there is NO active context          → ContextPortfolio (Portfolio Landing — Home 1)
 *     • Else                                         → Home2 (active-context home)
 *
 * H.1 change: the no-active-context branch was previously `Home1`
 * (legacy portfolio entry). It now routes to the redesigned
 * `ContextPortfolio` (Portfolio Landing) per the sketch-1 spec.
 *
 * /app/portfolio still renders the legacy Home1 for any external
 * bookmarks (back-compat alias). /app/companies is the canonical
 * route for the new Portfolio Landing.
 *
 * The FirstSessionGuard in App.js still bounces brand-new accounts to
 * /app/first-session before they reach this dispatcher.
 */
import React from "react";
import { useAuth } from "@/contexts/AuthContext";
import ContextPortfolio from "@/pages/ContextPortfolio";
import Home2 from "@/pages/home/Home2";
import HomeUndeclared from "@/pages/home/HomeUndeclared";

export default function AppHome() {
  const { account, activeContext } = useAuth();
  const role = (account?.declared_role || "undeclared").toLowerCase();

  if (role === "undeclared") return <HomeUndeclared />;
  if (!activeContext) return <ContextPortfolio />;
  return <Home2 />;
}
