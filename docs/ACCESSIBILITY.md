# Accessibility — WCAG 2.2 AA posture

_Phase 13.4 closeout (2026-05-04). Companion to `SURFACE_TYPES.md`._

## Scope

WCAG 2.2 **Level A and Level AA** only. Level AAA is explicitly out of scope
per the UI/UX architect brief. The baseline scan covers the public marketing
and auth surfaces; authenticated app routes (`/app/*`) are deferred to a
follow-up iteration that will add a session bootstrapper to the pa11y config.

## Tool stack

| Tool | When | Where | What it does |
| --- | --- | --- | --- |
| `@axe-core/react` | Dev | `frontend/src/index.js` (NODE_ENV !== production gate) | Logs WCAG 2.2 AA violations to the browser console as users navigate. Zero impact on the production bundle. |
| `pa11y-ci` | CI | `frontend/.pa11yci.json` + `yarn a11y:ci` | Headless Chrome scan over a fixed list of URLs at the `WCAG2AA` standard, axe runner. |
| Lighthouse CI | CI | `frontend/lighthouserc.json` + `yarn perf:ci` | Performance budgets per surface type; see `SURFACE_TYPES.md`. |

## What's enforced vs warned

| Tool | First-run posture | Follow-up posture |
| --- | --- | --- |
| `pa11y-ci` Level A errors | **Warn** (threshold = 9999) | Block on merge |
| `pa11y-ci` Level AA errors | Warn | Warn (cap to ~10) |
| Lighthouse CI assertions | All `warn` | Tighten per surface budget once the desktop baseline is stable |

The first-run gate is intentionally lenient: we want a baseline established
before we block merges. The brief explicitly endorsed this posture ("AA fixes
come in waves").

## Phase 13.4 fix delta

Baseline (pre-13.4):  **159 issues** across 10 URLs (69 errors + 90 warnings).
Post-fix (Phase 13.4): **10 issues** across 10 URLs (10 errors, all flagged
by axe but pass manual contrast verification — see Known exceptions).

Net delta: **−149 issues**, including the entire `region` warning class
(87 → 0) and the entire `landmark-one-main` warning class (2 → 0).

## How to run locally

```bash
cd /app/frontend
yarn a11y:ci      # pa11y-ci scan
yarn perf:ci      # Lighthouse CI
```

The pa11y-ci config uses `/usr/bin/google-chrome` directly with `--no-sandbox`
for container compatibility. If running outside the cloud container, drop
those flags from `.pa11yci.json` `chromeLaunchConfig`.

## Adding URLs

Edit `frontend/.pa11yci.json` `urls` array. Public URLs work out of the box.
Authenticated routes will need a `headers.Cookie` or `actions` step to log in;
the scaffolding for that lands in 13.x+1.

## Known exceptions (false positives or accepted deferrals)

- **`#emergent-badge`**: external badge injected by the preview environment.
  Hidden from pa11y scans via the `hideElements` config. Not our markup.
- **Accent on cream-deep at 6.9:1**: 10 hits across `/features`, `/security`,
  `/blog`, `/solva`. WebAIM contrast checker confirms `#8B2E2B` (oxblood
  accent) on `#EFE9D9` (cream-deep) passes WCAG AA at 6.9:1 (small bold
  threshold is 4.5:1). axe-core 4.11 appears to compute an effective
  background that includes a parent layer; the visual contrast is fine.
  Tracked for follow-up if axe behaviour persists or upstream fixes the rule.
- **Authenticated `/app/*` routes**: not in the baseline scan. Covered by the
  same shared chrome (top nav, AppShell footer, dialog primitives) so the
  marketing scan exercises the same component surface.
