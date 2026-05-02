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
