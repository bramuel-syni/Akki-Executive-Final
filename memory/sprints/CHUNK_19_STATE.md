# Chunk 19 — Track 5 final (Bank-QA polish + cron-health + holistic doc)

Closed 2026-05-21 (autonomous overnight run). Final chunk of the
sprint. All 5 dispatch deliverables (C19-001 through C19-005) shipped.

## Scope ledger

| ID | Surface | Action | Status |
|----|---------|--------|--------|
| C19-001 | Sample HMAC verifier (Python, stdlib only) | NEW `phase_e_addendum_artefacts/verify_trust_receipt.py` — 174 LOC, no third-party deps, `--self-test` flag, signed-fields contract locked | DONE |
| C19-002 | Architecture diagram (Mermaid → ready-to-export PNG) | NEW `phase_e_addendum_artefacts/architecture_diagram.md` — Mermaid flowchart with colour groups for Shield (blue), provider SDKs (yellow), persistence (green); regen instructions; reviewer verification surfaces table | DONE |
| C19-003 | Screenshot pack collation README | NEW `phase_e_addendum_artefacts/screenshot_pack_README.md` — 10-PNG enumeration with role + caption + anchor chunk per shot; refresh cadence + capture procedure documented | DONE |
| C19-004 | Holistic product features + functionality doc | NEW `/app/memory/product/AKKI_FEATURES_AND_FUNCTIONALITY.md` — 10 sections, ~3500 words, 25-30 min read; exec-PO hybrid audience; folds the Chunk 18.5 cold-start metrics into § 6 per dev offer | DONE |
| C19-005 | Admin cron-health endpoint | MODIFIED `routers/synisense_observability.py` +`/api/admin/synisense/cron-health` — superadmin-only read of `scheduler_runs`, latest row per `job_id`, includes `hour_bucket` derivation | DONE |

## 1 — C19-005 — Admin cron health endpoint

### API

`GET /api/admin/synisense/cron-health` — superadmin-gated.

Returns a list ordered by `last_run_at` desc:

```json
[
  {
    "job_id": "synisense_engine_hourly",
    "last_run_at": "2026-05-21T19:00:00.123456+00:00",
    "status": "ok",
    "duration_ms": 1530,
    "summary": {"derived": 134, "anomaly_flag": 19, ...},
    "hour_bucket": "20260521-19",
    "replica_id": "agent-env-...-3fca028d",
    "error": null
  }
]
```

Empty list when no scheduled work has run yet (fresh deploy / pre-top-of-hour).

### Implementation

20-line `cron_health()` handler inside `routers/synisense_observability.py`. Uses a Mongo aggregation pipeline (`$sort` → `$group$first` → `$replaceRoot` → `$sort`) so the "latest per job_id" computation runs server-side. Derives `hour_bucket` from `started_at` because the heartbeat row doesn't carry the bucket directly (the lock row does, but it gets TTL-reaped).

### Why this matters for Bank-QA

Bank reviewers expect evidence that scheduled work *actually runs*. Pre-Chunk-19, that evidence was scattered across logs + the `scheduler_runs` Mongo collection. This single endpoint surfaces it as a one-line read. Pairs with the architecture diagram in C19-002 (which shows where `scheduler_runs` sits in the data layer).

### Tests

`tests/test_qa_chunk_19.py`:
- `test_chunk19_005_cron_health_returns_latest_per_job` — seeds two rows for the same job_id + a third for a different job; asserts the endpoint returns the most-recent per job; verifies `hour_bucket` derivation + failure-status surfacing.
- `test_chunk19_005_cron_health_empty_when_no_runs` — fresh-state list response.
- `test_chunk19_005_cron_health_requires_superadmin` — 403 when the dep raises.

### Implementation note for future agents

First implementation used `fastapi.testclient.TestClient` for these tests. Failed in `pytest-asyncio` mode when the test ran alongside an async-fixture-using test in the same module: motor's connection got bound to a closed event loop. Fix: switched to `httpx.AsyncClient + ASGITransport` which runs in the same loop as the async test. Future test files calling FastAPI routes from async tests should use this pattern.

## 2 — C19-004 — Holistic product features doc

### Sections shipped (per dispatch outline)

