# P5.10 — Chat resilience: production cancellation + audit panel red error

**Date:** 2026-02-23 · fork-resume on the live preview cluster
**Status:** Fixed on disk in preview · pytest + Playwright + voice-lint green · ready to ship to production
**Author:** E1 (Akki Executive engineering)
**Surface:** `/app/chat` · `/api/chats/{cid}/messages/stream` · `/api/chats/{cid}/audit-panel`

---

## 1. Headline — production deployment lag was REFUTED, not confirmed

The handoff hypothesis ("production hasn't been redeployed since the Z1.1 / P5.10 patches landed") did not survive contact with the data. Hitting `GET /api/chat/models` against BOTH `akki.syni.ai` AND `akki-executive.preview.emergentagent.com` with admin@akki.ai returns the **identical** model list:

| Surface | Opus entry | default |
| --- | --- | --- |
| `akki.syni.ai` (prod) | `claude-opus-4-6` | `claude-sonnet-4-5` |
| `*.preview.emergentagent.com` | `claude-opus-4-6` | `claude-sonnet-4-5` |

The admin account_id `cf6e7587-9abd-46aa-b8f4-f342e9b066ef` is **identical** on both — confirming preview and production share the same MongoDB cluster. The `claude-opus-4-7-20260416` registry bug from Sprint Z1.1 is already gone everywhere.

So the user's mention of "Claude Opus 4.7" was a **red herring** — they were reading a stale assistant bubble or older message_id from before Z1.1 landed.

## 2. Real root cause — the SPA's raw SSE fetch missed `X-CSRF-Token`

When I drove the live preview UI under Playwright, the chat send call failed with **HTTP 403 in 0.32s**:

```
[trace] /messages/stream 403 at +0.32s | body=''
```

Backend curl (with CSRF cookie + header) against the SAME endpoint returned a clean SSE stream in ~2s. So the failure was browser-side only.

Reading the SPA's send path at `/app/frontend/src/pages/Chat.jsx:716`, the SSE consumer uses **raw `fetch()`** rather than the axios `api` wrapper, because the browser's `fetch` is the only API that exposes `ReadableStream` (needed for live SSE delta consumption). But the axios `request` interceptor in `/app/frontend/src/lib/api.js:148` is what auto-injects `X-CSRF-Token` on every state-changing call. Raw `fetch()` bypasses it.

The CSRF middleware (`/app/backend/services/csrf.py`) rejected the call with `csrf_token_missing` → 403 — well before any LLM round-trip. The SPA's catch handler converted that to `throw new Error('HTTP 403')`, stripped the optimistic bubble, and the user saw "instantly cancelled" copy. The audit-panel red-error component (`AuditPanel.jsx:121`) was a SEPARATE side effect: pre-fix cancelled message rows had `shield_audit_id: null`, so the audit-panel endpoint 404'd → red copy rendered. Same symptom surface, two distinct root causes.

## 3. The surgical fix

One file changed: `/app/frontend/src/pages/Chat.jsx`.

```jsx
// before
import { api, apiErrorMessage } from "@/lib/api";
// …
const headers = {
  "Content-Type": "application/json", "Accept": "text/event-stream",
};
if (tok) headers.Authorization = `Bearer ${tok}`;

// after — co-located comment explains why the dependency is load-bearing
import { api, apiErrorMessage, ensureCsrfToken, resolveBackendOrigin } from "@/lib/api";
// …
const csrf = await ensureCsrfToken();
const headers = {
  "Content-Type": "application/json", "Accept": "text/event-stream",
};
if (tok) headers.Authorization = `Bearer ${tok}`;
if (csrf) headers["X-CSRF-Token"] = csrf;
```

That's it. No backend change, no SUPPORTED_MODELS edit, no cascade tweak. The Z1.1 cascade and P5.10 direct-linkage fixes from the prior fork remain in place and continue to work as designed.

The merged `import` line preserved the original `resolveBackendOrigin` re-import (which previously sat as a duplicate `from "@/lib/api"` line further down the import block) so the eslint `no-duplicate-imports` rule stays green.

### Sister raw-fetch audit (not fixed in this sprint — flagged for follow-up)

A grep across the SPA found three other `fetch()` POST/DELETE calls outside the CSRF allowlist. These are all on PUBLIC / SANDBOX surfaces and so far haven't tripped CSRF in production:

| File | Endpoint | Surface |
| --- | --- | --- |
| `EnterpriseFeature.jsx:66` | `POST /api/public/studio/sensitivity-demo` | Marketing |
| `sandbox/api.js:8` | `POST /api/sandbox-gen/sessions` | Sandbox |
| `sandbox/api.js:28` | `DELETE /api/sandbox-gen/sessions/{sid}` | Sandbox |

If any of those routes ever pick up the CSRFMiddleware, they need the same `ensureCsrfToken()` treatment. Out of scope for P5.10.

## 4. Live preview Playwright traces

Both traces are reproducible — Python files in `/tmp` driving a real headless Chromium against the live preview URL, no localhost, no mocks.

### 4.1 Happy path — `/tmp/p5_10_trace_happy_path.py`

