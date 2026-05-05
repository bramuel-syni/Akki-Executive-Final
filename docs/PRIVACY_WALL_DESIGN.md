# AKKI — Privacy Wall Design (Phase 2a)

> **Status.** DESIGN ONLY — no code in this round. Author: main agent,
> 2026-05-05. Reviewers: human product owner.
>
> **Why we are doing design first.** Akki Pulse (Phase 3) is the
> headline NED feature: cross-board pattern detection. It cannot ship
> without a Privacy Wall, because the moment a NED on three boards
> sees a Pulse summary, the only thing standing between board A's
> minutes and board B's NED-context view is whatever guard we choose
> in this document. Get the wall wrong and Pulse has to be re-done.
> One round of design is cheaper than that.

---

## 1 · Threat model

The unit of trust is a **context** (a board seat or an executive role).
The Privacy Wall protects content from crossing context boundaries
when the user, server-side aggregator, or LLM operates over more than
one context at a time. We are **NOT** trying to prevent the user
herself from seeing her own data — she has membership on every
context she's logged into. We are preventing **content from one
context entering an output that is computed for, attributed to, or
delivered as another context.**

Concrete bad outcomes we are preventing:

| # | Bad outcome | Why it matters |
|---|---|---|
| T1 | NED context A's minutes leak into context B's Pulse summary card. | Direct confidentiality breach. Board A's chairman would consider this material. |
| T2 | LLM is shown content from context A while answering a Pulse-scoped question for context B. | Subtle — the user might never see the leaked content but it influences the model's reply. Reversible only with prompt isolation. |
| T3 | Metadata that is itself sensitive (deal codenames in document titles, attendee names on agendas) leaks via a "metadata-only" projection. | Most likely failure mode. "Project Falcon" in a document title is content, not metadata, but a naïve allowlist would ship it. |
| T4 | Audit row from context A is readable in context B's audit feed. | The audit log already aggregates by user; the question is whether per-row content fields (`details.payload`) leak. |
| T5 | Pulse aggregator caches the full source-text it computed over and re-serves it on a metadata endpoint. | Engineering footgun — the metadata endpoint shipped on top of a cache that wasn't sanitised. |
| T6 | LLM output for context B contains a verbatim phrase from context A because both were in the prompt. | Hardest to detect post-hoc. Mitigation is prompt-time isolation, not output-time scrub. |
| T7 | A future "global search" or "command palette" surfaces context A hits to a user querying inside context B. | Out of scope today (no such surface ships). Wall design must not preclude it. |
| T8 | Synisense `synisense_runs.input_sha256` collisions reveal that the same text appears in two contexts. | Vanishingly low risk. Documented for honesty, no mitigation required. |

**Not in scope for this wall:** cross-tenant isolation between
different `account_id`s. Today an account is a single user. Multi-
tenant guardrails are a separate layer and Phase 16 (reportee
accounts) is the time to revisit.

---

## 2 · Definitions — metadata vs content

### Definition

* **Metadata-class** = field is safe to materialise in a
  cross-context surface (Pulse, multi-board summary, governance
  digest). It carries enough information to *count, classify, route,
  and timestamp* an event but not enough to *reproduce the event's
  substance*.
* **Content-class** = field is the substance. Never crosses contexts.
  Always carries a single `context_id` it belongs to and is only
  served when the caller is reading inside that exact context.

> **Litmus test for ambiguous fields.** Read the field in isolation,
> with no other field. If the field alone could embarrass the board,
> name a person, or reveal a deal — it is **content**. If it could not
> — it is metadata.

### Field-level taxonomy (current schema)

#### `documents`
| Field | Class | Notes |
|---|---|---|
| `id`, `context_id`, `created_at`, `updated_at` | metadata | Always safe. |
| `kind`, `doc_kind`, `doc_type` | metadata | Categorical only. |
| `status`, `extraction_status` | metadata | |
| `trust_score`, `trust_tier` | metadata | Numeric / banded. |
| `sensitivity_band` | metadata | One of {public, internal, confidential, restricted}. |
| `page_count`, `synisense_version`, `journal_commentary_synisense_version` | metadata | |
| `name`, `title`, `original_filename` | **content** | Most-likely M&A target / deal codename leak. (T3) |
| `extracted_text`, `body_redacted` | **content** | Self-evident. |
| `paragraphs[]`, `paragraph_anchors[]` | **content** | |
| `akki_summary`, `journal_commentary`, `journal_commentary_redacted` | **content** | LLM output **derived from** content is content. (T2) |
| `sender`, `uploader_email`, `attendees[]` | **content** | Names. (T3) |
| `tags[]` | **TBD-1** | A tag like `"Q3 audit"` is metadata. A tag like `"Project Falcon"` is content. We don't enforce tag classification today. |

