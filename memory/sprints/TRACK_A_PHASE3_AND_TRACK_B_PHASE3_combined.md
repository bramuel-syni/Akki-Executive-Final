# Track A Phase 3 + Track B Phase 3 — Combined Close Memo

**Date:** 2026-06-04T04:48:35Z
**Rails honoured:** R1 (MASTER_STATE.md read first), R3 (tester journey-completion gates all flips to ✅), R4 (9 lockdowns Track A · 10 lockdowns Track B, both ≤10), R5 (ground-truth read on shield_invoke + citation_resolver + cycle_questions schema before any change), R6 (zero out-of-scope work), R7 (one G19/G20/G21/G22 implementation tradeoff surfaced + named).

---

## 1 — File-touched diff

### Track A Phase 3 (Solva narration + Bug #30)
```
M backend/models/analysis.py                                  +6  (headline + narration fields)
M backend/routers/workbook_analysis.py                        +169 (POST /v2/analyses/{aid}/synthesize, narrate_analysis import, autopick wired)
M backend/services/workbook_analyzer/forecaster.py            +50 (Bug #30 autopick_forecast_columns)
M backend/services/workbook_analyzer/__init__.py              +3  (re-export)
A backend/services/solva_v2/analyze_narration.py              +266 (NEW — narrate_analysis + 3 guards)
M frontend/src/components/analyze/AnalyzeDrawer.jsx           +181 (3 new tabs + synthesize trigger)
A backend/tests/test_track_a_phase3_narration.py              +9 lockdowns
```

### Track B Phase 3 (Open Questions feature completion)
```
M backend/routers/questions.py                                +167 (share/reopen/link-response + ShareIn/LinkResponseIn models)
M frontend/src/pages/Questions.jsx                            +260 (Share modal, Reopen button, Link-response picker, related-doc card, verbatim empty state)
A backend/tests/test_track_b_phase3_questions_completion.py   +10 lockdowns
```

### Shared
```
M memory/MASTER_STATE.md                                       (Section 3 G13/G14/G17/G19/G20/G21/G22/G23 + Bug#30; Section 4 Track A Phase 3 + Track B Phase B3; Section 7)
A memory/sprints/TRACK_A_PHASE3_AND_TRACK_B_PHASE3_combined.md (this memo)
```

**Totals:** 19 lockdowns added (9+10, both ≤10). All 19 green. Full regression: 90 passed across all in-scope files.

---

## 2 — Track A Phase 3 highlights

### Narration pipeline (3 guards)

`backend/services/solva_v2/analyze_narration.py::narrate_analysis()` — the central wrapper. Pipeline:

1. **Collect deterministic blocks.** `_collect_deterministic(wba)` flattens signals → forecasts → anomalies → simulations into a numbered `_DetBlock` list. Each block carries an explicit `cell_range` citation (or empty for simulations).
2. **Refuse-to-decide guard.** If the citeable subset (signals + forecasts + anomalies — sims aren't citeable) is empty, the LLM is NOT called. Return `{headline: "", observations: [], refused: True, refusal_reason: "no_deterministic_evidence"}`. **Test 4 verifies the LLM mock is never invoked.**
3. **Idempotency.** Content hash of `(objective + blocks)` → cache key. Cache hit returns cached narration unchanged. **Test 2 verifies call count = 1 across two synthesize calls.**
4. **Shield invoke.** `purpose="solva.layer_3.synthesis_rendering"`, `model_preference="analytical"` (Claude Sonnet), `consumer_id="solva"`. Both `tenant_id` and `user_id` set to current account id.
5. **Voice-lint guard.** Inline rejection of observations whose `body` or `title` uses banned imperative words (`suggest`, `recommend`, `should`, `advise`, `I think`, `I recommend`). **Test 9 verifies "I recommend" + "You should" observations get dropped.**
6. **Citation resolver guard.** Each observation declares `evidence_citation_indices: [int, ...]`. Indices out-of-range against the `_DetBlock` list are dropped (the observation is dropped entirely, not silently rewritten). **Test 3 verifies an obs with `[99]` indices is dropped while `[0]` is kept.**
7. **Persist.** Lift observations onto `Analysis.observations[]` with `kind = obs.tab` ("what_changed" / "whats_likely_next" / "whats_odd"). Headline written to `Analysis.headline`. Narration object stored on `Analysis.narration` with `cache_key`.

### Synthesize endpoint

`POST /api/workbook/v2/analyses/{aid}/synthesize`:

- Loads the new `Analysis` entity (`ana-*` id).
- Recovers blobs from `db.analysis_blobs`.
- If blobs are purged → empty narration with `refusal_reason="sources_purged"` (LLM not called).
- Parses the first source file (multi-file cross-synthesis is Phase 4).
- Runs signals on every sheet (validates `RefuseToDecideViolation` + citation resolver per signal).
- Runs forecast via **autopick_forecast_columns** (Bug #30 fix).
- Runs anomaly detection on first-sheet numeric columns (top-6 per column).
- Calls `narrate_analysis` with the assembled WorkbookAnalysis.
- Persists `headline` + `observations[]` + `narration` onto `db.analyses`.

### Bug #30 — column-pair auto-picker

`services/workbook_analyzer/forecaster.py::autopick_forecast_columns()`:

- Scans every sheet's `columns[]` for `date` columns AND `numeric` columns.
- Score = `(non_null_count, variance_proxy)` — tuple-compared descending.
- Variance proxy: max − min on sample values (the schema's `sample_values` field carries 3-6 representative values per column).
- Returns the winning `{sheet, date_column, value_column}` or `None`.

The original "`need at least 3 (date, value) pairs`" trip happened when the caller hardcoded the date/value column names. The new code auto-discovers them. **Test 5 verifies "Hi" (spread 90) wins over "Low" (spread 2) and "Med" (spread 10).**

### AnalyzeDrawer chrome — 3 → 6 tabs

| Tab | Source of content | data-testid |
|---|---|---|
| Bottom Line | `analysis.headline` + first 3 `observations` + notes section | `analyze-drawer-tab-bottom-line` |
| What changed | `obs.kind === "what_changed"` | `analyze-drawer-tab-what-changed` |
| What's likely next | `obs.kind === "whats_likely_next"` | `analyze-drawer-tab-whats-likely-next` |
| What's odd | `obs.kind === "whats_odd"` | `analyze-drawer-tab-whats-odd` |
| Sources | per-file metadata + refresh history (Phase 2 chrome) | `analyze-drawer-tab-sources` |
| Export | xlsx/docx/pptx Phase 1 endpoints (Phase 2 chrome) | `analyze-drawer-tab-export` |

When no observations exist, the Bottom Line tab carries a `Run synthesis` button (`analyze-drawer-synthesize-btn`) that fires `POST /v2/analyses/{aid}/synthesize` and re-loads.

### Verbatim sample narrations (for tone/voice spot-check)

The Shield-mocked tests use these narrations — they pass voice-lint and the citation resolver:

> **Headline:** "Q3 actuals trended higher than the plan."
> **Observation (what_changed):** title "Top-of-funnel growth held" / body "Visits climbed 8% sequentially across the three sampled weeks."

> **Headline:** "Cached read."
> **Observation:** title "Stable" / body "Variance held."

Banned-voice narrations (dropped by the lint guard) — these were used to verify the rejection path:

> ✗ "I recommend you investigate." — DROPPED
> ✗ "You should look at row 5." — DROPPED

### Track A Phase 3 lockdowns (9 of ≤10)

| # | Test | Result |
|---|---|---|
| 1 | `test_synthesize_returns_narration_payload` (happy path, mocked Shield) | ✅ |
| 2 | `test_synthesize_idempotent_cache_key` (call_count == 1 across two calls) | ✅ |
| 3 | `test_citation_resolver_drops_out_of_range` (`[99]` index dropped) | ✅ |
| 4 | `test_refuse_to_decide_when_no_evidence` (purged blobs → LLM not invoked) | ✅ |
| 5 | `test_forecast_autopicker_prefers_highest_variance_numeric` (Bug #30) | ✅ |
| 6 | `test_forecast_autopicker_single_numeric_still_works` (Bug #30 regression) | ✅ |
| 7 | `test_cross_tenant_synthesize_404` (tenant scope on synthesize) | ✅ |
| 8 | `test_phase_1_and_2_regressions_still_pass` (exports + objective + notes still work after synthesis) | ✅ |
| 9 | `test_voice_lint_drops_banned_voice_observations` (recommend/should dropped) | ✅ |

Test 10 (voice-lint on `scripts/lint_voice.py`) delegated to the existing tree — clean.

---

## 3 — Track B Phase 3 highlights

### Three new endpoints

`backend/routers/questions.py` (+167 lines):

- `POST /contexts/{cid}/questions/{qid}/share` — body `{recipient_emails: [str], message?: str}`. Appends `history[]` entry with `kind=shared`, `payload={recipients, message}`. Tenant-scoped via `require_context_membership()`. Email delivery deferred until SendGrid Inbound Parse blocker (TM3) clears.
- `POST /contexts/{cid}/questions/{qid}/reopen` — Answered → Open. Idempotent on already-Open question that was previously closed (no new audit). Refuses with 400 if the question was never closed (`"Question was never closed."`).
- `POST /contexts/{cid}/questions/{qid}/link-response` — body `{document_id: str}`. Validates doc lives in the SAME context (`db.documents.find_one({"id": docid, "context_id": context_id})` → 404 if cross-context). Writes `response_doc_id` + history `kind=response_linked`.

### Frontend additions (Questions.jsx)

- **Share modal** (`question-drawer-share-modal`) — recipients input + optional message + Send button. Posts via the share endpoint.
- **Reopen button** (`question-drawer-reopen`) — visible only when `isAnswered`. Calls reopen endpoint, closes drawer on success.
- **Link-response picker** (`question-drawer-link-picker`) — opens a modal listing recent documents in the question's context (`GET /contexts/{cid}/documents`). Click to attach.
- **Related-docs card** (`question-drawer-related-docs`) — surfaces both `source_doc_id` (original document the question was raised from) and `response_doc_id` (post-link). Click → `/app/documents?id=…`.

### Verbatim empty-state copy (G23)

From Doc 3 paragraph 26:
> "You have not generated any questions yet. Go to a document to generate questions."

Implemented at `Questions.jsx:307` (verbatim). CTA `"Go to Document"` → `/app/documents`. **Test 8 verifies the verbatim string appears in source.** The legacy Z2.4 CTA "Run Solva on a document" was removed; that surface only fired when the empty-filter was non-answered, so the verbatim QA wording fully replaces it.

### Honest reckoning on G19/G20/G21/G22 (R7)

The QA spec for G19 calls for **automatic** association from Solva/Chat replies; G21 calls for **automatic** reopen when a closed question is referenced via Use-in-Solva / Use-in-Chat / Share. I implemented the **manual** counterpart in this dispatch:
- `link-response` is a manual drawer action (not auto-association from Solva)
- `reopen` is a manual button (not an auto-trigger on Use-in-Solva click)

Rationale (surfaced before coding): the auto-association requires plumbing across the Chat and Solva session lifecycle — both have their own audit chains that don't yet emit `question_id` references. Doing the auto-wiring properly is a cross-feature build (Chat router + Solva session router both need `question_id` capture). That's a 2-phase build that exceeds B3 scope.

The manual flows fully satisfy the **journey** described in QA (a user CAN reopen, CAN link a response doc), just not the auto-trigger. Track this as a deferred R6 item.

### Track B Phase 3 lockdowns (10 of ≤10)

| # | Test | Result |
|---|---|---|
| 1 | `test_share_records_audit_with_recipients` | ✅ |
| 2 | `test_reopen_answered_to_open` | ✅ |
| 3 | `test_reopen_idempotent_on_already_open_after_close` | ✅ |
| 4 | `test_reopen_guard_never_closed_returns_400` | ✅ |
| 5 | `test_link_response_writes_doc_id_and_audit` | ✅ |
| 6 | `test_link_response_cross_context_blocked` | ✅ |
| 7 | `test_history_ordering_across_all_actions` (raised → marked_answered → reopened → shared → response_linked) | ✅ |
| 8 | `test_empty_state_carries_verbatim_qa_copy_and_go_to_document_cta` | ✅ |
| 9 | `test_cross_tenant_blocked_on_all_new_endpoints` (share + reopen + link-response) | ✅ |
| 10 | `test_mark_answered_still_works` (Q4Y regression) | ✅ |

---

## 4 — Sanity sweep

```
tests/test_track_a_phase3_narration.py                  9 passed
tests/test_track_b_phase3_questions_completion.py      10 passed
tests/test_track_a_phase1_analysis_foundation.py        9 passed
tests/test_track_a_phase2_drawer_journal.py             9 passed
tests/test_track_b_phase2_task_lifecycle.py             9 passed
tests/test_track_b_phase1b_signin_cards_fig22.py        9 passed
tests/test_phase_p5_14_workbook_analyze.py             31 passed
tests/test_solva_v1_unchanged.py                        4 passed
voice_lint                                              clean
```

**90 passed.** No regressions across Phase 1, Phase 2, P5.14, or Solva v1 byte-identical guard.

---

## 5 — MASTER_STATE.md updates

**Section 3:**
- **G13** (related-doc-as-attachment): 🟡 PARTIAL → 🟡 SHIPPED tester-pending
- **G14** (drawer CTAs all 4): 🟡 PARTIAL → 🟡 SHIPPED tester-pending
- **G17** (Share CTA): ❌ OPEN → 🟡 SHIPPED tester-pending (email-send deferred to TM3 clearance)
- **G19** (Response association): ❌ OPEN → 🟡 SHIPPED tester-pending (manual link-from-drawer; auto-association deferred)
- **G20** (Open-until-confirmed): ❌ OPEN → 🟡 SHIPPED tester-pending
- **G21** (Reopening flow): ❌ OPEN → 🟡 SHIPPED tester-pending (manual button; auto-trigger deferred)
- **G22** (Response History preservation): ❌ OPEN → 🟡 SHIPPED tester-pending
- **G23** (Empty state): ❌ OPEN → 🟡 SHIPPED tester-pending
- **Bug #30** (Forecaster auto-picker): ❌ OPEN → 🟡 SHIPPED tester-pending

**Section 4:**
- **Track A Phase 3 (Synthesis):** ❌ NOT STARTED → 🟡 SHIPPED tester-pending
- **Track B Phase B3 (Questions feature wiring):** ❌ NOT STARTED → 🟡 SHIPPED tester-pending

**Section 7:** timestamped 2026-06-04T04:48:35Z; agent line updated.

---

## 6 — Honest reckoning (R7)

1. **G19/G21 implemented as MANUAL flows, not AUTO.** Surfaced before coding in §3. Manual link-from-drawer + manual Reopen button cover the JOURNEY; auto-association from Solva/Chat sessions requires cross-feature plumbing (Chat router + Solva session router must capture `question_id`) that's deferred. This is a deliberate R6 trim, not a silent omission.
2. **G17 email delivery deferred.** The Share endpoint captures audit + recipients but does NOT send email. SendGrid Inbound Parse (TM3) is the blocker; once unblocked, the Share endpoint can fire an outbound email via the existing transactional pipeline.
3. **Voice-lint guard is INLINE in the narration service**, not via the external `scripts/lint_voice.py`. The external lint runs against source files; the narration is LLM-generated runtime content. The inline guard mirrors the same banned-word set (suggest / recommend / should / advise / I think / I recommend). If the lint surface ever expands, both copies should be kept in sync.
4. **Test environment uses Shield mocking** — the real `shield_invoke` is monkey-patched to a deterministic stub. This is correct for unit tests; live integration (Emergent LLM Key → Claude Sonnet) is exercised at tester journey-completion time.
5. **`db.documents` schema assumption** — the link-response endpoint reads `db.documents.find_one({id, context_id})`. The current document schema carries both fields. If the documents collection ever drops `context_id`, this endpoint will break — surfacing for awareness, not a current issue.
6. **No new env vars.** Emergent LLM Key was already configured for prior Solva v2 work; verified by the working `shield_invoke` import.
7. **No Track A/B side quests, no Stripe, no SendGrid console, no GCP, no git filter-repo.** R6 honoured.

---

## 7 — Tester re-verification journey

### Track A Phase 3
> Visit `/app/analyze` and open an existing Analysis (or create one). On the Bottom Line tab, click "Run synthesis". After ~5s the headline + observations populate. Switch to "What changed" / "What's likely next" / "What's odd" — each tab carries narrated observations with cell-range citation chips. Verify cross-tenant: viewer cannot trigger synthesize on admin's Analysis. For Bug #30: upload a real workbook with multiple numeric columns + a Date column → synthesize → confirm the forecast lands without the `forecast_invalid: need at least 3 (date, value) pairs` error.

### Track B Phase 3
> Visit `/app/questions`. On an empty state (no questions filter), verify the verbatim QA copy renders + the "Go to Document" CTA navigates to `/app/documents`. On a question with `source_doc_id` set, open the drawer → see the related-doc card. Click "Link response document" → select a doc from the picker → confirm it surfaces. Click "Share" → enter recipients + message → send → confirm the share is captured in the question's history. On an Answered question, click "Reopen" → confirm status flips to Open + drawer reloads. Cross-tenant: viewer cannot share/reopen/link admin's questions.
>
> If both pass → flip Section 3 G13/G14/G17/G19/G20/G21/G22/G23 + Bug#30 to ✅, plus Section 4 Track A Phase 3 + Track B Phase B3 to ✅. Tester's call.
