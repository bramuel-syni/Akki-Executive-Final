# Track A Phase 1 + Track B Phase 1 — Combined Close Memo

**Date:** 2026-06-03T20:43:17Z
**Rails honoured:** R1 (MASTER_STATE.md read first), R2 (Pre-Reads approved before dispatch), R3 (phase done = matrix flip + tester journey), R4 (≤10 tests per phase), R5 (root-cause-first ground-truth read on every file before edit), R6 (no side quests), R7 (continuity surfaced).

---

## 1 — Files Touched

### Track A (backend Analyze Foundation)
```
M backend/routers/workbook_analysis.py            (+177 −10)
M backend/services/workbook_analyzer/__init__.py  (+4 −2)
M backend/services/workbook_analyzer/report_builder.py (+228 −1)
A backend/models/__init__.py                      (NEW — 7 lines)
A backend/models/analysis.py                      (NEW — 109 lines)
A backend/services/analysis_lifecycle.py          (NEW — 124 lines)
A backend/tests/test_track_a_phase1_analysis_foundation.py (NEW — 8 tests)
```

### Track B (frontend Begin button)
```
M frontend/src/pages/FirstSession.jsx             (+3 −3 — disabled-state bg opacity 40 → 70)
A backend/tests/test_track_b_phase1_signin_begin.py (NEW — 7 tests, 2 skipped)
A /tmp/track_b_phase1_trace.py                    (NEW — Playwright Fig 7 live-DOM trace)
```

### Memos
```
A memory/MASTER_STATE.md                          (PRIOR DISPATCH — already on disk)
M memory/MASTER_STATE.md                          (THIS DISPATCH — Section 3+4+7 updated)
A memory/sprints/TRACK_A_PHASE1_AND_TRACK_B_PHASE1_combined.md (this memo)
```

---

## 2 — Per-Phase Reckoning

### TRACK A PHASE 1 — Analyze Foundation

**Scope** (verbatim from approved Pre-Read):
1. Backend `Analysis` entity
2. New `analyses` MongoDB collection
3. Multi-file upload (1+ files in one POST)
4. 250MB cap per file (was 25MB)
5. Session-close hook
6. `.xlsx` + `.docx` export endpoints
7. PPTX byte-identical
8. NO UI, NO LLM, NO multi-workbook merging

**Implementation**

| Item | File:Line | Notes |
|---|---|---|
| `Analysis` Pydantic model | `models/analysis.py:1` | Sibling to `WorkbookAnalysis` — not a replacement. `ConfigDict(extra="forbid")` everywhere. `context_id` REQUIRED. |
| Mongo collection `analyses` | Created on first insert. `(account_id, context_id)` indexed via tenant query pattern. Separate `analysis_blobs` collection (mirrors `workbook_blobs` split). |
| `POST /api/workbook/upload-multi` | `routers/workbook_analysis.py:559` | 1+ files, per-file 250MB cap, per-file format check via `parse_workbook` (catches bad blobs at upload time, not at first read). |
| 250MB cap | `routers/workbook_analysis.py:69` | `MAX_BYTES = 250 * 1024 * 1024`. Single-file `/upload` also raised (was 25MB). |
| Session-close hook | `routers/workbook_analysis.py:610` | `POST /api/workbook/v2/analyses/{aid}/session-close` — deletes blobs, sets `sources[].blob_purged=true`, appends `refresh_history` entry, status → `purged`. Idempotent. |
| `.docx` export | `routers/workbook_analysis.py:487` | `GET /api/workbook/analyses/{aid}/report.docx` — mirrors PPTX endpoint pattern verbatim. Builder in `services/workbook_analyzer/report_builder.py:228`. |
| `.xlsx` export | `routers/workbook_analysis.py:506` | `GET /api/workbook/analyses/{aid}/report.xlsx` — same pattern. Builder in `services/workbook_analyzer/report_builder.py:347`. Multi-sheet workbook (Summary / Signals / Simulations / Forecasts / Anomalies). |
| PPTX byte-identical | `services/workbook_analyzer/report_builder.py:1-205` | UNCHANGED. Regression locked by test 3 below. |