#### `boardpacks`
| Field | Class | Notes |
|---|---|---|
| `id`, `context_id`, `cycle_id`, `cycle_label`, `created_at`, `updated_at`, `status` | metadata | |
| `commentary_synisense_version` | metadata | |
| `document_ids[]` | metadata | Plural-of-id; carrying it cross-context is fine because the resolution from id → content is always context-scoped. |
| `title`, `subject` | **content** | (T3) |
| `commentary`, `commentary_redacted` | **content** | LLM output. |

#### `signals`
| Field | Class | Notes |
|---|---|---|
| `id`, `context_id`, `created_at`, `severity`, `status` | metadata | |
| `signal_kind`, `topic_class` | **TBD-2** | Today free-form strings ("Capital pressure", "Regulatory drift"). The Pulse design relies on these being categorical metadata. We need product to commit to a 4–8 entity-class enum. |
| `headline`, `body`, `evidence_excerpt`, `recommended_actions[]` | **content** | |

#### `chat_audit_log`
| Field | Class | Notes |
|---|---|---|
| `id`, `at`, `account_id`, `chat_id`, `action`, `prev_hash`, `row_hash`, `ip_sha`, `ua_sha` | metadata | |
| `payload` | **content** | Carries the chat message body in some actions. Already gated per `chat_id` + `account_id` so does not currently leak. Must NOT be rolled into any cross-chat aggregator. |

#### `synisense_runs`
| Field | Class | Notes |
|---|---|---|
| `id`, `surface`, `context_id`, `account_id`, `ts`, `mode`, `layers_used`, `spans_count`, `latency_ms`, `input_sha256` | metadata | (T8 — sha is fingerprint, not content.) |
| `spans[]` (the actual entity types found) | **TBD-3** | The entity types (`PERSON`, `EMAIL`, `IBAN`) are categorical and metadata. The character offsets within the original text are content (they reveal where in the doc the PII is). Today we ship offsets in `spans[]`. The admin perf ring drops them, the per-context query (none today) would. |

#### `solva_v2_sessions`
| Field | Class | Notes |
|---|---|---|
| `id`, `account_id`, `context_id`, `submodule`, `state`, `status`, `created_at`, `completed_at` | metadata | |
| `intent_text`, `framing[]`, `clarity_q*[]`, `depth_q*[]`, `artefact[]`, `reflection[]` | **content** | Whole-session content. |

#### `audit_log`
| Field | Class | Notes |
|---|---|---|
| `id`, `created_at`, `account_id`, `context_id`, `action`, `target_type`, `target_id` | metadata | |
| `details` | **TBD-4** | Free-form blob. Some action types put titles or names in `details`. Needs an action-type-by-action-type sweep before we ship a cross-context audit feed. The current `/api/me/governance/audit` endpoint serves it raw — see leakage audit. |

#### `cycle_configs`, `cycles`, `reports`, `submissions`
Mostly content (board-pack composition, reportee submissions). Per-context only by definition. Out of scope for cross-context surfaces.

---

## 3 · Approaches considered

### (a) Field-projection guard — recommended starting point

> One central helper, `project_for_pulse(collection: str, doc: dict) → dict`,
> living next to `core.py`. Every cross-context query funnels through
> it. The helper carries an immutable allowlist per collection (the
> "metadata" rows in §2), logs at WARN every time a non-allowlisted
> field would have shipped, and has a `STRICT_PRIVACY_WALL=true` env
> flag that turns the warn into a 500 in CI / staging.

* **How it works.** Aggregator → `find()` over `documents` /
  `signals` / `boardpacks` → results pass through
  `project_for_pulse(...)` → caller never sees content fields.
  Optional matching `redact_for_pulse_text(text, surface)` for any
  free-form string field that survives (e.g. `topic_class`).
