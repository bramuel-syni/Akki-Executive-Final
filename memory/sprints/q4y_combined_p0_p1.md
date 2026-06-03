# Q4Y combined dispatch — P0 + P1 in one ship
**Date:** 2026-02 (sprint, fork-resume)
**Scope:** Q4Y "Questions for you" surface — P0-S1 (sort wiring),
P0-C3 (Mark as Answered), P1-C1 (Use in Solva), P1-C2 (Use in
Chat), P1-F3 (server-side text search), P1-S2 (Sort by
answered_at, covered by S1).
**Author:** main agent (autonomous on user scope approval)

---

## Spec grounding

**No external Q4Y spec doc exists in `/app/memory/`.** Per the
prior gap-analysis dispatch, your dispatch + the de facto
contract from Pulse/DocumentDrawer/TaskDrawer is the spec. Every
wiring decision cites the reused pattern below.

| Item | Reused pattern (cited) |
|---|---|
| P1-C1 "Use in Solva" | `frontend/src/lib/takeToSolva.js` (Pulse caller at `pages/Pulse.jsx:607-613`); backend resolver `routers/solva_v2.py::fetch_take_to_solva_seed` |
| P1-C2 "Use in Chat" | `routers/chat.py::LinkedContextIn` allow-list + `_resolve_linked_context` branch matching the `document`/`task`/`cycle`/`work_studio_artefact` shape |
| P0-C3 idempotency + tenant scope | Mirrors `routers/questions.py::answer_question` and the `require_context_membership` dependency used elsewhere in the router |
| P0-S1 sort + P1-F3 q-search | Backend query mutation patterns from the existing `list_questions` endpoint; client URL-param sync from the existing `filter`+`role` chips |

---

## Honesty Protocol — what shipped

### Backend changes (5 routers)

| File | Change | Cite |
|---|---|---|
| `routers/questions.py` | Added `_SORT_KEYS` map; added `q`/`sort` params to `/me/questions`; added `sort` to `/contexts/{cid}/cycles/{cid}/questions`; added `POST /contexts/{cid}/questions/{qid}/mark-answered`; `_strip()` now drops `_qa_seed` marker | `questions.py:1-110, 141-170, 263-326` |
| `routers/solva_v2.py` | New `kind="question"` branch in `fetch_take_to_solva_seed`; doc-comment lists `question`; supported-kinds error string lists `question` | `solva_v2.py:152-156, 2017-2042, 2150-2155` |
| `routers/chat.py` | `LinkedContextIn._check_ctx_type` allow-list now includes `question`; `_resolve_linked_context` has the `question` branch returning `{ctx_type, ctx_id, title, excerpt, href}` | `chat.py:175-189, 339-381` |
| `routers/admin_qa_hooks.py` | New `POST /api/admin/qa/seed/question` super-admin-gated harness | `admin_qa_hooks.py:264-322` |

### Frontend changes (1 file)

| File | Change |
|---|---|
| `frontend/src/pages/Questions.jsx` | (a) Wired the dead sort dropdown to URL `?sort=` with 3 keys; default `recent` stripped from URL; (b) Added `q` query param to backend list call (server-side narrowing); (c) Added 3 drawer CTAs: `Mark as Answered` (POST + toast), `Use in Solva` (calls `takeToSolva({navigate, kind:"question", id})`), `Use in Chat` (navigates to `/app/chat?ctx_type=question&ctx_id=...`); (d) Passed `navigate` to QuestionDrawer; (e) Added `Zap`, `MessageCircle`, `Check` lucide icon imports + `takeToSolva` import |

### NOT touched (per hard constraints)

- No new entity types — `cycle_questions` schema unchanged. New `marked_answered` is just a new string in the existing `history[].kind` array.
- No new chat/Solva flows — both CTAs reuse the existing seed/allow-list paths.
- No new env vars.
- Manual pricing untouched.
- No git filter-repo / SendGrid console / GCP creds touched.
- `assignee` filter (P2-F4) NOT added — deferred per your decision.

---

## Lockdown tests (5 new files, 34 new tests)

| File | Tests | Coverage |
|---|---|---|
| `test_q4y_p0_s1_sort_wiring.py` | 7 | Source-strict, 3 sort keys exercise correct ordering, unknown sort → 400, idempotency on repeat call |
| `test_q4y_p0_c3_mark_answered.py` | 7 | Source-strict, status flip + history append, idempotent re-call, works without note, tenant scope (cross-context → 403/404), 404 on missing question |
| `test_q4y_p1_c1_use_in_solva.py` | 6 | Source-strict, seed payload short + long text, citation_label format `"Question · {first 60 chars}…"`, 404 missing, **negative-leak** cross-tenant guard (calls `/api/solva/v2/seed` directly) |
| `test_q4y_p1_c2_use_in_chat.py` | 8 | Source-strict, seed shape for open + answered, long-title truncation, **negative-leak** cross-tenant via wrong `context_id`, `LinkedContextIn` validator allow-list |
| `test_q4y_p1_f3_server_search.py` | 6 | Source-strict (`re.escape` defense), case-insensitive hit, **cross-page hit** (the legacy bug — client filter only narrowed the already-returned page), regex-injection defense (`.`, `[is]` literal), combines with status + asker_role, **negative-leak** tenant scope, empty `q` skips filter |

