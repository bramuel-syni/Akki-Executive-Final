# Production Hardening Sprint — Log

**Sprint dispatched:** 2026-05-25, immediately after session closeout (T1-T5 + backlog-b + chunk-d + J1-J4 + chunk-c). 5-step user-approved sequence.

**Pre-hardening hygiene:**

| Artifact | Path / detail | UTC timestamp |
| --- | --- | --- |
| Git tag | `v-pre-hardening -m "snapshot before production-hardening sequence"` (local-only) | 2026-05-25T16:35Z |
| Mongo dump | `/app/backup/pre_hardening_20260525T163546Z/` (78 MB, 240+ collections) | 2026-05-25T16:35:46Z |

**Steps (sequence locked at user dispatch):**
1. ClamAV prod-status verification endpoint — IN PROGRESS
2. False-green pattern sweep — pending
3. (steps 3-5 TBA at user dispatch)

---

## Step 1 — ClamAV prod-status verification endpoint

### Goal
Settle the security-posture question raised at the close of the preview-environment EICAR spot-check. We confirmed `clamd` is STOPPED in the preview env (`upload_scan_log` rows show `scan_result=bypassed` under the dev-bypass branch). Need a clean way to verify clamd's status in prod (and any env) without shell access.

### Implementation

**New endpoint:** `GET /api/healthz/clamav` — read-only health-status report. Unauthenticated, same surface stance as the existing `/api/healthz/shield` Shield readiness probe. HTTP 200 always (this is a status report, not a gate). Mirrors the H2.5 follow-up Part B convention.

**Response shape:**

```json
{
  "clamd_daemon": "alive" | "unreachable" | "unknown",
  "clamd_ping_response_ms": <number or null>,
  "last_scan_at_utc": "<ISO timestamp or null>",
  "scans_last_24h": {
    "ok": <n>,
    "infected": <n>,
    "bypassed": <n>,
    "error": <n>
  },
  "checked_at_utc": "<now ISO>",
  "preflight_size_check_active": true
}
```

**Behavior:**
- Issues a `clamd.ClamdNetworkSocket(host=CLAMAV_HOST, port=CLAMAV_PORT, timeout=3).ping()`. Times the round-trip. Classifies `alive` on success.
- `ClamAVUnreachable` (network refused / dns failure / clamd python missing / etc.) → `unreachable` with `clamd_ping_response_ms: null`. **HTTP 200.**
- Anything else → `unknown` with the exception class surfaced via `debug.exception_class`.
- Reads `upload_scan_log` to compute `last_scan_at_utc` and the 24h scan-result histogram. Empty log → `last_scan_at_utc: null`, all counts zero.
- Reports `preflight_size_check_active: true` unconditionally — `CLAMAV_MAX_FILE_SIZE_BYTES` is a hard-coded service constant (currently 25 MB) and the preflight always fires before any clamd I/O.

**Files:**

| File | Change |
| --- | --- |
| `backend/routers/healthz_clamav.py` | NEW. ~120 lines. Same `APIRouter(prefix="/api/healthz", tags=["healthz"])` shape as `healthz_shield.py`. Reads constants from `services.clamav_service` (CLAMAV_HOST, CLAMAV_PORT, ClamAVUnreachable, UPLOAD_SCAN_LOG_COLLECTION) but does NOT modify the service. Lazy-imports `clamd` to match the dev-bypass tolerance pattern used in `_scan_blocking`. |
| `backend/server.py` | +2 lines. Imports `healthz_clamav` router and registers via `app.include_router(...)`. |
| `backend/tests/test_hardening_step1_healthz_clamav.py` | NEW. 5 anchor-chain tests covering all 3 daemon states + 24h histogram + schema-shape behavior assertion. |

### Tests (anti-false-green discipline)

| Test | Anchor chain | Pre-fix evidence |
| --- | --- | --- |
| `test_step1_alive_branch` | monkeypatch `clamd.ClamdNetworkSocket.ping` to return success → response `clamd_daemon == "alive"` AND `clamd_ping_response_ms` is a positive number | Pre-endpoint: 404. Post-endpoint: PASS. |
| `test_step1_unreachable_branch` | monkeypatch `clamd.ClamdNetworkSocket` to raise `ConnectionRefusedError` → response `clamd_daemon == "unreachable"` AND `clamd_ping_response_ms is None` AND HTTP 200 (not 503) | Pre: 404. Post: PASS. |
| `test_step1_unknown_branch` | monkeypatch ping to raise an unrelated `ValueError` → response `clamd_daemon == "unknown"` AND `debug.exception_class == "ValueError"` AND HTTP 200 | Pre: 404. Post: PASS. |
| `test_step1_histogram_24h_from_upload_scan_log` | seed 4 `upload_scan_log` rows (one of each result, all within 24h) → response `scans_last_24h == {"ok": 1, "infected": 1, "bypassed": 1, "error": 1}`. Plus a stale row >24h → still 4, not 5 | Pre: 404. Post: PASS. |
| `test_step1_empty_log_branch` | drop `upload_scan_log` collection → `last_scan_at_utc is None` AND all counts zero. | Pre: 404. Post: PASS. |
| `test_step1_schema_shape_live` | Hits the actual endpoint (no monkeypatch) — asserts the schema keys are all present and the daemon state is one of the allowed strings. Daemon classification not asserted (env-dependent). | Pre: 404. Post: PASS. |