* **Surface area to change.** ~ 1 new helper module
  (`backend/services/privacy_wall.py`), ~ 4 cross-context call sites
  in `routers/shares.py` and `routers/governance.py`, ~ 1 new env
  flag, ~ 6 unit tests. No schema changes. No write-path changes.
  No frontend changes.
* **Runtime cost.** O(n) field walk per shipped doc, dominated by
  Mongo network. Negligible.
* **Blast radius if wrong.** A new endpoint that forgets to call the
  helper leaks. Caught by (a) the runtime warn log, (b) the
  recommended periodic regression test (§5).
* **This fails when…** A new field is added to a content collection
  and no one updates the allowlist. The default-deny posture means
  the field doesn't ship rather than ships-as-content (good failure
  mode).

### (b) Two-collection split

> For each content collection, derive a
> `<collection>_metadata` projection collection at write time.
> Pulse / cross-context aggregators read **only** from the `_metadata`
> collections. They have no read permission on the source content
> collections (enforced by a wrapper around `db.<name>` access).

* **How it works.** Document write path now does:
  `db.documents.insert_one(full_doc)` →
  `db.documents_metadata.insert_one(project_for_pulse("documents", full_doc))`.
  Pulse aggregator reads `db.documents_metadata` only. Source
  collections become read-restricted to the per-context surfaces.
* **Surface area to change.** Every write path on every content
  collection. Two-phase commit considerations on retry. New
  background job to backfill the existing 154 documents + 88
  boardpacks + ~3,500 signals into their metadata twins. Frontend
  unchanged but every cross-context test must be re-baselined.
* **Runtime cost.** Doubled write volume on hot collections. Also
  doubled storage on the metadata copy.
* **Blast radius if wrong.** Drift between source and metadata
  collections — silent, hard to detect. Catastrophic if
  `documents_metadata` is allowed to be edited independently of
  `documents`. Mitigated by making it strictly write-only-from-server.
* **This fails when…** A migration backfills source rows and
  forgets to backfill the metadata twin. Pulse silently shows
  "no signals" instead of the real count.

### (c) Tag-on-field policy

> Annotate each schema field with a `metadata|content|tbd`
> classification at the model level (Pydantic `Field(...,
> json_schema_extra={"privacy_class": "content"})`). The serialiser
> reads the annotation and refuses to ship `content` fields to a
> cross-context route. Pulse routes pass `cross_context=True` to the
> serialiser; per-context routes pass `cross_context=False`.

* **How it works.** Every Pydantic model that touches a content
  collection grows a class annotation. A custom `BaseModel.dict_for_pulse()`
  walks the model and emits only metadata-class fields. Routes opt
  in to cross-context rendering by calling `.dict_for_pulse()` instead
  of `.dict()` / `model_dump()`.
* **Surface area to change.** Schema-wide annotation pass — every
  model, every field. Requires that every cross-context surface
  goes through Pydantic models (today many use raw `dict`s from
  Motor). Frontend unchanged.
* **Runtime cost.** Negligible per-call. Higher cognitive cost during
  schema authoring.
* **Blast radius if wrong.** A new field added without an annotation
  defaults to `tbd`; the serialiser must default to deny for `tbd`
  to be safe, which means new fields are invisible to Pulse until
  someone classifies them. Acceptable failure mode, but easy to miss
  in PR review.
* **This fails when…** A route ships a raw dict (not via a Pydantic
  model) on a cross-context surface. The annotation is on the model,
  but the route never instantiated one. Today's codebase has lots
  of these — the home-stream route serialises Motor dicts directly.

---

## 4 · Recommendation

**Pick (a) — field-projection guard. Defer (b) until Phase 4 if
volume warrants it.**

(a) gives us 80% of the safety for ~5% of the engineering cost. The
two collections that drive Pulse — `signals` and `documents` — are
already queried in three predictable places (`shares.py:home/stream`,
the still-to-be-built `routers/pulse.py`, and `governance.py`). One
central helper plus a `STRICT_PRIVACY_WALL=true` posture in CI gives
us hard failure on the day we forget. A regression-test that
crawls every router for cross-context queries (§5) keeps the
honesty cheap.

