# Synisense Rewrite — FINAL CLOSEOUT (A → F)

**Period:** 2026-05-13 → 2026-05-16 (4 days, 6 phases).
**Outcome:** ✅ All six phases complete. 648 pytest passing. CI guard green. Render-smoke green across 11 routes.

---

## Five-paragraph bank-QA briefing

### 1. Why this rewrite happened

The previous AKKI codebase had ~14 different call sites making direct LLM
requests against OpenAI, Anthropic, and Gemini SDKs — chat, Solva, Work
Studio, Document Journal, Cycle Manager, Pulse, Monitor. Each call site
had its own (mostly absent) de-identification, its own retry / timeout
defaults, and there was no single audit trail bank QA could point to.
The rewrite consolidates every outbound LLM request behind one gateway —
`services/synisense/shield/` — that handles de-identification, audit
logging, HMAC-signed trust receipts, purpose validation, and provider
routing. The gateway is enforced by a CI guard
(`tests/test_no_direct_llm_calls_outside_shield.py`) so future call sites
can't accidentally bypass it. The architectural invariant is now:
**no LLM call leaves the AKKI process without passing through
`synisense.shield.llm_router`.**

### 2. What "privacy by structure, not by promise" means in the new code

Synisense Shield runs **local** de-identification (regex + spaCy NER +
a per-tenant Presidio recogniser) BEFORE any text reaches an LLM. The
de-identified text is what the provider sees. Re-identification (token
swap-back to surface names, monetary figures, emails to the user) happens
locally on the response, after the LLM call returns. Every LLM call now
emits two records: a `synisense_audit_log` row (the full pipeline
metadata — provider, model, dilution score, exposure reduction score,
purpose, outcome) and a `synisense_trust_receipts` row (HMAC-SHA256-
signed, per-tenant key, deterministic body). The tenant can recompute
the HMAC of the audit body with their key and verify the chain
themselves. The chat privacy-report PDF (Phase E.H + Fix Bundle 1)
surfaces all of this in natural-language prose, with the full HMAC
signature for every audit entry, so bank QA can pick any conversation,
download the PDF, and verify it without server-side help.

### 3. What "single voice" means in the new code

Solva, Akki's reasoning engine, was rewritten from a two-engine "v2 +
Phase D" split into a single Phase D 5-layer pipeline. The legacy
`solva_v2.py` paths still exist for historical sessions but no new
session ever lands there — the Solva landing page and every handoff
button (Cycle Manager / Work Studio / Document Journal) now route into
Phase D. Phase E shipped the guardrail ladder (jailbreak / therapy /
coaching classifiers gated by purpose-validated Shield calls). Phase F
added seed-payload support to the Phase D framing endpoint so cycle /
work-studio / document-journal handoffs carry their context into Solva
as Layer 0 evidence anchors — Solva is now grounded by real documents
when it's invoked from a real seed, rather than starting from a blank
slate. Refusals are routed through a single explainer path
(`solva.refusal.compose`) so every "I can't help with that" sentence is
produced through Shield with an audit trail; nothing is hardcoded.

### 4. What "signals, not narratives" means in the new code

The Synisense Engine produces SIGNALS only — `anomaly_flag`,
`life_stage`, `churn_risk`, `behavioral_vector`, `compliance_trigger`,
`operational_health`. No LLM is involved in signal production; every
signal is deterministically derived from real Mongo data by a rule in
`services/synisense/engine/signal_derivation.py`. Each signal carries a
permanent `derivation_source` field — `derived_from_<rule>_<collection>`
so it's distinguishable from the Phase A seeded stubs (`seeded_from_*`)
and from future real-ingestion signals (`real_ingestion`). The Engine
runs a one-shot derivation backfill on app boot and exposes
`POST /api/v1/engine/admin/derive` for on-demand re-derivation. The
Monitor "Update goal" mechanic (Phase F Sub-task C) is the first
consumer of these signals: when a user clicks "Update goal" on an
objective or project, Akki queries the relevant signals + recent
documents, calls Shield with a constrained prompt, and persists the
resulting status + rationale + supporting signal_ids + audit_id on the
item — with the status non-overridable, per the locked PO default.

