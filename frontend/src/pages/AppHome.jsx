/**
 * AppHome — Phase 13.3 role-aware home dispatcher.
 *
 * Branches on `account.declared_role`:
 *   - `ned`        → <HomeNed />
 *   - `executive`  → <HomeExecutive />  (wraps the existing executive
 *                                        layout from LegacyAppHome,
 *                                        now plus a Work Studio band)
 *   - `dual`       → <HomeDual />
 *   - `undeclared` → <HomeUndeclared />
 *   - anything else (shouldn't happen post-Phase-1, but defensive) →
 *     <HomeUndeclared />
 *
 * The legacy `?home=v2` flag-switch behaviour is preserved as an
 * override for users who explicitly opt into the v2 home — the
 * declared-role branch only kicks in when the override isn't set, so
 * we don't regress anyone who shared a `?home=v2` URL.
 *
 * Sandbox accounts are pinned to <HomeExecutive /> (the legacy home)
 * because the v2 / role surfaces don't have sensible semantics inside
 * a single frozen sandbox context.
 *
 * The FirstSessionGuard in App.js has already run by the time we
 * mount, so brand-new accounts are bounced to /app/first-session
 * before they can land here.
 */
import React from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import LegacyAppHome from "@/pages/LegacyAppHome";
import HomeV2 from "@/pages/HomeV2";
import HomeNed from "@/pages/home/HomeNed";
import HomeExecutive from "@/pages/home/HomeExecutive";
import HomeDual from "@/pages/home/HomeDual";
import HomeUndeclared from "@/pages/home/HomeUndeclared";

export default function AppHome() {
  const { account } = useAuth();
  const location = useLocation();
  const params = new URLSearchParams(location.search || "");
  const flag = (params.get("home") || "").toLowerCase();

  // Explicit ?home=v2 override (legacy contract preserved).
  if (flag === "v2" && !account?.is_sandbox) return <HomeV2 />;
  if (flag === "v1" || flag === "legacy") return <LegacyAppHome />;

  // Sandbox keeps the legacy home — role surfaces don't have semantics
  // inside a frozen sandbox.
  if (account?.is_sandbox) return <LegacyAppHome />;

  const role = (account?.declared_role || "undeclared").toLowerCase();
  if (role === "ned") return <HomeNed />;
  if (role === "executive") return <HomeExecutive />;
  if (role === "dual") return <HomeDual />;
  return <HomeUndeclared />;
}
