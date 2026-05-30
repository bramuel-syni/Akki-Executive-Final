# Admin · Prompt tuning

Prompt tuning is where the team rehearses changes to the reasoning
surface before they land for users. Dry-runs only — no real
sessions are affected.

## What it does

The prompt-tune surface accepts a candidate framing and runs it
through the engine in a sandboxed lane. The output is comparable to
production but written to a separate ledger so you can audit the
change without touching the live workspace.

## How to use it

1. Open Admin → Prompt tuning.
2. Paste the candidate framing into the panel on the left.
3. Pick the scenarios on the right that should exercise the change.
4. Hit "Dry run". The output ships side-by-side with the current
   production output for each scenario.
5. If the candidate output is consistently better, the change is
   ready to be promoted. If not, iterate on the framing.

**Worked example.** The team wanted to tighten how Akki names
counter-positions. They drafted a candidate, ran it against twelve
scenarios in the dry-run surface, and read the side-by-side
output. Eleven scenarios held; one regressed. They tightened the
candidate to handle the regressing scenario, re-ran, all twelve
held. The change was promoted that afternoon.

## Common questions

- **Does a dry-run cost LLM quota?** Yes, but the dry-run ledger
  caps spend separately so it cannot blow the live workspace
  budget.
- **Can a non-admin run prompt tuning?** No. The surface requires
  superadmin.
- **Where does promoted output go?** Into the framing layer that
  every Solva session in production reads from.

## Troubleshooting

- **A dry run failed mid-scenario.** Check the run id in the
  console. If the failure was deterministic, it surfaces on
  re-run; if it was a quota miss, retry once the quota window
  resets.
- **The side-by-side diff is empty.** The candidate produced the
  same output as production — usually a sign the framing change
  did not bite. Make it sharper.