### 5. How a bank QA reviewer can validate the system end-to-end

(a) Open `/app/admin/synisense-observability` as superadmin. The
**Activity** tab shows live aggregate metrics per consumer (Shield
invokes, refusal rates, average dilution + exposure reduction). The
**Billing estimate** tab (Phase F Sub-task D) shows the per-consumer
USD-estimate roll-up against a code-controlled pricing table. (b) Open
any chat conversation and click "Download privacy report" — the
generated PDF (Phase E + Fix Bundle 1) carries natural-language prose
per turn AND the full HMAC-SHA256 signature for each audit entry, with
a verification recipe footer. (c) Open the Monitor and click "Update
goal" on any objective — the resulting assessment cites real engine
signals by signal_id and a real audit_id, both of which can be
cross-checked against the database. (d) The pytest suite at 648
passing tests, with a CI guard test that grep-asserts no Python module
outside `synisense/shield/llm_router.py` issues a direct LLM call. (e)
The full git history of the rewrite is visible — each of phases A → F
shipped its own closeout document in `/app/memory/sprints/`, all of
which are checked in.

---

## Test count progression

| Phase | Topic | Tests at end | Net new |
|------:|-------|-------------:|--------:|
| —     | Pre-rewrite baseline | 469 | — |
| **A** | Shield gateway + tenant-scoped routes | 517 | +48 |
| **B** | Migrate every direct LLM call to Shield | 528 | +11 |
| **C** | Chat protective layer + audit panel | 552 | +24 |
| **D** | Solva Phase D 5-layer pipeline + fix bundle v2 | 584 | +32 |
| **E** | Solva phases 2-4 + observability + PDF + fix bundle 1 | 629 | +45 |
| **F** | Engine real signals + seed handoff + Update goal + billing | **648** | +19 |

**Zero regressions across A → F.** Skipped tests (565) are all pre-rewrite
quarantines from Patch 8 / Patch 19 (E2E `requests.Session()` tests that
need an httpx + ASGI rewrite).

## Architectural invariants in force (post-rewrite)

1. **No direct LLM calls outside Shield** — enforced by CI guard.
2. **Strict tenant_id == account_id scoping** — every Shield call validates `tenant_id == current_account['id']`; every signal row carries `tenant_id`; observability + billing endpoints filter on it.
3. **No raw fetch() in the frontend** — all API calls go through `lib/api.js`.
4. **`{type(exc).__name__}: {str(exc)[:300]}` error formatting** — uniform across all Shield boundaries.
5. **Pricing table is code-controlled, not API-editable** — same governance as `ALLOWED_PURPOSES`.
6. **Trust receipts are HMAC-signed with per-tenant keys derived via HKDF from `SYNISENSE_MASTER_SECRET`** — production boot guard refuses to start without it (dev fallback emits a 60-second stderr warning loop).
7. **Phase D Solva is the single Solva engine** — legacy `solva_v2.py` paths exist for read-only historical sessions only; no new session lands there.

## What's NOT in this rewrite (deliberate scope)

- Real-time CDC / Kafka ingestion of external partner signals → Phase G+ (external infra required).
- Full migration of the 524 orphan legacy Solva sessions → Phase E shipped soft-archive; full shape migration is post-rewrite.
- Token-accurate Shield billing → Phase G+ (audit log needs token counts added).
- APScheduler hourly cron for engine derivation → today we run on startup + on-demand; hourly cron is post-rewrite.
- The 14 deferred 15-May QA findings (Pulse / Cycle Manager / Monitor / Document Journal / Work Studio / Misc UX) → resume post-rewrite per `POST_REWRITE_RAMP.md`.

## Status

✅ **REWRITE COMPLETE (2026-05-16).** All six phases shipped, verified, and documented. Bank QA artefact set ready: closeout docs in `/app/memory/sprints/`, code in `/app/backend/services/synisense/`, CI guard green, render-smoke green, 648 pytest passing.

Next sprint dispatch: see `POST_REWRITE_RAMP.md`.