### Canonical clamd status check

`GET /api/healthz/clamav` is the canonical endpoint for verifying clamd daemon status in any environment going forward. Operators / ops dashboards / Kubernetes liveness probes can hit it without authentication. The legacy `services.clamav_service.healthcheck()` function remains in place for the `/admin/health` admin surface; new monitoring should prefer the new endpoint because:
- It's stable wire-format (vs. the looser `healthcheck()` dict).
- It surfaces 24h scan distribution (forensic value).
- It distinguishes `unreachable` from `unknown` (helps triage clamd vs. network vs. python-package issues).

### Live-probe surface bug caught + fixed

When I first hit `GET /api/healthz/clamav` in this preview env (immediately after the initial implementation), the response was:

```json
{
  "clamd_daemon": "unknown",
  "debug": {"exception_class": "ConnectionError"},
  ...
}
```

This was WRONG — clamd being stopped IS the canonical "unreachable" state. The bug:
- The `clamd` library raises its OWN `clamd.ConnectionError` class which inherits from `clamd.ClamdError → Exception`. It does NOT inherit from Python's built-in `ConnectionError`.
- My initial except clause `except (ConnectionError, ConnectionRefusedError, OSError, TimeoutError):` therefore didn't catch the lib's `ConnectionError` and fell through to the catch-all `unknown` branch.

**Fix:** in `_ping_clamd()`, after the lazy `import clamd`, dynamically extend the `unreachable_exc_types` tuple to include `clamd.ConnectionError` and `clamd.ClamdError` if they exist on the module. Catch them explicitly.

**Added regression test** `test_step1_unreachable_branch_clamd_lib_connection_error` — pins the fix: a fake `clamd` module whose PING raises an exception modeled on the lib's hierarchy must classify as `unreachable`, not `unknown`.

**Confirmed live**: after the fix, `GET /api/healthz/clamav` in the preview env returns:

```json
{
  "clamd_daemon": "unreachable",
  "clamd_ping_response_ms": null,
  ...
  "preflight_size_check_active": true
}
```

HTTP 200. No `debug` key (correctly suppressed on the unreachable path). This proves the unreachable branch works end-to-end in production-shaped traffic — clamd stopped in this preview pod, surface honestly reports it.

### Status

**Step 1 IN PROGRESS.** Implementation + tests landed; pending e1_tester verification.

---

## 2026-05-25 — Step 1 closure

**e1_tester verdict: 3/3 PASS.** Endpoint returns canonical schema in all branches. Live preview-env probe correctly classifies as `unreachable` after the `clamd.ConnectionError` regression-fix. HTTP 200 + no `debug` key on the unreachable path. 24h histogram + most-recent-scan timestamp behave correctly.

**Git tag `v-post-hardening-step-1`** created (local-only). Marks the post-Step-1 worktree boundary; Phase A audit reads against this tag.

**User runs `/api/healthz/clamav` against prod independently** — agent doesn't block on this; user will surface findings if any.

**Step 1 status: CLOSED.**

---

## Step 2 — False-green pattern sweep (audit + surgical fixes)

### Goal

Find and fix the same class of bugs we caught at T2.3, B3, and J2.3 before they bite real users on the cold onboarding surface. Three known patterns from the closeout doc lessons (§5.6, §5.7, §5.8).

### Phase A — Read-only audit

Static-analysis script at `/app/scripts/hardening_step2_phase_a_audit.py`. Ledger at `/app/memory/sprints/FALSE_GREEN_AUDIT_LEDGER.md`.

**Raw sweep counts:**

| Pattern | Total raw hits | Real findings (post-triage) | False-positive / legitimate-conditional |
| --- | --- | --- | --- |
| P1 — T2.3 (conditional render hiding spec sections) | 246 | **1** (`AppShell.jsx:432` trust-center-tooltip) | 245 (legitimate conditional UI) |
| P2 — B3 (undefined-symbol-in-conditional) | 4 | **0** (all 4 false positives — locally-destructured props) | 4 |
| P3 — J2.3 (auth-writer-without-refresh) | 5 | **3** (FirstSession::onIntakeSubmitted / onArtefactReady / onSkip) | 2 (SignIn/SignUp correctly call `afterAuth`) |

**4 real findings from the static audit** — all P0 (onboarding hot path).

### Phase B — Surgical fixes

