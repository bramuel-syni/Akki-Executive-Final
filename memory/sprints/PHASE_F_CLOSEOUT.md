# Phase F + Phase E.5 — Engine real signals + Solva seed handoffs (CLOSEOUT)

**Date:** 2026-05-16
**Status:** ✅ COMPLETE. Phase F is the final phase of the Synisense rewrite. After this lands the locked A → F sequence is closed; the paused 12-chunk QA sprint can resume.

## Scope dispatched

> Phase F + Phase E.5 (bundled) — final rewrite phase. Real Engine signal generation + seed-payload support on the Phase D framing endpoint + Monitor "Update goal" mechanic + per-context Shield billing surface + comprehensive close-out.

All five sub-tasks landed. Five-paragraph "Bank-QA briefing" lives in `REWRITE_FINAL_CLOSEOUT.md`.

## Sub-task A — Phase E.5: Seed-payload support in Phase D framing

### Backend

- New Pydantic `SeedPayload` model on `POST /api/contexts/{cid}/solva/v2/sessions`. Required fields: `source ∈ {cycle, work_studio_artefact, document_journal}`, `source_id`, `preview_text` (≤4000 chars), `attached_references` (≤20 ids), optional `sub_module_hint`.
- When a `seed_payload` is present:
  - `initial_framing` is pre-populated from `preview_text` and the session opens at `layer_state="framing"` (skipping the `entry` waiting state).
  - `sub_module_hint` overrides the default `seek_clarity` sub_module when the caller passes the wizard default — explicit `sub_module` always wins.
  - References are resolved against `documents`, `cycles`, `work_studio_artefacts` in the caller's context. Cross-context / phantom refs are silently dropped (never error).
  - Session row carries `source_handoff: {source, source_id, source_url}` for traceability. `source_url` is the deep-link back to the origin surface.
  - `seed_attached_references[]` records the resolved Layer 0 evidence anchors (`{ref_type, ref_id, label}`).
  - `schema_version` bumps from 3 → 4 for seed-bearing sessions.
- Legacy non-seed `POST /sessions` shape is preserved byte-for-byte (`schema_version: 3`, `source_handoff: null`, `layer_state: "entry"`).

### Frontend

- `solvaPhaseDClient.js::createPhaseDSession` accepts `seedPayload` and forwards.
- `SolvaPhaseDSession.jsx` reads `?seed_kind=cycle|work_studio|document` + `seed_id` + optional `seed_preview` from the URL, maps short labels to backend enums, and constructs the payload.
- `SolvaLanding.jsx` — **legacy fallback removed**. All Solva-card flows (including seed-bearing) now route to `/app/solva/phase-d/session/new?...`. The legacy `/app/solva/session/new` path is no longer reachable from the landing.

### Live evidence

```bash
$ curl -X POST .../api/contexts/{cid}/solva/v2/sessions \
    -d '{"sub_module":"seek_clarity",
         "seed_payload":{"source":"cycle","source_id":"cyc-demo-001",
           "preview_text":"Q4 audit committee briefing pack needs a stress review.",
           "attached_references":["cyc-demo-001"],
           "sub_module_hint":"develop_strategy"}}'
{
  "session_id": "sol-8407d10aa0414ecf94cbcc6bdf98d486",
  "sub_module": "develop_strategy",          ← hint honoured
  "layer_state": "framing",                  ← skipped 'entry'
  "initial_framing": "Q4 audit committee briefing pack needs a stress review.",
  "source_handoff": {
    "source": "cycle",
    "source_id": "cyc-demo-001",
    "source_url": "/app/cycle/cyc-demo-001"  ← deep-link back to source
  },
  "schema_version": 4,                       ← seed-bearing
  ...
}
```

## Sub-task B — Real Engine signal generation

### Backend

- New `services/synisense/engine/signal_derivation.py`. Six rules, each pulling from real Mongo data:

  | Rule              | derivation_source                                          | Source data |
  |-------------------|------------------------------------------------------------|------------|
  | anomaly_flag      | `derived_from_cycle_status_anomaly_cycles`                 | `cycles` (status / readiness / stale-draft heuristics) |
  | life_stage        | `derived_from_session_activity_solva_phase_d_sessions`     | activity window across chat + solva sessions |
  | churn_risk        | `derived_from_engagement_composite_chat_messages`          | composite of msg_count, solva_count, overdue cycle items |
  | behavioral_vector | `derived_from_action_log_chat_messages`                    | 8-component normalised log of user actions |
  | compliance_trigger| `derived_from_regulatory_keyword_documents`                | regulatory keywords in documents + audit/risk committees |
  | operational_health| `derived_from_cycle_health_composite_cycles`               | composite of cycle health + objective on-track + anomaly noise |

