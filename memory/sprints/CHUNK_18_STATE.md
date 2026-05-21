# Chunk 18 — Track 4 infra (cron + token metering)

Closed 2026-05-21 (autonomous overnight run). Two of the four Track 4
items shipped this chunk; the remaining two (cold-start latency Item 1,
orphan-session migration Item 4) carry forward to Chunk 18.5 per the
dispatch's scope guard.

## Scope ledger

| Item | Track 4 # | Shipped here? | Anchor |
|------|-----------|---------------|--------|
| Cron — APScheduler hourly `derivation_scheduler.run_hourly_pass()` | 3 | ✅ | §1 |
| Metering — token-accurate Shield audit (`tokens_in/out`, `metering_method`, `actual_cost_usd`) | 2 | ✅ | §2 |
| Cold-start latency on `evolution-diff` + `generate-meta` | 1 | ⏸ deferred to Chunk 18.5 | (out of scope) |
| Orphan `solva_sessions` migration | 4 | ⏸ deferred to Chunk 18.5 | (out of scope) |

Also shipped: render-smoke hygiene fix on step 14 (Chunk 12 probe now
prefers Exec contexts so the Update Goal assertion fires on a role
where the RBAC gate doesn't hide the CTA). Details in §3.

## 1 — Item 3 — APScheduler hourly cron + Mongo-locked single-instance

### New module — `services/synisense/engine/scheduler_lock.py`

Tiny helper (140 lines) exposing four primitives:

- `replica_id()` — process-stable identifier (`hostname-pid-uuid`).
- `ensure_indexes()` — creates the TTL index `scheduler_locks_ttl` on
  `expires_at` (expireAfterSeconds=0) so dead lock rows reap once
  the lease elapses.
- `run_locked(*, job_id, fn, bucket, lease_seconds=3600)` — async
  context that:
    1. `insert_one({_id: f"{job_id}:{bucket}", owner: replica_id(), ...})`
       — a `DuplicateKeyError` is the lose-the-race signal.
    2. Runs `fn()` on the winner.
    3. Writes a `scheduler_runs` heartbeat row on success OR failure.
- `current_hour_bucket()` — returns `YYYYMMDDHH` UTC.

### Why two collections

- `scheduler_locks` — coordination (TTL-reaped, ephemeral). Stores
  `_id`, `job_id`, `hour_bucket`, `owner`, `acquired_at`, `expires_at`.
- `scheduler_runs` — observability (durable, append-only). Stores
  `job_id`, `replica_id`, `started_at`, `finished_at`, `duration_ms`,
  `status` ("ok" | "failed"), `summary`, `error`.

Operators verify the cron is alive via:

```js
db.scheduler_runs.find(
  { job_id: "synisense_engine_hourly", status: "ok" },
).sort({ started_at: -1 }).limit(1)
```

If the most recent `started_at` is > 2 hours old → alert.

### Boot wiring in `server.py` (lines ~982-1019)

Independent `AsyncIOScheduler` instance armed AFTER the weekly-secret-
gated scheduler block. Runs regardless of `AKKI_CRON_SECRET` because it's
an internal background pass, not a webhook-triggered cron.

```python
engine_sched = AsyncIOScheduler(timezone="UTC")
engine_sched.add_job(
    _fire_engine_hourly_pass,
    CronTrigger(minute=0),  # top of every hour UTC
    id="synisense_engine_hourly",
    replace_existing=True,
)
engine_sched.start()
app.state.engine_scheduler = engine_sched
```

`_fire_engine_hourly_pass` calls `run_locked()` with bucket =
`current_hour_bucket()`, which compacts the (job_id, hour) tuple into
the lock's `_id` field. The shutdown handler now also stops
`app.state.engine_scheduler`.

### Live confirmation on boot

```
Chunk 18 (Track 4 item 3): Synisense Engine hourly cron armed
  (top-of-hour UTC, Mongo-locked, replica=agent-env-...-3fca028d).
```

A direct test-fire on the local pod (bypassing APScheduler, but
calling `run_locked + run_hourly_pass` end-to-end) wrote:

```
{
  job_id: "synisense_engine_hourly_smoke",
  status: "ok",
  duration_ms: 1530,
  summary: {
    anomaly_flag: 19,
    life_stage: 132,
    churn_risk: 132,
    behavioral_vector: 132,
    compliance_trigger: 0,
    operational_health: 2,
  },
  ...
}
```

## 2 — Item 2 — Token-accurate Shield metering

### Audit-log schema additions (`services/synisense/shield/audit_log.py`)

`write_audit()` gained one new optional field, `actual_cost_usd`, on
top of the Chunk-17-era `tokens_in / tokens_out / metering_method`
triple. Backward-compat: missing on legacy rows; queries reading these
fields must treat absence as `None`/unknown.

Two new helpers in the same module:

- `_RATE_TABLE: Dict[(provider, model), (input_per_M_usd, output_per_M_usd)]`
  — 5 rows covering the providers we proxy through Emergent today.
  `_DEFAULT_RATE` mirrors Claude Sonnet 4.5 pricing for unknown pairs
  (`$3 / $15 per 1M`).
- `compute_cost_usd(*, provider, model, tokens_in, tokens_out) -> Optional[float]`
  — strips the `:mock` suffix from provider/model strings (so the same
  rate row covers both live and mock paths), looks up the table, and
  returns USD. Returns `None` if both token counts are `None`.

### Router rewrite (`services/synisense/shield/llm_router.py`)

The legacy `invoke()` (3-tuple) is now a thin wrapper around the new
`invoke_with_metering()` (4-tuple). The implementation calls
`litellm.acompletion` directly with the same OpenAI-compat proxy URL
that `emergentintegrations.LlmChat._execute_completion` builds — but
because we keep the raw `ModelResponse`, we can pull
`response.usage.prompt_tokens` / `completion_tokens` and surface them
through `usage = {"input_tokens", "output_tokens", "method": "exact"}`.

Mock-mode + missing-key paths return `usage = {}`, which signals the
caller to fall back to the char/4 estimator.

### Client + router rewrites

- `services/synisense/shield/client.py::invoke()` — now branches on the
  usage payload. Exact path: persist provider tokens + flag
  `metering_method="exact"`. Estimated path: existing char/4 estimator
  + `metering_method="estimated"`. Both paths compute
  `actual_cost_usd` via `compute_cost_usd()`.
- `routers/synisense_shield.py::invoke()` (the legacy
  `/api/v1/shield/llm/invoke` REST surface) gets the SAME branch logic
  so byte-identical persistence behaviour applies to direct
  programmatic callers + the HTTP route.

### Backward-compat invariants

- The 3-tuple `llm_router.invoke()` signature is preserved.
- The audit row's pre-Chunk-17 columns are untouched.
- Queries reading `metering_method=None` continue to work.

## 3 — Render-smoke hygiene fix (pre-Chunk-18 unblock)

The Chunk 12 step 14 probe was first-with-seed agnostic. After data
drift moved `fbc54a51-…` (TEST_SeededNedCo, role=ned) to the front of
`/api/me/contexts`, the probe landed on a NED ctx where the Update
Goal CTA is RBAC-hidden (Chunk 11 QA-048) — assertion fired against a
correctly-hidden button.

Fix (`render-smoke.js:2071-2138` + `:2218-2243`):
- Pull `role` per ctx from `/api/me/contexts` response shape (`role`
  field, not `my_role`).
- Order visit list: Exec contexts first (active-first if Exec), NEDs
  second.
- Soft-skip the Update Goal assertion when `role !== "executive"` with
  a clear log line — RBAC hiding is the correct outcome, not a regression.
- All other Chunk 12 drawer assertions (Performance Score label, legacy
  Edit removed, % formatting, card-level timestamp) continue to hard-
  assert regardless of role.

Re-ran render-smoke → step 14 now lands on `dcc263b1` (Tuli FG CFO,
role=executive), Update Goal button visible, all 18 steps GREEN.

## Memory-mitigation note (for future agents grepping forgetting docs)

> Smoke probes that filter by role/context must prefer specific role
> first, not first-with-seed. Seed-data ordering can shift based on
> insertion timing across re-runs; landing on the wrong role flips
> an RBAC-correct assertion into a false negative.

Rule applies anywhere a probe walks the contexts list and then makes a
role-gated UI assertion (StrategicGoals · Cycle assignment · Monitor
extract). When in doubt, soft-skip on the wrong-role branch and log
loudly rather than fail.

## Tests

`backend/tests/test_qa_chunk_18.py` — 9 tests covering:

| # | Surface | Test |
|---|---------|------|
| 1 | Cron once per bucket | `test_chunk18_scheduler_lock_runs_once_per_bucket` |
| 2 | Cron failure heartbeat | `test_chunk18_scheduler_lock_records_failure` |
| 3 | TTL index present | `test_chunk18_scheduler_lock_ttl_index_present` |
| 4 | Boot wiring static check | `test_chunk18_engine_hourly_cron_registered_in_server` |
| 5 | Cost table coverage | `test_chunk18_compute_cost_uses_per_model_rate_table` |
| 6 | Audit row round-trip | `test_chunk18_audit_log_persists_chunk18_fields` |
| 7 | Exact metering path | `test_chunk18_shield_invoke_records_exact_metering_when_sdk_returns_usage` |
| 8 | Estimated fallback path | `test_chunk18_shield_invoke_falls_back_to_estimated_when_usage_missing` |
| 9 | CI Shield-exclusivity guard | `test_chunk18_no_new_direct_llm_calls` |

**All 9 pass.** Cross-chunk regression (9.5/10/11/12/13/14/15/16/17/18 +
CI guard) = **89 passed** (+9 from the Chunk-17 baseline of 80).

## Architectural invariants checkpoint

- ✅ Shield gateway exclusivity preserved. No new direct LLM call
  sites; the new `litellm.acompletion` call is INSIDE the Shield's
  `llm_router` module (the canonical proxy entry point).
- ✅ `tenant_id == account_id` boundary intact.
- ✅ No `repr(exc)` leaks. New cron error path uses
  `f"{type(exc).__name__}: {str(exc)[:200]}"` per Chunk 3 rule.
- ✅ No new third-party libraries (APScheduler + litellm already
  installed; `pymongo.errors.DuplicateKeyError` is part of the
  motor/pymongo stack).
- ✅ Schema-drift defensiveness — `compute_cost_usd` tolerates
  `None`/empty input + `:mock` suffixes.
- ✅ Chunks 7-17 work intact — pytest +9 (80 → 89).
- ✅ Chunk-8 lifecycle state machine NOT modified.

## ESLint + Ruff

ESLint clean on `render-smoke.js`. Ruff clean on
`services/synisense/shield/audit_log.py`,
`services/synisense/shield/client.py`,
`services/synisense/shield/llm_router.py`,
`services/synisense/engine/scheduler_lock.py`,
`tests/test_qa_chunk_18.py`. (The pre-existing F401 on
`routers/synisense_shield.py::GovernanceRefused` import is NOT a
Chunk-18 regression and is left in place — see `git log`.)

## Carry-forward — Chunk 18.5 backlog

- Track 4 Item 1 — 30s cold-start latency on `evolution-diff` +
  `generate-meta` (investigation first, then fix).
- Track 4 Item 4 — 524 (TBD — exact count needs a direct query
  before scoping; brief said 541) orphan `solva_sessions` rows
  migrating to `solva_phase_d_sessions`. Migration must be idempotent
  + reversible + audited.

Both deferred per the dispatch's scope guard so this chunk's blast
radius stays surgical.
