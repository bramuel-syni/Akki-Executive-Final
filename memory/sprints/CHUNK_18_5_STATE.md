# Chunk 18.5 — Track 4 cold-start fix + orphan probe + shield-internal CI guard

Closed 2026-05-21 (autonomous overnight run). Two of Chunk 18's
deferred Track 4 items shipped clean, plus a third architectural
hardening (the CI guard) the original Chunk 18 dispatch didn't
anticipate — but Chunk 18.5's diagnostic surfaced and the orchestrator
authorised.

## Scope ledger

| Item | Track 4 # | Action | Status |
|------|-----------|--------|--------|
| Cold-start latency on `evolution-diff` + `generate-meta` | 1 | Route `_legacy_llm_fallback._classify_one` through `llm_router.invoke()` + lift `litellm` imports to module-level | ✅ |
| 524-vs-541 orphan `solva_sessions` migration | 4 | Empty-state confirmed via probe; dormant migration script ready for the day a re-seed re-introduces rows; regression test pins `pending_orphans == 0` | ✅ |
| Shield-internal CI guard | NEW | `test_no_direct_llm_calls_inside_shield_except_router` — only `llm_router.py` + `streaming.py` may import provider SDKs | ✅ |

## 1 — Item 1 — Cold-start latency

### Root cause (diagnosed pre-flight, summary from reply)

`call_llm` in `llm_service.py` runs `_syn_shield → pipeline.dryrun` as a PRE-pass before handing to `shield.client.invoke()`. That pre-pass runs the full 3-layer Synisense pipeline; Layer 3 (`_legacy_llm_fallback.py::_classify_one`) called `emergentintegrations.LlmChat` DIRECTLY, **bypassing the gateway**. Consequences:

1. `SYNISENSE_LLM_MODE=mock` was ignored → tests + dev paid 5-13s per pre-pass.
2. A separate Anthropic/Gemini SDK pool warmed up on first use → 30s cold-start on `evolution-diff` / `generate-meta`.
3. The CI guard `test_no_direct_llm_calls_outside_shield` waived it because the file lived INSIDE `shield/`.

### Fix

`services/synisense/shield/_legacy_llm_fallback.py` rewritten end-to-end:
- Removed direct `LlmChat` construction + `EMERGENT_LLM_KEY` env read.
- New path: `await llm_router.invoke(prompt, model_preference="balanced", timeout_seconds=…)` — `balanced` maps to Gemini 2.5 Flash, the same classifier the legacy path used.
- Inherits the router's `SYNISENSE_LLM_MODE=mock` honoring + shared litellm pool.
- 1 imported less (`uuid`) + 1 imported less (`os`).

Companion change in `services/synisense/shield/llm_router.py`:
- `litellm` + `get_integration_proxy_url` lifted from per-call lazy imports inside `invoke_with_metering` to module-level. `_LITELLM_AVAILABLE` flag mirrors the `_EMERGENT_AVAILABLE` probe pattern.
- One less import-cache lookup per Shield call.

### Measured impact (mock mode, hermetic)

| Path | Pre-fix p50 / p95 | Post-fix p50 / p95 | Speedup |
|------|-------------------|--------------------|---------|
| `shield_invoke` cold | 651-741ms | **605ms** | 1.1× (already on the fast path; this measurement isolates spaCy NER first-load) |
| `shield_invoke` warm | 5ms | 5ms | unchanged (already optimal) |
| `call_llm` cold | **14,000ms** | **891ms** | **15.7×** |
| `call_llm` warm p50 | **11,962ms** | **98ms** | **122.3×** |
| `call_llm` warm p95 | **23,298ms** | **99ms** | **235×** |

Production projection (`evolution-diff` + `generate-meta`):
- Pre-fix: ~30s cold (mock-mode-blind pre-pass × claude-sonnet-4-5 cold start).
- Post-fix: ~5-8s cold (single classifier warm-up + sonnet-4-5 first call). **Inside the dispatch's 8s acceptance target.**

### Files touched

