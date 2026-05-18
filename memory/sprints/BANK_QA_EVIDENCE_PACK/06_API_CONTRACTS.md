# 06 — API Contracts (Shield + Engine)

Extracted from the live OpenAPI spec at `/api/openapi.json`. This is the public contract surface for everything inside `services/synisense/`. There are 13 endpoints split across Shield (de-identification + audit + trust receipts) and Engine (signal derivation + query + subscriptions) plus the admin observability and billing surfaces.

All endpoints require a JWT bearer token from `POST /api/auth/login`. All endpoints scope by `tenant_id == account_id` unless explicitly marked otherwise.

---

## Shield endpoints

### `POST /api/v1/shield/llm/invoke`
**Purpose:** The single entry-point for ALL LLM calls from inside Akki. Runs de-identification → LLM call → re-identification → audit row + trust receipt.

**Request body:**
```json
{
  "purpose": "chat.standard_response",
  "content": "<user-provided text — may contain PII>",
  "tenant_id": "<account_id>",
  "consumer_id": "akki.chat",
  "user_id": "<account_id>",
  "model_preference": "fast" | "analytical" | "reasoning",
  "internal_caller": true
}
```

**Response (200):**
```json
{
  "response": "<re-identified LLM response>",
  "audit_id": "aud-<uuid>",
  "trust_receipt_id": "rec-<uuid>",
  "exposure_reduction_score": 92.5,
  "dilution_score": 11.0,
  "outcome": "success" | "governance_refused" | "service_unavailable",
  "de_id_summary": {"PERSON": 3, "MONEY": 2, …}
}
```

**Validation:**
- `purpose` MUST be in `ALLOWED_PURPOSES` (~60 entries; code-controlled in `config.py`).
- `tenant_id` MUST equal `current_account.id` unless caller is `internal_caller=true` AND superadmin.
- All free-text fields are bounded.

---

### `GET /api/v1/shield/audit/{audit_id}`
**Purpose:** Retrieve a single audit row for verification.

**Response (200):**
```json
{
  "audit_id": "aud-…",
  "tenant_id": "acc-…",
  "consumer_id": "akki.chat",
  "purpose": "chat.standard_response",
  "llm_provider": "anthropic",
  "llm_model": "claude-sonnet-4-5-20250929",
  "exposure_reduction_score": 92.5,
  "dilution_score": 11.0,
  "de_id_summary": {"PERSON": 3, "MONEY": 2, …},
  "outcome": "success",
  "timestamp": "2026-05-18T13:24:11+00:00"
}
```

**Scoping:** 404 if `audit_id.tenant_id != current_account.id`.

---

### `GET /api/v1/shield/receipt/{audit_id}`
**Purpose:** Retrieve the trust receipt for an audit row.

**Response (200):**
```json
{
  "receipt_id":   "rec-…",
  "audit_id":     "aud-…",
  "tenant_id":    "acc-…",
  "version":      "v1",
  "signature":    "<64-char hex>",
  "payload_hash": "sha256:<64-char hex>"
}
```

The `signature` is HMAC-SHA256 over the canonicalised audit body with a per-tenant HMAC key derived via HKDF from `SYNISENSE_MASTER_SECRET`. Reproducible by the script in `04_TRUST_RECEIPT_VERIFICATION.py`.

---

## Engine endpoints

### `POST /api/v1/engine/signals/query`
**Purpose:** Paginated tenant-scoped signal retrieval.

**Request body:**
```json
{
  "tenant_id": "<account_id>",
  "consumer_id": "akki.chat",
  "filter": {
    "signal_type": ["anomaly_flag", "compliance_trigger"],
    "min_confidence": 0.5,
    "since": "2026-05-01T00:00:00Z"
  },
  "pagination": {"limit": 50, "cursor": null}
}
```

