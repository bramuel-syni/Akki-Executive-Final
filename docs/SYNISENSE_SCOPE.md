# Synisense — in-house de-identification scope

_Scope document for Phase 11. Read-only review of the code that exists today and a concrete plan for what "live" means. This document is the input to Phase 11; no code in this phase changes Synisense behaviour._

---

## 1. What exists today

Synisense is, at this date, a **regex-only shielding layer in `llm_service.py`** plus a thin status + dry-run API in `routers/synisense.py`. "Synisense" is branding; the implementation is local and deterministic.

### 1.1 Patterns

All nine active regex patterns live in `/app/backend/llm_service.py`, lines 55–71:

| Category | Pattern (identifier variable in code) | What it catches |
|---|---|---|
| `email` | `_EMAIL_RE` | Standard RFC-ish emails |
| `url` | `_URL_RE` | `http(s)://…` |
| `phone` | `_PHONE_RE` | +254 / +44 / +1 / +27 or bare 8–16 digit sequences |
| `natid` | `_KE_NATID_RE` | Kenya national ID (7–8 digits, only when prefixed by ID/Nat.ID/etc. to avoid collapsing loan amounts) |
| `iban` | `_IBAN_RE` | Two-letter country + two-digit checksum + 4–30 alphanum |
| `acct` | `_BANK_ACCT_RE` | "A/c", "Account no.", "Acct #" followed by 8–16 digits |
| `cc` | `_CC_RE` | 13–16-digit card-shaped sequences |
| `swift` | `_SWIFT_RE` | Standard 8- or 11-char SWIFT/BIC |
| `person` | `_PERSON_RE` | Title (Mr/Mrs/Dr/…) + TitleCase run of 1–3 words |

Also referenced as regex inside the composer sensitivity classifier (`studio_sensitivity.py`): the nine `SENSITIVITY_RULES` patterns (M&A, conduct, litigation, MNPI, etc.) are _classification_ rules, not shielding — they do not mask anything, they only score. They are mentioned here for completeness so Phase 11 does not accidentally re-scope them.

### 1.2 What's actively masked, what isn't