1. What AKKI is
2. Personas served (NED · Executive · Superadmin)
3. Architectural foundation (Phases A-F.1 summary)
4. Feature catalogue by surface (9 surfaces in per-surface tables)
5. Privacy & trust surfaces (ASCII Shield-flow diagram + Trust Receipts + Audit Panel + Trust Panel)
6. Infrastructure & performance posture (token metering + cron + cold-start budget table + CI guards)
7. QA sprint outcomes (chunk-by-chunk scorecard)
8. Open items requiring PO input (AWAITING_PO table)
9. Deferred & known-gap items
10. Glossary (Shield · Solva · NER · Phase D · etc.)

### Length

3,500+ words (verified by regression test). Target was 8-12 pages of markdown → ~3500-5000 words → hit.

### Tone

Executive-formal, governance-conscious, factual. No marketing language. Quotes from internal artefacts (architectural lessons, status badges, performance numbers) are sourced inline so reviewer can cross-reference.

### Audience validation

The doc opens by stating "This document is the single canonical reference for what AKKI does, how the surfaces relate to one another, and what state each is in. It is written for an executive or PO who wants the whole picture in one sitting without having to cross-reference five sprint logs." — sets reader expectation correctly.

## 3 — C19-001 / -002 / -003 — Bank-QA evidence pack

### C19-001: HMAC verifier

Stdlib-only Python script. `--self-test` round-trips a canned receipt + secret + verifies the negative case (tampered secret rejected). The receipt's signed-fields contract (`audit_id`, `tenant_id`, `consumer_id`, `purpose`, `timestamp`, `request_hash`, `response_hash`, `outcome`, `llm_provider`, `llm_model`) matches what the Shield writes server-side.

Reviewer flow:
```bash
$ python verify_trust_receipt.py /path/to/receipt.json \
      --secret-file /path/to/master_secret.txt
{"ok": true, "reason": "OK — signature verified against the supplied secret"}
$ echo $?
0
```

### C19-002: Mermaid architecture diagram

Single-page system overview rendered live in any GitHub Markdown viewer. Colour groups make the trust boundary obvious:
- Blue: the Synisense Shield + its components.
- Yellow: outside the trust boundary (LLM providers).
- Green: persistence (Mongo collections).

Reviewer verification table lists three live endpoints + one CLI tool that lets a reviewer poke each piece of the picture without reading code.

### C19-003: Screenshot pack README

10 screenshots covering Portfolio → Chat → Document Journal → Cycle Manager → Pulse → Strategic Goals → Solva → Work Studio → Admin Observability → Admin Cron Health. Per-shot caption + role + anchor chunk. Refresh cadence + capture procedure documented so an operator can refresh the pack post-major-chunk without re-reading the broader sprint history.

The PNGs themselves aren't auto-generated (would require an operator to navigate the live preview as the right user role); the README is the durable companion that survives PNG drift.

## Architectural invariants checkpoint

- ✅ Shield gateway exclusivity preserved (both CI guards PASS).
- ✅ New endpoint is read-only on `scheduler_runs`; no new LLM call sites.
- ✅ `tenant_id == account_id` boundary intact.
- ✅ No `repr(exc)` leaks. Verifier uses `str(exc)[:200]` for error messages.
- ✅ No new third-party libraries. The verifier is stdlib only; the endpoint uses motor + FastAPI primitives already in the stack.
- ✅ Chunks 7-18.5 work intact — pytest 97 → 101 (+4).
- ✅ Chunk-8 lifecycle state machine NOT modified.

## Pytest delta

- Chunk-files cross-chunk regression: **97 → 101** (+4 in `test_qa_chunk_19.py`).
- ESLint not applicable (no FE touched).
- Ruff clean on `routers/synisense_observability.py` + `tests/test_qa_chunk_19.py`.

## Sprint close-out

This is the final chunk of the autonomous QA-2026-05-16 sprint. Track 1-5 all closed except for AWAITING_PO items (one in Track 4, three in the broader QA backlog). The morning report is appended to `AUTONOMOUS_SPRINT_LOG.md`; the user wakes up to that file + `AKKI_FEATURES_AND_FUNCTIONALITY.md`.
