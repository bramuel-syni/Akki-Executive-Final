import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

/**
 * R.followup.2 (2026-05-27) — Page-level superadmin enforcement.
 *
 * Wraps any `/app/admin/*` route. Behaviour:
 *
 *   • `account === null` (still bootstrapping) → render the same
 *     "Verifying session" placeholder that <ProtectedRoute> uses
 *     so the flicker isn't a redirect-then-redirect.
 *   • `account === false` (unauthenticated) → redirect to /signin
 *     with `from` state so the user lands back here post-login.
 *   • `account.is_superadmin !== true` → redirect to /app/.
 *     A non-superadmin reaching `/app/admin/*` is either a wrong
 *     bookmark or a probe; either way we send them home.
 *   • Superadmin → render children.
 *
 * This is the SECOND gate. The first is the existing
 * <ProtectedRoute> auth check, which any admin caller MUST also
 * pass (data endpoints behind `/api/admin/*` enforce superadmin
 * server-side via `require_superadmin()` — this guard adds the
 * page-level enforcement the user explicitly asked for).
 */
export default function SuperadminRoute({ children }) {
  const { account } = useAuth();
  const location = useLocation();

  if (account === null) {
    return (
      <div
        className="h-screen flex items-center justify-center bg-[#FAFBFC]"
        data-testid="superadmin-route-loading"
      >
        <div className="flex flex-col items-center gap-3">
          <div className="w-1.5 h-1.5 bg-[var(--accent)] akki-pulse-gold rounded-full" />
          <p className="text-xs uppercase tracking-[0.2em] text-slate-400">
            Verifying session
          </p>
        </div>
      </div>
    );
  }
  if (!account) {
    return <Navigate to="/signin" state={{ from: location.pathname }} replace />;
  }
  if (!account.is_superadmin) {
    return (
      <Navigate
        to="/app/"
        state={{ adminBlocked: true, from: location.pathname }}
        replace
      />
    );
  }
  return children;
}
