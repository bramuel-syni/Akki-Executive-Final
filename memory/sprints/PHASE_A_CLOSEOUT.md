# Phase A — Synisense Foundation — Close-out

## Status: COMPLETE
## Date: 2026-05-13 (UTC)

## File diff summary

### New files
- `backend/services/synisense/shield/__init__.py`
- `backend/services/synisense/shield/deidentifier.py`
- `backend/services/synisense/shield/reidentifier.py`
- `backend/services/synisense/shield/purpose_validator.py`
- `backend/services/synisense/shield/llm_router.py`
- `backend/services/synisense/shield/trust_receipt.py`
- `backend/services/synisense/shield/audit_log.py`
- `backend/services/synisense/shield/client.py`
- `backend/services/synisense/shield/tenant_entities.py`
- `backend/services/synisense/engine/__init__.py`
- `backend/services/synisense/engine/signal_types.py`
- `backend/services/synisense/engine/signal_seeder.py`
- `backend/services/synisense/engine/signal_query.py`
- `backend/services/synisense/engine/subscription.py`
- `backend/routers/synisense_shield.py`
- `backend/routers/synisense_engine.py`
- `backend/tests/test_synisense_shield.py`
- `backend/tests/test_synisense_engine.py`
- `backend/tests/test_synisense_e2e.py`
- `memory/REWRITE_SPRINT_STATE.md`
- `memory/sprints/PHASE_A_CLOSEOUT.md` (this file)

### Modified files
- `backend/services/synisense/config.py` — removed `synisense.shield.internal.ner` from `ALLOWED_PURPOSES` (NER is now local; the cloud-NER purpose was retired).
- `backend/server.py` — wired `synisense_shield` + `synisense_engine` routers under `/api/v1/`.
- `backend/.env` — added `SYNISENSE_MASTER_SECRET` (dev fixed value for cross-process receipt verification; replaced pre-Bank-QA per user direction).

### Environment side-effects
- Removed the broken `torch` package directory (`/root/.venv/lib/python3.11/site-packages/torch/`) — a previous partial install left `libtorch_global_deps.so` missing, which made `thinc.compat`'s opportunistic `import torch` raise `OSError` and broke spaCy loading in fresh Python processes. Removal returns thinc to its `ImportError` fallback path. spaCy now loads `en_core_web_sm` cleanly.
- Pip cache wiped (2GB recovered) to fit the workspace.

## Test results

### New test count
| File | Tests |
|---|---|
| `test_synisense_shield.py` | 28 |
| `test_synisense_engine.py` | 9 |
| `test_synisense_e2e.py` | 10 |
| **Total Phase A tests** | **47** |

(Phase A target was ≥25 — delivered 47.)

### Full suite result
```
517 passed, 565 skipped, 44 warnings in 138s
```
- **517 passed** (baseline was 469 — +48 new this phase; one Phase A test is counted by pytest as a sub-test of a parametrised case in the engine file, hence 47 file-count vs 48 pytest-count).
- **0 failures.**
- **565 skipped** — entirely the pre-existing quarantine set documented in §7 of SYSTEM_STATE.md; not introduced by Phase A.
- **No regressions** against the prior 469-passing baseline.

### render-smoke
N/A — Phase A is backend-only. No frontend surface touched.

## Curl evidence — John Smith / Apple / $50k e2e flow

### Request
```
POST /api/v1/shield/llm/invoke
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "purpose": "test.smoke",
  "content": "John Smith bought 500 shares of Apple Inc. for $50,000 on 2026-01-15. Contact: john.smith@example.com. Wire to IBAN GB29NWBK60161331926819 via +1-415-555-1234.",
  "model_preference": "balanced",
  "consumer_id": "curl",
  "tenant_id": "acc-phasea-curl-001",
  "user_id": "acc-phasea-curl-001"
}
```

### What the LLM actually saw (de-identified content)
```
[[ENT_PERSON_001]] bought 500 shares of [[ENT_ORG_001]] for [[ENT_MONEY_001]] on [[ENT_DATE_ISO_001]]. Contact: [[ENT_EMAIL_001]]. Wire to [[ENT_ORG_002]] [[ENT_IBAN_001]] via [[ENT_PHONE_E164_001]].
```

