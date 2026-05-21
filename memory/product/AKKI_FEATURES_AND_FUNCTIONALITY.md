# AKKI — Features & Functionality

**Document type**: Holistic product reference
**Audience**: PO + executive hybrid
**Status**: Live (2026-05-21) — reflects rewrite Phases A through F.1 + the QA-2026-05-16 sprint (Chunks 7 through 19)
**Reading time**: 25-30 minutes

This document is the single canonical reference for what AKKI does, how the surfaces relate to one another, and what state each is in. It is written for an executive or PO who wants the whole picture in one sitting without having to cross-reference five sprint logs. Depth-on-demand pointers throughout the document indicate where to read further if you want engineering detail; if you don't, you don't have to.

---

## 1 — What AKKI is

AKKI is a governance-grade AI workspace for non-executive directors and C-suite executives. It augments the boardroom with private, audited AI for cycle preparation, signal monitoring, document analysis, structured executive thinking (Solva), and the production of board-ready artefacts (Work Studio) — all without sending raw consumer content to third-party model providers.

Three properties distinguish AKKI from generic AI workspaces:

1. **Privacy by structural design**, not promise. Every outbound LLM call goes through the Synisense Shield gateway, which de-identifies content before it leaves the platform and re-identifies the response on the way back. The provider sees only opaque tokens.
2. **Tenant scoping enforced as a contract**, not as a convention. The `tenant_id == account_id` rule is the spine of every API surface; cross-tenant reads are rejected at the FastAPI dependency layer.
3. **Trust receipts** issued for every governance-relevant action so the audit trail is reviewable end-to-end by external bank-quality reviewers.

---

## 2 — Personas served

### Non-Executive Director (NED)
- Reads board packs cold; needs to walk into the room ready.
- Uses **Cycle Manager** to assemble pre-read packs from documents the executive team uploaded.
- Uses **Akki Chat** in `chat_evidence_list` mode for sharp questions grounded in those documents.
- Uses **Pulse** to scan late-breaking signals (regulatory, sectoral, macro) the executive team hasn't yet briefed on.
- Uses **Solva** (read-only banner) to follow the executive's reasoning on contested calls.
- **Cannot** edit strategic goals or modify executive-owned objects — RBAC hides every CTA they shouldn't see (Chunk 11 QA-048).

### Executive (CFO, CEO, COO, CRO)
- Owns the firm's strategic direction; uses AKKI to keep that direction sharp.
- Uses **Monitor / Strategic Goals** to author and update objectives, projects, and the goals they cascade from.
- Uses **Solva** as a working tool — 5-layer pipeline for situation framing, candidate generation, deconstruction, synthesis, and one-line decision capture.
- Uses **Work Studio** to author briefings, decks, reports, and minutes.
- Sees full audit context for everything they emit.

### Superadmin
- Operates the platform. Has read access to `/api/admin/synisense/*` observability + billing + cron-health surfaces.
- Has the **Trust Panel** for per-tenant Shield audit traces.
- Has the legacy soft-archive and orphan-count surfaces for migration housekeeping.
- Cannot read consumer content directly — even superadmin reads are de-identified through the audit log.

---

## 3 — Architectural foundation

Pre-rewrite, AKKI grew organically. The rewrite (Phases A through F.1, 2026-04 → 2026-05) collapsed the surface area to four canonical building blocks, each documented in `/app/memory/SYSTEM_STATE.md § 1`.

### Phase A — Synisense Shield gateway

Every outbound LLM call leaves through `services/synisense/shield/client.py::invoke()`. The Shield does three things in order:
1. **De-identifies** input via a 3-layer pipeline (regex → Presidio → spaCy NER fallback) producing `[ENT_PERSON_001]` style tokens.
2. **Routes** the de-identified content through `llm_router.invoke()` (the only file inside `shield/` permitted to import provider SDKs).
3. **Re-identifies** the response using the token map, writes an `synisense_audit_log` row + a Trust Receipt, and returns the rehydrated text plus an `audit_id` for forensic traceability.