What we lose by not picking (b): if a future component reads
`db.documents` directly (bypassing both `find()` and the helper),
nothing in the code stops it from leaking. We accept that risk on the
basis that (1) every cross-context surface today goes through one of
three identifiable code paths, (2) the helper raises in CI on
unauthorised field shipping, and (3) when Pulse volume forces us to
denormalise for performance, we'll have learned the actual access
patterns and can do the split with eyes open.

What we lose by not picking (c): per-field discipline at the schema
layer. Acceptable because today most cross-context routes ship raw
Motor dicts; (c) only helps once those are migrated to Pydantic
models, which is not a Phase-2 goal.

---

## 5 · Failure modes & detection

| Failure | Detected by |
|---|---|
| New field shipped on `documents` without an allowlist update. | **Unit test** (`backend/tests/test_privacy_wall_field_drift.py`) — walks every collection's distinct field set and asserts every field is either in the allowlist or in an explicit `KNOWN_CONTENT_FIELDS` set. CI fails on drift. |
| Engineer adds a new cross-context endpoint that forgets to call `project_for_pulse`. | **Static AST sweep** (`backend/tests/test_privacy_wall_route_coverage.py`) — parses every router file, finds `db.<collection>.find(...)` and `aggregate(...)` calls inside route handlers, asserts each one either (a) constrains by a single `context_id` from the URL path (per-context surface), or (b) is wrapped in a `with privacy_wall(...)` context. CI fails on uncovered call sites. |
| The helper is called but a content field still ships because the allowlist is wrong. | **Runtime canary**: in non-prod environments, a reflection on the OUT dict at the helper boundary asserts `set(out.keys()) ⊆ allowlist`. Off in prod (cost). |
| Cross-context audit-log row contains a content field in `details.payload`. | **Periodic audit job** (`backend/scripts/audit_privacy_wall.py`, scheduled weekly via the existing APScheduler) — samples 100 random `audit_log` rows where `context_id` is multi-tenant-aggregable, JSON-walks `details`, fails hard if any string > 256 chars (heuristic for "this is a body excerpt") survives the projection. Posts the result to `db.privacy_wall_audit`. |
| LLM output for context B contains content from context A (T6). | **Prompt-time isolation, not detection.** The Pulse-side LLM prompt MUST be assembled from per-context outputs that were already projected through (a). The Pulse aggregator never asks the LLM "summarise across boards X, Y, Z" with the source content of all three in the prompt; it always summarises each board's metadata-only signals separately, then composes the multi-board card from the per-context summaries. Documented as a contract in `services/privacy_wall.py:assemble_pulse_prompt(...)` with a reference test that fails if the function is bypassed. |
| Synisense run row leaks character offsets across contexts. | TBD-3 sign-off. If product opts to keep offsets in `spans[]`, we add `surface ∈ {pulse, public_read}` to the projection allowlist as **drop-offsets**. If product opts to drop offsets entirely, `synisense_runs.spans[].offset` becomes content-class everywhere. |
| Hash-chain audit (`chat_audit_log`) is queried cross-account in a future debug tool. | Out of scope for Phase 2 (no such tool today). Documented so the next agent doesn't accidentally build one. |

---

## 6 · Phasing

| Step | What | Estimate | Status |
|---|---|---|---|
| **2a** | This document. Design + leakage audit. Decision on (a)/(b)/(c). Sign-off on the four TBDs in §2. | 0.5 day | **IN PROGRESS** |
| **2b** | Implementation foundation. (1) `backend/services/privacy_wall.py` with `project_for_pulse`, `redact_for_pulse_text`, `assemble_pulse_prompt`, `STRICT_PRIVACY_WALL` env flag. (2) Refactor `routers/shares.py:/me/home/stream` and `routers/governance.py:/me/governance/audit` to call the helper. (3) Both regression tests from §5. (4) Wall flag-OFF by default in dev, **flag-ON in test_credentials.md tester runs.** No Pulse build yet — Pulse stays a placeholder. | 1 day | NOT STARTED |
| **2c** | Build Pulse on top of the wall. New router `backend/routers/pulse.py` with metadata-only endpoints. Replace `pages/PulsePlaceholder.jsx` with the real surface. Pulse cron registered. Per-context flag-ON gate. End-to-end test. | 1 day | NOT STARTED (blocked on 2b) |

---
Last updated: 2026-05-05 by main agent.
