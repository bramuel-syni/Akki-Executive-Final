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

  const bootstrap = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setAccount(data.account);
      setContexts(data.contexts);
      if (!activeContextId && data.contexts.length > 0) {
        const primary = pickPrimaryContext(data.account, data.contexts);
        if (primary) {
          setActiveContextId(primary);
          window.localStorage.setItem("akki.activeContextId", primary);
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
    }
  }, [activeContextId, activeRole]);

  useEffect(() => {
    bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const afterAuth = useCallback((data) => {
    setAccount(data.account);
    setContexts(data.contexts || []);
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
    setAccount(false);
    setContexts([]);
    setActiveContextId(null);
    setActiveRole(null);
  }, []);

  const switchContext = useCallback((cid) => {
    setActiveContextId(cid);
    window.localStorage.setItem("akki.activeContextId", cid);
  }, []);

  const switchRole = useCallback((role) => {
    setActiveRole(role);
    window.localStorage.setItem("akki.activeRole", role);
  }, []);

  const refreshContexts = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setContexts(data.contexts);
      setAccount(data.account);
      return data.contexts;
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
