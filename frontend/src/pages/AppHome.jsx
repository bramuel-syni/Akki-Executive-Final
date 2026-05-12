/**
 * AppHome — Patch 3 dispatcher.
 *
 *   /app  →
 *     • If account.declared_role is undeclared → HomeUndeclared (unchanged)
 *     • Else, if there is NO active context → Home1 (portfolio entry)
 *     • Else                                → Home2 (active-context home)
 *
 * /app/portfolio always renders Home1 (the explicit "Back to portfolio"
 * affordance from Home 2 routes here).
 *
 * Legacy role-specific homes (HomeNed / HomeExecutive / HomeDual) were
 * deleted in Patch 17 after the LEGACY_HOME_PARITY audit confirmed all
 * sections were either preserved on Home 2 or relocated to a dedicated
 * route (NedInbox / NedMeeting / Pulse).
 *
 * The FirstSessionGuard in App.js still bounces brand-new accounts to
 * /app/first-session before they reach this dispatcher.
 */
import React from "react";
import { useAuth } from "@/contexts/AuthContext";
import Home1 from "@/pages/home/Home1";
import Home2 from "@/pages/home/Home2";
import HomeUndeclared from "@/pages/home/HomeUndeclared";

export default function AppHome() {
  const { account, activeContext } = useAuth();
  const role = (account?.declared_role || "undeclared").toLowerCase();

  if (role === "undeclared") return <HomeUndeclared />;
  if (!activeContext) return <Home1 />;
  return <Home2 />;
}
