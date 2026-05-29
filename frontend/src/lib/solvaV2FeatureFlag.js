/**
 * Solva v2 — Frontend feature flag helper (Slice 2b, 2026-05-29).
 *
 * Mirrors the backend two-layer flag (`SOLVA_V2_ENABLED` env + per-
 * account override `account.feature_flags.solva_v2`). The frontend
 * reads from `account.feature_flags.solva_v2` only — the env layer is
 * already collapsed into the backend's account-payload response, so
 * the frontend doesn't need to know about the env.
 *
 * Slice 2b adds a URL-override path (`?v2=1` / `?v2=0`) so cross-account
 * smoke testing works without a backend flag flip. URL > account flag.
 *
 * Truth table (Slice 2b):
 *   URL `?v2=1`                              → ON  (override)
 *   URL `?v2=0`                              → OFF (override)
 *   No URL override + account flag true      → ON
 *   No URL override + account flag false/missing → OFF (safe default)
 *
 * NEVER read process.env at the frontend layer — frontend cannot read
 * the backend env at runtime, and a hardcoded webpack env baked at
 * build time would defeat the per-account kill-switch capability.
 */

const TRUE_TOKENS = ["true", "1", "yes", "y", "on"];
const FALSE_TOKENS = ["false", "0", "no", "n", "off"];


function _readUrlOverride() {
  if (typeof window === "undefined" || !window.location) return null;
  try {
    const sp = new URLSearchParams(window.location.search);
    if (!sp.has("v2")) return null;
    const raw = String(sp.get("v2") || "").trim().toLowerCase();
    if (TRUE_TOKENS.includes(raw)) return true;
    if (FALSE_TOKENS.includes(raw)) return false;
  } catch {
    // noop
  }
  return null;
}


export function solvaV2EnabledFor(account) {
  // URL override always wins — supports cross-account smoke testing.
  const override = _readUrlOverride();
  if (override !== null) return override;

  if (!account || typeof account !== "object") return false;
  const flags = account.feature_flags;
  if (!flags || typeof flags !== "object") return false;
  const value = flags.solva_v2;
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    return TRUE_TOKENS.includes(value.trim().toLowerCase());
  }
  return false;
}
