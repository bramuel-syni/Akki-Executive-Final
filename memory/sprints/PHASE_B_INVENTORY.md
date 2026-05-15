# Phase B — LLM Call Migration Inventory

> Read-only scan output. Catalogues every direct LLM/SDK call site in
> `/app/backend/` that exists BEFORE Phase B refactors. Used as the
> migration checklist; the post-migration CI guard
> (`test_no_direct_llm_calls_outside_shield.py`) enforces zero
> remaining call sites.

## Methodology
Grepped the tree (excluding `services/synisense/shield/` and
`tests/test_phase_b_chat_stream.py` / `tests/test_phase_a_chat_streaming_audit.py`
which monkeypatch the SDK by necessity) for:
- `from emergentintegrations.llm` / `import emergentintegrations.llm`
- `LlmChat`, `UserMessage`, `ChatError`, `FileContentWithMimeType`
- `EMERGENT_LLM_KEY` (string reference)
- `openai.`, `anthropic.`, `genai.`, `litellm.`

## Inventory table

| # | File | Line(s) | Consumer | Proposed purpose | Current error pattern | Migration |
|---|------|---------|----------|------------------|-----------------------|-----------|
| 1 | `services/llm_streaming.py` | 251, 254-291, 302-324 | **gateway** (chat/solva/work_studio/docs all flow through this) | `<consumer>.<surface>.<op>` per caller | `RuntimeError("EMERGENT_LLM_KEY not set")`; emits `LlmStreamChunk(kind="error", error="…")` | **MOVE** → `services/synisense/shield/streaming.py` (file relocated under Shield's umbrella; re-export shim at old path for unchanged imports) |
| 2 | `services/synisense/llm_fallback.py` | 47, 67-77 | legacy Phase 12.1 NER fallback (in-process pipeline) | n/a (Shield-internal; not exposed to external consumers) | try/except → fallback stats | **MOVE** → `services/synisense/shield/_legacy_llm_fallback.py` (same file, under Shield) |
| 3 | `services/sandbox_generation.py` | 154, 156-163 | `work_studio.sandbox.generate` | `work_studio.sandbox.generate` | `RuntimeError("EMERGENT_LLM_KEY not configured")`; outer `try/except` catches all | **MIGRATE** → `shield.client.invoke(purpose="work_studio.sandbox.generate", …)` |
| 4 | `llm_service.py` | 177, 333, 386-395 | **central gateway** for non-streaming Akki LLM calls (chat, briefing, decks, reports, ask) | dispatched by call site's `module` kwarg | wraps in `try/except Exception` → returns `{mode: "error", response: "[LLM error: …]"}` | **MIGRATE** → internally delegates to `shield.client.invoke(...)`; keeps the rich return-dict signature; sets `audit_id` and `trust_receipt` on the response |
| 5 | `routers/chat.py` | 278-298 | `chat.summarise` (one-shot summary call) | `chat.session.summarise` | `try/except Exception` → swallow | **MIGRATE** → `shield.client.invoke(purpose="chat.session.summarise", …)` |
| 6 | `routers/chat.py` | 1541-1554 | `chat.fm_a.hypothesis_detection` (failure-mode A) | `chat.fm_a.hypothesis_detection` | wrapped catch | **MIGRATE** |
| 7 | `routers/chat.py` | 1904-1953 | `chat.streaming.standard_response` (streamed) | `chat.streaming.standard_response` | wrapped catch | **MIGRATE** (via streaming path under shield) |
| 8 | `routers/chat.py` | 2235-2409 | `chat.tools.{ner,classify,extract}` (failure-mode B + C) | `chat.fm_b.claim_extraction`, `chat.fm_c.consequence_classification` | wrapped catch | **MIGRATE** |
| 9 | `routers/chat.py` | 2536-2549 | `chat.repair.refusal` (refusal compose) | `chat.refusal.compose` | wrapped catch | **MIGRATE** |
| 10 | `routers/admin_health.py` | 65-89 | dev/ops LLM ping (no PII) | `health.ping` | proper `{type(exc).__name__}: {str(exc)[:200]}` already | **MIGRATE** → `shield.client.invoke(purpose="health.ping", content="ping", …)` |
| 11 | `routers/work_studio_export.py` | 366, 374 | imports `ChatError` for `except` block only (no LLM call) | n/a | `except ChatError` | **REFACTOR** → drop the import, use `except Exception` (Shield surfaces errors via `ServiceUnavailable`) |

## Out-of-scope (intentional)
- `routers/billing.py` — imports `StripeCheckout` from `emergentintegrations.payments.stripe.checkout`. Payment SDK, not LLM. Phase B does not touch.
- `scripts/bootstrap_prod.py` — string reference only to `EMERGENT_LLM_KEY` in a required-env-vars list. No SDK call. Left as-is.
- `tests/test_phase_b_chat_stream.py`, `tests/test_phase_a_chat_streaming_audit.py` — monkeypatch the SDK to make streaming tests hermetic. The CI guard explicitly allows imports from `tests/` because tests need to mock providers; the guard catches consumer-code violations, not test scaffolding.

## Counts
- Direct call sites located outside Shield: **11** (8 LLM call sites + 1 import-only + 2 gateway files).
- Files to migrate: **6 unique** (`services/llm_streaming.py`, `services/synisense/llm_fallback.py`, `services/sandbox_generation.py`, `llm_service.py`, `routers/chat.py`, `routers/admin_health.py`).
- Files to refactor (import-only): **1** (`routers/work_studio_export.py`).
- Files to MOVE under `services/synisense/shield/`: **2** (`llm_streaming.py`, `llm_fallback.py`).

## ALLOWED_PURPOSES additions (Phase B canonical set)

```
# Chat (Phase B migration target; Phase C will add the protective layer)
"chat.session.summarise",
"chat.streaming.standard_response",
"chat.standard_response",
"chat.fm_a.hypothesis_detection",
"chat.fm_b.claim_extraction",
"chat.fm_c.consequence_classification",
"chat.refusal.compose",
"chat.*",

# Solva (Phase D will exercise; declared now for clean migration when
# the entry path swaps providers)
"solva.layer_0.frame_audit",
"solva.layer_0.situation_classification",
"solva.layer_1.candidate_generation",
"solva.layer_2.triangulation.claim_extraction",
"solva.layer_2.triangulation.entailment_classification",
"solva.layer_2.tension_detection",
"solva.layer_3.scenario_narrative_generation",
"solva.layer_3.synthesis_rendering",
"solva.refusal.compose",
"solva.entry.frame_payload",
"solva.*",

# Work Studio
"work_studio.brief.enhance",
"work_studio.brief.seed",
"work_studio.deck.generate",
"work_studio.report.generate",
"work_studio.minutes.enhance",
"work_studio.compile.board_pack",
"work_studio.sandbox.generate",
"work_studio.*",

# Document Journal
"document_journal.commentary.generate",
"document_journal.meta.generate",
"document_journal.summary.generate",
"document_journal.evolution_diff",
"document_journal.signals.generate",
"document_journal.add_to_cycle.prep",
"document_journal.take_to_solva.prep",
"document_journal.*",

# Cycle Manager
"cycle_manager.agenda.generate",
"cycle_manager.briefing.aggregate",
"cycle_manager.*",

# Monitor (Phase F will exercise)
"monitor.objective.status_assessment",
"monitor.project.status_assessment",
"monitor.strategic_goal.update",
"monitor.*",

# Pulse
"pulse.signal.commentary",
"pulse.*",

# Ops / health
"health.ping",
```

## Audit ID storage schema

Per the brief, every consumer collection grows a `synisense_audit_ids` column:
- `chat_sessions.synisense_audit_ids: List[str]`
- `solva_v2_sessions.synisense_audit_ids: List[str]` (Phase D will reshape; Phase B just appends per LLM turn the existing entry-path makes)
- `documents.synisense_audit_ids: Dict[str, List[str]]` (keyed by operation: `commentary`, `summary`, `evolution_diff`, `signals`)
- `work_studio_briefs.synisense_audit_ids: List[str]`
- `decks.synisense_audit_ids: List[str]`
- `reports.synisense_audit_ids: List[str]`
- `cycles.synisense_audit_ids: List[str]`

## Deliberately-deferred items

- **Streaming-through-Shield with per-chunk re-identification.** Phase B keeps streaming under Shield's namespace by relocating `llm_streaming.py` into `shield/`, but the per-chunk Shield receipt is **deferred** to Phase C. Streaming today goes: shield-de-id → stream → caller-side rehydrate via shield's regex tokens (the existing pattern). Per-chunk audit rows + per-chunk trust receipts are a Phase C deliverable when the chat protective layer arrives.
- **Sync→async conversion of the 4 Document Reader endpoints** (`generate-meta`, `summary`, `journal-commentary`, `evolution-diff`). Done in this phase but scoped tightly to wrapping the existing handler bodies in `services/job_queue.py` background jobs — no behavior changes beyond returning `{job_id, audit_id}` and adding a `GET /jobs/{id}` poll handler that already exists.


---

## Phase B Inventory Outcome (post-migration, 2026-05-13)

**Total direct-call sites identified pre-Phase B**: **11**.
**Total migrated**: **10** (all consumer-facing call sites + the
gateway). **Refactored without migration**: **1**
(`routers/work_studio_export.py` ChatError import → local marker).
**Files moved under `services/synisense/shield/`**: **2**.
**Deliberately-skipped**: **0** in inventory; **2 absorbed-but-deferred
to Phase C** (the sync→async Document Reader endpoints + Commentary
loading state — they belong with the Phase C audit-panel surface).

**CI guard outcome**: ZERO violations. The Phase B invariant — "no
direct LLM provider SDK call survives outside
`services/synisense/shield/`" — is locked by
`tests/test_no_direct_llm_calls_outside_shield.py`.

Full pytest count: **524 passed** (was 520 baseline). 0 regressions.
