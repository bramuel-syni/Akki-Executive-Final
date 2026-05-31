/**
 * Phase P5.9.2 (2026-02) — Akki Inbox unread-count poller.
 *
 * Polls `GET /api/admin/inbox/unread-count` every 60s while the
 * current account is a super-admin. Returns the count + a manual
 * refresh handle so the topbar Admin dropdown can refresh
 * immediately after a user action (e.g. opening a row).
 *
 * Returns 0 (and skips the request) for non-super-admin sessions
 * so non-admins never trigger a 401/403 in the background.
 */
import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

const POLL_INTERVAL_MS = 60_000;

export default function useAdminInboxUnreadCount() {
  const { account } = useAuth();
  const isAdmin = account?.is_superadmin === true;
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!isAdmin) {
      setCount(0);
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.get("/admin/inbox/unread-count");
      setCount(typeof data?.count === "number" ? data.count : 0);
    } catch {
      // Silent — this is a courtesy badge. Don't toast.
    } finally {
      setLoading(false);
    }
  }, [isAdmin]);

  useEffect(() => {
    if (!isAdmin) {
      setCount(0);
      return;
    }
    refresh();
    const id = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [isAdmin, refresh]);

  return { count, loading, refresh };
}