All 34 tests PASS. **5 explicit cross-tenant leak guards** (`negative-leak` comments) lock in isolation on every new write/read path.

---

## Verbatim discipline gates

```
4 passed, 15 warnings in 3.26s         # Solva v1 byte-identical guard
voice_lint: clean across customer-copy surfaces.
34 passed, 15 warnings in 12.36s       # Q4Y bundle (this dispatch)
187 passed, 22 warnings in 524.32s (0:08:44)   # FULL BROAD SWEEP (22 files)
```

### Suite-size delta

Prior dispatch baseline (bug 27 / P4 / tooltip): **153 passing.**
This dispatch: **187 passing.**
Net new: **+34** (all Q4Y).

### Active bundle (22 files)
- test_solva_v1_unchanged
- test_admin_qa_hooks
- test_p0_c_oauth_session_ingestion
- test_p1_a_intel_to_pulse
- test_p1_b_cohort_approval_email
- test_phase_r1_cohort_foundation
- test_phase_p4_cohort_funnel (14/14)
- test_phase_p5_5_session_reauth
- test_phase_s_password_reset
- test_home_cleanup_phase_f5
- test_c1_a_first_login_password_set
- test_c1_b_contributor_link_codes
- test_phase_r2_welcome_email
- test_phase_p3_1_csrf
- test_phase_p5_6_csrf_cookie_domain
- test_bug27_email_reply_plumbing
- test_set_password_tooltip
- **test_q4y_p0_s1_sort_wiring** (NEW, 7 tests)
- **test_q4y_p0_c3_mark_answered** (NEW, 7 tests)
- **test_q4y_p1_c1_use_in_solva** (NEW, 6 tests)
- **test_q4y_p1_c2_use_in_chat** (NEW, 8 tests)
- **test_q4y_p1_f3_server_search** (NEW, 6 tests)

---

## No silent deviations

1. **Membership collection name** — initial test scaffolding used `db.context_memberships` (the name I'd inferred). Real codebase convention is `db.memberships` with `status: "active"` (cited from `core.py:258` `require_context_membership` + `routers/events.py:84`, `routers/admin_qa_hooks.py::admin_qa_seed_recent_doc`). Fixed in the Solva-v2 code AND all 3 test fixtures. **Surfacing this divergence here**: my first pass of solva_v2.py had `db.context_memberships` — corrected to `db.memberships` BEFORE any tests ran against the broken path. No prior dispatch shipped the wrong collection.

2. **Chat helper function name** — initial test imports used `_seed_from_context` from my own gap-table; the actual function is `_resolve_linked_context` (chat.py:309). Fixed across tests + my code comment in chat.py:181.

3. **No Q4Y spec doc** — already surfaced in the prior gap-analysis dispatch. This memo is also explicit about it.

4. **`_qa_seed` marker leakage** — I noticed during smoke-test that the harness's `_qa_seed: true` marker was leaking on the wire. Added `rec.pop("_qa_seed", None)` to `_strip()` so neither list endpoint nor the mark-answered round-trip exposes the test fixture marker to clients.

---

## Files touched (verbatim `git status --short`)

```
 M backend/routers/admin_qa_hooks.py
 M backend/routers/chat.py
 M backend/routers/questions.py
 M backend/routers/solva_v2.py
 M frontend/src/pages/Questions.jsx
?? backend/tests/test_q4y_p0_c3_mark_answered.py
?? backend/tests/test_q4y_p0_s1_sort_wiring.py
?? backend/tests/test_q4y_p1_c1_use_in_solva.py
?? backend/tests/test_q4y_p1_c2_use_in_chat.py
?? backend/tests/test_q4y_p1_f3_server_search.py
?? memory/sprints/q4y_combined_p0_p1.md
```

---

## Production env actions

**None.** No new env vars. No new collections needed (uses existing `cycle_questions` + `memberships` + `contexts`). The new `mark-answered` endpoint inherits the existing CSRF + auth middleware chain — no separate config.

---

## Harness — `POST /api/admin/qa/seed/question`

Super-admin gated (`_require_super_admin_with_mfa`). Body:

```json
{
  "text": "What is the runway under stress scenario B?",
  "asker_role": "board",            // optional, default "board"
  "status": "open",                  // optional, default "open"
  "context_id": "ctx-xyz",           // optional, falls back to admin's default_context_id
  "cycle_id": "",                    // optional
  "assignee_account_id": "acc-abc"   // optional, defaults to admin
}
```

Returns `{ok: true, question: {...row...}}`. Each call mints a fresh id. The `_qa_seed: true` marker is stored in Mongo for headless cleanup but stripped from all wire responses by `_strip()`.

Documented in `auth_testing.md` §17.

---

## Resume contract

Q4Y P0 + P1 closed clean. Pause for e1_tester re-verification before the next phase.

Remaining backlog:
- 🟡 P8 SendGrid Inbound Parse webhook — BLOCKED on you configuring the SendGrid console webhook URL
- 🟢 P5.18 OAuth migration — BLOCKED on Google GCP creds
- 🟢 Q4Y P2-F4 (assignee filter) — explicitly deferred this dispatch; resurface if you want it later
- 🔵 Future / backlog: digest cadence, why-not-shown diff, re-target badge, Postmark history scrub
