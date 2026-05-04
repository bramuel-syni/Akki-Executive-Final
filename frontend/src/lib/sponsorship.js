/**
 * Phase B.5 — single-source isSponsored predicate.
 *
 * Phase 15.3.5 collapsed the legacy "sponsored vs non-sponsored Home"
 * fork into a single AppHome dispatcher branched on `account.declared_role`
 * (NED / Executive / Dual / Undeclared) — sponsorship was no longer a
 * Home-variant axis.
 *
 * Sponsorship still drives **chrome** decisions inside the shell:
 *   - the topbar context banner (`AppShell.jsx`)
 *   - the portfolio rail group label (`PortfolioRail.jsx`)
 *   - the per-context "· sponsored" tag next to the cycle context name
 *     (`CycleContextIndicator.jsx`)
 *
 * Each of those used to compute the predicate inline. This util
 * centralises it so a future schema change (e.g. adding
 * `provisioning="sponsored_invite_pending"` or a new context type) is
 * a one-line edit, not a three-place hunt.
 */

/**
 * Returns true if the supplied context object is sponsored (i.e.
 * funded / provisioned by another organisation, not personally owned).
 *
 * Accepted shapes (any of):
 *   - `{ provisioning: "sponsored" }`
 *   - `{ type: "ned_sponsored" }`
 *   - `{ type: "executive_enterprise" }`
 *   - `{ kind: "sponsored" }` (older shape — still seen on a few rows)
 *   - `{ is_sponsored: true }` (override flag)
 *
 * Returns false for any falsy / unknown context.
 */
export function isSponsoredContext(ctx) {
  if (!ctx) return false;
  if (ctx.is_sponsored === true) return true;
  if (ctx.kind === "sponsored") return true;
  if (ctx.provisioning === "sponsored") return true;
  if (ctx.type === "ned_sponsored") return true;
  if (ctx.type === "executive_enterprise") return true;
  return false;
}
