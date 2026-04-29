import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // null = checking session, false = unauthenticated, object = account
  const [account, setAccount] = useState(null);
  const [contexts, setContexts] = useState([]);
  const [activeContextId, setActiveContextId] = useState(
    () => window.localStorage.getItem("akki.activeContextId") || null
  );
  const [activeRole, setActiveRole] = useState(
    () => window.localStorage.getItem("akki.activeRole") || null
  );

  const pickPrimaryContext = (acc, ctxs) =>
    acc?.default_context_id || (ctxs && ctxs[0] && ctxs[0].id) || null;

  // Apr-2026: /auth/me sometimes omits my_role on a context membership.
  // Derive it from c.type (ned_* / executive_*) so every downstream
  // consumer (ContextChooser, InSummaryTiles, role isolation) has a
  // single source of truth without needing a backend round-trip.
  const enrichContexts = (ctxs) =>
    (ctxs || []).map((c) => {
      if (c.my_role === "ned" || c.my_role === "executive") return c;
      const t = (c.type || "").toLowerCase();
      const derived =
        t.startsWith("ned_") ? "ned" :
        t.startsWith("executive_") ? "executive" :
        null;
      return derived ? { ...c, my_role: derived } : c;
    });

  const bootstrap = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setAccount(data.account);
      setContexts(enrichContexts(data.contexts));
      if (!activeContextId && data.contexts.length > 0) {
        const primary = pickPrimaryContext(data.account, data.contexts);
        if (primary) {
          setActiveContextId(primary);
          window.localStorage.setItem("akki.activeContextId", primary);
          // Auto-align activeRole with the primary context's my_role
          const primaryCtx = data.contexts.find((c) => c.id === primary);
          if (primaryCtx?.my_role && (primaryCtx.my_role === "ned" || primaryCtx.my_role === "executive")) {
            setActiveRole(primaryCtx.my_role);
            window.localStorage.setItem("akki.activeRole", primaryCtx.my_role);
          }
        }
      } else if (activeContextId) {
        // If we already had a persisted activeContextId, always realign the
        // stored activeRole to the context's my_role on bootstrap — this covers
        // both mismatch and the first-login case where activeRole is still null.
        const ctx = data.contexts.find((c) => c.id === activeContextId);
        if (ctx?.my_role && (ctx.my_role === "ned" || ctx.my_role === "executive") &&
            activeRole !== ctx.my_role) {
          setActiveRole(ctx.my_role);
          window.localStorage.setItem("akki.activeRole", ctx.my_role);
        }
      }
      if (!activeRole && data.account?.declared_role && data.account.declared_role !== "undeclared") {
        const r = data.account.declared_role === "dual" ? "executive" : data.account.declared_role;
        setActiveRole(r);
        window.localStorage.setItem("akki.activeRole", r);
      }
    } catch {
      setAccount(false);
      setContexts([]);
      // If /auth/me failed, BOTH credentials (Bearer + cookie) are
      // suspect — the iter59 bug taught us that just clearing one leaves
      // the other to keep poisoning future requests. Drop the localStorage
      // Bearer AND best-effort POST /auth/logout so the server-side cookie
      // is cleared too. Errors on logout are ignored on purpose: it's a
      // self-healing courtesy, not a hard requirement.
      try { window.localStorage.removeItem("akki_access_token"); } catch { /* noop */ }
      try { await api.post("/auth/logout"); } catch { /* noop — best effort */ }
    }
  }, [activeContextId, activeRole]);

  useEffect(() => {
    bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const afterAuth = useCallback((data) => {
    setAccount(data.account);
    setContexts(enrichContexts(data.contexts || []));
    // Persist the access_token to localStorage so the Bearer interceptor
    // can recover when cross-site cookies are blocked (Safari 16+ ITP,
    // Brave shields, Firefox strict, or any deploy where the API and
    // the SPA live on different parent domains). The httpOnly cookie
    // remains the primary auth surface; this is a graceful-degradation
    // backup that prevents users from being bounced back to the landing
    // page after a successful login.
    if (data.access_token) {
      try { window.localStorage.setItem("akki_access_token", data.access_token); }
      catch { /* quota/private-mode noop */ }
    }
    const primary = pickPrimaryContext(data.account, data.contexts);
    if (primary) {
      setActiveContextId(primary);
      window.localStorage.setItem("akki.activeContextId", primary);
    }
  }, []);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch { /* ignore */ }
    window.localStorage.removeItem("akki.activeContextId");
    window.localStorage.removeItem("akki.activeRole");
    window.localStorage.removeItem("akki_access_token");
    setAccount(false);
    setContexts([]);
    setActiveContextId(null);
    setActiveRole(null);
  }, []);

  const switchContext = useCallback((cid) => {
    setActiveContextId(cid);
    window.localStorage.setItem("akki.activeContextId", cid);
    // Auto-route activeRole to the context's my_role when they differ, so
    // Bramuel opening a NED board stops firing the role-mismatch banner.
    setContexts((prev) => {
      const target = prev.find((c) => c.id === cid);
      if (target?.my_role && (target.my_role === "ned" || target.my_role === "executive")) {
        setActiveRole(target.my_role);
        window.localStorage.setItem("akki.activeRole", target.my_role);
      }
      return prev;
    });
  }, []);

  // Role isolation rule (Apr-2026): switching role rebuilds the lens —
  // if the active context isn't a board where the user holds the new
  // role, drop them on Home so they can pick a context that fits.
  // Same-org NED↔Exec switches are preserved.
  const switchRole = useCallback((role) => {
    setActiveRole(role);
    window.localStorage.setItem("akki.activeRole", role);
    setContexts((prev) => {
      const current = prev.find((c) => c.id === activeContextId);
      if (current && current.my_role && current.my_role !== role) {
        // Try to find another context where the user holds the new role —
        // ideally in the same organisation, falling back to any.
        const sameOrg = prev.find(
          (c) => c.my_role === role && (c.org_id ? c.org_id === current.org_id : false)
        );
        const anyMatch = sameOrg || prev.find((c) => c.my_role === role);
        if (anyMatch) {
          setActiveContextId(anyMatch.id);
          window.localStorage.setItem("akki.activeContextId", anyMatch.id);
        }
        // Reset to Home so the user re-anchors deliberately.
        if (typeof window !== "undefined") {
          window.location.assign("/app");
        }
      }
      return prev;
    });
  }, [activeContextId]);

  const refreshContexts = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      const enriched = enrichContexts(data.contexts);
      setContexts(enriched);
      setAccount(data.account);
      return enriched;
    } catch {
      return [];
    }
  }, []);

  const activeContext = useMemo(
    () => contexts.find((c) => c.id === activeContextId) || null,
    [contexts, activeContextId]
  );

  // Available roles for switcher derive from declared_role + active memberships
  const availableRoles = useMemo(() => {
    const roles = new Set();
    if (account?.declared_role === "ned" || account?.declared_role === "dual") roles.add("ned");
    if (account?.declared_role === "executive" || account?.declared_role === "dual") roles.add("executive");
    contexts.forEach((c) => c.my_role && roles.add(c.my_role));
    return Array.from(roles);
  }, [account, contexts]);

  const effectiveRole = activeRole || (availableRoles[0] || "executive");

  const value = useMemo(
    () => ({
      account, contexts, activeContext, activeContextId,
      activeRole: effectiveRole, availableRoles,
      afterAuth, logout, switchContext, switchRole, refreshContexts, bootstrap,
    }),
    [account, contexts, activeContext, activeContextId, effectiveRole, availableRoles,
      afterAuth, logout, switchContext, switchRole, refreshContexts, bootstrap]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