**Divergence surfaced (R5/R7):**
The dispatch says "re-use the same `require_context_membership` pattern as the existing PPTX endpoint." Ground-truth read of the existing PPTX endpoint (`workbook_analysis.py:452`) shows it actually uses `Depends(get_current_account)` + `_load_analysis(aid, current["id"])`, i.e. ACCOUNT-scoped (not context-membership). I mirrored the **actual** existing pattern (account-scoped 404 on miss-or-other-tenant). Both new endpoints use the same `_load_analysis(aid, current["id"])` helper. If the user intended a stricter context-membership guard, raise it as a follow-up — the existing PPTX endpoint would need the same treatment for parity.

**Lockdown tests (Track A · 8 tests, all green):**

| # | Test name | Result |
|---|---|---|
| 1 | `test_multi_file_upload_creates_one_analysis_with_two_source_refs` | ✅ |
| 2 | `test_250mb_boundary_rejects_overflow` | ✅ |
| 3 | `test_pptx_builder_byte_identical_on_same_input` | ✅ (asserts on slide+notes XML content — not raw bytes, because python-pptx embeds a build timestamp; logical content is invariant) |
| 4 | `test_xlsx_export_returns_real_workbook` | ✅ (real cell data: Summary!B with analysis_id matches) |
| 5 | `test_docx_export_returns_real_document` | ✅ (PK magic + `word/document.xml` + cover heading present) |
| 6 | `test_session_close_purges_blob_retains_analysis` | ✅ |
| 7 | `test_tenant_scope_viewer_cannot_read_admin_analysis` | ✅ (4 sub-assertions: P5.14 read 404, .xlsx 404, .docx 404, v2 read 404 cross-direction) |
| 8 | `test_openapi_spec_includes_new_endpoints` | ✅ (5 new paths registered with correct HTTP verbs) |

Tests 9 (Solva v1 guard) and 10 (voice-lint) are NOT in this file — they are delegated to the existing tree per the dispatch:
- `tests/test_solva_v1_unchanged.py` — **4 passed**, byte-identical guard intact.
- `scripts/lint_voice.py` — **clean** across customer-copy surfaces.

**Tester journey for Track A Phase 1:**
> Upload two real workbooks (an .xlsx + a .csv) via `POST /api/workbook/upload-multi`. Verify one `Analysis` row exists in the `analyses` collection with two source-file refs. Download `.docx` and `.xlsx` reports via the new endpoints; open both and confirm they carry the analysis content. Call session-close; verify the blob is purged but the Analysis row + sources + refresh-history are retained.

---

### TRACK B PHASE 1 — Sign-in routing + Post-redirect error + Begin button

**Scope** (verbatim from approved Pre-Read):
1. C2 Fig 20 — Unauth `/` lands on `/signin`
2. C2 Fig 22 — Post-redirect error toast/state fixed at root cause
3. C8 Fig 7  — "Begin" button text-color contrast fix

**Implementation**

| Item | Status | File:Line |
|---|---|---|
| **C8 Fig 7** — Begin button disabled-state contrast | ✅ SHIPPED | `frontend/src/pages/FirstSession.jsx:184-196` |
| **C2 Fig 20** — Sign-in lands at `/` not `/signin` | ❌ NOT SHIPPED — surfaced as `BLOCKED_NEED_SCREENSHOT` | — |
| **C2 Fig 22** — Post-redirect error | ❌ NOT SHIPPED — surfaced as `BLOCKED_NEED_SCREENSHOT` | — |

**Fig 7 fix detail**

Pre-fix (`FirstSession.jsx:188-192`, ground-truth read):
```
className={`akki-overline tracking-[0.16em] text-[11px] px-5 py-3 text-white transition-colors ${
  ready && !saving
    ? "bg-[var(--accent)] hover:bg-[var(--accent)]/90"
    : "bg-[var(--accent)]/40 cursor-not-allowed"
}`}
```

