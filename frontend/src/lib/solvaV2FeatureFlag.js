/**
 * Solva v2 — Frontend feature flag helper (Slice 2a, 2026-05-29).
 *
 * Mirrors the backend two-layer flag (`SOLVA_V2_ENABLED` env + per-
 * account override `account.feature_flags.solva_v2`). The frontend
 * reads from `account.feature_flags.solva_v2` only — the env layer is
 * already collapsed into the backend's account-payload response, so
 * the frontend doesn't need to know about the env.
 *
 * Truth table:
 *   account.feature_flags.solva_v2 === true  → ON
 *   account.feature_flags.solva_v2 === false → OFF
 *   missing / null / undefined                → OFF (safe default)
 *
 * NEVER read process.env at the frontend layer — frontend cannot read
 * the backend env at runtime, and a hardcoded webpack env baked at
 * build time would defeat the per-account kill-switch capability.
 */
export function solvaV2EnabledFor(account) {
  if (!account || typeof account !== "object") return false;
  const flags = account.feature_flags;
  if (!flags || typeof flags !== "object") return false;
  const value = flags.solva_v2;
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    return ["true", "1", "yes", "y", "on"].includes(value.trim().toLowerCase());
  }
  return false;
}
