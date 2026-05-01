/**
 * useReviewQueue — fetches the unified Daily Review queue + the
 * cross-context counts. Stale-while-revalidate so the queue stays
 * rendered while we revalidate after an action.
 *
 * Returns:
 *   items, totalPending, loading, error
 *   refetch()                       — force-refresh the queue
 *   approve(item, body?)            — POST /approve, returns next_item_id
 *   reject(item, reason?)           — POST /reject
 *   edit(item)                      — POST /edit, returns {edit_url, inline}
 */
import { useCallback, useEffect, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";

export default function useReviewQueue() {
  const [items, setItems] = useState([]);
  const [totalPending, setTotalPending] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [acting, setActing] = useState(false);

  const refetch = useCallback(async () => {
    setError(null);
    try {
      const { data } = await api.get("/me/review-queue?limit=50");
      setItems(Array.isArray(data?.items) ? data.items : []);
      setTotalPending(data?.total_pending || 0);
    } catch (err) {
      setError(apiErrorMessage(err, "AKKI couldn’t load your review queue."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  const approve = useCallback(async (item, body) => {
    if (!item) return null;
    setActing(true);
    try {
      const { data } = await api.post(
        `/me/review-queue/items/${item.kind}/${encodeURIComponent(item.id)}/approve`,
        body || {},
      );
      // Optimistic local removal so the queue advances instantly.
      setItems((prev) => prev.filter((it) => it.id !== item.id));
      setTotalPending((n) => Math.max(0, n - 1));
      return data;
    } finally {
      setActing(false);
    }
  }, []);

  const reject = useCallback(async (item, reason) => {
    if (!item) return null;
    setActing(true);
    try {
      const { data } = await api.post(
        `/me/review-queue/items/${item.kind}/${encodeURIComponent(item.id)}/reject`,
        reason ? { reason } : {},
      );
      setItems((prev) => prev.filter((it) => it.id !== item.id));
      setTotalPending((n) => Math.max(0, n - 1));
      return data;
    } finally {
      setActing(false);
    }
  }, []);

  const edit = useCallback(async (item) => {
    if (!item) return null;
    const { data } = await api.post(
      `/me/review-queue/items/${item.kind}/${encodeURIComponent(item.id)}/edit`,
    );
    return data;
  }, []);

  return { items, totalPending, loading, error, acting, refetch, approve, reject, edit };
}