### Token map (held in memory for the request; never persisted)
```
[[ENT_PERSON_001]]      →  John Smith
[[ENT_ORG_001]]         →  Apple Inc.
[[ENT_MONEY_001]]       →  $50,000
[[ENT_DATE_ISO_001]]    →  2026-01-15
[[ENT_EMAIL_001]]       →  john.smith@example.com
[[ENT_ORG_002]]         →  IBAN          (spaCy tagged "IBAN" as ORG — harmless over-flag)
[[ENT_IBAN_001]]        →  GB29NWBK60161331926819
[[ENT_PHONE_E164_001]]  →  +1-415-555-1234
```

### Re-identified response (what the consumer got back)
```
John Smith purchased 500 shares of Apple Inc. for $50,000 on 2026-01-15. Contact john.smith@example.com. Funds should be wired to IBAN at GB29NWBK60161331926819 via +1-415-555-1234.
```
**`[[ENT_` token count in response: 0.** Re-identifier swapped every token back successfully even though Gemini paraphrased the content ("bought" → "purchased", added "Funds should be wired to").

### Scores
- `exposure_reduction_score`: **62.89** (> 50 threshold ✅)
- `dilution_score`: **40.0**

### Audit row (`db.synisense_audit_log`)
```json
{
  "audit_id": "aud-d00ad507cb1a40f2aa704f6b885ab948",
  "tenant_id": "acc-phasea-curl-001",
  "consumer_id": "curl",
  "user_id": "acc-phasea-curl-001",
  "purpose": "test.smoke",
  "timestamp": "2026-05-15T21:25:00.057679+00:00",
  "de_id_summary": {"PERSON": 1, "ORG": 2, "MONEY": 1, "DATE_ISO": 1,
                    "EMAIL": 1, "IBAN": 1, "PHONE_E164": 1},
  "dilution_score": 40.0,
  "exposure_reduction_score": 62.89,
  "llm_provider": "gemini",
  "llm_model": "gemini-2.5-flash",
  "request_hash": "sha256:6f51d81ac8c9381431664c642681d076678b0d42bf7f158c69e91d52506e5444",
  "response_hash": "sha256:02f1e6ce5c25a7585de6f45f83a7bfb9567216055e938ab79ebbe52ed72a4a6e",
  "outcome": "success",
  "latency_ms": 1842
}
```

## Sample Trust Receipt JSON (with verified signature)

```json
{
  "receipt_id": "rcp-f7103a71f0914c00a6d311904d7ff26e",
  "audit_id": "aud-bc2b6da6ab7a434e978a67f799e1901f",
  "version": "v1",
  "tenant_id": "acc-phasea-curl-001",
  "consumer_id": "curl",
  "purpose": "test.smoke",
  "timestamp": "2026-05-15T21:25:43.679605+00:00",
  "llm_provider": "gemini",
  "llm_model": "gemini-2.5-flash",
  "de_id_summary": {"PERSON": 1, "ORG": 1, "MONEY": 1},
  "dilution_score": 30.0,
  "exposure_reduction_score": 49.09,
  "request_hash": "sha256:06d856fcc6f7c7d66e815ad03565d921ec79c50c1c2c30d2c30c5f5754371776",
  "response_hash": "sha256:87faf1daa27e36b0e6b55f84699f4f1aa007fd0ab02a525790e83b2f093da419",
  "signature": "b5b87073ffca46776c6695023f9f14164dffcc000b249d27096d8bb82cdb96f9"
}
```

### Cross-process signature verification (with `SYNISENSE_MASTER_SECRET` set)
```
Signature (correct tenant):  True
Signature (wrong tenant):    False
Tamper detected:             True
```

The signature scheme works as designed. Without the env var, the dev-fallback ephemeral secret is process-local — receipts signed in process A do not verify in process B (this is the **STARTUP WARNING** behaviour and is intentional: forces production deployments to set the env var).

## Confirmation checklist

