# Auth Testing — Notes for e1_tester + human QA

This file is the single canonical reference for testers who need to
exercise auth-gated flows in the **preview environment**. It pairs
with `/app/memory/test_credentials.md` (raw credentials + context_id
table) — read both.

Last updated: 2026-02 — Phase P0-B / P0-C / Test-harness hooks /
C1-revised Phase A (First-login password set) + Phase B
(Contribution magic-link error codes) / Bug 27 (Email Reply mode
plumbing) + tooltip on /auth/set-password / Q4Y P0+P1 (sort,
mark-answered, Use in Solva, Use in Chat, server-side q search).

---

## 1. Canonical credentials

| Account         | Email             | Password         | Notes                              |
|-----------------|-------------------|------------------|------------------------------------|
| Superadmin      | admin@akki.ai     | `AkkiAdmin2026!` | MFA grace via `MFA_ADMIN_GRACE_EMAILS` |
| Viewer (member) | viewer@akki.ai    | `Viewer2026!`    | Single membership on `Syni.ai HQ` |

Both `email` and `email_lc` are indexed; the login handler accepts
either case.

---

## 2. CSRF + session contract (live wire)

`/api/auth/login` requires a `X-CSRF-Token` header. Mint it via
`GET /api/csrf` first. Subsequent state-changing requests also need
the header.

`SessionTimeoutMiddleware` enforces a **30-minute idle window**
against `accounts.last_activity_at`. As of P0-C (2026-02), both
password-login AND OAuth callbacks refresh that field on success —
prior to this, the first authenticated API call after OAuth would
401 with `session_idle_timeout` if the account's prior
`last_activity_at` was stale.

---

## 3. SPA workspace-picker bootstrap

Many SPA surfaces (Cycle, Pulse, Task Manager, Solva, Work Studio)
render an empty workspace-picker state when
`sessionStorage["akki_active_context_id"]` is unset. After login,
inject the test context_id from the table in `test_credentials.md`:

```python
# Playwright async API — verbatim.
await page.wait_for_timeout(3000)  # let AuthProvider bootstrap settle
await page.evaluate(
    "() => sessionStorage.setItem('akki_active_context_id', '<CTX_ID>')"
)
await page.reload(wait_until="domcontentloaded")
```

Common pitfalls (P5.20.1 / P0-B re-confirmed):
1. Key is `akki_active_context_id` (underscores, lowercase).
2. `sessionStorage` is per-tab — re-inject after each new browser
   context.
3. The post-login settle wait is mandatory; without it AuthProvider's
   bootstrap races your `setItem` and clobbers the value.
4. Reload (or any full-mount nav) is required after `set()` —
   AuthProvider only reads sessionStorage on initial mount.

---

## 4. Test-harness hooks (admin-gated, preview-safe)

Two POST endpoints under `/api/admin/qa` give e1_tester
deterministic state for the onboarding and Continue-card flows.
Discoverable in `/api/openapi.json` under tag `admin-qa`.

### 4.1 Reset first-session state

`POST /api/admin/qa/first-session/reset`

Body (optional): `{ "account_email": "viewer@akki.ai" }`. Defaults to
the calling admin.

Effect:
```
accounts.first_session = {
  status: "in_progress",
  current_step: "door",
  door_taken: null,
  intake: <prior intake preserved>,
}
```

Why this exists: each onboarding door click advances the user past
the door step, so traversing all 4 doors with one admin requires
resetting between clicks. The reset is idempotent (running it twice
produces the same state).

### 4.2 Seed a Home-Continue-eligible doc

`POST /api/admin/qa/seed/recent-doc`

Body (both optional):
- `account_email` — defaults to caller.
- `context_name` — defaults to `"QA Continue-Card Context"`.

Effect: idempotently provisions a context + a document + a
`user_recent_views` row scoped to the target account. After this,
the Home / Portfolio "Continue" card renders a row with the
deep_link `/app/work-studio?doc_id=<doc>&context_id=<ctx>`.