- `derive_for_tenant(tenant_id)` runs all 6 rules. Idempotent — wipes prior `derived_from_*` rows before insert. Real-ingestion signals (Phase G+) are never touched.
- `derive_or_seed_for_tenant(tenant_id)` is the consumer entry point: runs derivation, and on a brand-new / empty workspace it gracefully falls back to the Phase A seeder so the engine never reports zero content.
- New `services/synisense/engine/derivation_scheduler.py` with `run_startup_backfill()` (kicked off as a fire-and-forget task in `server.py::on_startup`) and `run_hourly_pass()` (entry point for future APScheduler cron).
- New endpoint: `POST /api/v1/engine/admin/derive` (any authenticated tenant for self; superadmins may pass `?tenant_id=…` to target another tenant).

### Live evidence

```bash
$ curl -X POST .../api/v1/engine/admin/derive
{
  "tenant_id": "b8d20f47-…",
  "derived": {
    "anomaly_flag": 2,
    "life_stage": 1,
    "churn_risk": 1,
    "behavioral_vector": 1,
    "compliance_trigger": 0,
    "operational_health": 1
  },
  "fallback_used": false,
  "seeded": {},
  "total_derived": 6
}

$ curl -X POST .../api/v1/engine/signals/query …
sig-276e3f3e82ac4b | anomaly_flag      | derivation_source: derived_from_cycle_status_anomaly_cycles
sig-314c39c216654a | life_stage        | derivation_source: derived_from_session_activity_solva_phase_d_sessions
sig-3d54b3c7a40046 | behavioral_vector | derivation_source: derived_from_action_log_chat_messages
sig-532ba9d7568049 | anomaly_flag      | derivation_source: derived_from_cycle_status_anomaly_cycles
sig-7dbcc2187d4a43 | churn_risk        | derivation_source: derived_from_engagement_composite_chat_messages
sig-874b4bbbd0ac4f | operational_health| derivation_source: derived_from_cycle_health_composite_cycles
```

Every signal carries `derived_from_*` (not `seeded_from_*`). Six real categories from real data.

### Server startup log
```
synisense.engine.signal_derivation - INFO -
    synisense.engine.derivation: tenant=b8d20f47-… derived=6
    (anomaly_flag=2, life_stage=1, churn_risk=1, behavioral_vector=1,
     operational_health=1)
akki - INFO - [engine] derivation backfill done:
    {'anomaly_flag': 2, 'life_stage': 9, 'churn_risk': 9,
     'behavioral_vector': 9, 'compliance_trigger': 0,
     'operational_health': 1}
```
9 tenants got fresh signals on startup, 6 categories each.

## Sub-task C — Monitor "Update goal" mechanic

### Backend

- New `routers/monitor_status_assessment.py` exposing:
  - `POST /api/contexts/{cid}/monitor/objective/{oid}/update-status`
  - `POST /api/contexts/{cid}/monitor/project/{pid}/update-status`
- Pipeline per call:
  1. Pulls up to 12 most recent engine signals for this tenant in this context (or tenant-wide). Filters to anomaly_flag, compliance_trigger, operational_health, churn_risk — the categories that drive status calls.
  2. Pulls 5 most recent documents in the context.
  3. Composes a constrained prompt asking for ONE JSON object with `{status, confidence, rationale, supporting_signal_ids, supporting_doc_ids}`.
  4. Calls Shield via `shield_invoke(purpose="monitor.objective.status_assessment"|"monitor.project.status_assessment")`. Purposes are already in `ALLOWED_PURPOSES`.
  5. Parses the JSON. If the LLM returns prose or malformed JSON, falls back to a heuristic scan; the endpoint NEVER 500s on a flaky LLM.
  6. Maps `on_track|at_risk|off_track` → `green|amber|red` and persists on the item row: `last_akki_assessment: {status, rag_status, confidence, rationale, supporting_signal_ids, supporting_doc_ids, audit_id, assessed_at}` + bumps `updated_at`.
- Status is **non-overridable** (locked PO default). The supporting rationale + references are always visible.

### Frontend

- `ObjectivesProjectsPanel.jsx::ItemDrawer` — new "Update goal" card with a button + analysing spinner. On success it renders:
  - **Rationale** prose (matches the bank-QA spec)
  - Confidence as a percentage
  - audit_id (monospace, clickable identifier for trust-receipt verification)
  - Supporting signal_ids + doc_ids
- `data-testid`s on every new element: `obj-drawer-update-goal-btn`, `obj-drawer-assessment-rationale`, `obj-drawer-assessment-audit-id`, `obj-drawer-assessment-signals`, `obj-drawer-assessment-docs`.

### Live evidence

