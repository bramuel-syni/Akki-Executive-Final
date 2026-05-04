/**
 * AppHome — role-aware home dispatcher (Phase 15.3.5 cutover).
 *
 * Single canonical home. Branches on `account.declared_role`:
 *   - `ned`        → <HomeNed />
 *   - `executive`  → <HomeExecutive />
 *   - `dual`       → <HomeDual />
 *   - `undeclared` → <HomeUndeclared />
 *   - anything else (defensive) → <HomeUndeclared />
 *
 * Phase 15.3.5 retired:
 *   - `?home=v2` and `?home=v1|legacy` URL switches (single production
 *     surface; archived under /app/_legacy/).
 *   - LegacyAppHome.jsx and HomeV2.jsx components.
 *
 * Sandbox accounts now route through HomeExecutive (the closest legacy
 * shape) rather than LegacyAppHome.
 *
 * The FirstSessionGuard in App.js has already run by the time we
 * mount, so brand-new accounts are bounced to /app/first-session
 * before they can land here.
 */
import React from "react";
import { useAuth } from "@/contexts/AuthContext";
import HomeNed from "@/pages/home/HomeNed";
import HomeExecutive from "@/pages/home/HomeExecutive";
import HomeDual from "@/pages/home/HomeDual";
import HomeUndeclared from "@/pages/home/HomeUndeclared";

export default function AppHome() {
  const { account } = useAuth();

  // Sandbox accounts use the executive home — closest match to the
  // pre-15.3.5 LegacyAppHome shape, semantics-preserving for the
  // sandbox-pinned demo flow.
  if (account?.is_sandbox) return <HomeExecutive />;

  const role = (account?.declared_role || "undeclared").toLowerCase();
  if (role === "ned") return <HomeNed />;
  if (role === "executive") return <HomeExecutive />;
  if (role === "dual") return <HomeDual />;
  return <HomeUndeclared />;
}