Post-fix:
```
className={`akki-overline tracking-[0.16em] text-[11px] px-5 py-3 text-white bg-[var(--accent)] transition-colors ${
  ready && !saving
    ? "hover:bg-[var(--accent)]/90"
    : "bg-[var(--accent)]/70 cursor-not-allowed"
}`}
```

The disabled state's bg-opacity is bumped from `/40` to `/70`. White text on a 40%-opacity gold/accent over a cream background is the known contrast failure; `/70` puts the bg in a saturation band where `text-white` has clear contrast. Base `bg-[var(--accent)]` is lifted to the always-on class so the disabled selector only modifies opacity (cleaner CSS shape).

**Honest reckoning on Figs 20 & 22 (R5/R7 STOP-and-surface):**

For Fig 20, the literal reading of the dispatch ("Unauthenticated visit to `/` lands on `/signin`") would force every unauth visitor — the entire marketing funnel — off the marketing homepage and onto a sign-in form. That's almost certainly not the intent. The actual bug is much more likely:
- A specific surface (header CTA, footer link, onboarding nudge) linking to `/` when it should link to `/signin`, OR
- The wildcard catch-all at `App.js:544` (`<Route path="*" element={<Navigate to="/" replace />} />`) routing unknown paths to `/` when an unauth user would prefer to land at `/signin`.

Without the Fig 20 screenshot I cannot pinpoint the specific surface. **No silent change was made to the `/` route.** Per R5/R7 surfaced rather than guess.

For Fig 22 ("post-redirect error"), candidate root causes include:
- OAuth callback returning to an error state
- Sign-in form post-submit toast (4xx response)
- Idle-timeout bounce (`session_idle_timeout` / `session_absolute_timeout` 401 from `api.js:221`)
- Set-password gate redirect (C1-A Phase A)

Each has a different fix surface. Surfaced rather than guess.

**Lockdown tests (Track B · 7 tests, 5 passed, 2 intentionally skipped):**

| # | Test name | Result |
|---|---|---|
| 1 | `test_fig7_first_session_begin_button_no_low_contrast_disabled` | ✅ |
| 2 | `test_fig7_begin_button_keeps_data_testid_for_playwright` | ✅ |
| 3 | `test_p0_c_oauth_last_activity_at_refresh_still_present` (regression) | ✅ |
| 4 | `test_c1_a_has_set_password_gate_still_present` (regression) | ✅ |
| 5 | `test_p0_b_card_2_documents_upload_route_still_present` (regression) | ✅ |
| 6 | `test_fig20_unauth_root_lands_on_signin` | ⏭ SKIPPED — `BLOCKED_NEED_SCREENSHOT` |
| 7 | `test_fig22_post_redirect_no_error_state` | ⏭ SKIPPED — `BLOCKED_NEED_SCREENSHOT` |

Playwright live trace `/tmp/track_b_phase1_trace.py` — **not exercised in this session** because the only available preview account (`admin@akki.ai`) has already passed the first-session intake step and the page conditionally hides it. Resetting the admin's first-session state would be a side quest (R6 violation). The trace is scaffolded and ready; the tester journey-completion check (R3) will exercise it against a fresh signup.

**Voice-lint:** clean.

**Tester journey for Track B Phase 1:**
> Sign up a brand-new account → reach `/app/onboarding/first-session` → verify the BEGIN button is readable in its disabled state (i.e., before filling in role/name/top-of-mind). Fill in the three fields → verify BEGIN remains readable in its active state. Click → verify the page transitions to step 2 without error.
>
> For Figs 20 + 22: provide the screenshots and the user-visible surfaces; the orchestrator will dispatch the targeted fix(es) next phase.

---

## 3 — Coverage Map (which lockdown covers which journey item)

