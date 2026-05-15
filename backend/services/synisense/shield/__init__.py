"""Synisense Shield — governance layer (Phase A).

Sub-package layout:
- `deidentifier`  : regex → tenant dict → spaCy NER (local only).
- `reidentifier`  : token → original re-substitution.
- `purpose_validator` : allow-list check, internal-purpose gate.
- `llm_router`    : outbound LLM provider call (post-de-id).
- `trust_receipt` : HMAC-SHA256 with HKDF per-tenant key.
- `audit_log`     : tamper-evident Mongo writes.
- `client`        : in-process Python client for Phase B call-site migration.
- `tenant_entities` : harvest + lookup tenant-known entities.
"""
