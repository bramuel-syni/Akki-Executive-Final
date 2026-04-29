/**
 * ESLint config — minimum-viable rule set focused on bug-prevention.
 *
 * Iter61 — added explicitly after the iter58 regression where a duplicate
 * `Layers` import in AppShell.jsx slipped past lint and white-screened the
 * entire app. The default `no-redeclare` rule catches this kind of mistake.
 *
 * The MCP lint tool we use in CI already enforces `no-undef` and friends;
 * this file makes the duplicate-identifier guard explicit so the rule
 * survives any future tool swap.
 */
module.exports = {
  root: false,
  rules: {
    "no-redeclare": ["error", { builtinGlobals: false }],
    "no-dupe-keys": "error",
    "no-dupe-class-members": "error",
    "no-duplicate-imports": ["error", { includeExports: true }],
  },
};
