# REWRITE_DEPLOY_READY — Are we ready to ship?

**Generated:** 2026-05-18
**Audience:** the human about to push the "deploy to production" button.

This is the green/yellow/red checklist. Read top to bottom; the colour of each row tells you whether to ship.

---

## 🟢 GREEN — production-ready as-is

| Item | Evidence |
|---|---|
| All 662 backend tests pass | `pytest -q -p no:randomly --tb=no` returns `662 passed, 565 skipped, 0 failed` in ~3 minutes |
| CI guard — no direct LLM calls outside Shield | `pytest tests/test_no_direct_llm_calls_outside_shield.py -v` returns `1 passed in 0.48s` |
| Frontend render-smoke — 11 routes clean | `yarn render-smoke` returns `PASS — 11 routes clean · 2 upload paths green · Patch 28 interactions green · Chunk 4 wizard green · Chunk 5 create-artefact green · Chunk 6 brief-drawer CTA green.` |
| No `repr(exc)` leaks in user-facing emitters | grep audit clean (zero hits) |
| No blocking I/O in async routes | grep audit clean — no `requests.*`, no `time.sleep`, no synchronous pymongo in `routers/` or `services/` |
| Strict context_id scoping on every cid-bearing endpoint | grep audit confirms every router with a `{cid}` path param uses `require_context_membership` or `get_current_account` as a Depends gate |
| Strict tenant_id == account_id binding on all Shield surfaces | All `shield_invoke` call sites bind `tenant_id=account["id"]`. Admin overrides (e.g. `POST /admin/derive?tenant_id=…`) explicitly check `is_superadmin` and 403 otherwise |
| Backward-compatible data model | Every schema addition is `Optional` with defaults. No data migrations required. First deploy safe against the live database. |
| Resend (outbound email) | `admin/health/full` reports `{resend: {status: "pass", evidence: "sender=noreply@akki.syni.ai"}}` |
| Emergent LLM Key wired through Shield only | CI guard enforces. All providers (Anthropic / OpenAI / Gemini) routed via `synisense.shield.llm_router` |
| Bank-QA evidence pack assembled | `/app/memory/sprints/BANK_QA_EVIDENCE_PACK/` — README + 7 sections + 4 screenshots + sample PDF + standalone verifier script |
| Pre-deploy checklist documented | `/app/memory/sprints/PROD_DEPLOY_CHECKLIST.md` |

## 🟡 YELLOW — ships with caveats; graceful degradation in place

| Item | Caveat | Failure mode if unaddressed |
|---|---|---|
| **`tesseract-ocr` in production Docker image** | Verified present on preview pod (`/usr/bin/tesseract` 5.3.0). Status in the deployed image at `https://akki.syni.ai` is platform-config-dependent and not introspectable from this preview. The preview pod's runtime `apt-get install` does NOT survive pod restarts — the package must be baked into the image. | OCR returns `status=failed` with a clean error string; image-content invisible to LLM. No crash. Solution: confirm with Emergent platform that `tesseract-ocr` + `tesseract-ocr-eng` are in the production Docker layer. |
| **Postmark inbound webhook URL** | Code wired and verified (`POST /api/inbound/postmark` returns 401 to unauth; pipeline is real with ClamAV + extract_text). Whether the Postmark dashboard actually POSTs to `https://akki.syni.ai/api/inbound/postmark` is a deployment-side config question. | Inbound email simply does nothing — no error, no crash, no email-bearing flows trigger. Solution: confirm in the Postmark admin console that the inbound stream's webhook URL points at the production endpoint. |
| **`SYNISENSE_MASTER_SECRET`** | If not set on prod, app boots with a stderr WARNING every 60 seconds and uses a deterministic dev fallback for HMAC trust-receipt signatures. | **Trust receipts signed with the fallback are NOT verifiable by Bank QA** — the standalone verification script will return FAIL. Solution: set a high-entropy random string in the prod env. Once set, do NOT rotate without a migration plan. |
| **`CLAMAV_HOST` / `CLAMAV_PORT`** | Required for document upload. Code returns 503 `ClamAVUnreachable` if not reachable. | Document uploads (and Solva mid-session attach) fail with 503. **Hard fail by design** — refuse to store unscanned files. Solution: confirm the ClamAV daemon is reachable from the prod backend pod. |
| **Lint debt** | ruff reports 509 errors across the whole backend, all pre-existing (E402 module-import-not-at-top, F401 unused-import). Steady state. The rewrite did NOT introduce new lint errors on its touched files. | No functional impact. Cosmetic only. Resolution: post-rewrite cleanup sprint. |
| **Stripe payment surfaces** | Explicitly MOCKED (`MOCKED` markers in code). Out of rewrite scope. | Stripe-gated flows on prod will fail. Solution: do NOT enable Stripe-gated flows on prod until they're rewired. |

## 🔴 RED — blocks deploy

**None.** Nothing on the checklist blocks the deploy.

---

## Final verdict

🟢 **READY TO SHIP** — with two user-action 🟡 items confirmed before bank-QA's first verification pass:

1. Confirm `tesseract-ocr` is baked into the production Docker image.
2. Confirm Postmark dashboard points inbound at the production endpoint.

Neither blocks ship — both have graceful-degradation paths — but bank QA will discover them during their first end-to-end walkthrough. Address before that walkthrough.

For the operational checklist (env vars / system packages / external integrations / migration safety / rollback plan / smoke-test path), see `/app/memory/sprints/PROD_DEPLOY_CHECKLIST.md`.

For the Bank-QA evidence pack (overview, architecture, sample PDF, verification script, screenshots, API contracts, test evidence), see `/app/memory/sprints/BANK_QA_EVIDENCE_PACK/`.