Response shape includes `created_context` / `created_document`
booleans — second call returns the same ids with both flags `false`.

### Live-wire curl recipe (verbatim, both endpoints)

```bash
URL="https://akki-executive.preview.emergentagent.com"

# 1. Mint CSRF + login (admin).
curl -s -c /tmp/jar "$URL/api/csrf" > /tmp/csrf.json
CSRF=$(python3 -c "import json; print(json.load(open('/tmp/csrf.json'))['csrf_token'])")
LOGIN=$(curl -s -c /tmp/jar -b /tmp/jar -X POST "$URL/api/auth/login" \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $CSRF" \
  -d '{"email":"admin@akki.ai","password":"AkkiAdmin2026!"}')
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token') or d.get('token') or '')")

# Mint a fresh CSRF (the auth cookie just changed).
curl -s -c /tmp/jar -b /tmp/jar "$URL/api/csrf" > /tmp/csrf2.json
CSRF2=$(python3 -c "import json; print(json.load(open('/tmp/csrf2.json'))['csrf_token'])")

# 2. Reset first-session for self (or pass {"account_email": "..."}).
curl -s -b /tmp/jar -X POST "$URL/api/admin/qa/first-session/reset" \
  -H "Authorization: Bearer $TOKEN" -H "X-CSRF-Token: $CSRF2" \
  -H "Content-Type: application/json" -d '{}'

# 3. Seed a recent doc for the Continue card.
curl -s -b /tmp/jar -X POST "$URL/api/admin/qa/seed/recent-doc" \
  -H "Authorization: Bearer $TOKEN" -H "X-CSRF-Token: $CSRF2" \
  -H "Content-Type: application/json" -d '{}'
```

Live verification at hook-rollout time (2026-02-06, this dispatch):

```
=== Block 1: reset admin first-session ===
{
  "ok": true,
  "account_id": "cf6e7587-9abd-46aa-b8f4-f342e9b066ef",
  "email": "admin@akki.ai",
  "first_session": {"status":"in_progress","current_step":"door","door_taken":null,"intake":{...}}
}
=== Block 2: seed recent doc ===
{
  "ok": true,
  "account_id": "cf6e7587-9abd-46aa-b8f4-f342e9b066ef",
  "context_id": "ctx-qa-recent-851931d984",
  "doc_id":     "doc-qa-recent-8d9969869a",
  "deep_link":  "/app/work-studio?doc_id=doc-qa-recent-8d9969869a&context_id=ctx-qa-recent-851931d984",
  "created_context":  true,
  "created_document": true
}
```

Locked by `backend/tests/test_admin_qa_hooks.py` — 6 tests:
- Non-admin → 403.
- Self-reset lands on `current_step="door"` and preserves `intake`.
- Reset another account via `account_email`.
- Seed creates context+doc+view, idempotent on second call.
- Seed non-admin → 403.
- Both endpoints visible in `/api/openapi.json` tag `admin-qa`.

---

## 5. OAuth deterministic test (no browser, no Google creds)

`backend/tests/test_p0_c_oauth_session_ingestion.py` — 5 tests:

1. `test_oauth_finish_refreshes_last_activity_at` — direct DB
   assertion of the post-fix shape.
2. `test_authenticated_api_call_post_oauth_does_not_idle_401` — drives
   `/api/auth/me` against a stale-seeded account after applying the
   post-fix `last_activity_at` write, asserts NOT
   `session_idle_timeout`.
3. `test_regression_without_fix_would_have_failed` — **reverse-canary**.
   Pre-fix state (stale `last_activity_at`, no refresh) MUST 401 with
   `session_idle_timeout`. If this canary stops firing, the positive
   tests above aren't exercising the real bug — the suite raises
   immediately.
4. `test_oauth_route_files_carry_the_fix_marker` — source-strict guard
   on `routers/auth_oauth.py`.