- `services/synisense/shield/_legacy_llm_fallback.py` — rewritten (133 → 121 LOC); same contract, different SDK path.
- `services/synisense/shield/llm_router.py` — `_LITELLM_AVAILABLE` probe added at module level; per-call imports inside `invoke_with_metering` removed; live-mode availability check now guards both `_EMERGENT_AVAILABLE` AND `_LITELLM_AVAILABLE`.

## 2 — Item 4 — Orphan session migration

### Live probe result

```
GET /api/admin/solva/legacy/orphan-count
→ {"pending_orphans": 0, "archived_orphans": 0}
```

Both the brief's 541 and POST_REWRITE_RAMP's 524 referred to historical counts. The current `solva_sessions` collection is empty. No migration runtime needed.

### Three-collection inventory (post-probe, documented for future agents)

| Collection | Role | Count (live preview) |
|------------|------|----------------------|
| `solva_sessions` | LEGACY orphan source | 0 |
| `solva_phase_d_sessions` | Phase D canonical | ✓ active |
| `solva_v2_sessions` | v2 orchestration runs | 158 (per Chunk 9.5 smoke) |

### Files shipped

- `scripts/probe_solva_legacy_orphans.py` — NEW read-only diagnostic. `python -m scripts.probe_solva_legacy_orphans` prints the three counts + the summary. Programmatically importable as `probe()` for tests.
- `scripts/migrate_solva_legacy_to_phase_d.py` — NEW DORMANT migration. Idempotent (`legacy_to_phase_d_migrated_at` marker), reversible (`solva_sessions_archived` preserved before destination write), audited (`solva_migration_audit` row per source row). Unmappable rows → `archived_only` (count documented in the audit log). Carries a `--dry-run` flag for safe diagnostic re-runs.

### Tests

- `test_chunk18_5_solva_legacy_orphan_count_is_zero` — pins the empty state. Fails loudly if a future seed re-introduces orphan rows.
- `test_chunk18_5_migration_script_idempotent_on_empty_collection` — dry-run + empty source returns all-zero counters.
- `test_chunk18_5_migration_script_handles_unmappable_row` — seeds one mappable + one unmappable row; confirms migration writes Phase D row + archives + audits both, and re-runs are idempotent via the marker.

## 3 — NEW: shield-internal CI guard

### Context

Chunk 18.5's pre-flight surfaced exactly the failure mode the original `test_no_direct_llm_calls_outside_shield` guard couldn't catch: a file living INSIDE `services/synisense/shield/` (`_legacy_llm_fallback.py`) was bypassing the gateway just as badly as any external caller would, but the guard's allow-prefix waived it. The same architectural shape can recur — anyone adding a new file inside `shield/` is one `LlmChat()` call away from re-introducing this failure.

### File shipped

`tests/test_qa_chunk_18_5.py::test_no_direct_llm_calls_inside_shield_except_router` — companion guard that scans `services/synisense/shield/` recursively with the same forbidden patterns (`LlmChat`, `UserMessage`, `litellm.completion`, `emergentintegrations.llm.*` import, etc.) but inverts the allowlist:

```python
SHIELD_ALLOWED_DIRECT_LLM = {
    str(SHIELD / "llm_router.py"),   # non-streaming sync invoke
    str(SHIELD / "streaming.py"),    # streaming counterpart
}
```

These are the TWO approved gateway entry points. Everything else inside `shield/` must route through one of them.

### First hit

The guard found a SECOND violator at first run: `services/synisense/shield/streaming.py` lines 254-315 (its own `import litellm` + `LlmChat` block for the streaming path). This is structurally legitimate — streaming responses have a different response shape (token-by-token deltas + final usage event) that doesn't fit the `invoke()` 3-tuple. It's added to `SHIELD_ALLOWED_DIRECT_LLM` with an explanatory comment so the architectural intent is clear: there are TWO approved entry points (sync + streaming), and only these two.

### Architectural lesson

> Shield-internal files can leak as easily as external callers — guard scope must include `shield/` itself.

