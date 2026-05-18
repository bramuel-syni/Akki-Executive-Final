# 07 — Test Evidence

**As of:** 2026-05-18
**Test suite size:** 662 passing · 0 failing · 565 skipped (pre-existing quarantines from Patch 8 / 19 — `requests.Session()` E2E tests awaiting httpx + ASGI rewrite).
**Time-to-run:** ~3 minutes.

## Breakdown by phase

| Phase | Topic | Tests added |
|------:|-------|------------:|
| Pre-rewrite baseline | — | 469 |
| A | Shield gateway + tenant-scoped routes | +48 |
| B | Migrate every direct LLM call to Shield | +11 |
| C | Chat protective layer + audit panel | +24 |
| D | Solva Phase D 5-layer pipeline + fix bundle v2 | +32 |
| E | Solva phases 2-4 + observability + PDF + fix bundle 1 | +45 |
| F | Engine real signals + seed handoff + Update goal + billing | +19 |
| F.1 | Three production gaps (P0 + P1 + P2) + cleanup | +14 |
| **Total** | — | **662** |

## CI guard — what enforces "no direct LLM calls outside Shield"

`tests/test_no_direct_llm_calls_outside_shield.py` walks every `.py` file under `/app/backend/` (skipping `__pycache__`, tests, and the Shield module itself) and grep-asserts the absence of:

* `import anthropic` / `from anthropic`
* `import openai` / `from openai`
* `import google.generativeai` / `from google.generativeai`
* `import emergentintegrations.chat` outside `synisense/shield/llm_router.py`

The test fails the build if any new code imports an LLM SDK outside Shield. **This is what makes the architectural invariant durable** — engineers cannot accidentally regress the gateway.

Run:
```bash
pytest tests/test_no_direct_llm_calls_outside_shield.py -v
```
Latest live run: **1 passed in 0.48s** (2026-05-18).

## Render-smoke — what's exercised on the frontend

`/app/frontend/scripts/render-smoke.js` boots a real Chromium headless instance, logs in via the test account, and visits every product route, capturing:
- Page load completion
- Absence of fatal console errors
- Absence of uncaught page errors
- Presence of expected `data-testid` markers

Routes covered (11 total):
1. `/app` — app shell
2. `/app/cycle` — Cycle Manager list
3. `/app/work-studio` — Work Studio
4. `/app/monitor` — Monitor
5. `/app/pulse` — Pulse
6. `/app/learn` — Learn
7. `/app/questions` — Questions
8. `/app/workspace` — Documents Journal
9. `/app/solva` — Solva landing
10. `/app/solva/phase-d/session/new?submodule=seek_clarity` — Phase D new session
11. `/app/admin/synisense-observability` — Synisense Observability admin

Latest live output: `PASS — 11 routes clean · 2 upload paths green · Patch 28 interactions green · Chunk 4 wizard green · Chunk 5 create-artefact green · Chunk 6 brief-drawer CTA green.`

## What is tested

* **Strict tenant_id scoping** — Shield surfaces all assert `tenant_id == current_account.id`; admin override paths explicitly check `is_superadmin`. Multiple per-surface tests (e.g. `test_billing_endpoint_requires_superadmin`, `test_p1_attach_rejects_cross_context_document`).
* **De-identification pipeline** — regex + spaCy NER + per-tenant Presidio recogniser. Tests cover PERSON, MONEY, ORG, EMAIL, DATE_ISO, PHONE, IBAN. Round-trip tests confirm re-identification restores original tokens.
* **Trust receipt HMAC chain** — signature is deterministic for a given (key, body) pair. Tests cover signature generation, verification, tampering detection.
* **Audit log shape** — every Shield invoke writes exactly one audit row + one receipt; format locked by test.
* **CI guard** — direct LLM imports caught and rejected.
* **Engine signal derivation** — six rules, each with a unit test asserting the `derivation_source` and the schema shape.
* **Solva Phase D 5-layer state machine** — entry → framing → layer_1 → layer_2 → layer_3 → layer_4 → completed (or refused at any point). Refusal trace tests for `far_insufficient_unresolved`, guardrail blocks, and macro-leak detection.
* **Mid-Solva-session document attach** — multipart upload AND existing-doc link, both produce anchors with real text excerpts.
* **OCR + spreadsheet extraction** — PNG (Tesseract), XLSX (openpyxl), CSV (csv.reader), corrupt image graceful failure.
* **Monitor "Update goal" mechanic** — engine-signal-cited rationale + audit_id, non-overridable status.
* **Privacy-report PDF** — full HMAC signature rendered, narrative prose composed via the shared composer (DRY with the UI audit panel), verification recipe footer.
* **Render-smoke** — 11 routes boot clean.

## What is NOT tested (honest disclosure)

* **Live OCR accuracy** on real-world scans (regulator letters, board minutes printouts). The tests use a generated PNG with rendered text; production OCR quality depends on input scan resolution.
* **Tesseract presence in the production Docker image.** Verified on preview pod; status on `https://akki.syni.ai` is platform-dependent.
* **Postmark inbound webhook URL configuration.** The route is wired and the auth gate is verified live. Whether Postmark's dashboard actually POSTs to it is a deployment-config question.
* **Real load / concurrency** — no load tests. Endpoints are async, no synchronous I/O in request handlers, but exact throughput numbers under production load are not measured.
* **Real partner-data ingestion** — Engine signals are derived from internal Mongo data only. Phase G+ scope.
* **Stripe payment flows** — explicitly stubbed (`MOCKED`) and out of rewrite scope.
* **Real malware payloads** in ClamAV. Tests use the EICAR test string. Real-world AV efficacy depends on ClamAV signature freshness on the deployed pod.
* **Token-accurate billing.** The audit log does not record token counts today; billing surface uses a flat-per-call estimate from a code-controlled table.
* **Multi-tenant scale stress** — every test uses small fixtures. Tenant-isolation contracts are verified per-call but not under thousands of concurrent tenants.

## How to run the suite locally

```bash
cd /app/backend
SYNISENSE_LLM_MODE=mock pytest -q -p no:randomly --tb=line
```

`SYNISENSE_LLM_MODE=mock` swaps real LLM provider calls for canned responses so the suite doesn't burn `EMERGENT_LLM_KEY` credits. The mock fully exercises the de-identification, audit, and trust-receipt pipelines.

## How to add a new LLM consumer (the contract)

Any new code that needs to invoke an LLM MUST:
1. Import the Shield client only: `from services.synisense.shield.client import invoke as shield_invoke`.
2. Pick a `purpose` from `ALLOWED_PURPOSES` (or add a new one + cover with a test).
3. Pass `tenant_id=current_account["id"]`.
4. Handle the three outcomes: `success`, `governance_refused`, `service_unavailable`.

The CI guard will fail the build if step 1 is violated.
