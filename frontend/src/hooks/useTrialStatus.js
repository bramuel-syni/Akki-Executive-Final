/**
 * Phase R.5.a (2026-05-27) — Trial status hook + hard-lock guard.
 *
 * Reads `/api/me/trial-status` on mount + every 60s. When the
 * backend returns `locked: true` (computed from `trial_status ===
 * "expired_hard_lock"`), all `<Gated>` routes short-circuit to the
 * `/app/early-access-opt-in` page.
 *
 * Returns `{ status, locked, day, totalDays, softWarningAt, hardLockAt,
 *            cohortTag, refresh }`.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

const INITIAL = {
  status:          null,
  locked:          false,
  day:             null,
  totalDays:       null,
  softWarningAt:   null,
  hardLockAt:      null,
  cohortTag:       null,
};

export default function useTrialStatus() {
  const [data, setData] = useState(INITIAL);
  const fetchedOnce = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const res = await api.get("/me/trial-status");
      const d = res?.data || {};
      setData({
        status:          d.trial_status || "pending",
        locked:          Boolean(d.locked),
        day:             d.trial_day ?? null,
        totalDays:       d.trial_total_days ?? null,
        softWarningAt:   d.soft_warning_at_day ?? null,
        hardLockAt:      d.hard_lock_at_day ?? null,
        cohortTag:       d.cohort_tag || null,
      });
      fetchedOnce.current = true;
    } catch (_) {
      // Silent failure — the route guard treats `null` status as
      // "no trial, no lock" so missing data never accidentally locks
      // a user out.
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 60_000);
    return () => clearInterval(t);
  }, [refresh]);

  return { ...data, refresh };
}
