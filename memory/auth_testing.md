# Auth Testing — Notes for e1_tester + human QA

This file is the single canonical reference for testers who need to
exercise auth-gated flows in the **preview environment**. It pairs
with `/app/memory/test_credentials.md` (raw credentials + context_id
table) — read both.

Last updated: 2026-02 — Phase P0-B / P0-C / Test-harness hooks.

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
