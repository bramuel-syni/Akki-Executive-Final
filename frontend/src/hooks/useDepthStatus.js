/**
 * useDepthStatus — session-cached hook over `GET /api/me/depth-status`.
 *
 * Used by AppShell (nav filtering) and HomeV2 (offer card). One fetch
 * per session; `refresh()` forces a re-fetch (e.g. after dismissal).
 *
 * Cache is keyed on `account.id` so switching accounts invalidates it.
 * We deliberately don't poll — depth eligibility is sticky once crossed
 * and a minute of staleness on nav gating is harmless.
 */
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

// Module-scope cache so multiple consumers share one fetch.
const _cache = { accountId: null, status: null, promise: null };

export default function useDepthStatus() {
  const { account } = useAuth();
  const accountId = account?.id || null;
  const [status, setStatus] = useState(() =>
    _cache.accountId === accountId ? _cache.status : null
  );
  const [loading, setLoading] = useState(() => !(_cache.accountId === accountId && _cache.status));

  const fetchStatus = useCallback(async (force = false) => {
    if (!accountId) {
      setStatus(null);
      setLoading(false);
      return null;
    }
    if (!force && _cache.accountId === accountId && _cache.status) {
      setStatus(_cache.status);
      setLoading(false);
      return _cache.status;
    }
    if (_cache.promise && _cache.accountId === accountId && !force) {
      const s = await _cache.promise;
      setStatus(s);
      setLoading(false);
      return s;
    }
    setLoading(true);
    const p = (async () => {
      try {
        const { data } = await api.get("/me/depth-status");
        _cache.accountId = accountId;
        _cache.status = data;
        return data;
      } catch {
        _cache.accountId = accountId;
        _cache.status = null;
        return null;
      } finally {
        _cache.promise = null;
      }
    })();
    _cache.promise = p;
    const s = await p;
    setStatus(s);
    setLoading(false);
    return s;
  }, [accountId]);

  useEffect(() => {
    if (!accountId) return;
    if (_cache.accountId !== accountId) {
      _cache.status = null;
      _cache.accountId = accountId;
    }
    if (!_cache.status) fetchStatus();
    else {
      setStatus(_cache.status);
      setLoading(false);
    }
  }, [accountId, fetchStatus]);

  const refresh = useCallback(() => fetchStatus(true), [fetchStatus]);
  return { status, loading, refresh };
}

/** Force-invalidate the cached status (e.g. after dismissal). */
export function invalidateDepthStatus() {
  _cache.status = null;
  _cache.promise = null;
}
