# 02 — Architecture Diagram

## Data flow: consumer → Synisense Shield → cloud LLM → consumer

```
                                  AKKI BACKEND POD
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐   │
│   │  Chat       │  │  Solva       │  │  Work       │  │  Document    │   │
│   │  router     │  │  Phase D     │  │  Studio     │  │  Journal     │   │
│   └──────┬──────┘  └──────┬───────┘  └──────┬──────┘  └──────┬───────┘   │
│          │                │                 │                │           │
│   ┌──────┴────────┐ ┌─────┴────────┐ ┌──────┴─────┐ ┌────────┴───────┐   │
│   │  Cycle Mgr    │ │  Monitor     │ │  Pulse     │ │  News / RSS    │   │
│   │  router       │ │  router      │ │  router    │ │  pipeline      │   │
│   └──────┬────────┘ └──────┬───────┘ └──────┬─────┘ └────────┬───────┘   │
│          │                 │                │                │           │
│          │   ┌─────────────┴────────────────┴────────────────┘           │
│          ▼   ▼                                                           │
│   ╔══════════════════════════════════════════════════════════╗           │
│   ║         services.synisense.shield.llm_router             ║           │
│   ║   (THE ONLY MODULE THAT ISSUES LLM CALLS — CI-ENFORCED)  ║           │
│   ║                                                          ║           │
│   ║   1. Validate purpose ∈ ALLOWED_PURPOSES                 ║           │
│   ║   2. Validate tenant_id == account_id                    ║           │
│   ║   3. De-identify(text):                                  ║           │
│   ║       regex pass → spaCy NER → tenant Presidio recog.    ║           │
│   ║      Produces redacted_text + reidentification_map       ║           │
│   ║      + exposure_reduction_score + dilution_score         ║           │
│   ║   4. → emergentintegrations.chat                         ║           │
│   ║       (provider + model picked by purpose policy)        ║           │
│   ║   5. Re-identify(response, map)                          ║           │
│   ║   6. Write audit row + HMAC-SHA256 trust receipt         ║           │
│   ║   7. Return {response, audit_id, scores, …}              ║           │
│   ╚══════════════════════════════════════════════════════════╝           │
│                                  │                                       │
│                                  │ HTTPS, redacted text only             │
└──────────────────────────────────┼───────────────────────────────────────┘
                                   │
              ┌────────────────────┴───────────────────┐
              │                                        │
              ▼                                        ▼
   ┌───────────────────┐                  ┌───────────────────────┐
   │  EMERGENT LLM     │                  │  Direct provider      │
   │  GATEWAY          │                  │  (only via Emergent   │
   │  (Anthropic +     │                  │   gateway — never     │
   │  OpenAI + Gemini) │                  │   bypassed)           │
   └───────────────────┘                  └───────────────────────┘


                                  MONGO
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   synisense_audit_log         ← every Shield invoke                      │
│       audit_id, tenant_id, consumer_id, purpose, llm_provider,           │
│       llm_model, exposure_reduction_score, dilution_score,               │
│       de_id_summary, outcome, timestamp                                  │
│                                                                          │
│   synisense_trust_receipts    ← HMAC-SHA256 signed                       │
│       receipt_id, audit_id, tenant_id, version="v1",                     │
│       signature (hex), payload_hash (sha256:hex)                         │
│                                                                          │
│   synisense_signals           ← Engine derived signals                   │
│       signal_id, tenant_id, signal_type, payload,                        │
│       derivation_source="derived_from_<rule>_<collection>"               │
│                                                                          │
│   solva_phase_d_sessions      ← five-layer session state                 │
│       layer_state, seed_attached_references[],                           │
│       source_handoff, synisense_audit_ids[]                              │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Trust receipt verification flow

```
   1. Bank reviewer obtains:                  2. Verifier reads receipt:
      • A trust receipt JSON                     {audit_id, payload_hash,
      • The per-tenant HMAC key                   signature, version}
                                                          │
                                                          ▼
                                          ┌──────────────────────────────┐
                                          │  Pull the audit_log row by   │
                                          │  audit_id (or have the bank  │
                                          │  export the canonical body)  │
                                          └──────────────┬───────────────┘
                                                         │
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │  Canonicalise the audit body │
                                          │  via JSON-canonical-form     │
                                          │  (sorted keys, no whitespace)│
                                          └──────────────┬───────────────┘
                                                         │
                                                         ▼
                                          ┌──────────────────────────────┐
                                          │  HMAC-SHA256(per-tenant-key, │
                                          │   canonical_body)            │
                                          └──────────────┬───────────────┘
                                                         │
                                                         ▼
                                                 ╔═══════════════╗
                                                 ║  EQUALS       ║
                                                 ║  receipt      ║
                                                 ║  signature?   ║
                                                 ╚══════╤════════╝
                                                        │
                                          ┌─────────────┴────────────┐
                                          │                          │
                                          ▼                          ▼
                                  ✅ PASS — chain                 ❌ FAIL — tampering
                                     intact                          detected
                                                                     OR wrong key
                                                                     OR wrong body
```

The standalone script that implements this is in `04_TRUST_RECEIPT_VERIFICATION.py`. It has no Akki dependencies — it's pure Python standard library — and runs in under a second.

## Engine signal generation (no LLM involved)

```
   Mongo collections                  Deterministic rules            Signal store
   ─────────────────────              ────────────────────           ─────────────
   cycles                  ─────►   anomaly_flag rule ─────────►
                                    operational_health rule ──►
   chat_messages           ─────►   churn_risk rule ──────────►
                                    behavioral_vector rule ───►   synisense_signals
   solva_phase_d_sessions  ─────►   life_stage rule ──────────►   (every row carries
                                                                   derivation_source =
   documents               ─────►   compliance_trigger rule ──►    "derived_from_*")

       Runs:
       • once on app boot (run_startup_backfill, fire-and-forget)
       • on-demand via POST /api/v1/engine/admin/derive
       • (Phase G+ will add an hourly APScheduler cron)
```

Engine signal production is **deterministic**. No LLM. No external partner data. Every signal is reproducible from the current Mongo state.
