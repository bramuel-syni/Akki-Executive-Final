/**
 * useCycleConfig — Phase 2.
 *
 * Fetches and mutates the per-context cycle config that powers the
 * Cycle Strip on Home + /app/cycle. Stale-while-revalidate semantics:
 * the previously cached config stays visible while the next fetch is
 * in flight, so the strip never collapses to a blank state.
 *
 * Returns:
 *   config              — latest cycle config or null while loading
 *   loading, error
 *   currentPhase        — derived phase object
 *   refetch()           — force-refresh
 *   updateConfig(body)  — PUT (owner/admin only)
 *   advancePhase()      — POST /advance
 *   resetConfig()       — POST /reset
 *   loadPhaseSummary(phaseId, cycleOffset?)
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiErrorMessage } from "@/lib/api";

export default function useCycleConfig(contextId) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [acting, setActing] = useState(false);
  const lastContextIdRef = useRef(null);

  const refetch = useCallback(async () => {
    if (!contextId) return null;
    setError(null);
    // Don't reset `config` so the strip stays rendered while we revalidate.
    if (lastContextIdRef.current !== contextId) setLoading(true);
    try {
      const { data } = await api.get(`/contexts/${contextId}/cycle-config`);
      setConfig(data);
      lastContextIdRef.current = contextId;
      return data;
    } catch (err) {
      setError(apiErrorMessage(err, "AKKI couldn’t load the cycle phases."));
      return null;
    } finally {
      setLoading(false);
    }
  }, [contextId]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  const currentPhase =
    config && Array.isArray(config.phases)
      ? config.phases.find((p) => p.id === config.current_phase_id) || null
      : null;

  const updateConfig = useCallback(
    async (body) => {
      if (!contextId) return null;
      setActing(true);
      try {
        const { data } = await api.put(`/contexts/${contextId}/cycle-config`, body);
        setConfig(data);
        return data;
      } finally {
        setActing(false);
      }
    },
    [contextId],
  );

  const advancePhase = useCallback(async () => {
    if (!contextId) return null;
    setActing(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/cycle-config/advance`);
      setConfig(data);
      return data;
    } finally {
      setActing(false);
    }
  }, [contextId]);

  const resetConfig = useCallback(async () => {
    if (!contextId) return null;
    setActing(true);
    try {
      const { data } = await api.post(`/contexts/${contextId}/cycle-config/reset`);
      setConfig(data);
      return data;
    } finally {
      setActing(false);
    }
  }, [contextId]);

  const loadPhaseSummary = useCallback(
    async (phaseId, cycleOffset = 0) => {
      if (!contextId || !phaseId) return null;
      const { data } = await api.get(
        `/contexts/${contextId}/cycle-config/phases/${phaseId}/summary?cycle_offset=${cycleOffset}`,
      );
      return data;
    },
    [contextId],
  );

  return {
    config,
    loading,
    error,
    acting,
    currentPhase,
    refetch,
    updateConfig,
    advancePhase,
    resetConfig,
    loadPhaseSummary,
  };
}