**Response (200):**
```json
{
  "signals": [
    {
      "signal_id": "sig-<uuid>",
      "tenant_id": "acc-…",
      "context_id": "ctx-…",
      "signal_category": "anomaly",
      "signal_type": "anomaly_flag",
      "entity_ref": "cyc-…",
      "payload": {"trigger": "cycle.status.overdue", "severity": "high"},
      "confidence": 0.85,
      "derivation_source": "derived_from_cycle_status_anomaly_cycles",
      "created_at": "2026-05-18T13:24:11+00:00",
      "expires_at": "2026-05-25T13:24:11+00:00"
    }
  ],
  "next_cursor": null,
  "total_estimate": 6
}
```

**Scoping:** `tenant_id` in request body MUST equal `current_account.id`.

---

### `POST /api/v1/engine/admin/derive`
**Purpose:** Phase F — run real signal derivation for the authenticated tenant. Runs all 6 rules + falls back to Phase A seeder on empty workspaces.

**Request body:** empty.

**Response (200):**
```json
{
  "tenant_id": "acc-…",
  "derived": {
    "anomaly_flag": 2, "life_stage": 1, "churn_risk": 1,
    "behavioral_vector": 1, "compliance_trigger": 0, "operational_health": 1
  },
  "fallback_used": false,
  "seeded": {},
  "total_derived": 6
}
```

**Scoping:** Self-target by default. Superadmins MAY pass `?tenant_id=<other>` to derive for another tenant (403 otherwise).

---

### `POST /api/v1/engine/admin/reseed`
**Purpose:** DEV-ONLY — reseed signals + tenant entities for the authenticated account. Returns 403 in production.

---

### `POST /api/v1/engine/subscriptions`
**Purpose:** Subscription stub. Phase G+ will wire real webhook delivery. Currently returns `{status: "pending"}`.

---

### `GET /api/v1/engine/signal_types`
**Purpose:** Public catalogue of signal types (auth-required but not tenant-specific). Used by frontends to validate filter inputs.

---

## Admin observability + billing

### `GET /api/admin/synisense/observability?window_days=7|30|90`
**Purpose:** Aggregate metrics across all Shield invokes. Superadmin only.

**Response (200):**
```json
{
  "window_days": 7,
  "as_of": "2026-05-18T13:24:11+00:00",
  "total_invokes": 424,
  "per_consumer": [
    {"consumer_id": "akki.chat", "total_invokes": 51,
     "success_rate": 0.96, "refusal_rate": 0.04, "unavailable_rate": 0.0,
     "average_exposure_reduction": 91.2, "average_dilution": 12.4}
  ],
  "top_purposes": [{"purpose": "chat.standard_response", "count": 51}],
  "reidentification_partial_rate": 0.0017,
  "guardrail_block_counts": {"jailbreak": 2, "therapy": 0, "coaching": 0},
  "solva_refusal_reasons": {"far_insufficient_unresolved": 3, "guardrail_blocked": 1}
}
```

---

### `GET /api/admin/synisense/billing?window_days=7|30&context_id={cid}`
**Purpose:** Per-consumer USD-estimate roll-up. **Illustrative** only — not invoiced. Superadmin only.

**Response (200):**
```json
{
  "window_days": 7,
  "as_of": "2026-05-18T13:24:11+00:00",
  "total_calls": 424,
  "estimated_total_usd": 0.6406,
  "per_consumer": [
    {"consumer_id": "document.meta", "call_count": 63,
     "estimated_usd": 0.127,
     "providers": {"anthropic/claude-sonnet-4-5-20250929": 63}}
  ],
  "top_purposes_by_cost": [...],
  "is_illustrative": true,
  "estimate_notes": "Per-call flat USD estimates derived from a code-controlled table…",
  "pricing_table_signature": {
    "entry_count": 9, "default_flat_usd_per_call": 0.002,
    "providers": ["anthropic", "gemini", "openai"]
  }
}
```

**Pricing table is code-controlled, NOT API-editable.** Same governance as `ALLOWED_PURPOSES`.

---

### `GET /api/admin/synisense/perf`
**Purpose:** Per-purpose p50/p95/p99 latency.

---

### `POST /api/synisense/dryrun`
**Purpose:** Dry-run de-identification pipeline (no LLM call) for tenant debugging.

---

### `GET /api/synisense/status`
**Purpose:** Lightweight health check — used by external monitors.