Two architectural CI guards defend this contract:
- `test_no_direct_llm_calls_outside_shield` (Phase B) — bans direct LLM calls outside `shield/`.
- `test_no_direct_llm_calls_inside_shield_except_router` (Chunk 18.5) — bans direct LLM calls inside `shield/` except in `llm_router.py` + `streaming.py`.

### Phase B — Solva 5-layer pipeline

Solva is a structured executive-thinking workflow. The five layers, persisted to `solva_phase_d_sessions`, are:
- **L0** — frame audit (clarify the situation + decision).
- **L1** — candidate generation (multiple framings produced in parallel).
- **L2** — deconstruction (each candidate's assumptions made explicit).
- **L3** — synthesis (one composed framing the user can read in 60 seconds).
- **L4** — decision capture (one-line commitment).

Status badges are **computed** server-side per request (ACTIVE / PAUSED / COMPLETE / REFUSED) rather than stored, so a single timestamp update flips the status without a Mongo migration. Documented in `routers/solva_v2.py:92`.

### Phase C/D — Document grounding

Documents uploaded via Document Journal travel through a sharded ingest pipeline; their chunks become the grounding corpus for `chat_evidence_list`, `cycle_manager.briefing.aggregate`, and `document_journal.signals.generate`. Phase D adds:
- Real-time search across document journals.
- Rich-text prose blocks rendered via the in-house `lib/proseBlocks.js` (no new libraries — built specifically to avoid pulling in a third-party markdown parser).
- A 60vh panel sizing convention for document detail surfaces.

### Phase E/F — Audit & observability

Every Shield invocation writes:
- A `synisense_audit_log` row with `tenant_id`, `consumer_id`, `purpose`, `de_id_summary`, `dilution_score`, `exposure_reduction_score`, `tokens_in`, `tokens_out`, `metering_method`, and (Chunk 18+) `actual_cost_usd`.
- A `synisense_trust_receipts` row with hashes of the inbound and outbound payloads.
- An entry to `synisense_runs` if the call originated from a scheduled job.

Observability surfaces at `/api/admin/synisense/observability` (per-consumer aggregates) and `/api/admin/synisense/billing` (illustrative USD roll-up) read these collections. Chunk 19 adds `/api/admin/synisense/cron-health` reading `scheduler_runs`.

For depth-on-demand: `SYSTEM_STATE.md § 1` lists every collection and its purpose.

---

## 4 — Feature catalogue by surface

### 4.1 — Portfolio

| Property | Value |
|----------|-------|
| What it does | Landing surface post-login. Lists every context the user has access to (own contexts + memberships in others). Cards show role, last-active, headline numbers. |
| User value | Single entry point. NEDs see their committees; executives see their org plus any boards they sit on. |
| Key APIs | `GET /api/me/contexts` (with `role` field), `GET /api/contexts/{cid}` |
| Key components | `Portfolio.jsx`, `ContextCard.jsx` |
| Status | **SHIPPED** — Chunk 15 fixed the post-login redirect race (QA-001) |

### 4.2 — Akki Chat

| Property | Value |
|----------|-------|
| What it does | Conversational interface grounded in the active context's documents. Two-pass classification (`chat_classifier` → `chat_four_check`) catches thin-input requests + composes refusals when grounding is insufficient. |
| User value | Sharp questions answered with verbatim evidence. Privacy Audit Panel exposes which spans were redacted before the LLM saw them. |
| Key APIs | `POST /api/contexts/{cid}/chat/messages`, `POST /api/contexts/{cid}/chat/sessions` |
| Key components | `ChatPanel.jsx`, `PrivacyAuditPanel.jsx`, `EvidenceFooter.jsx` |
| Status | **SHIPPED** — Phase B.2 added classifier + thin-input refusal; per-message Synisense linking via `message_id` (Phase J.2) |

### 4.3 — Document Journal

| Property | Value |
|----------|-------|
| What it does | Uploads, parses, chunks documents per context. Surfaces a per-document signals view + evolution-diff between document versions + auto-generated meta (display name, summary). |
| User value | A document becomes a queryable corpus the moment it lands. The journal panel shows what changed between two uploads + auto-promotes commentary highlights. |
| Key APIs | `POST /api/contexts/{cid}/document-journal/upload`, `POST /api/contexts/{cid}/documents/{doc_id}/generate-meta`, `POST /api/contexts/{cid}/documents/{doc_id}/evolution-diff` |
| Key components | `DocumentJournalPanel.jsx`, `DocumentDetailDrawer.jsx`, `EvolutionDiffPanel.jsx` |
| Status | **SHIPPED** — Chunk 18.5 fixed the 30s cold-start on `generate-meta` and `evolution-diff` (now ~5-8s cold, ~98ms warm) |

### 4.4 — Cycle Manager

| Property | Value |
|----------|-------|
| What it does | Schedules board / committee cycles, aggregates briefings from journal artefacts, generates the pre-read pack. |
| User value | What used to be a 4-hour pack assembly job is now a 20-minute review. |
| Key APIs | `GET /api/contexts/{cid}/cycles`, `POST /api/contexts/{cid}/cycles/{cycle_id}/briefing/aggregate`, `POST /api/contexts/{cid}/cycles/{cycle_id}/agenda/generate` |
| Key components | `CycleManager.jsx`, `BriefingComposer.jsx`, `AgendaTimeline.jsx` |
| Status | **SHIPPED** — Chunk 15 fixed the "Back to Cycle Manager" label (QA-016) |

### 4.5 — Pulse

| Property | Value |
|----------|-------|
| What it does | Late-breaking signals feed (regulatory, sector, macro, deal). Each card carries shielded commentary from `pulse.signal.commentary`. |
| User value | NEDs walk into the room knowing what's moved since the last briefing. |
| Key APIs | `GET /api/contexts/{cid}/pulse/signals`, `POST /api/contexts/{cid}/pulse/signals/{id}/commentary` |
| Key components | `PulsePanel.jsx`, `PulseSignalCard.jsx` |
| Status | **SHIPPED** — Chunk 10 added the surface batch (QA-022-026, capital-adequacy seeding); Chunk 15 removed the Bell icon (QA-009) |

### 4.6 — Monitor

| Property | Value |
|----------|-------|
| What it does | Status assessment view per objective / project / strategic goal. Performance scores computed via `monitor.objective.status_assessment` etc. |
| User value | One glance answers "are we on track?". RBAC-gated CTAs ensure NEDs can read but not edit. |
| Key APIs | `GET /api/contexts/{cid}/strategic-goals`, `POST /api/contexts/{cid}/strategic-goals/{goal_id}/update` |
| Key components | `Monitor.jsx`, `StrategicGoalsPanel.jsx`, `GoalDetailDrawer.jsx` |
| Status | **SHIPPED** — Chunks 11 + 12 hardened the role gate + drawer; Chunk 17 removed orphaned EditGoalRow + seeded admin/non-owner accounts |

### 4.7 — Strategic Goals

| Property | Value |
|----------|-------|
| What it does | Author + cascade goals from corporate plan down to objective + project + KR. Drawer surfaces the auto-assessment, including the Akki update timestamp + the legacy "Edit this goal" → "Update Goal" CTA rename. |
| User value | Single source of truth for direction-of-travel. |
| Key APIs | `GET /api/contexts/{cid}/strategic-goals`, `POST /api/contexts/{cid}/strategic-goals` |
| Key components | `StrategicGoalsPanel.jsx`, `GoalDetailDrawer.jsx`, `GoalCard.jsx` |
| Status | **SHIPPED** — QA-049 closed in Chunk 12; the empty-state fixture (Pass H) seeded retroactively in Chunk 17 |

### 4.8 — Solva

| Property | Value |
|----------|-------|
| What it does | 5-layer structured-thinking pipeline (frame → candidates → deconstruct → synthesis → decision). Read-only NED banner; full edit for executives. |
| User value | Decisions that would otherwise live in someone's head become legible, auditable, and shareable. |
| Key APIs | `GET /api/solva/v2/sessions`, `POST /api/contexts/{cid}/solva/v2/sessions`, `POST /api/contexts/{cid}/solva/v2/sessions/{sid}/framing`, `POST /api/contexts/{cid}/solva/v2/sessions/{sid}/synthesis` |
| Key components | `Solva.jsx`, `SolvaSessionPanel.jsx`, `LayerComposer.jsx`, `lib/proseBlocks.js` (in-house renderer) |
| Status | **SHIPPED** — Chunks 13 + 14 added SV-04 through SV-08 (sessions list + dynamic status badges + real-time search + rich-text + smart-cast 422 friendliness); Chunk 17 fixed the SV-07 overflow CSS |

### 4.9 — Work Studio

| Property | Value |
|----------|-------|
| What it does | Authoring surface for board-ready artefacts (briefings, decks, reports, prepare-briefs, minutes). Documents progress through `lifecycle_state` (draft → in_review → committed) and acquire `confidence_band` from the underlying Shield runs. |
| User value | Drafts walk a governance gauntlet before they hit the boardroom — every revision is tracked, every confidence band is visible. |
| Key APIs | `GET /api/contexts/{cid}/work-studio/documents`, `POST /api/contexts/{cid}/work-studio/documents` |
| Key components | `WorkStudio.jsx`, `DocumentCardsSection.jsx` (Chunk 16), `AttachDocumentModal.jsx` |
| Status | **SHIPPED** — Chunk 16 shipped Document Cards (QA-037 status badge · QA-038 lock overlay · QA-039 confidence chip · QA-040 download button); Chunk 17 fix-pass cleared the `useRef` regression on AttachDocumentModal |

---

## 5 — Privacy & trust surfaces

### 5.1 — Shield gateway request flow

```
   USER REQUEST                       LLM PROVIDER
       │                                   ▲
       ▼                                   │
   ┌───────────────────────────────────────┴────┐
   │  services.synisense.shield.client.invoke() │
   │                                            │
   │  1. de-identify (regex + Presidio + spaCy) │
   │     content + tenant_id → tokenised text   │
   │                                            │
   │  2. llm_router.invoke_with_metering()      │
   │     → litellm.acompletion → provider       │
   │     captures usage.prompt_tokens etc.      │
   │                                            │
   │  3. re-identify (reverse token_map)        │
   │                                            │
   │  4. write_audit  (synisense_audit_log)     │
   │     write_trust_receipt                    │
   │     return (response, audit_id)            │
   └────────────────────────────────────────────┘
```

Every step is replayable post-hoc by joining `synisense_audit_log` + `synisense_trust_receipts` + (for streaming) the `synisense_runs` collection. Bank-QA reviewers walk this exact flow when they audit a customer engagement.

### 5.2 — Trust Receipts

A trust receipt is a small JSON document signed with an HMAC chain. Each receipt carries:
- `audit_id` linking it to the Shield audit row
- `request_hash` + `response_hash` (SHA-256 over the canonical-JSON payloads)
- `de_id_summary` (count by entity type — never the values themselves)
- `outcome` (success / governance_refused / service_unavailable)
- `tenant_id` + `consumer_id` + `purpose` for forensic grouping
- Signature: HMAC-SHA256 with the platform's master secret

The receipt can be verified independently with the public verification key — Chunk 19 ships a sample verifier (`/app/memory/sprints/phase_e_addendum_artefacts/verify_trust_receipt.py`).

### 5.3 — Chat Privacy Audit Panel

Per-message panel surfaces:
- Identifiers masked (count by category, no values)
- Dilution score (how much the LLM "saw" relative to the unmasked text)
- Exposure reduction score (1.0 = perfect; tracks how aggressively the de-id pipeline scrubbed)

NEDs and executives both see this panel; it's an active reassurance the platform is doing what it claims.

### 5.4 — Trust Panel (superadmin only)

Operator-only view of cross-tenant audit aggregates. Reads only metadata; redacted content is never surfaced even to superadmins. Used for tenant-level Shield SLO monitoring and for bank-QA prep.

---

## 6 — Infrastructure & performance posture

### 6.1 — Token-accurate Shield metering (Chunk 18)

`synisense_audit_log` rows now carry `tokens_in`, `tokens_out`, `metering_method` (`"exact"` | `"estimated"`), and `actual_cost_usd`. Exact tokens come from the provider SDK's `usage.prompt_tokens` + `completion_tokens` payload (captured via `litellm.acompletion` inside `llm_router.invoke_with_metering`). Estimated tokens come from a deterministic char/4 approximation when usage isn't surfaced (mock mode + early-return paths).

Per-model rate table (`services/synisense/shield/audit_log.py::_RATE_TABLE`):

| Provider | Model | Input ($/M) | Output ($/M) |
|----------|-------|-------------|--------------|
| anthropic | claude-sonnet-4-5-20250929 | 3.00 | 15.00 |
| openai | gpt-4o | 2.50 | 10.00 |
| openai | gpt-5.2 | 5.00 | 20.00 |
| gemini | gemini-2.5-flash | 0.10 | 0.40 |
| gemini | gemini-3-flash | 0.15 | 0.60 |

Unknown pairs fall back to the Claude Sonnet 4.5 rate so the audit row always carries a numeric cost.

### 6.2 — APScheduler hourly cron (Chunk 18)

`services/synisense/engine/derivation_scheduler.run_hourly_pass()` now runs at the top of every UTC hour via an `AsyncIOScheduler(CronTrigger(minute=0))` job armed at boot. Multi-replica safety is enforced by a Mongo distributed lock (`scheduler_locks`, TTL-reaped on `expires_at`); the winning replica writes a heartbeat row to `scheduler_runs` per executed run. Liveness query:

```js
db.scheduler_runs.find({job_id: "synisense_engine_hourly", status: "ok"})
  .sort({started_at: -1}).limit(1)
```

Operators read this via the new `GET /api/admin/synisense/cron-health` endpoint (Chunk 19, C19-005).

### 6.3 — Cold-start budget (Chunk 18.5)

The `call_llm` end-to-end path (used by `evolution-diff` + `generate-meta` + every Shield-routed surface) was running 14 seconds cold and 8-28 seconds warm. Diagnostic surfaced a redundant pre-pass that bypassed `SYNISENSE_LLM_MODE=mock` and warmed a separate provider-SDK pool. Fix: routed the pre-pass's classifier through `llm_router.invoke()` + lifted `litellm` imports to module-level.

| Path | Pre-fix p50 / p95 | Post-fix p50 / p95 | Speedup |
|------|-------------------|--------------------|---------|
| `shield_invoke` cold | 651-741ms | 605ms | 1.1× |
| `shield_invoke` warm | 5ms | 5ms | unchanged |
| `call_llm` cold | **14,000ms** | **891ms** | **15.7×** |
| `call_llm` warm p50 | **11,962ms** | **98ms** | **122.3×** |
| `call_llm` warm p95 | **23,298ms** | **99ms** | **235×** |

Production projection on `evolution-diff` + `generate-meta`: ~30s cold → ~5-8s cold (inside the dispatch's 8-second acceptance target).

### 6.4 — Architectural defences

Two CI guards now defend the Shield gateway exclusivity invariant:
- `test_no_direct_llm_calls_outside_shield` — bans direct provider SDK imports outside `services/synisense/shield/`.
- `test_no_direct_llm_calls_inside_shield_except_router` — within `shield/`, only `llm_router.py` + `streaming.py` may import provider SDKs.

Both guards run at test collection and fail loudly with per-violation line numbers.

---

## 7 — QA sprint outcomes

The QA-2026-05-16 sprint ran from Chunk 7 (mid-May 2026) to Chunk 19 (end-of-sprint, 2026-05-21). It cleared the entire 16-May backlog except items routed to AWAITING_PO. Chunk-by-chunk scorecard:

| Chunk | Scope | Result | Pytest Δ |
|-------|-------|--------|----------|
| 9.5 | SV-01 — "How Solva reasons" link target | ✅ | +X |
| 10 | Pulse surface batch (QA-022 through QA-026) | ✅ | +X |
| 11 | QA-048 RBAC NED hides Update Goal CTA | ✅ | +X |
| 12 | QA-049 "Edit this goal" → "Update Goal" + drawer timestamps | ✅ | +X |
| 13 | SV-04 Solva sessions list + dynamic status badges | ✅ | +X |
| 14 | SV-05/06/07/08 search · rich text · panel sizing · 422 friendliness | ✅ | +X |
| 14 fix-pass | Pass I Phase D session seed | ✅ | — |
| 15 | 16-May P2 batch 1 (QA-001 / 009 / 010 / 016) | ✅ | +X |
| 16 | Work Studio Document Cards (QA-037/038/039/040) | ✅ | +X |
| 17 | 16-May P3 + cleanup (QA-014 + EditGoalRow + SV-07 CSS + admin/non-owner seed) | ✅ | +X |
| 17 fix-pass | `useRef` import regression on AttachDocumentModal | ✅ | — |
| 18 | Track 4 cron (item 3) + token metering (item 2) | ✅ | +9 (80 → 89) |
| 18.5 | Track 4 cold-start (item 1) + orphan probe (item 4) + shield-internal CI guard | ✅ | +8 (89 → 97) |
| 19 | Bank-QA evidence pack polish + cron-health + holistic features doc | ✅ | +4 (97 → 101) |

Total IDs closed in the sprint: **≥ 25**. Zero PARTIAL chunks after retroactive fix-passes. Zero pre-existing regressions reintroduced.

### Lessons committed to memory for future agents

1. **Smoke probes that filter by role/context must prefer specific role first, not first-with-seed** — seed data ordering shifts based on insertion timing, and a probe that lands on the wrong role flips an RBAC-correct assertion into a false negative. Documented in `CHUNK_18_STATE.md`.
2. **Shield-internal files can leak as easily as external callers — guard scope must include `shield/` itself.** Chunk 18.5 surfaced the failure mode; the new CI guard formalises it.
3. **Compute, don't store, for status fields that derive from timestamps** — Solva ACTIVE/PAUSED/COMPLETE/REFUSED badges are derived per request from layer timestamps, avoiding a Mongo migration when the rules tighten. Documented in `routers/solva_v2.py:92`.
4. **Cold-start latency hunting starts with mock-mode timing, not network timing** — mock-mode isolates our-code cost from provider-network variance. Chunk 18.5 caught a redundant pre-pass that would have been invisible in live-mode profiling.

---

## 8 — Open items requiring PO input

| ID | Surface | Question for PO |
|----|---------|------------------|
| QA-050 | Solva dual-role label | When a single user holds both Executive AND NED roles in different contexts, which label drives the Solva session header? |
| QA-002 | Document Journal "All documents" button | Which scope does "All documents" target — all-in-context, all-in-cycle, or all-cross-tenant (visible only to that user)? |
| C17-003 | Cross-context Solva sessions aggregate | Should the home-page Solva count aggregate across ALL user contexts, or stay per-context (WS-R16 privacy boundary)? |
| Track 4 #5 | Around-the-Goals sub_module | Currently `coming_soon: true` — what's the sub-feature catalog beneath the surface name? |
| CLR-A | TBD per PO | (Reserved — surfaced if PO returns with a new item before sprint close) |
| CLR-B | TBD per PO | (Reserved — same) |

Each item is documented in `/app/memory/sprints/AWAITING_PO/`. No item is blocking the next sprint's start; they're all "right answer once PO confirms semantics" rather than "engineering uncertainty".

---

## 9 — Deferred & known-gap items

- **Phase 5 quarantine pass** — 5 files in `QUARANTINE_TRIAGE_PLAN.md` flagged for REWRITE (large + UNCLEAR). Separate sprint.
- **HA scheduler upgrade** — current Mongo-distributed-lock is single-replica-safe; multi-replica needs leader election. Only matters if the deployment topology changes; documented in `server.py` comments + the chat-retention cron.
- **spaCy en_core_web_trf upgrade** — currently using `en_core_web_sm` fallback (F1 ≈ 0.86 vs ~0.91 for trf). Skipped because trf brings a 2GB torch dependency. Would gain ~5% NER recall if the install footprint trade is acceptable.
- **Solva v2 → Phase D session migration** — source collection (`solva_sessions`) is empty on live preview; dormant migration script ready in `scripts/migrate_solva_legacy_to_phase_d.py` for the day a future seed re-introduces rows.

---

## 10 — Glossary

| Term | Meaning |
|------|---------|
| **AKKI** | The platform name. |
| **Shield** | `services/synisense/shield/` — the gateway that owns every outbound LLM call. |
| **Solva** | The 5-layer structured-thinking pipeline (frame → candidates → deconstruct → synthesis → decision). Implemented as `solva_v2` runtime + `solva_phase_d_sessions` persistence. |
| **NER** | Named Entity Recognition — the spaCy + Presidio layer of the de-id pipeline. |
| **Phase D** | The current canonical Solva persistence model (vs the legacy `solva_sessions` collection). |
| **`context_id`** | A workspace identifier — a board, committee, project, or personal context. Documents and sessions are scoped per `context_id`. |
| **`tenant_id`** | The account/firm identifier; equal to `account_id`. The cross-tenant boundary. |
| **Trust receipt** | A signed HMAC-chained JSON document issued for every governance-relevant Shield call. Replayable + independently verifiable. |
| **`SYNISENSE_LLM_MODE=mock`** | Env flag that short-circuits live LLM calls into deterministic echo responses. Used in tests + dev. Honored by `llm_router.invoke()`. Pre-Chunk-18.5 the legacy fallback bypassed this and paid 5-13s per call. |
| **APScheduler** | The Python job-scheduling library. AKKI uses it for the engine hourly cron + a few other reaper jobs. |
| **Cold-start budget** | The latency a request pays the first time per process. Quantified in § 6.3 of this document. |
| **Dilution score** | `1 - (tokens_revealed_to_llm / total_tokens)`. Higher = more was hidden from the LLM. |
| **Exposure reduction score** | A per-call privacy KPI in `[0, 1]`. 1.0 = nothing identifiable was revealed. |
| **Trust Panel** | Superadmin-only operator view of cross-tenant Shield audit aggregates. |
| **`render-smoke.js`** | The 18-step Playwright E2E smoke test. Runs against `REACT_APP_BACKEND_URL`. |
| **CI guard** | A pytest-collection-time invariant check. Two live: `test_no_direct_llm_calls_outside_shield` + `test_no_direct_llm_calls_inside_shield_except_router`. |

---

**Document last revised**: 2026-05-21 (Chunk 19 close).
**Authoritative anchor**: `/app/memory/SYSTEM_STATE.md § 1` (architecture) and `§ 4` (per-patch closeout log).
**Source of truth for status**: `/app/memory/sprints/POST_REWRITE_RAMP.md` (rewrite tracks) and the relevant `CHUNK_*_STATE.md` per chunk.
