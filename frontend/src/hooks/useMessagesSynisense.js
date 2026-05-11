/**
 * CHAT sprint (2026-05-12) — useMessagesSynisense.
 *
 * Batched fetch of per-message Synisense metrics for a given chat.
 * Replaces the N+1 pattern (one HTTP call per assistant message) with
 * a single POST to `/api/chats/{cid}/messages/synisense-runs/batch`.
 *
 * Returns:
 *   {
 *     map: Map<msg_id, { identifiers_redacted, model_calls, layer_breakdown }>,
 *     loading: boolean,
 *     refetch: () => void,
 *   }
 *
 * Polls every 30s while the chat is open, so the counts tick up as
 * streams complete and Synisense audit rows land. Cancels the timer
 * on chat change / unmount.
 *
 * Honours `prefers-reduced-motion`: the badge component using this hook
 * is responsible for its own animation policy; the hook itself is pure
 * data.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

const POLL_INTERVAL_MS = 30000;

export function useMessagesSynisense({ chatId, msgIds }) {
  const [map, setMap] = useState(new Map());
  const [loading, setLoading] = useState(false);
  const aliveRef = useRef(true);
  const idsSig = (msgIds || []).join(",");

  const fetchOnce = useCallback(async () => {
    if (!chatId) return;
    const ids = (msgIds || []).filter(Boolean);
    if (ids.length === 0) {
      setMap(new Map());
      return;
    }
    setLoading(true);
    try {
      const { data } = await api.post(
        `/chats/${chatId}/messages/synisense-runs/batch`,
        { msg_ids: ids },
      );
      if (!aliveRef.current) return;
      const next = new Map();
      const items = data?.items || {};
      for (const id of ids) {
        const row = items[id];
        if (row) next.set(id, row);
      }
      setMap(next);
    } catch {
      // Network blip — keep the last good map until the next tick.
    } finally {
      if (aliveRef.current) setLoading(false);
    }
  }, [chatId, idsSig]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    aliveRef.current = true;
    fetchOnce();
    const tid = setInterval(fetchOnce, POLL_INTERVAL_MS);
    return () => {
      aliveRef.current = false;
      clearInterval(tid);
    };
  }, [fetchOnce]);

  return { map, loading, refetch: fetchOnce };
}