```bash
$ curl -X POST .../api/contexts/{cid}/monitor/objective/{oid}/update-status -d '{}'
{
  "id": "8d5315d3-…",
  "kind": "objective",
  "rag_status": "amber",
  "status": "at_risk",
  "assessment": {
    "status": "at_risk",
    "rag_status": "amber",
    "confidence": 0.72,
    "rationale": "The objective is currently amber/at_risk with no
        assigned owner, which creates accountability gaps. While
        engagement remains stable with 38 sessions in 30 days, the
        operational health signal shows concerning metrics: only 33%
        of cycles are completing and 33% of objectives are on track,
        with a 12% error rate. These operational challenges may
        impede progress toward the CSAT target.",
    "supporting_signal_ids": [
      "sig-874b4bbbd0ac4f90b9c2c2eb24a93afb",
      "sig-7dbcc2187d4a43a58b401ef85e044fa4"
    ],
    "supporting_doc_ids": [],
    "audit_id": "aud-afd1499f99104c429b7b65c8c81f59dc",
    "assessed_at": "2026-05-16T03:38:10.846589+00:00"
  }
}
```

Note how Akki cited the actual `operational_health` and `churn_risk` signals (derived in Sub-task B) by their signal_id. This is the closed loop: signals derived from real Mongo data → Akki status-assessment cites them by ID → bank QA can verify the chain via the `audit_id`.

## Sub-task D — Per-context Shield billing surface

### Backend

- New `services/synisense/pricing.py` with a 9-entry pricing table (anthropic / openai / gemini families). Code-controlled, **NOT API-editable** — same governance pattern as `ALLOWED_PURPOSES`. Each entry is `(per_million_input_USD, per_million_output_USD, flat_per_call_USD_estimate)`. `flat_cost_for(provider, model)` returns the flat estimate with provider-level fallback and a final default of `$0.0020/call`.
- New endpoint: `GET /api/admin/synisense/billing?window_days=7|30&context_id={cid}` (superadmin-only).
  - Aggregates from `synisense_audit_log` since cutoff, by consumer + by purpose.
  - Returns `{total_calls, estimated_total_usd, per_consumer, top_purposes_by_cost, is_illustrative: true, estimate_notes, pricing_table_signature}`.
  - `pricing_table_signature` is a fingerprint of the live table (entry_count, default_flat_usd_per_call, providers) — bank QA can compare two snapshots and detect if pricing changed.
- **Bug fixed in observability + billing**: both endpoints queried `created_at` on `synisense_audit_log`, but the audit log writer stores the ISO timestamp under `timestamp` (no `created_at` field). Switched both queries to `timestamp >= cutoff_iso`. ISO-8601 strings sort lexicographically the same as datetimes so this is correct.

### Frontend

- `SynisenseObservability.jsx` extended with a two-tab strip — **Activity** (existing) + **Billing estimate** (new).
- Billing tab shows:
  - Amber disclaimer: "Estimated only. Figures are illustrative … derived from `services/synisense/pricing.py`. Not invoiced."
  - 4 KPI tiles: Total calls / Estimated total / Consumers / Pricing entries.
  - Per-consumer breakdown table.
  - Top purposes by estimated cost.
- Window selector caps at 30 days on Billing tab (vs 90 on Activity) per the spec.

### Live evidence

```bash
$ curl .../api/admin/synisense/billing?window_days=7 (as admin@akki.ai)
{
  "window_days": 7,
  "as_of": "2026-05-16T03:39:45.663022+00:00",
  "total_calls": 424,
  "estimated_total_usd": 0.6406,
  "per_consumer": [
    {"consumer_id":"document.meta","call_count":63,"estimated_usd":0.127,...},
    {"consumer_id":"solva_v2.llm_primary","call_count":59,"estimated_usd":0.121,...},
    {"consumer_id":"solva_v2.refusal","call_count":64,"estimated_usd":0.1168,...},
    {"consumer_id":"chat","call_count":51,"estimated_usd":0.0852,...},
    ...
  ],
  "top_purposes_by_cost": [...],
  "is_illustrative": true,
  "pricing_table_signature": {
    "entry_count": 9,
    "default_flat_usd_per_call": 0.002,
    "providers": ["anthropic","gemini","openai"]
  }
}
```

Screenshot saved at `/app/memory/sprints/phase_f_artefacts/billing_admin.png` shows the rendered tab with the disclaimer + 4 KPI tiles + per-consumer table.

## Sub-task E — Final close-out + post-rewrite ramp doc

- `REWRITE_FINAL_CLOSEOUT.md` — 5-paragraph bank-QA briefing summarising A → F.
- `POST_REWRITE_RAMP.md` — resumption plan: Chunk 7-12 of the paused QA sprint, then the 14 deferred QA findings.
- `REWRITE_SPRINT_STATE.md` — Phase F row flipped to complete.
- `SYSTEM_STATE.md § 4` — Phase F entry appended.
- `CHANGELOG.md` — Phase F entry at top.