The original Phase B guard was defined externally (Phase B brief: "the only thing inside `shield/` is allowed to talk to providers"). That framing is correct as INTENT but inverts the implementation: the file path matching `shield/` was used as an allowlist, when it should have been an allowlist scoped to specific entry-point modules. Chunk 18.5 corrects this.

The new guard's docstring carries this lesson verbatim so the next agent grepping the source sees the failure mode explained.

## Tests summary

`backend/tests/test_qa_chunk_18_5.py` — **8 tests, all passing**:

| # | Surface | Test |
|---|---------|------|
| 1 | Legacy fallback mock-mode honoring | `_legacy_fallback_honours_mock_mode` |
| 2 | Legacy fallback routes through `llm_router` | `_legacy_fallback_routes_through_llm_router` |
| 3 | Legacy fallback no direct LlmChat import | `_legacy_fallback_no_direct_llmchat_import` |
| 4 | litellm at module level in router | `_litellm_at_module_level_in_router` |
| 5 | Solva orphan count == 0 | `_solva_legacy_orphan_count_is_zero` |
| 6 | Migration idempotent on empty | `_migration_script_idempotent_on_empty_collection` |
| 7 | Migration handles unmappable row | `_migration_script_handles_unmappable_row` |
| 8 | Shield-internal CI guard | `test_no_direct_llm_calls_inside_shield_except_router` |

Cross-chunk regression (9.5/10/11/12/13/14/15/16/17/18/18.5 + CI guard) = **97 passed** (+8 from Chunk-18 baseline 89).

Wider Synisense suite (e2e + integration + security + Phase D Solva pipeline) = **42 passed** — proves the legacy-fallback rewrite didn't break the wider pipeline.

Wider repo suite = 551 passed + 496 skipped (one pre-existing fixture-pollution flake in `test_render_determinism::test_audit_summary_stamp_deterministic` — passes in isolation; not introduced by Chunk 18.5; tagged by the file itself as needing per-test fixture isolation).

## Live-preview confirmation

- `POST /api/v1/shield/llm/invoke` against `akki-executive.preview.emergentagent.com` returned `audit_id` + intelligible response (proves metering refactor didn't break the REST surface).
- `GET /api/admin/solva/legacy/orphan-count` returned `{pending_orphans: 0, archived_orphans: 0}` (proves the orphan probe surface is healthy).

## Architectural invariants checkpoint

- ✅ Shield gateway exclusivity STRENGTHENED. Two CI guards now in place:
  - `test_no_direct_llm_calls_outside_shield` — bans direct LLM calls outside `shield/`.
  - `test_no_direct_llm_calls_inside_shield_except_router` — bans direct LLM calls inside `shield/` except in `llm_router.py` + `streaming.py`.
- ✅ `tenant_id == account_id` boundary intact.
- ✅ No `repr(exc)` leaks. The legacy fallback's rewrite preserves the locked `e.__class__.__name__` short-name shape.
- ✅ No new third-party libraries. The migration script + probe use motor + python stdlib only.
- ✅ Schema-drift defensiveness — migration script's `_try_map_to_phase_d` falls back to `"unknown"` for unrecognised legacy `state` values + preserves `legacy_state` for forensics.
- ✅ Chunks 7-18 work intact — pytest 80 → 89 → 97 (Chunk 18.5 +8).
- ✅ Chunk-8 lifecycle state machine NOT modified.

## ESLint + Ruff

ESLint not applicable (no FE touched). Ruff clean on:
- `services/synisense/shield/_legacy_llm_fallback.py`
- `services/synisense/shield/llm_router.py`
- `scripts/probe_solva_legacy_orphans.py`
- `scripts/migrate_solva_legacy_to_phase_d.py`
- `tests/test_qa_chunk_18_5.py`

## Carry-forward — Chunk 19 backlog

`/app/memory/sprints/CHUNK_19_TASKS.md` already enumerates:
- C19-001 sample HMAC verification script (Python)
- C19-002 architecture diagram (mermaid → PNG)
- C19-003 screenshot pack collation
- C19-004 holistic product features + functionality document
- C19-005 admin cron-health endpoint (dev offer from Chunk 18, queued before this chunk)
