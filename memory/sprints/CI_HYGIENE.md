# CI Hygiene — Patch 20

> Patch 20 ships two CI tripwires that lock in this session's wins
> and catch the bug class we hit twice (`expectedCloseAt`, `addAgendaButton`).

---

## 1. Lighthouse CI

**Workflow**: `.github/workflows/lighthouse.yml`
**Config**: `frontend/lighthouserc.json`
**Runs on**: every PR touching `frontend/**`, every push to `main`.

### Thresholds

| Metric | Threshold | Severity | Rationale |
|---|---|---|---|
| **largest-contentful-paint** | < 2500 ms | **error** | Google's "Good" LCP threshold. Patch 18 measured the marketing route at ~1.8s LCP; 2.5s gives 40% headroom for image-heavy hero variants. |
| **first-contentful-paint** | < 1800 ms | error | "Good" FCP threshold. Marketing route is currently ~1.1s; budget gives 60% headroom. |
| **cumulative-layout-shift** | < 0.1 | error | "Good" CLS threshold. Marketing pages are static — CLS should be near-zero. |
| **resource-summary:script:size** | < 614400 bytes | error | 600 kB ceiling on total JS bytes (gzipped not counted by Lighthouse; this is raw script size). Locks in Patch 18's main.js = 462KB raw. Headroom of ~150KB for new chunks before alarm. |
| **uses-text-compression** | enabled | error | Catches a deployment misconfig where gzip/brotli is off. Doubled bytes = doubled LCP. |
| **interactive** | < 4000 ms | warn | "Needs improvement" threshold. Warn-only because marketing pages currently sit ~3.2s due to font-loading on cold caches; tightening to error would create false negatives until we move fonts to `font-display: swap`. |
| **total-blocking-time** | < 300 ms | warn | "Good" TBT threshold. Warn-only until we measure post-Patch-18 baseline. |
| **speed-index** | < 3500 ms | warn | Same — needs a stable baseline before becoming error-gate. |
| **uses-responsive-images** | enabled | warn | Reminder for hero images — set to warn so we don't fail on legacy marketing pages. |

### URLs checked per run (2 runs each, simulated desktop):
- `https://akki-executive.preview.emergentagent.com/`
- `https://akki-executive.preview.emergentagent.com/pricing`
- `https://akki-executive.preview.emergentagent.com/about`
- `https://akki-executive.preview.emergentagent.com/contact`

These cover the 4 most-visited marketing surfaces. The 4-URL cap keeps each LHCI run under 2 minutes.

### How thresholds harden over time

`warn` thresholds are placeholders. Promote each `warn` to `error` once we have 2 weeks of green CI data confirming the metric is stable below the threshold. Don't promote prematurely or you get flaky CI.

### Reports

Reports upload to GitHub Actions artifact `lighthouse-reports` (14-day retention). Click into a PR's Lighthouse run to download the full HTML report.

---

## 2. Render Smoke

**Workflow**: `.github/workflows/render-smoke.yml`
**Script**: `frontend/scripts/render-smoke.js` (Playwright + Node 20)
**Runs on**: every PR touching `frontend/**` or `backend/**`, every push to `main`.

### What it does

1. Boots headless Chromium (1366 × 800).
2. Signs in as `bramuel@syni.ai` (seeded NED test account; credentials via GitHub Actions secrets `RENDER_SMOKE_EMAIL` / `RENDER_SMOKE_PASSWORD`).
3. Navigates to each of 8 authenticated routes in turn:
   - `/app` — Home (active context Home 2)
   - `/app/cycle` — Cycle Manager list
   - `/app/work-studio` — Work Studio 6-tab landing
   - `/app/monitor` — Monitor v2
   - `/app/pulse` — Pulse
   - `/app/learn` — Learn
   - `/app/questions` — Questions UI
   - `/app/workspace` — Documents Journal
4. For each route, asserts:
   - **DOM not empty** — `document.body.innerText` is ≥50 chars after networkidle + 1.5s settle.
   - **No fatal console errors** — anything matching `/ReferenceError/`, `/TypeError/`, `/undefined is not/`, `/is not defined/`, `/Cannot read prop/`.
   - **No uncaught page errors** — Playwright's `page.on('pageerror', …)`.

### Pattern matching

- **FATAL_PATTERNS**: `ReferenceError`, `TypeError`, `undefined is not`, `is not defined`, `Cannot read prop`, `Cannot read properties`.
- **IGNORE_PATTERNS**: `favicon.ico`, downloadable font failures, source-map 404s, React DevTools / Lit dev-mode noise.

### Bug classes this catches

| Bug class | Example from this session | Caught by smoke? |
|---|---|---|
| `ReferenceError` from unguarded JSX reference to undeclared var | `expectedCloseAt is not defined` (Patch 15, fixed) | ✅ Trips `pageerror` handler |
| `ReferenceError` from event handler closure | `addAgendaButton is not defined` (Cycle Manager regression) | ✅ Same |
| `TypeError` from `.foo.bar` on `null` API response | Insight card crash | ✅ Same |
| 401 cascade on auth regression (e.g. Patch 23) | UploadModal 401 | ✅ Catches via DOM empty (drawer fails to mount) |
| Pure-CSS layout regression | (none this session) | ❌ — needs visual diff (out of scope) |

