/**
 * useReviewCounts — polls /api/me/review-queue/counts on a 60s interval
 * and on tab focus. Powers the top-bar Daily Review badge.
 *
 * Polling is conservative per the rules doc constraint (60s minimum,
 * polling-only, no SSE / websockets).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

const POLL_MS = 60_000;

export default function useReviewCounts({ enabled = true } = {}) {
  const [counts, setCounts] = useState({ total: 0, by_kind: {}, by_context: [] });
  const [loading, setLoading] = useState(true);
  const timerRef = useRef(null);

  const fetchOnce = useCallback(async () => {
    try {
      const { data } = await api.get("/me/review-queue/counts");
      setCounts(data || { total: 0, by_kind: {}, by_context: [] });
    } catch (_err) {
      // Silent — the badge degrades to hidden / stale; no toast.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return undefined;
    fetchOnce();
    timerRef.current = window.setInterval(fetchOnce, POLL_MS);
    const onFocus = () => fetchOnce();
    window.addEventListener("focus", onFocus);
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      window.removeEventListener("focus", onFocus);
    };
  }, [enabled, fetchOnce]);

  return { counts, total: counts.total, loading, refetch: fetchOnce };
}