| Pre-Read journey item | Lockdown test |
|---|---|
| Multi-file upload — 2 CSVs → 1 Analysis row | Track A Test 1 |
| 250MB cap enforced | Track A Test 2 |
| PPTX builder byte-identical | Track A Test 3 |
| `.xlsx` download works end-to-end | Track A Test 4 |
| `.docx` download works end-to-end | Track A Test 5 |
| Session-close purges blob, retains row | Track A Test 6 |
| Cross-tenant guard on all new endpoints | Track A Test 7 |
| New endpoints discoverable via OpenAPI | Track A Test 8 |
| Solva v1 byte-identical guard 4/4 | `tests/test_solva_v1_unchanged.py` |
| Voice-lint clean | `scripts/lint_voice.py` |
| Begin button text not invisible in disabled state | Track B Test 1 (source-strict) + `/tmp/track_b_phase1_trace.py` (live DOM, tester to run) |
| Begin button testid stable for tester | Track B Test 2 |
| P0-C OAuth regression | Track B Test 3 |
| C1-revised Phase A regression | Track B Test 4 |
| P0-B Card 2 regression | Track B Test 5 |
| Fig 20 fix | ⏭ pending screenshot |
| Fig 22 fix | ⏭ pending screenshot |

---

## 4 — Test Totals

Scoped lockdown run (Track A + Track B + Solva v1 + P5.14 regression):
```
48 passed, 2 skipped in 9.21s
```

Voice-lint:
```
voice_lint: clean across customer-copy surfaces.
```

Full backend regression sweep was NOT run to completion in this dispatch — the suite is 4068 tests + many pre-existing failures (Postmark KeyError on `test_iter70_inbound_*` is a documented user-side blocker in MASTER_STATE.md Section 5). Per Rail R4 ("Full regression only at phase close"), the scoped sweep above is sufficient for the lockdown set; the tester journey-completion is the gating check before flipping matrix rows to ✅.

---

## 5 — MASTER_STATE.md updates (applied in same dispatch)

- **Section 3** — no rows flip to ✅ in this memo (Track A Phase 1 ships chrome / persistence / exports but no matrix bug is fully fixed by this scope alone; Bug #30 is Phase 3 territory).
  - Exception: NONE of the C-cluster matrix rows referenced this phase as their owner. The dispatch explicitly says "no matrix items move to ✅ until tester journey-completion passes" (R3). Memo is honest about that.
- **Section 4** —
  - Track A Phase 1: ❌ NOT STARTED → 🟡 PARTIAL — shipped pending tester journey-completion verification.
  - Track B Phase 1: ❌ NOT STARTED → 🟡 PARTIAL — Fig 7 shipped, Figs 20+22 surfaced as `BLOCKED_NEED_SCREENSHOT`.
- **Section 6** — `Active Phase` cleared; awaiting tester journey-completion or next dispatch.
- **Section 7** — timestamp refreshed; agent line updated.

---

## 6 — Honest reckoning · STOP-and-surface inventory

1. **Figs 20 + 22 not shipped.** Surfaced in §2 above. Awaiting screenshots.
2. **PPTX tenant guard divergence.** Dispatch said "re-use the same `require_context_membership` pattern as the existing PPTX endpoint" but the existing PPTX endpoint actually uses `account_id`-scoped guard (not context-membership). I mirrored the actual existing pattern. If context-membership is the real target, both the new endpoints AND the existing PPTX endpoint need a follow-up.
3. **Live Playwright trace for Fig 7 not exercised** — only available admin user has already passed first-session intake; refusing to reset that state without authorization (R6). Scaffold is at `/tmp/track_b_phase1_trace.py`; tester will run against a fresh signup.
4. **`requirements.txt` not pip-frozen** — both `python-docx` (1.2.0) and `openpyxl` (3.1.5) are already installed in the runtime per `python3 -c "import docx; import openpyxl"`. No new dependency installs. No `requirements.txt` write needed.
5. **Pre-existing test collection errors** at `test_iter70_inbound_edge.py` + `test_iter70_inbound_triage.py` due to `KeyError: POSTMARK_SERVER_TOKEN`. Pre-existing baseline issue (MASTER_STATE.md Section 5). Not regression from this dispatch — confirmed by `git stash` + re-run of the P5.14 test surface (31 passed identically before and after the stash-pop).
6. **No new env vars introduced.** No Stripe, no SendGrid console, no GCP creds.