**Fix 1 — `AppShell.jsx:432` trust-center-tooltip DOM-unconditional** (P1/T2.3, mirrors J4 G31 pattern).
- Removed the `{onbStatus?.trust_center_tooltip?.show && (...)}` JSX gate.
- Wrapper now renders unconditionally with `data-tooltip-visible="true|false"` + CSS class flip (`pointer-events-auto opacity-100` vs. `pointer-events-none invisible opacity-0`).
- Test: `S2.A` — 3-anchor chain (no `&& (` gate · `data-tooltip-visible` attribute · class flip both directions).

**Fix 2-4 — `FirstSession.jsx` auth-writer paths** (P3/J2.3 recurrence).
- `onIntakeSubmitted`, `onArtefactReady`, `onSkip` — all three switched from `refreshContexts()` to `bootstrap()`. `bootstrap()` re-fetches `/auth/me` so `account.first_session.*` stays fresh after the auth-mutating endpoints fire. `refreshContexts()` only touches the contexts list and leaves `account` state stale.
- Tests: `S2.B`, `S2.C`, `S2.D` (per-callback anchor-chains) + `S2.E` (cross-file confirmation that `bootstrap` is destructured from `useAuth()` in the FirstSession component).

### Phase C — Generalized ESLint rule

Added two rules to `craco.config.js::ESLintPlugin`:
- `"react/jsx-no-undef": "error"` — catches any JSX symbol not in scope.
- `"no-undef": "error"` — catches any plain-JS identifier not in scope.

Both fire at webpack build time. Together they pin the B3 pattern at CI level — closer to source than the post-hoc grep audit.

**Phase C immediately surfaced TWO additional real B3 sites** that my static audit script missed (because regex can't walk JS scope chains):

| Site | Symbol | Impact |
| --- | --- | --- |
| `frontend/src/components/solva/AttachDocumentModal.jsx:201` | `<Search />` lucide icon | Not imported. `ReferenceError` whenever the empty-state JSX for the journal tab rendered. |
| `frontend/src/pages/WorkStudio.jsx:669` | `navigate(...)` | Top-level `WorkStudio` never called `useNavigate()`. The line-213 `navigate` belongs to the sibling `BriefDrawer` scope. `ReferenceError` whenever a user clicked a Board Pack / Committee Pack card (G8-ratified routing). |

Both fixed in the same chunk:
- AttachDocumentModal.jsx — added `Search` to the `lucide-react` named-import list.
- WorkStudio.jsx — added `const navigate = useNavigate();` at the top of the `WorkStudio()` body.

Tests: `S2.F` (rules pinned in craco config), `S2.G` (Search import pinned), `S2.H` (WorkStudio useNavigate pinned).

### Tests

| Test | Anchor | Pre-fix |
| --- | --- | --- |
| `S2.A` test_s2_a_trust_center_tooltip_dom_unconditional | no-gate regex · `data-tooltip-visible` · class-flip CSS | FAIL |
| `S2.B` test_s2_b_on_intake_submitted_calls_bootstrap | setState · bootstrap() · no refreshContexts() | FAIL |
| `S2.C` test_s2_c_on_artefact_ready_calls_bootstrap | POST URL · setState(data.state) · bootstrap() · no refreshContexts() | FAIL |
| `S2.D` test_s2_d_on_skip_calls_bootstrap | POST URL · bootstrap() · no refreshContexts() · navigate("/app") | FAIL |
| `S2.E` test_s2_e_first_session_landing_destructures_bootstrap | useAuth() destructure carries `bootstrap` | PASS (J2.3 already wired it) |
| `S2.F` test_s2_f_craco_eslint_pins_b3_pattern | `react/jsx-no-undef: error` + `no-undef: error` in craco | FAIL |
| `S2.G` test_s2_g_attach_document_modal_imports_search_icon | `Search` in lucide-react named imports + used in JSX | FAIL |
| `S2.H` test_s2_h_work_studio_top_level_has_use_navigate | `const navigate = useNavigate();` inside WorkStudio body | FAIL |

**7/8 fail pre-fix vs `v-post-hardening-step-1`.** 8/8 PASS post-fix.

### Full pytest

```
$ cd /app/backend && python -m pytest -q --no-header --tb=no
1 failed · 1224 passed · 490 skipped · 88 warnings in 256.78s (4:16)
```

- Post-Step-2 passing count: **1224** (= 1216 prior post-Step-1 + 8 new Step-2 tests).
- Zero regressions.
- The 1 failure is the same pre-existing `test_real_requirements_file_is_clean`.

### Phase C pinning value

Phase C's ESLint rules immediately surfaced 2 real bugs my static-analysis script couldn't detect. Going forward, ANY future cherry-pick or new component that smuggles a B3-pattern bug will break the webpack build instead of silently waiting for a user to hit the conditional branch. This is a permanent quality gate — recommend NEVER demoting these rules from `error` to `warn`.

### Status

**Step 2 IN PROGRESS.** Implementation + tests landed; pending e1_tester verification.