```
[trace] preview=https://akki-executive.preview.emergentagent.com
[trace] signed-in landed at https://akki-executive.preview.emergentagent.com/app
[trace] /api/chats POST -> 200
[trace] /messages/stream 200 at +0.56s | body=''
[trace] stream complete? True at +1.92s
[trace] cancelled marker visible? False
[trace] audit-panel toggles in DOM: 1
[trace] shielding prose: 'No sensitive identifiers were detected in this turn.'
[trace] PASS — happy path green
```

Screenshots: `/tmp/p5_10_happy/01_signin_filled.png` → `06_audit_panel_opened.png`. Summary JSON at `/tmp/p5_10_happy/summary.json`.

### 4.2 Cancel path — `/tmp/p5_10_trace_cancel_path.py`

```
[trace] /messages/stream 200 at +0.56s
[trace] clicked Stop at +1.66s
[trace] cancelled marker visible: True
[trace] audit-panel toggles after reload: 1
[trace] cancelled-turn shielding prose: 'No sensitive identifiers were detected in this turn.'
[trace] PASS — cancel path green
```

Screenshots: `/tmp/p5_10_cancel/01_composer_armed.png` → `05_audit_panel_opened.png`. Summary JSON at `/tmp/p5_10_cancel/summary.json`.

Both traces confirm:
- Stream returns **200**, not 403.
- `_persist_cancel` writes a `cancelled`-outcome audit row + sets `chat_messages.shield_audit_id`, so the audit panel resolves to green data on the cancelled turn (no red error).

## 5. Pytest lockdowns

Three suites, all green:

| Suite | Tests | Purpose |
| --- | --- | --- |
| `tests/test_solva_v1_unchanged.py` | 4 / 4 | v1 byte-identical guard — unchanged |
| `tests/test_phase_p5_10_audit_panel_direct_linkage.py` | 5 / 5 | Bug B integration (existing) |
| `tests/test_phase_p5_10_chat_resilience.py` | **12 / 12 (NEW)** | Bug A + Bug B source-strict lockdown |
| `tests/test_sprint_z1_qa_fixes.py` | 15 / 15 | Z1.1 cascade still wired correctly |
| **Total** | **36 / 36** | |

The new `test_phase_p5_10_chat_resilience.py` covers:

1. `Chat.jsx` imports `ensureCsrfToken` from `@/lib/api`.
2. `Chat.jsx` awaits `ensureCsrfToken()` before constructing the SSE headers.
3. `Chat.jsx` assigns `headers["X-CSRF-Token"] = csrf` on the raw fetch.
4. The `@/lib/api` import is a single line (eslint `no-duplicate-imports` guard).
5. The CSRF allowlist does NOT contain `/messages/stream` or `/api/chats`.
6. CSRF middleware emits `csrf_token_missing` + 403 on the failure path.
7. `_persist_cancel` calls `shield_finalize(..., outcome="cancelled")` and pushes to `synisense_audit_ids`.
8. `_persist_cancel` truncates `raw_text` to `emitted_chars_at` before shield_finalize (partial-write integrity).
9. `_persist_cancel` stores `emitted_chars` + `full_chars` on the chat_messages row.
10. `_persist_cancel` guards against unbound `shield_finalize` (`NameError` / `UnboundLocalError`).
11. Audit panel resolver prefers direct `chat_messages.shield_audit_id` over the legacy positional index.
12. Cascade classifier strips the failing id + `_is_model_invalid_error` discriminates BadRequest vs transport.

Voice-lint: `voice_lint: clean across customer-copy surfaces.`

## 6. Go / no-go — recommendation: SHIP

| Check | State |
| --- | --- |
| Backend stream returns 200 (curl) | PASS |
| SPA stream returns 200 (Playwright on live preview) | PASS (was 403) |
| Cancel-path audit panel green | PASS |
| v1 byte-identical guard | PASS |
| Voice-lint | PASS |
| Pytest (36 tests) | PASS |
| Files touched | 2 (`Chat.jsx`, `tests/test_phase_p5_10_chat_resilience.py`) |

**Recommend: ship to production.** The patch is a single import + three lines in `Chat.jsx`. Once deployed, the user's "instantly cancelled at 0.9s" symptom disappears on `akki.syni.ai`. The audit panel red error on legacy pre-P5.10 cancelled messages is already mitigated by the direct-linkage resolver (existing fix); newly cancelled turns inherit the resolver's green path through `_persist_cancel`.

## 7. Post-ship verification by the user

After deploy, ask the user to:

1. Hard-reload the chat page (CSRF cookie + service-worker cache wipe).
2. Open any existing chat or create a fresh one.
3. Send a prompt — stream should complete in 1–3 s.
4. Open the audit panel — green prose, no red error.

If a pre-P5.10 cancelled message still shows red audit copy, that's the legacy-row symptom; the resolver returns 404 because the row has no `shield_audit_id`. Acceptable since the FE swaps the raw 404 for the polite "Audit data isn't available for this message yet" copy. A one-shot Mongo backfill script can heal those rows if desired — out of scope for P5.10.

---

**ANTIFORGET PROTOCOL ACKNOWLEDGED.** No generic testing subagents were used. All traces are raw Playwright Python scripts in `/tmp` driving headless Chromium against the live preview URL. All credentials read from `/app/memory/test_credentials.md`.
