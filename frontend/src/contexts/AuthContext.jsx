import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, readActiveContextId, writeActiveContextId } from "@/lib/api";

const AuthContext = createContext(null);

/**
 * AuthContext — Phase A rewire (Memo Item 5 / D-004 / D-005).
 *
 * Active context is held PER-TAB in sessionStorage (not localStorage) so
 * two tabs in the same browser, in different contexts, do not trample
 * each other. The persisted state is in `sessionStorage`; the in-memory
 * state mirrors it. The `api` axios instance attaches the value as the
 * `X-Active-Context` header on every authenticated request via the
 * interceptor in `lib/api.js`.
 *
 * Role is derived from the active context's membership (NOT
 * `account.declared_role`). A superadmin who is NED at one context and
 * Executive at another sees the live role of whichever context is
 * active — never the declared_role.
 *
 * Switching contexts:
 *   1. UI calls `switchContext(toContextId, { fromContextId })`.
 *   2. The function POSTs `/api/me/active-context` — server validates
 *      membership, writes a `context.switched` audit row, returns the
 *      verbatim memo modal copy.
 *   3. On success: the SPA stashes the new id in sessionStorage AND
 *      surfaces the memo modal payload via `pendingSwitchModal` so
 *      AppShell can render the modal. The user dismisses with
 *      "Continue"; the SPA reloads the current page so all data on
 *      screen re-fetches with the new role.
 *   4. On `403 MEMBERSHIP_REVOKED`: AuthContext clears the active
 *      context and surfaces a `rbacError` so the boot guard pushes
 *      the user back to the switcher.
 */

const SESSION_KEY_FORMER_LOCAL = "akki.activeContextId";  // legacy localStorage key
const SESSION_KEY_FORMER_LOCAL_ROLE = "akki.activeRole";  // legacy localStorage key