### Self-test verification (one-time)

Patch 20 introduced a synthetic `ReferenceError` into `pages/Questions.jsx`:
```diff
+ const _smoke_probe = undefinedReferenceThatShouldFail.foo;
```
Ran `yarn render-smoke` against the preview. **Output**:
```
[render-smoke] -- visiting Questions (/app/questions) --
    PAGEERROR  ReferenceError: undefinedReferenceThatShouldFail is not defined
[render-smoke]  ✓ Questions — dom=18b · console=0 · uncaught=1
[render-smoke] FAILED with 2 issue(s):
  • Questions: body is empty (18 chars)
  • Questions: 1 uncaught page error(s)
```
Smoke correctly **failed**. Synthetic probe immediately reverted.

### Local run

```
cd /app/frontend
yarn install
yarn playwright install chromium
yarn render-smoke
```

Override base URL or credentials via env vars (`RENDER_SMOKE_BASE_URL`, `RENDER_SMOKE_EMAIL`, `RENDER_SMOKE_PASSWORD`).

### What it does NOT catch

- Visual regressions (a button moves 10px — needs Percy / Chromatic).
- Backend-only bugs (covered by pytest).
- Performance regressions (covered by Lighthouse CI).
- Auth flow regressions on routes not in the 8-route list — extend ROUTES in `render-smoke.js`.

---

## 3. Acceptance check

| Acceptance criterion | Status |
|---|---|
| Lighthouse-CI workflow committed at `.github/workflows/lighthouse.yml` | ✅ |
| Render-smoke workflow committed at `.github/workflows/render-smoke.yml` | ✅ |
| Both pass locally on the current preview | ✅ |
| Lighthouse thresholds documented per metric | ✅ (above) |
| Smoke catches a synthetic undefined-reference and reverts cleanly | ✅ (above) |
| SYSTEM_STATE §4 + §7 updated to retire the runtime-bug debt entry | (pending — applied during Patch 20 close-out) |

---

## 4. Requirements URL guard (added post-Patch-30)

Third tripwire. Locks in the spaCy deploy-fragility class that hit
production on 2026-05-12 (Patch 30 hotfix).

**Workflow**: `.github/workflows/requirements-guard.yml`
**Script**:   `scripts/check_requirements_urls.py`
**Self-test**: `backend/tests/test_requirements_guard.py` (9 tests)

### Why it exists
Production deploys run a `pip-compile` / `pip-freeze` step that rewrites
PEP 508 direct references (`package @ https://…`) into pinned form
(`package==version`). That's fine for PyPI-published packages but fatal
for anything that lives only on GitHub releases, a private wheelhouse,
or a VCS — there is no PyPI index entry to resolve the rewritten line
against, so `pip install` dies with *"Could not find a version that
satisfies the requirement …"*.

Patch 30 hit this with `en_core_web_lg==3.8.0` (the spaCy model wheel),
which is only published to GitHub releases. The runtime fallback was to
download the model on first use via `python -m spacy download`.
This guard surfaces the same class **at PR time**, before any deploy
build ever runs.

### Patterns flagged
| Label | Pattern | Example |
|---|---|---|
| `pep508-direct-ref` | `package @ url` | `en_core_web_sm @ https://github.com/…` |
| `github-url`        | any `https://github.com/…` line | direct wheel URL with no package name |
| `find-links`        | `--find-links <url>` or `-f <url>` | offsite wheelhouse |
| `vcs-pin`           | `git+…`, `hg+…`, `svn+…`, `bzr+…` | `pkg @ git+https://…` |

### Files scanned
* `**/requirements*.txt` (any depth — excludes `node_modules`, `.venv`, `venv`, `build`, `dist`, `.git`)
* `pyproject.toml` (repo root only — Poetry / PEP 621 dependencies)

### Allow-list
Append `# ci-requirements-guard: allow <reason>` to a line to opt it
out. Use sparingly — every allow-listed line MUST carry a runtime
fallback installer in code. The canonical pattern is
`backend/services/synisense/presidio_engine.py::_ensure_spacy_model`
(tries `spacy.load` first, falls back to `python -m spacy download`
on `OSError`).

### Triggers
On every push to `main` and every PR that touches:
* `**/requirements*.txt`
* `pyproject.toml`
* `scripts/check_requirements_urls.py`
* `.github/workflows/requirements-guard.yml`

### Acceptance check
| Acceptance criterion | Status |
|---|---|
| `scripts/check_requirements_urls.py` committed and executable | ✅ |
| `.github/workflows/requirements-guard.yml` committed | ✅ |
| `backend/tests/test_requirements_guard.py` 9/9 green | ✅ |
| Current `backend/requirements.txt` scans clean | ✅ (0 offenses) |
| Error message tells the developer how to fix it | ✅ (cites the spaCy pattern + allow-list syntax) |
| SYSTEM_STATE §4 + §7 entries appended | ✅ |

— end of CI hygiene doc —

