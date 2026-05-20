# AWAITING_PO — CHUNK 11 QA-050 dual-role label interpretation

**Status:** NON-BLOCKING. Current implementation ships and passes the verbatim spec.
**Surface:** Context Bar (`CycleContextIndicator.jsx`)
**Origin:** Tester flagged after Chunk 11 close (2026-05-21).

## Verbatim QA spec

> "In your Context Bar when the user account is for an executive only show Executive if user is both a NED and Executive then you can have both."
> — `qa_reports/QA_REPORT_16MAY2026.md#qa-2026-05-16-050`

## Tester observation

bramuel has `accounts.declared_role = "ned"` but membership rows in BOTH NED contexts AND Exec contexts. Current Chunk-11 implementation does NOT compose "Executive · NED" for bramuel because the literal flag is "ned" not "dual".

## Three competing interpretations

### (a) Literal `declared_role === "dual"`  ← CURRENTLY SHIPPED

The Context Bar shows the dual label ONLY when the account is explicitly flagged dual-declared AND has ≥1 NED context membership.

**Pros:**
- Mirrors the exact intent of an existing first-class account attribute.
- Predictable / explicit user-controlled state — admin sets `declared_role="dual"` when onboarding.
- No false-positives when a one-off NED guest context is granted to an Exec user.

**Cons:**
- bramuel-like users with cross-role memberships don't get the dual label even though they functionally are "both".
- The QA author's intent likely matches the broader (b) or (c) reading.

### (b) Has membership in ANY NED context AND ANY Exec context

Compose dual label when `contexts.some(c => c.my_role === "ned")` AND `contexts.some(c => c.my_role === "executive")`.

**Pros:**
- Matches the QA author's apparent intent ("if user is both a NED and Executive").
- Surfaces dual-role for bramuel-style accounts automatically.
- No new account flag needed — derived from membership.

**Cons:**
- A one-off NED guest context promotion can suddenly flip the label across every Exec context the user is in (might surprise).
- Account-wide label regardless of current-context role — possibly noisy.

### (c) Per-context dual (NED + Exec on the same context)

Compose dual label only when `activeContext.my_role` is somehow "dual" (NOT today's data model — would require schema extension).

**Pros:**
- Most precise — label reflects the user's role in the context they're viewing.

**Cons:**
- Requires schema migration (`memberships.my_role` doesn't currently accept "dual").
- Most cycles/boards don't have a single dual-role member — would never fire.
- Highest implementation cost.

## Recommendation

If PO wants the broader interpretation (most likely from the spec text), pick (b). One-line code change in `deriveRoleKicker`:

```js
// (b) — replace the current check
const hasNed = Array.isArray(contexts) && contexts.some(c => c?.my_role === "ned");
const hasExec = Array.isArray(contexts) && contexts.some(c => c?.my_role === "executive");
if (hasNed && hasExec && role === "executive") {
  label = "Executive · NED";
}
```

(c) requires schema work and is over-engineered for the stated need.
(a) ships as-is.

## Decision needed

PO to pick (a) / (b) / (c). Non-blocking — current behaviour is shipped, tested, and passes verbatim. Re-open as `QA-2026-05-16-050-followup` in a future chunk if (b) or (c) is selected.