export function AuthProvider({ children }) {
  // null = checking session, false = unauthenticated, object = account
  const [account, setAccount] = useState(null);
  const [contexts, setContexts] = useState([]);
  // Active context id — sessionStorage keyed (D-004). Initialise from
  // the api.js helper so the X-Active-Context header is in lockstep.
  const [activeContextId, setActiveContextIdState] = useState(() => readActiveContextId());
  // Switch-modal payload — non-null while the memo modal is open.
  // Shape: {title, body, fromContextId, toContextId}.
  const [pendingSwitchModal, setPendingSwitchModal] = useState(null);
  // Surfaced when the server responds with 403 MEMBERSHIP_REVOKED on
  // the active context's role check; the boot guard listens.
  const [rbacError, setRbacError] = useState(null);

  // Helper that writes both the React state AND sessionStorage AND
  // dispatches the global event so listeners (api interceptor, role
  // badge, switcher) reactively pick up the change.
  const persistActiveContext = useCallback((cid) => {
    setActiveContextIdState(cid);
    writeActiveContextId(cid);
  }, []);

  /** Merge the membership-authoritative `/api/me/contexts` data into
   *  the legacy `/auth/me` context list. The new endpoint is the
   *  source of truth for `role` (per-context membership). The old
   *  endpoint still ships some context metadata (org_id, type) we
   *  haven't migrated, so we keep it as the secondary source. */
  const fetchAuthoritativeContexts = useCallback(async () => {
    try {
      const { data } = await api.get("/me/contexts");
      return (data?.items || []).map((m) => ({
        id: m.context_id,
        name: m.context_name,
        type: m.context_type,
        status: m.context_status,
        industry: m.industry,
        jurisdiction: m.jurisdiction,
        my_role: m.role,
        role_display: m.role_display,
        sub_role: m.sub_role,
        is_owner: m.is_owner,
        joined_at: m.joined_at,
      }));
    } catch {
      return null;
    }
  }, []);

  const bootstrap = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setAccount(data.account);

      // /api/me/contexts is authoritative for membership + role. Fall
      // back to /auth/me's contexts only if the new endpoint isn't
      // reachable (server warming up, etc.).
      const fromMembership = await fetchAuthoritativeContexts();
      const ctxs = fromMembership || (data.contexts || []);
      setContexts(ctxs);

      // Phase A boot guard (D-005):
      //   * If the cached active-context id is no longer in the
      //     membership list → clear it (the user got removed mid-
      //     session) and auto-pick the most-recently-joined valid
      //     membership so the SPA isn't left in a "no context" hole.
      //   * If the tab has no cached id at all (cold-start in a new
      //     tab where the cookie session is valid) → auto-pick the
      //     first membership. The dedicated "Pick a context" full
      //     screen is invoked from the in-topbar switcher; it is
      //     not the boot path's responsibility.
      const cached = readActiveContextId();
      const cachedStillValid = cached && ctxs.some((c) => c.id === cached);
      if (cached && !cachedStillValid) {
        if (ctxs.length >= 1) {
          persistActiveContext(ctxs[0].id);
        } else {
          persistActiveContext(null);
        }
      } else if (cached && cachedStillValid && cached !== activeContextId) {
        // Re-sync React state with sessionStorage on first boot —
        // useState init only runs once, but a second tab might have
        // a different value than this tab's first read.
        setActiveContextIdState(cached);
      }
      // Phase P5.12.2 (2026-02) — DO NOT auto-pick the first
      // membership on a cold-start (no cached id) any more. The
      // previous behaviour silently warped users into a specific
      // company on every new tab, which conflicts with the
      // post-login default landing rule: leave activeContextId
      // null so AppHome.jsx dispatches to ContextPortfolio
      // (Home 1, the portfolio overview) — the user picks a
      // company consciously by clicking a portfolio tile. The
      // mid-session membership-revoked branch above keeps its
      // auto-pick to avoid leaving an authenticated tab in a
      // broken "no context" state when its cached id silently
      // expires.

      // One-time legacy migration — copy the old localStorage value
      // into sessionStorage IF this tab has none AND the localStorage
      // value is still a valid membership for this user. After this
      // first migration, the old key is wiped so we don't keep
      // dragging it around. Per-tab semantics take effect from this
      // point onwards.
      if (!cached) {
        try {
          const legacy = window.localStorage.getItem(SESSION_KEY_FORMER_LOCAL);
          if (legacy && ctxs.some((c) => c.id === legacy)) {
            persistActiveContext(legacy);
          }
        } catch { /* noop */ }
      }
      try { window.localStorage.removeItem(SESSION_KEY_FORMER_LOCAL); } catch { /* noop */ }
      try { window.localStorage.removeItem(SESSION_KEY_FORMER_LOCAL_ROLE); } catch { /* noop */ }
    } catch {
      setAccount(false);
      setContexts([]);
      try { window.localStorage.removeItem("akki_access_token"); } catch { /* noop */ }
      try { await api.post("/auth/logout"); } catch { /* noop — best effort */ }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetchAuthoritativeContexts, persistActiveContext]);

  useEffect(() => {
    bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Listen for RBAC errors emitted by the api interceptor; the boot
  // guard at the AppShell level reacts to MEMBERSHIP_REVOKED by
  // forcing a re-pick.
  useEffect(() => {
    const onRbacError = (e) => {
      setRbacError(e?.detail || null);
      if (e?.detail?.code === "MEMBERSHIP_REVOKED") {
        // Clear the now-invalid active context.
        persistActiveContext(null);
      }
    };
    window.addEventListener("akki:rbac-error", onRbacError);
    return () => window.removeEventListener("akki:rbac-error", onRbacError);
  }, [persistActiveContext]);

  const afterAuth = useCallback(async (data) => {
    setAccount(data.account);
    if (data.access_token) {
      try { window.localStorage.setItem("akki_access_token", data.access_token); }
      catch { /* quota/private-mode noop */ }
    }
    // Pull authoritative memberships now that we have a token.
    const fromMembership = await fetchAuthoritativeContexts();
    const ctxs = fromMembership || (data.contexts || []);
    setContexts(ctxs);

    // Phase P5.12.2 (2026-02) — post-login default landing rule.
    //
    // The previous behaviour auto-picked the most-recently-joined
    // membership and stamped it onto sessionStorage. That sent
    // every sign-in straight into Home 2 (CompanyHome —
    // "Inside <Company>"), skipping Home 1 (ContextPortfolio —
    // the portfolio overview with NED/Executive tabs + Boards to
    // watch + Where you left off).
    //
    // We now leave `activeContextId` null on login so AppHome.jsx
    // dispatches to ContextPortfolio. The portfolio overview is
    // the canonical post-login landing surface; the user clicks
    // into any company tile to drill down into CompanyHome.
    //
    // If a future "remember last company" preference ever lands,
    // it should opt-in by writing to sessionStorage HERE — i.e.
    // the default stays Home 1 and the preference is the override,
    // not the other way round.
    persistActiveContext(null);
  }, [fetchAuthoritativeContexts, persistActiveContext]);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch { /* ignore */ }
    persistActiveContext(null);
    try { window.localStorage.removeItem("akki_access_token"); } catch { /* noop */ }
    setAccount(false);
    setContexts([]);
  }, [persistActiveContext]);

  /** Switch the active context.
   * @param toContextId target context membership id.
   * @param opts.fromContextId pass the previously-active id so the
   *   memo modal copy can render "back to <Company A>" correctly.
   * @param opts.silent skip the modal display (used by the boot
   *   auto-pick path; the user didn't intentionally switch).
   * @returns the server's switch payload (including memo modal copy)
   *   on success, or throws on failure.
   */
  const switchContext = useCallback(async (toContextId, opts = {}) => {
    const { fromContextId, silent = false } = opts;
    const { data } = await api.post("/me/active-context", {
      context_id: toContextId,
      from_context_id: fromContextId || activeContextId || null,
    });
    persistActiveContext(toContextId);
    if (!silent && data?.switch_notification) {
      setPendingSwitchModal({
        title: data.switch_notification.title,
        body: data.switch_notification.body,
        toContextId,
        fromContextId: fromContextId || activeContextId || null,
        toRole: data.role,
      });
    } else if (!silent) {
      // T1.3 (2026-05-24) — explicit user switch with no role-change
      // modal: still navigate to Home of the newly selected account
      // per Document Journal report item 1. Silent switches (boot
      // hydration, etc.) keep the previous behaviour of NOT
      // touching the URL.
      if (typeof window !== "undefined") {
        window.location.href = "/app";
      }
    }
    return data;
  }, [activeContextId, persistActiveContext]);

  const dismissSwitchModal = useCallback(() => {
    // T1.3 (2026-05-24) — Per Document Journal report item 1: every
    // context switch must land on Home of the newly selected
    // account, NOT on the previous path. Replacing the prior
    // `window.location.reload()` (which preserved URL) with a hard
    // navigation to `/app` forces both (a) the canonical home route
    // AND (b) a fresh data-fetch cycle (because the route component
    // re-mounts under the new active-context header).
    setPendingSwitchModal(null);
    if (typeof window !== "undefined") {
      window.location.href = "/app";
    }
  }, []);

  const refreshContexts = useCallback(async () => {
    const fromMembership = await fetchAuthoritativeContexts();
    const ctxs = fromMembership || [];
    setContexts(ctxs);
    return ctxs;
  }, [fetchAuthoritativeContexts]);

  const activeContext = useMemo(
    () => contexts.find((c) => c.id === activeContextId) || null,
    [contexts, activeContextId]
  );

  // Phase A — `activeRole` is now a DERIVED value off the active
  // context's membership role. Never `account.declared_role`. Never
  // a localStorage / sessionStorage value. The server resolves role
  // fresh on every request from the X-Active-Context header; the SPA
  // mirrors that here so the role badge in the topbar matches.
  const activeRole = activeContext?.my_role || null;

  // For UI components that need to know the set of roles the user
  // has across ALL their contexts (e.g. the role-picker on Home for
  // an undeclared user). Drives the role-card on /app.
  const availableRoles = useMemo(() => {
    const roles = new Set();
    contexts.forEach((c) => c.my_role && roles.add(c.my_role));
    return Array.from(roles);
  }, [contexts]);

  // Backwards-compat shim — switchRole used to swap declared_role
  // independently of context. Phase A removes that concept (memo
  // Item 5: roles are per-context). We keep the function name so
  // existing callers don't break, but it now no-ops with a warning.
  const switchRole = useCallback((role) => {
    // eslint-disable-next-line no-console
    console.warn(
      "[Phase A] switchRole(role) is deprecated — roles are now bound to (user, context). " +
      "Use switchContext(contextId) to switch the active context, which determines the role.",
      { attempted: role }
    );
  }, []);

  // Phase I.1 (2026-05-27) — Clear active context without server
  // round-trip. Used by CompanyHome's "← Back to Portfolio" link to
  // drop into AppHome's no-active-context branch (Portfolio Landing).
  // The server is stateless about active context (per /me/active-context
  // docstring) so this is a pure client-side state reset.
  const clearActiveContext = useCallback(() => {
    persistActiveContext(null);
  }, [persistActiveContext]);

  const value = useMemo(
    () => ({
      account, contexts, activeContext, activeContextId,
      activeRole, availableRoles,
      pendingSwitchModal, dismissSwitchModal,
      rbacError,
      afterAuth, logout, switchContext, switchRole,
      clearActiveContext,
      refreshContexts, bootstrap,
    }),
    [account, contexts, activeContext, activeContextId,
      activeRole, availableRoles,
      pendingSwitchModal, dismissSwitchModal,
      rbacError,
      afterAuth, logout, switchContext, switchRole,
      clearActiveContext,
      refreshContexts, bootstrap]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