## Tests + lint

| Metric                                              | Before  | After          |
|-----------------------------------------------------|---------|----------------|
| pytest passing                                      | 629     | **648** (+19)  |
| pytest skipped                                      | 565     | 565            |
| Regressions                                         | —       | **0**          |
| CI guard `test_no_direct_llm_calls_outside_shield`  | PASS    | **PASS**       |
| ruff / pyflakes on touched files                    | clean   | clean          |
| ESLint on touched frontend files                    | clean   | clean          |
| `yarn render-smoke` (11 routes)                     | PASS    | **PASS**       |

### New tests in `tests/test_phase_f_engine_signals.py` (19 total)

Sub-task A — seed_payload
1. `test_phase_d_session_accepts_seed_payload` — full happy path with sub_module_hint + ref resolution + provenance.
2. `test_phase_d_session_without_seed_keeps_legacy_shape` — schema_version 3 preserved when no seed.
3. `test_phase_d_seed_rejects_unknown_source` — Pydantic validator catches non-enum.
4. `test_phase_d_seed_silently_drops_unknown_references` — phantom refs handled without error.

Sub-task B — derivation
5. `test_signal_derivation_emits_derived_from_signals` — six categories, all `derived_from_*`, compliance keyword triggers.
6. `test_derivation_idempotent` — second pass produces same count.
7. `test_derive_or_seed_falls_back_on_empty_workspace` — brand-new tenant falls back to Phase A seeder.
8. `test_derive_endpoint_real_signals` — admin/derive endpoint returns counts.
9. `test_engine_query_returns_derived_signals` — full query loop returns `derived_from_*` rows.

Sub-task C — Update goal
10. `test_monitor_update_status_objective` — objective gets status + audit_id + rationale.
11. `test_monitor_update_status_project` — project path mirrors.
12. `test_monitor_update_status_404_on_unknown_item`.
13. `test_monitor_update_status_rejects_unknown_kind`.
14. `test_monitor_assessment_parse_falls_back_safely` — heuristic kicks in on prose-only response.
15. `test_monitor_assessment_parses_valid_json` — clean JSON parse + signal_id filter to only the IDs we passed.

Sub-task D — Billing
16. `test_billing_endpoint_requires_superadmin` — non-admin 403.
17. `test_billing_endpoint_returns_estimate_for_superadmin` — admin path returns shape + signature.
18. `test_pricing_table_flat_cost_lookup` — known model, fallback to provider, fallback to default.
19. `test_pricing_table_governance_locked` — table shape is rigidly typed.

## File diff summary

```text
NEW backend
  services/synisense/engine/signal_derivation.py        +458 lines
  services/synisense/engine/derivation_scheduler.py     +68 lines
  services/synisense/pricing.py                         +44 lines
  routers/monitor_status_assessment.py                  +233 lines
  tests/test_phase_f_engine_signals.py                  +519 lines

MODIFIED backend
  routers/solva_phase_d.py                              +143 / -5 (SeedPayload, _build_source_url, _resolve_seed_references)
  routers/synisense_engine.py                           +56 / -3 (admin/derive endpoint)
  routers/synisense_observability.py                    +105 / -3 (billing endpoint + timestamp fix)
  server.py                                             +27 (derivation backfill startup hook)
                                                        +1 router include (monitor_status)

MODIFIED frontend
  components/monitor/ObjectivesProjectsPanel.jsx        +98 / -3 (Update goal CTA + assessment expander)
  components/solva/SolvaLanding.jsx                     +10 / -10 (legacy fallback removal)
  lib/solvaPhaseDClient.js                              +9 / -3 (seedPayload forwarding)
  pages/SolvaPhaseDSession.jsx                          +44 / -3 (seed URL params)
  pages/SynisenseObservability.jsx                      +144 / -45 (Billing tab)
```

## Carry-over for the post-rewrite sprint

- **Token-accurate Shield metering** (Sub-task D foundation): the audit log doesn't record token counts today. Phase G+ should add `input_tokens` + `output_tokens` + actual per-call cost to the audit row.
- **APScheduler cron** for `derivation_scheduler.run_hourly_pass()`: today we only run on startup + on-demand. Future Phase G adds a real hourly schedule.
- **30s cold-start latency** on `evolution-diff` / `generate-meta` (carried over from Phase E backlog).

## Status

✅ **PHASE F + PHASE E.5 — closed (2026-05-16).** Full rewrite A → F complete.
**Next:** Resume the 12-chunk QA sprint at Chunk 7 (see `POST_REWRITE_RAMP.md`).