- ✅ **HKDF per-tenant key derivation** — `cryptography.hazmat.primitives.kdf.hkdf.HKDF(SHA-256, salt=b"synisense/v1", info=tenant_id, length=32)`. Cached per-tenant in process memory. `derive_tenant_key()` proven deterministic for same tenant + distinct for different tenants (tests `test_hkdf_per_tenant_keys_differ`, `test_hkdf_deterministic_for_same_tenant`).
- ✅ **Fail-closed on spaCy errors** — `_ensure_spacy()` returns `None` on load failure → caller raises `ServiceUnavailable`. Route surfaces 503. Test `test_fail_closed_on_spacy_failure` locks the behaviour by force-failing the loader.
- ✅ **Seeded signals carry `derivation_source`** — every row written by `signal_seeder.seed_for_tenant()` carries `derivation_source: "seeded_from_<collection>"`. The seeder explicitly preserves real-ingestion rows (`derivation_source: "real_ingestion"`). Locked by `test_seeder_writes_signals_with_derivation_source` and `test_seeder_keeps_real_ingestion_rows`.
- ✅ **openapi.json shows new endpoints** — verified via `curl /api/openapi.json | python3 -c "..."`:
  ```
  /api/v1/engine/admin/reseed       POST
  /api/v1/engine/signal_types       GET
  /api/v1/engine/signals/query      POST
  /api/v1/engine/subscriptions      POST
  /api/v1/shield/audit/{audit_id}   GET
  /api/v1/shield/llm/invoke         POST
  /api/v1/shield/receipt/{audit_id} GET
  ```
- ✅ **Local NER only** — no cloud-LLM-NER call path. `llm_router.py` is for the post-de-id outbound LLM call only. The `synisense.shield.internal.ner` purpose was removed from `ALLOWED_PURPOSES`.
- ✅ **`SYNISENSE_MASTER_SECRET` dev fallback** — STARTUP WARNING logged in caps when the env var is absent.
- ✅ **`tenant_id` = `account_id`** — route enforces `body.tenant_id == current["id"]` for non-`test.*` purposes; returns `AUTH_DENIED` (401) otherwise.

## Decisions made autonomously (logged for PO review)

1. **Fallback to `en_core_web_sm` is silent (warning only).** The brief explicitly permits this when trf is unavailable. The dev container's `torch` package was broken at the time of writing (missing `libtorch_global_deps.so`), so spacy-transformers couldn't load. Production should ship `spacy-transformers` + `en_core_web_trf` in the image. Surfaced in `get_spacy_model_name()` for ops visibility.

2. **`ACCOUNT_NUM` regex is broad** — 8–17 digit bare runs. After MONEY/IBAN/PHONE/SSN/DATE_ISO so order-of-priority prevents overlaps. May over-flag plain numeric IDs that aren't account numbers; the deidentifier's overlap-resolver gives MONEY priority for currency-symbol-led runs so prices aren't swallowed.

3. **Tenant entity harvest is greedy.** Errs on over-collection — `cycles.title` extracts every PascalCase run as ORG. False positives in the dictionary cost only a token; false negatives cost privacy.

4. **`payload_hash` stored alongside the receipt.** Strictly derivable from the receipt body, but indexing on a precomputed column makes audit chain verification O(1). Phase B may swap this to a `prev_hash` chain for tamper-evident sequencing.

5. **Subscriptions stub persists.** Even though Phase A returns `status: "pending"` without delivering, we persist the subscription row so Phase F can resume subscriber wiring without consumer-side migration.

6. **`LATENCY_BUDGET_*` constants kept as informational only.** The route writes `latency_ms` to every audit row; surfacing a budget-exceeded counter is Phase F observability work.

7. **`payload_hash` excluded from `verify()`.** Only the canonical signature body is hashed for HMAC; `payload_hash` is metadata, not part of the chain. Tests confirm tamper detection on every signed field.

## Open items for Phase B

- Migrate every direct LLM call site in `/app/backend/` to `services.synisense.shield.client.invoke(...)`.
- Extend `ALLOWED_PURPOSES` with `chat.*`, `solva.*`, `work_studio.*`, `signals.*`, `monitor.*` (locked by purpose registry doc TBD).
- Absorb the 3 P1 risks listed in REWRITE_SPRINT_STATE.md:
  - Sync Document detail endpoints (524 timeouts) — wrap in async job queue.
  - Solva single-session routes missing `context_id` scope — privacy lockdown.
  - `streaming_v9.py` SSE `repr(exc)` leaks — replace with `{type(exc).__name__}: {str(exc)[:300]}` per the Chunk 3 rule.
- Wire the user-facing audit panel hooks (Phase C consumes them).
- Optional: install `spacy-transformers` + `en_core_web_trf` to unlock the F1 upgrade.

## Backwards compatibility

- The legacy Phase 12.1 Synisense pipeline (`pipeline.py`, `adapter.py`, `pool.py`, `presidio_engine.py`, `regex_recognisers.py`, `encryption.py`, `llm_fallback.py`) is **untouched**. Existing chat / briefing / deck call sites continue to use it. Phase B migrates them off; until then, both pipelines coexist.