- **Masked today:** emails, URLs, phone numbers, Kenya national IDs, IBANs, bank accounts, card numbers, SWIFT/BICs, honorific-prefixed personal names.
- **Not masked today (gap):**
  - Personal names without an honorific (plain "Jane Okonkwo" or "James Harrington" pass through untouched).
  - Company names / organisations (every listed entity's name goes into the LLM in clear).
  - Deal codenames (e.g. "Project Atlas", "Project Harbour") — these are the largest single leakage risk on briefings.
  - Financial figures tied to unannounced results ("£42m revenue", "EBITDA down 12 pp") are not masked, only _classified_ by the sensitivity scorer.
  - Geographies, customer names, product codenames, M&A targets.
  - Dates of future material events.
  - Employee IDs, HR case numbers, regulator reference numbers.

### 1.3 Call sites

Three surfaces invoke the shielding layer:

| File | Line | What it shields |
|---|---|---|
| `/app/backend/routers/chat.py` | 288, 376 | Every chat turn before the LLM call; also each historical message replayed in the context window. Reply is `rehydrate()`d post-LLM. |
| `/app/backend/routers/synisense.py` | 118 | The `/api/synisense/dryrun` endpoint — a preview surface for operators and the enterprise-sales team. |
| (implicit) `llm_service.py` bespoke calls | — | The `_build_messages`-style helpers in `briefings_service.py`, `decks.py`, `cycle.py`, `solve_engine.py`, `lens.py`, `simulate.py`, `signals_ask.py`, `strategic_goals.py`, `influence_map.py` do **NOT** invoke `shield_payload` — they pass raw context to the LLM. **This is the single biggest gap**: Chat is shielded, Studio is not. |

### 1.4 What the status endpoint tells the user

`GET /api/synisense/status` returns a static payload describing the 9 categories, a `shielded_by: "regex"` marker, and no live-service URL. The Governance panel reads this payload and renders the "SHIELDED · REGEX" chip. The chip is therefore truthful: regex-only, local.

---

## 2. What "live de-identification" should mean

**Recommended posture: hybrid pipeline (c).** Regex fast-path for the deterministic categories we already catch, Presidio-backed NER for plain personal names and organisations, LLM fallback (Claude Sonnet via the Emergent universal key) for deal codenames / ambiguous project names / context-dependent identifiers that neither regex nor a general-purpose NER can catch. Defended below.

### 2.1 Why not regex-only (status quo)

Regex misses every category flagged in §1.2. The biggest practical loss is deal codenames — "Project Atlas" is the most sensitive single string on a typical M&A briefing, and regex has no way to know "Atlas" is a codename versus a star. Regex cannot generalise.

### 2.2 Why not pure NER (option a)

A pre-trained spaCy model catches plain personal names and mainstream organisation names cheaply and offline. It is brittle on:
- Non-Western names (the corpus is genuinely global — Kenyan boards, UK/SA listed cos, MENA state enterprises).
- Project / deal codenames (no NER model is trained to flag "Project Atlas" as sensitive).
- Company-internal acronyms (e.g. "TPC", "CSO review").

Presidio adds configurable anonymisers on top of the spaCy/transformer backbone and covers 50+ languages; worth using as the NER layer, but it is not enough alone.

### 2.3 Why not pure LLM (option b)

An LLM call can catch everything, including codenames, with good prompting. The problems are cost (per-page LLM call on every upload at ingest time + on every shielded chat turn), latency (hundreds of milliseconds added to every request), and non-determinism (the same page redacted twice can drift). For the Governance audit ledger to remain meaningful, the shielding output must be stable enough that a re-run produces the same redacted text bit-for-bit. LLM-alone fails that test.

### 2.4 Why hybrid (option c) is the right default

Three tiers, run in order, each cheap enough that the expensive one rarely fires:

1. **Tier 1 — regex (present).** Sub-millisecond per page. Covers emails, URLs, phones, card-shaped numbers, IBANs, SWIFT, account numbers, national IDs, honorific-prefixed names.
2. **Tier 2 — Presidio + custom recognisers.** ~15–40 ms per page on CPU. Catches plain personal names, organisations, geographies, dates, and a configurable list of custom recognisers seeded from a per-context dictionary (board seats, exec team, key customers, known project names already disclosed).
3. **Tier 3 — LLM fallback (Claude Sonnet, 2-3k token ceiling).** Only invoked when Tier 2 emits low-confidence spans, or when the document carries a "candidate codename" heuristic (capitalised word following "Project", "Plan", "Operation", a colour, a mythological reference, or a two-word TitleCase phrase that is not in any Wikipedia-scale gazetteer). ~600–1200 ms per page when fired, usually 0 ms because the gating heuristic passes most pages straight through.

All three tiers feed a **single merged span list** which is applied to the original text via a deterministic reducer (longest span wins, then leftmost). The redacted output is stable across runs given the same inputs.

---

## 3. Data contract for a "Synisense run"

### 3.1 Input

```jsonc
{
  "text":          "string (or array of strings — per-paragraph for long docs)",
  "context_id":    "string — used to load the per-context custom recogniser dictionary",
  "surface":       "chat | briefing | deck | report | ingest",
  "mode":          "preview | persist",   // preview returns without writing
  "tier_limit":    3,                      // 1 = regex only; 2 = regex+NER; 3 = full
  "max_spans":     250                     // safety cap
}
```

### 3.2 Output

```jsonc
{
  "redacted_text":  "string with [PERSON_1] / [ORG_4] / [DEAL_2] markers",
  "shield_map":     { "[PERSON_1]": "Jane Okonkwo", "[DEAL_2]": "Project Atlas", ... },
  "spans": [
    {
      "category":   "person | org | deal | email | phone | natid | ...",
      "tier":       1 | 2 | 3,
      "score":      0.0-1.0,                         // confidence
      "start":      int, "end": int,                 // char offsets on original text
      "token":      "[PERSON_1]",                    // stable-per-run replacement
      "source":     "regex | presidio | llm"        // provenance
    }
  ],
  "stats": {
    "span_count":    int,
    "by_category":   { "person": 3, "org": 2, ... },
    "by_tier":       { "1": 5, "2": 7, "3": 1 },
    "latency_ms":    { "tier1": 1, "tier2": 22, "tier3": 0, "total": 23 },
    "text_length":   int
  },
  "shielded_by":     "hybrid",                      // the chip in the top bar
  "run_id":          "uuid",                        // audit ledger anchor
  "generated_at":    "iso8601"
}
```

### 3.3 Persistence

- **`db.synisense_runs`** — one row per persisted run. Fields: `{run_id, context_id, surface, text_sha256, redacted_text_sha256, span_count, by_category, by_tier, latency_ms, tier_limit, shielded_by, created_at, account_id}`. TTL 90 days on chat-surface runs; retained indefinitely on Studio/ingest surfaces so the audit pack can reproduce any redacted output.
- **`db.synisense_original_payloads`** — hash-addressed original texts, encrypted at rest with the same AES256 envelope we use for S3 uploads. Separate collection + stricter ACL. Only operator + the originating account can read.
- **Never persisted:** the `shield_map` (the key that rehydrates tokens back to originals). This only exists in-memory for the duration of the request, exactly as today. This is how the chat surface already works and is the right posture.

### 3.4 UI surfacing

- **Default per surface:**
  - Chat → automatic, silent, shielded-on-send. Chip in top bar confirms "SHIELDED · HYBRID". No per-message toggle; override via the existing per-message setting in `db.chat_messages.shielding_override` stays.
  - Studio (briefing / deck / report composer) → **preview-before-save on the first save, then automatic**. The first save surfaces a drawer listing every span and its category with the option to accept, reject per-span, or accept-all. Subsequent saves re-run silently.
  - Ingest (document upload) → automatic at ingest time. Adds a second body field on `db.documents` (`extracted_text_redacted`). The LLM retrieval code always reads the redacted field.
- **No per-block toggle.** Per-block toggles in the composer were considered and rejected: the granularity is wrong (the user wants to redact a name everywhere, not here but not there), and a per-block toggle hides footguns behind the UI.
- **Trust panel.** The Governance panel gains a "Synisense" section with: last run time per context, span count by category over the last 30 days, link to the dry-run surface, and a button to run an on-demand re-redaction sweep against an artefact.

---

## 4. Latency and cost budget per page

Budget for a 2,000-character "page" (board-pack page-equivalent):

| Tier | Work | p50 latency | p95 latency | $/page |
|---|---|---|---|---|
| 1 | Regex over 9 categories | <1 ms | 2 ms | 0 |
| 2 | Presidio + custom recognisers | 15 ms | 40 ms | 0 (CPU) |
| 3 | LLM fallback on flagged pages only (~5–10 % of pages) | 0 ms (not fired) | 1,200 ms | ≈ $0.0008 when fired (Claude Sonnet @ 2k tokens in/out, weighted for the 5-10 % firing rate = **≈ $0.00005–$0.00008 per page amortised**) |
| **total** | | **≈ 20 ms** p50 | **≈ 60 ms** p95 | **< $0.0001** amortised |

Budget discipline: any page crossing 200 ms is logged as a slow span in `synisense_runs.latency_ms`; any per-context month crossing $1 of LLM fallback cost flags on the admin LLM-spend panel. Neither should happen in normal operation.

---

## 5. Engineering lift

All estimates in engineer-days, solo, with a working dev env.

| Work | Days | Notes |
|---|---|---|
| Pipeline service (`services/synisense_service.py`) — regex layer reuse, Presidio setup, LLM fallback call, span merge, deterministic reducer | 2.5 | Presidio is pip-installable; spaCy transformer model ships as a package. |
| Storage of original-vs-redacted pairs + envelope encryption key management | 1.0 | Same AES256 envelope wrapper as S3; key via env var. |
| Migration of ingest path to call Synisense post-extract | 0.5 | Single hook in `documents_service.extract_text` flow. |
| Studio composer "first-save preview drawer" + span-accept UI | 1.5 | New `components/studio/SynisenseDrawer.jsx`. |
| Chat hot path tier-1+2 wiring (tier 3 gated by a feature flag for the first week) | 0.5 | Already have tier 1. |
| Governance panel Synisense section | 0.5 | Additive read from `db.synisense_runs`. |
| Audit ledger integration | 0.25 | Two new actions: `synisense.run`, `synisense.override`. |
| Tests (unit per tier, integration for pipeline, golden-file regression for deterministic output) | 2.0 | Golden files are the cheap way to lock in determinism. |
| Admin / cost dashboards | 0.5 | Additive to `/admin/llm-spend`. |
| Runbook + operator docs | 0.25 | |
| **Total** | **≈ 9.5 days** | |

Phasing recommendation: ship tier 1 + tier 2 to chat + ingest (≈ 4 days) behind a flag, then Studio preview drawer (≈ 2 days), then tier 3 behind a secondary flag once the first two are stable (≈ 2 days), then audit/panel polish (≈ 1.5 days). Cleanly interruptible.

---

_End of scope. Phase 11 takes this document as its input; the lift above is the shape of that phase._

---

## Actually shipped — Phase 12.1 (2026-05-03)

Phase 12.1 closed the **engine** deliverables. Surface wiring, UI, and marketing copy are Phase 12.2 / 12.3.

**Delivered in 12.1:**
- `backend/services/synisense/` package: `regex_recognisers.py`, `presidio_engine.py` (with custom `DEAL_CODENAME`, `EXECUTIVE_TITLE`, `CHAIR_NAME`, `FINANCIAL_FIGURE_LARGE` recognisers), `llm_fallback.py` (Gemini 2.5 Flash, concurrency-capped, timeout-bounded), `encryption.py` (AES-GCM envelope, per-record DEK, `key_version` rotation), `pool.py` (sizing + health surface), `pipeline.py` (public entry, deterministic replacement tokens, perf ring buffer, audit writer).
- `db.synisense_runs` (context/surface/time indexes) + `db.synisense_shield_maps` (TTL index on `expires_at`, per-surface defaults 1h/24h, hard max 7d).
- `routers/synisense.py` rewritten: real `GET /api/synisense/status` (pool/model/key_version/perf snapshot), real `POST /api/synisense/dryrun` executing the pipeline without persisting.
- New `GET /api/admin/synisense/perf` — superadmin-gated, p50/p95/p99 over a 10k-entry ring buffer.
- Boot guard in `server.py on_startup`: refuses start in production (`AKKI_ENV=production` or `BILLING_ENABLED=true`) without `SYNISENSE_MASTER_KEY`; dev fallback warns every 60 seconds.
- Full test pack: **22 tests pass** (7 regex + 5 encryption + 6 integration + 4 security). Phase 11 regression pack (studio blocks, decks validation, chat context) still green.
- Perf benchmark: **p50 7ms, p95 10ms, p99 10ms, mean 7.5ms** over 50 governance samples — well inside the 20ms/60ms scope-doc target. Cold start (first call) is ~2s (spaCy model load); subsequent calls warm.
- `requirements.txt` + `.env` + `PRODUCTION_ENV.md` § 11 updated with 9 new env vars.

**Intentional drift from original scope:**
- Process pool is scaffolding only (sizing + health surface are live; actual pool wiring behind `SYNISENSE_USE_POOL=true`, disabled by default). Presidio runs in-process today because forking from the uvicorn dev-reloader process creates zombie children. Production container (non-reloading) is fork-safe; pool wiring lands in 12.2 alongside surface integration.
- Merge policy tightened from the brief's "score-based" to "regex wins on any overlap". In testing, Presidio was greedily labelling regex-detectable patterns plus surrounding context (e.g. `IBAN GB33BUKB...` → ORGANIZATION). Giving regex priority keeps the label taxonomy accurate on the hard cases the legacy shield ladder already knew how to catch.
- Spans below the low-confidence threshold that get dropped by the LLM fallback (`llm_verdict = 'not_pii'`) are removed from the output entirely, not kept with a "not PII" tag. Cleaner output; honest about what's redacted.

**Not in 12.1 (confirmed carry to 12.2):**
- Chat pre-LLM redaction hook.
- Ingest path redaction on `documents.extracted_text` and each `paragraphs[i].text`.
- Studio block-save hook + `PreviewDrawer.jsx` state machine.
- Solva synthesis hook.
- Public-read `synisense_version` assertion.
- TrustPanel rewrite (`mock_scaffolding_note` still in place).
- Chat inline "N spans redacted" icon.

**Not in 12.1 (confirmed carry to 12.3):**
- Marketing copy honesty pass on `/plans` and `/security`.

---

## Actually shipped — Phase 12.2 (2026-05-03)

Phase 12.2 closed the **surface wiring + UI** deliverables. Marketing copy is Phase 12.3.

**Delivered in 12.2:**
- **ITEM A — Chat pre-LLM hook.** `routers/chat.py:send_message` now runs `synisense.run(..., surface="chat", mode="redact")` BEFORE retrieval/grounding/LLM. The legacy regex `shield_payload` runs as defence-in-depth on already-redacted text. `synisense_stats` mirrored on both user and assistant message records (counts only — no spans, no shield map). `synisense.chat.ran` audit row per turn. Frontend `Chat.jsx` renders a `Content screened · N` chip beneath assistant messages whose preceding user turn carried redactions, with hover tooltip showing the entity-type breakdown — never original text or replacement tokens.
- **ITEM B — Ingest hook + paragraph anchor stability.** `routers/documents.py:_materialise_paragraphs` runs Synisense per-paragraph in `shield_reversible` mode (24h TTL) AFTER `compute_paragraphs` has stamped anchor IDs from the original text. Anchor IDs stay stable through redaction (asserted by the new `test_paragraph_anchors_stable_through_redaction` unit test). New `GET /api/contexts/{cid}/documents/{doc_id}/paragraphs/{pid}/original` endpoint reverses the per-paragraph shield map server-side for context members; never returns the shield_map itself; 410s after TTL. Per-request audit via `synisense.unshield`.
- **ITEM C — Studio block-save hook + PreviewDrawer.** `routers/studio_blocks.py:_persist_and_project` runs Synisense on the concatenated block text on every save, persists `body_redacted` + `synisense` (spans, stats, histogram, version) on the artefact, and returns `synisense_first_accept_pending` / `synisense_drawer_reopen` flags. New `POST /api/studio/{kind}/{aid}/synisense-accept` records the user's first accept and snapshots the entity histogram so future saves can detect *new* sensitive content. New `frontend/src/components/synisense/PreviewDrawer.jsx` opens once on first save, again only when new entity types appear. Original blocks remain the editable source of truth; redacted projection feeds public-read and validator surfaces.
- **ITEM D — Solva synthesis hook.** `routers/solva_engine.py:post_turn` runs Synisense on synthesis output BEFORE the Phase 11 validator runs. Validation now sees only redacted content (consistent with the "LLM never sees original" promise). `synisense_run_recorded` flag persisted on the synthesis record. _(Phase 13.1 renamed `solve_engine.py` to `solva_engine.py`; product name is "Solva". Mongo collections retain the `solve_` prefix for stability.)_
- **ITEM E — Public-read assertion.** `routers/studio.py:get_public_studio_read` now refuses to serve any artefact without `synisense_version >= 1`, returning HTTP 410 with a clear "Pending review" body. Denylist extended with six shield-map keys (`dek_wrapped`, `dek_nonce`, `encrypted_original`, `envelope`, `shield_map`, `original_payload`) — verified by 14 negative-case asserts in the new `test_phase12_2_surfaces` pack.
- **ITEM F — TrustPanel rewrite.** `routers/governance.py` builds a real `synisense` block (status, last_run_at, spans_redacted_7d/30d, entity_histogram_7d, llm_fallback usage vs cap, key_version, model, insecure_fallback flag) aggregated from `db.synisense_runs` over the user's contexts. Frontend `TrustPanel.jsx` renders that block with stat cards, entity chips, and an honest empty state. The literal `mock_scaffolding_note` constant is gone (`grep` confirms zero live references in `.py`/`.js`/`.jsx`). Phase 12.1 isinstance dispatch on `classification` shape preserved.
- **ITEM G — Boot warmup.** `server.py` startup hook calls `presidio_engine.get_analyzer()` + a tiny dummy `analyze` in a thread; logs `synisense warmup ready event=ready surface=boot elapsed_ms=N`. First-request latency is now ~7ms (matching warm p50) instead of the ~2s cold load.

**Intentional drift from original scope:**
- **Process pool stays disabled.** The dev backend runs uvicorn with `--reload`, which is hostile to `multiprocessing.Pool` fork (zombie children). Per the brief's "honestly revert and note why" clause, `SYNISENSE_USE_POOL=false` in this environment. The status endpoint surfaces `mode: in_process` honestly. With Phase 12.1 perf already at p50=7ms / p95=10ms (3-6x under the 20ms/60ms scope target), there is no operational pressure to enable the pool until Azure prod (`--no-reload`) where forking is safe. The pool scaffolding (sizing, env vars, status surface) remains intact for that flip.
- **Studio block storage model.** The brief said "subsequent saves persist the redacted version". Implementation persists BOTH: the original blocks (editable source of truth) and a parallel `body_redacted` + `synisense` projection for downstream surfaces. This is functionally identical from the user's perspective (editor shows original, public surfaces show redacted) but cleaner than mutating block content destructively.
- **Synisense run from Studio uses `mode="redact"`, not `shield_reversible`.** Studio artefacts don't need to be reversed inside the editor (the original is right there in `blocks`); only ingested documents need reversibility for the Reading Viewer. Skipping the shield_map on Studio saves halves the per-save persistence cost.

**Carried to 12.3:**
- Marketing copy honesty pass on `/plans` and `/security` pages — both currently say "Synisense de-identification — coming soon" or similar; should now read "Synisense de-identification — live".
- "Actually shipped" final diff in `SYNISENSE_SCOPE.md`.


---

## Actually shipped — Phase 12.3 (2026-05-04)

Phase 12.3 was the small honesty pass: a single entity-priority fine-tune,
the marketing copy rewrite, and the consolidated record. No new surfaces,
no new env vars, no new routes.

**Delivered in 12.3:**
- **ITEM A — DEAL_CODENAME entity priority.** "Project Falcon" / "Project Atlas"
  consistently lost the Presidio internal merge to stock spaCy NER's
  PERSON / ORGANIZATION labels (redaction worked, the histogram label was
  wrong). Promoted DEAL_CODENAME from a Presidio `PatternRecognizer` to a
  regex pre-pass entry in `services/synisense/regex_recognisers.py`. The
  pipeline's `_merge_spans()` already gives regex precedence over Presidio,
  so the codename now wins deterministically, no matter what spaCy says.
  Removed the duplicate Presidio `PatternRecognizer` from
  `services/synisense/presidio_engine.py` to keep the taxonomy
  single-sourced. Two new regression tests
  (`test_deal_codename_wins_over_person`,
  `test_deal_codename_wins_over_organization`) lock the behaviour. Existing
  22 synisense tests untouched and still green (now 24 total).
- **ITEM B — Marketing copy honesty.** `pages/marketing/Security.jsx`
  Promise #02 ("Identities are scrubbed") rewritten to describe what
  actually ships: regex fast-path → Presidio NER on `en_core_web_sm` with
  custom recognisers → Gemini 2.5 Flash low-confidence fallback (capped,
  timeout-bounded). Names AES-GCM envelope encryption, per-record DEKs,
  key version pinning. Six live surfaces explicitly enumerated. Public
  HTTP 410 refusal documented as a verifiable artefact. `pages/marketing/Plans.jsx`
  unchanged — it carries no feature bullets and its "pricing will be
  published when general availability opens" stance is the right one
  pre-Phase-16. FT-voice grep on the diff showed zero banned words.
- **ITEM C — `SYNISENSE_SCOPE.md` consolidation (this section).** 12.1 and
  12.2 sections preserved verbatim as historical record. New 12.3 entry
  + the consolidated table below. No previous content rewritten.
- **ITEM D — Production readiness paragraph appended to
  `RUNBOOKS/PRODUCTION_ENV.md`** describing the `SYNISENSE_USE_POOL` flip
  procedure post-cutover.

**Consolidated 12.1 + 12.2 + 12.3 — what landed across the three phases**

| Layer | Phase | What shipped |
| --- | --- | --- |
| AES-GCM envelope encryption, per-record DEK, key version | 12.1 | `services/synisense/encryption.py` |
| Three-tier pipeline (regex → Presidio → LLM fallback) | 12.1 | `services/synisense/pipeline.py` |
| Presidio NER + custom recognisers (EXECUTIVE_TITLE, CHAIR_NAME, FIN_FIGURE_LARGE) | 12.1 | `services/synisense/presidio_engine.py` |
| 9-pattern regex fast-path | 12.1 | `services/synisense/regex_recognisers.py` |
| Capped, concurrency-bounded Gemini 2.5 Flash fallback | 12.1 | `services/synisense/llm_fallback.py` |
| TTL-indexed shield maps (1h public_read, 24h default, 7d hard max) | 12.1 | `services/synisense/pipeline.py`, `server.py` indexes |
| Admin endpoints (`/synisense/status`, `/dryrun`, `/admin/synisense/perf`) | 12.1 | `routers/synisense.py` |
| In-memory ring-buffer perf snapshot (p50/p95/p99) | 12.1 | `services/synisense/pipeline.py` |
| Boot guard (refuse prod start without master key) | 12.1 | `server.py` startup |
| spaCy warmup thread on boot | 12.2 | `server.py` startup hook |
| Chat pre-LLM redact + per-message `synisense_stats` | 12.2 | `routers/chat.py` |
| Document ingest per-paragraph `shield_reversible` (24h TTL) | 12.2 | `routers/documents.py` |
| Reversible-paragraph endpoint (per-context-member, audited) | 12.2 | `routers/documents.py` |
| Studio block-save hook + `synisense_first_accept` flow | 12.2 | `routers/studio_blocks.py` |
| Studio first-accept persistence (`synisense_version >= 1`) | 12.2 | `routers/studio_blocks.py` |
| `PreviewDrawer.jsx` (first-save preview, drawer-reopen on new entity types) | 12.2 | `frontend/src/components/synisense/PreviewDrawer.jsx` |
| Solva synthesis pre-validator redact | 12.2 | `routers/solva_engine.py` |
| Public-read 410-gate (asserts `synisense_version >= 1` BEFORE projection) | 12.2 closeout | `routers/studio.py` |
| Public-read content sourced from `body_redacted` (no original-body leak) | 12.2 closeout | `routers/studio.py` |
| Denylist extended with shield-map cryptographic keys | 12.2 | `routers/studio.py` |
| Governance synisense rollup (`$or` on context_id ∪ account_id) | 12.2 closeout | `routers/governance.py` |
| TrustPanel rewrite + `ValidatedBadge` honesty invariant | 12.2 | `frontend/src/components/governance/TrustPanel.jsx` |
| Chat inline "N spans redacted" chip | 12.2 | `frontend/src/pages/Chat.jsx` |
| Chat `synisense_stats.version` engine-version threading | 12.2 closeout | `routers/chat.py` |
| Backfill migration for legacy artefacts (`body_redacted`, `synisense_version=1`) | 12.2 closeout | `backend/scripts/backfill_synisense_version.py` |
| DEAL_CODENAME promoted to regex pre-pass (deterministic over spaCy NER) | 12.3 | `services/synisense/regex_recognisers.py` (+ removed from `presidio_engine.py`) |
| Marketing copy describes the engine truthfully | 12.3 | `frontend/src/pages/marketing/Security.jsx` |
| Production readiness note for `SYNISENSE_USE_POOL` | 12.3 | `docs/RUNBOOKS/PRODUCTION_ENV.md` |
| Chat surface unified onto Synisense (legacy regex shield in `llm_service.py` retired) | A | `routers/chat.py`, `llm_service.py` |
| `services/synisense/adapter.py` — legacy `(text, shield_map)` shape adapter so all LLM-touching call sites flow through `pipeline.dryrun` | A | `backend/services/synisense/adapter.py` |
| `llm_service.shield_payload` / `shielding_report` / `rehydrate` deleted; `call_llm` now consumes the Synisense adapter | A | `backend/llm_service.py` |
| `module → surface` mapper added so the perf ring buffer groups results per product surface | A | `backend/llm_service.py:_surface_for_module` |

**Honest deviations carried forward (expected, stay):**
- **Process pool stays disabled in dev** (`SYNISENSE_USE_POOL=false`). uvicorn
  `--reload` is hostile to `multiprocessing.Pool` fork (zombie children). With
  perf comfortably under budget (p50 ≈ 7ms, p95 ≈ 10ms vs. the 20ms / 60ms
  scope target), there is no operational pressure to flip the pool until
  the production cutover to a non-reloading runtime. Procedure is documented
  in `RUNBOOKS/PRODUCTION_ENV.md`. Status endpoint surfaces `mode: in_process`
  honestly today.

**Remaining open items:** _none._ The Synisense Shield (Phases 12.1 → 12.3,
extended through Phase A unification) is closed. Every LLM call across
chat, briefings, decks, reports, signals, simulate, lens, prepare,
plays, walkin, blog, learn, document ingestion, studio sensitivity,
strategic_goals, and the Solva v2 strict adapter routes its prompt
through the three-layer pipeline (regex → Presidio → LLM fallback).
Future work belongs in Phase B+ per `docs/ROADMAP.md`.