5. `test_oauth_google_finish_route_with_stubbed_session_then_me_returns_200` —
   the dispatch-required route-level test. Monkey-patches the single
   external dependency (`_fetch_emergent_session_data`) with a stub
   identity, POSTs `/api/auth/oauth/google/finish`, asserts the
   cookie carries to a follow-up `/api/auth/me` that returns 200
   (NOT 401).

Run verbatim:

```bash
cd /app/backend
python3 -m pytest tests/test_p0_c_oauth_session_ingestion.py -v
```

Expected: `5 passed`. No browser, no GCP creds, no mocks of the JWT
mint or middleware.

---

## 6. P0-B Card 4 cross-context propagation (live Playwright)

`/tmp/p0_b_routing/p0_b_routing_trace.py` — verifies all 4 onboarding
doors AND the Home Continue deep-link contract. Card 4 specifically
asserts:
- sessionStorage `akki_active_context_id` flips to the URL-target
  context (NOT just the user's default).
- The URL retains `?doc_id=<doc>` through the context switch.
- The page's breadcrumb text contains the target context's name.

Run verbatim:

```bash
PLAYWRIGHT_BROWSERS_PATH=/pw-browsers \
  python3 /tmp/p0_b_routing/p0_b_routing_trace.py
```

Expected final line: `✅ All 4 cards PASS`.

---

## 7. P1-A — Intelligence → Pulse Signals fan-out (no extra harness needed)

`document_intelligence.key_signals` now eagerly promotes into
`db.signals` at extraction time so the Pulse Signals feed surfaces
them without requiring a Brief click. Same store, same shape, same
stable id `sig:from_intel:{doc_id}:{idx}` — re-extraction refreshes
in place, no duplicates. Code lives in
`backend/services/documents/intelligence_service.py::promote_intelligence_signals_to_pulse`.

Two call sites use the helper:
- Eager: `regenerate_document_intelligence` `_run()` background task.
- Lazy: `generate_briefing_from_document` fallthrough (the original
  P0-A path — now a no-op when eager promotion has already run).

Locked by `backend/tests/test_p1_a_intel_to_pulse.py` (6 tests):
1. Helper writes Pulse-compatible rows with all serializer fields.
2. End-to-end via `GET /api/contexts/{cid}/pulse/feed` — promoted
   signals surface with matching headlines + doc references.
3. Idempotency — eager + lazy callers never duplicate rows.
4. `created_at` preserved across re-runs (Pulse recency sort
   invariant).
5. Tenant scoping — context A's signals never leak into context B's
   feed (asserted via two separate authenticated sessions hitting
   their own contexts' feeds).
6. Empty input → no-op.

Run: `pytest backend/tests/test_p1_a_intel_to_pulse.py -v`.

---

## 8. P1-B — Cohort approval magic-link email dispatch

`services/cohort_email.py::send_approval` is gated on the env var
`COHORT_EMAILS_ENABLED`. Pre-fix the var was unset → every approve
short-circuited with `{"status":"flag_off"}` and the magic link was
minted but the email never went out.

**Preview env was updated this dispatch:**
```
COHORT_EMAILS_ENABLED=true   ← appended to /app/backend/.env
```

**Production env still needs the same setting.** The user must add
`COHORT_EMAILS_ENABLED=true` to the production env vars before the
prod cohort approval emails start firing. There is NOTHING in the
code repo that fixes prod — this is environment configuration only.

(Honesty Protocol: I did NOT modify `prod/.env`. I cannot. The
preview env is mine; prod is the user's. Same gate, same fix, two
environments.)

Locked by `backend/tests/test_p1_b_cohort_approval_email.py` (4 tests):
1. Kill-switch negative — `COHORT_EMAILS_ENABLED=false` ⇒ SendGrid
   invoker NEVER called, response carries `flag_off`. Guards against
   future drift in the other direction.
2. Positive case — `COHORT_EMAILS_ENABLED=true` ⇒ `_send_via_sendgrid`
   is called exactly once with correct recipient, subject, magic URL
   in BOTH plain and HTML bodies, freshly-minted token surfaces.
3. Unit-level helper — `cohort_email.send_approval` direct call wires
   to the SendGrid invoker.
4. Source-strict — `cohort_email.py` carries the documented gate +
   `send_approval` entry point.

Run: `pytest backend/tests/test_p1_b_cohort_approval_email.py -v`.

### Verifying the live wire end-to-end

The test only proves the WIRE — that `send_approval` calls
`_send_via_sendgrid` with the right args. To verify the SendGrid HTTP
request actually goes out in preview, an admin can:

```bash
# 1. Seed a fresh application via the public apply endpoint.
URL="https://akki-executive.preview.emergentagent.com"
curl -s -X POST "$URL/api/cohort/apply" \
  -H "Content-Type: application/json" \
  -d '{"email":"YOUR_REAL_INBOX@example.com","name":"P1B verify",
       "organization":"Test","role":"founder"}'
# 2. Look up the application_id in db.cohort_applications.
# 3. Log in as admin@akki.ai + POST /admin/cohort/applications/<id>/approve.
# 4. Check the inbox at YOUR_REAL_INBOX@example.com — magic-link
#    email should arrive within seconds (or check SendGrid Activity
#    feed under the SENDGRID_FROM_EMAIL identity).
```



---

## 12. C1-revised Phase A — First-login password-set gate (2026-02)

**Spec:** Block any account marked `has_set_password === false`
(strict bool) from state-changing API calls until they set a
password. Legacy rows where the field is missing, null, or true
must bypass — only the strict-bool false triggers the gate.

### Field semantics
| Entry path                                   | `has_set_password` written |
|----------------------------------------------|----------------------------|
| `POST /api/auth/register` (form signup)      | **True**                   |
| `POST /api/auth/magic-link/consume` mode=password | **True**             |
| `POST /api/auth/magic-link/consume` mode=oauth (TBD) | False             |
| `GET  /api/auth/magic/{token}` (direct)      | **False**                  |
| `GET  /api/auth/oauth/google/finish`  (new acct) | **False**              |
| `GET  /api/auth/oauth/microsoft/finish` (new acct) | **False**            |
| Legacy rows pre-2026-02                       | **missing** → bypass       |

### Endpoint contract
* `POST /api/auth/set-password` — body `{password: str}`. Idempotent.
  Sets `password_hash` + flips `has_set_password=True` + refreshes
  `last_activity_at`. Returns `{ok: true, account: sanitize(...)}`.
* Sanitize_account surfaces the field ONLY for strict True/False;
  legacy missing stays lean (no field on the wire).

### Middleware shape
`services/first_login_password_set.py` — wraps
POST/PUT/PATCH/DELETE only. Allowlists auth-entry/exit + the new
endpoint (`/api/auth/set-password`, `/api/auth/magic*`,
`/api/auth/oauth/*`, `/api/csrf`, etc.). 428
`{detail: {code: "password_set_required", message, set_password_url}}`
on hit. Escape hatch: `FIRST_LOGIN_PASSWORD_GATE_DISABLED=1`.

### SPA shape
* `/auth/set-password` page (`pages/SetPasswordRequired.jsx`) —
  authenticated. Self-bounces to `/app/` if
  `account.has_set_password !== false`.
* `SetPasswordGuard` in `App.js` wraps inside `<Gated>` BEFORE
  `FirstSessionGuard`. Redirects `/app/*` → `/auth/set-password`
  when strict-bool false.

### Seeding a gated test account
```python
import bcrypt, uuid
from datetime import datetime, timezone
await db.accounts.insert_one({
    "id":            uuid.uuid4().hex,
    "email":         "c1a-gated@example.com",
    "email_lc":      "c1a-gated@example.com",
    "password_hash": bcrypt.hashpw(b"TempPass2026!", bcrypt.gensalt()).decode(),
    "has_set_password": False,
    "name":          "C1A Gated",
    "first_name":    "C1A",
    "declared_role": "executive",
    "mfa_enabled":   False,
    "first_session": {"status": "skipped"},  # skip first-session, gate at password
    "created_at":    datetime.now(timezone.utc).isoformat(),
})
```
Login → SPA bounces to `/auth/set-password`. Submit a 10+ char
password → land on `/app/`. Subsequent `/auth/set-password` visits
self-bounce.

### Lockdown tests
`backend/tests/test_c1_a_first_login_password_set.py` (16 tests):
1. Source-strict (file exists, middleware wired, endpoint exists, sanitize_account surfaces field, 5 entry-paths write the field).
2. Middleware blocks POST when strict-bool false (428).
3. Middleware allows POST when null / true / missing (legacy bypass).
4. Middleware allows GET regardless.
5. `/api/auth/set-password` is allowlisted and flips the flag + drops the gate on the next request.
6. Idempotent re-set rotates the password without error.
7. `/api/auth/register` always writes True.
8. Legacy missing → field NOT on wire (sanitize lean response).

### Raw Playwright trace
`/tmp/c1a_set_password_trace.py` — drives signin → bounce →
mismatch error → length error → success → self-bounce. 4 viewports
(1280 / 1024 / 820 / 414). 24/24 step assertions PASS.

---

## 13. C1-revised Phase B — Contribution magic link codes (2026-02)

**Spec:** Distinguish task-contribution magic-link failure modes so
the contributor portal renders a precise narrative per case instead
of the catch-all "Link not valid".

### Error code map (verifier `GET /api/tasks/contribute/{token}`)
| Status | Code           | Trigger                                                |
|--------|----------------|--------------------------------------------------------|
| 404    | `link_invalid` | Token never existed in `task_contributor_tokens`       |
| 410    | `link_revoked` | Token has `used=True` + `revoked_reason` (rotated)     |
| 410    | `link_used`    | Token has `used=True` with no `revoked_reason`         |
| 410    | `link_expired` | Token past `expires_at`                                |
| 410    | `task_gone`    | Token valid but referenced `tasks` row missing         |
| 410    | `not_on_team`  | Token valid + task exists but contributor not on team  |
| 200    | —              | Happy path (regression guard)                          |

Response shape: `{detail: {code: "<code>", message: "<narrative>"}}`.

### SPA shape
`ContributorPortal.jsx` reads `r.json().detail.code` and renders
one of seven narratives. The error surface carries
`data-error-code="<code>"` so Playwright + e1_tester can assert
the active narrative deterministically.

### Lockdown tests
`backend/tests/test_c1_b_contributor_link_codes.py` (10 tests):
1. Source-strict (backend codes + frontend narratives present).
2. Each of the 6 failure modes returns the precise code + status.
3. Happy path STILL returns 200 with full contribution payload.
4. Cross-tenant leak guard — a token-row's contributor_email
   mismatching the team membership returns `not_on_team` and the
   other contributor's data does NOT leak in the response body.

### Raw Playwright trace
`/tmp/c1b_contribution_trace.py` — seeds 7 (task, token) pairs per
viewport, visits each `/contribute/<token>` URL, asserts
`data-error-code` + narrative title. 4 viewports. 28/28 scenarios
PASS.

### Honesty note — what was NOT broken
The happy path verifier ALREADY worked end-to-end pre-Phase B
(verified via fresh task creation + token mint + GET
`/api/tasks/contribute/{token}` returning 200). The
user-perceived "magic link invalid" symptom mapped to three
indistinguishable 404 paths (revoked token / task deleted /
contributor removed). Phase B disambiguates the codes; the issuance
+ happy-path verifier code paths are unchanged.


---

## 14. Bug 27 / Fig 42 — Email Reply mode plumbing (2026-02 fork-resume)

**Symptom:** Email replies from contributors land in MongoDB
(`tasks.contributor_comments[]`) but were invisible to the task
owner because `_sanitize_task` stripped the field on the wire.
The right-rail audit feed showed the verb
(`submitted_via_email`) but no body content.

**Root cause:** Read-side adapter miss (option (c) in our defect
taxonomy). Write paths were fine; sender auth + audit + status
flip + confirmation reply all worked. Only the GET-task wire was
broken.

**Fix:**
- `routers/tasks.py::_sanitize_task` now includes
  `contributor_comments` (sanitized + most-recent-first).
- `_sanitize_comments(rows)` helper normalises both write paths:
  | kind | source |
  |------|--------|
  | `email_body` | inbound webhook → `_handle_task_contributor_reply` |
  | `contributor` | portal `POST /tasks/contribute/<token>/comment` |
- `TaskDrawer.jsx::ContributionsTab` renders the comments inline
  under each contributor row.

### Seeding a task with an email-reply comment
```python
import asyncio, os, uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    admin = await db.accounts.find_one({"email": "admin@akki.ai"}, {"_id":0})
    tid = f"task-bug27-fe-{uuid.uuid4().hex[:10]}"
    contributor = "review@example.com"
    now = datetime.now(timezone.utc).isoformat()
    await db.tasks.insert_one({
        "id": tid, "account_id": admin["id"], "owner_id": admin["id"],
        "name": "Bug27 trace", "objective": "x", "success_criteria": "x",
        "team": [{"name":"Reviewer","email":contributor,"role":"Reviewer",
                  "contribution":"Review section 1","contribution_mode":"email_reply",
                  "status":"submitted"}],
        "state": "active", "created_at": now, "updated_at": now,
        "contributor_comments": [{
            "id": uuid.uuid4().hex, "kind": "email_body",
            "reviewer": contributor, "subject": "Re: review",
            "comment": "Body of the reply…", "doc_ids": ["doc-x"],
            "created_at": now,
        }],
    })
    print(tid)

asyncio.run(main())
```

Open `/app/task-manager?task_id=<tid>` as admin → Contributions
tab → the email-reply row renders with `data-comment-kind="email_body"`.

### Lockdown tests
`backend/tests/test_bug27_email_reply_plumbing.py` (7 tests):
1. Source-strict + write-path regression guard.
2. End-to-end ingestion + read round-trip.
3. Sanitize_task direct call surfaces shape + most-recent-first.
4. Sender-mismatch silently dropped.
5. Cross-tenant isolation via `task_account_id`.
6. Attached docs surface in `doc_ids[]` + `documents` row exists.

### Raw Playwright trace
`/tmp/bug27_fe_trace.py` — seeds a task with an email-reply,
admin opens Task Manager → drawer → Contributions tab, asserts
comment row mounted with `data-comment-kind="email_body"`,
body + subject + doc count visible. **4 viewports × 5 steps =
20/20 PASS.**

---

## 15. Tooltip on /auth/set-password heading (2026-02 fork-resume)

Heading-only enhancement. Verbatim copy: **"Akki uses your
password as a fallback if your Google or Microsoft account
becomes unreachable."**

A11y wire:
- Heading `id="set-password-heading-text"`.
- Trigger `aria-label`, `aria-describedby` → heading id.
- Content `role="tooltip"` + `data-testid="set-password-tooltip-content"`.
- Hover AND keyboard focus both open (Radix default).

### Lockdown tests
`backend/tests/test_set_password_tooltip.py` (5 tests) — source-
strict + form-unchanged guard.

### Raw Playwright a11y trace
`/tmp/item3_tooltip_trace.py` — gated user → /auth/set-password
→ trigger visible → a11y wiring → hover shows copy → keyboard
focus shows copy. **4 viewports × 5 steps = 20/20 PASS.**

---

## 16. P4 cohort funnel test rot fix (2026-02 fork-resume)

`backend/tests/conftest.py` now sets
`COHORT_EMAILS_ENABLED=false` for the test session. P1-B's own
tests use `monkeypatch.setenv` so they're unaffected; the 2 P4
tests now see the legacy `flag_off` shape again. **P4 file
14/14, was 12/14.** Production env unchanged.



---

## 17. Q4Y harness — `POST /api/admin/qa/seed/question` (2026-02 fork-resume)

Super-admin gated test endpoint that seeds a `cycle_questions`
row directly so headless flows can exercise the Questions surface
without going through Solva. Same gating + pattern as the existing
`/api/admin/qa/seed/recent-doc` hook.

### Request shape
```json
POST /api/admin/qa/seed/question
{
  "text": "What is the runway under stress scenario B?",
  "asker_role": "board",            // optional — "board" | "ceo" | "team", default "board"
  "status": "open",                  // optional — "open" | "pending" | "answered" | "resolved", default "open"
  "context_id": "ctx-xyz",           // optional — falls back to admin's `default_context_id`
  "cycle_id": "",                    // optional — empty string by default
  "assignee_account_id": "acc-abc"   // optional — defaults to admin caller
}
```

### Response shape
```json
{
  "ok": true,
  "question": {
    "id": "<hex>",
    "context_id": "...",
    "cycle_id": "",
    "assignee_account_id": "...",
    "asker_role": "board",
    "text": "What is the runway under stress scenario B?",
    "status": "open",
    "asked_at": "<iso>",
    "history": [{"ts": "...", "kind": "raised", "actor_id": "..."}]
  }
}
```

The `_qa_seed: true` marker is stored on the Mongo row for headless
cleanup but is stripped from ALL list-endpoint and mark-answered
responses (see `routers/questions.py::_strip`).

### Manual repro
```python
import asyncio, os, requests
from motor.motor_asyncio import AsyncIOMotorClient

# 1. Sign in as admin, capture token + CSRF.
# 2. POST the seed.
URL = "https://akki-executive.preview.emergentagent.com"
# (token + csrf flow from §6 above)
r = requests.post(
    f"{URL}/api/admin/qa/seed/question",
    headers={"Authorization": f"Bearer {TOKEN}", "X-CSRF-Token": CSRF},
    json={"text": "What is the runway under stress scenario B?",
          "asker_role": "board"},
)
print(r.status_code, r.json()["question"]["id"])
```

### Q4Y wire surfaces (cite these in any future bug repro)
- List endpoint: `GET /api/me/questions?status=…&sort=…&q=…&asker_role=…&page=…`
- Cycle-scoped list: `GET /api/contexts/{cid}/cycles/{cid}/questions?status=…&sort=…&asker_role=…`
- Mark-answered: `POST /api/contexts/{cid}/questions/{qid}/mark-answered` body `{note?: str}`
- Use in Solva seed: `GET /api/solva/v2/seed?kind=question&id={qid}` → `{seed_text, citation_label}`
- Use in Chat linked-context: pass `ctx_type=question&ctx_id={qid}` to any chat-create or `/api/chat/messages` POST

### Sort keys (P0-S1)
`recent` (default — `asked_at desc`) · `oldest` (`asked_at asc`) ·
`answered_at_desc` (`answered_at desc`). Unknown keys → 400.

### Q4Y lockdown tests
- `tests/test_q4y_p0_s1_sort_wiring.py` (7)
- `tests/test_q4y_p0_c3_mark_answered.py` (7)
- `tests/test_q4y_p1_c1_use_in_solva.py` (6)
- `tests/test_q4y_p1_c2_use_in_chat.py` (8)
- `tests/test_q4y_p1_f3_server_search.py` (6)

**Total: 34 tests, all PASS.**

