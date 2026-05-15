"""Synisense Shield — HMAC-SHA256 Trust Receipt with HKDF per-tenant keys.

Phase A scheme (v1):

- **Master secret** : 32 bytes, resolved in `config.py`. In production
  set `SYNISENSE_MASTER_SECRET`. In dev a transient secret is generated
  AND a startup warning is logged.
- **Per-tenant key** : ``HKDF-SHA256(master_secret, info=tenant_id,
  length=32, salt=b"synisense/v1")``. Different tenants get different
  keys; the same tenant always derives the same key.
- **Signature**   : ``HMAC-SHA256(per_tenant_key, canonical_json(payload
  minus signature))``. We sort keys lexicographically and separators=
  (',', ':') for stability across language / version boundaries.
- **Version**     : `"v1"` is embedded in the receipt so future
  upgrades (asymmetric keys, post-quantum, etc.) can co-exist on the
  audit chain.

The receipt is consumer-visible — Solva / Chat will store and replay it.
Verification logic lives here too so tests can prove signatures
round-trip cleanly.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from services.synisense.config import MASTER_SECRET

log = logging.getLogger("synisense.shield.trust_receipt")

_HKDF_SALT = b"synisense/v1"
_HKDF_LENGTH = 32  # 256-bit per-tenant key

# In-process cache — recomputing HKDF on every call would be wasteful.
_TENANT_KEY_CACHE: Dict[str, bytes] = {}


def derive_tenant_key(tenant_id: str) -> bytes:
    """HKDF-SHA256 → 32-byte key, salted, info=tenant_id."""
    if tenant_id in _TENANT_KEY_CACHE:
        return _TENANT_KEY_CACHE[tenant_id]
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_HKDF_LENGTH,
        salt=_HKDF_SALT,
        info=tenant_id.encode("utf-8"),
    )
    key = kdf.derive(MASTER_SECRET)
    _TENANT_KEY_CACHE[tenant_id] = key
    return key


def _clear_cache_for_test() -> None:
    """Test-only hook."""
    _TENANT_KEY_CACHE.clear()


def _canonical_json(payload_no_sig: Dict[str, Any]) -> bytes:
    """Stable JSON encoding: sorted keys, compact separators, UTF-8."""
    return json.dumps(
        payload_no_sig, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sign(payload: Dict[str, Any], *, tenant_id: str) -> str:
    """Compute the HMAC-SHA256 hex over the canonical JSON of `payload`
    with the `signature` field stripped. Mutates nothing."""
    body = {k: v for k, v in payload.items() if k != "signature"}
    key = derive_tenant_key(tenant_id)
    mac = hmac.new(key, _canonical_json(body), hashlib.sha256)
    return mac.hexdigest()


def verify(payload: Dict[str, Any], *, tenant_id: str) -> bool:
    """Constant-time verify of a receipt's `signature`.

    Returns True iff the signature in `payload` matches the recomputed
    HMAC. Constant-time via `hmac.compare_digest`."""
    sig = payload.get("signature")
    if not isinstance(sig, str) or not sig:
        return False
    recomputed = sign(payload, tenant_id=tenant_id)
    return hmac.compare_digest(sig, recomputed)


def hash_payload(content: str) -> str:
    """SHA-256 of a content blob, prefixed with `sha256:` so the receipt
    is self-describing. Used for `request_hash` and `response_hash`."""
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_trust_receipt(
    *,
    receipt_id: str,
    audit_id: str,
    tenant_id: str,
    consumer_id: str,
    purpose: str,
    timestamp: str,
    llm_provider: str,
    llm_model: str,
    de_id_summary: Dict[str, int],
    dilution_score: float,
    exposure_reduction_score: float,
    request_hash: str,
    response_hash: str,
) -> Dict[str, Any]:
    """Build a v1 trust receipt, sign it, return the signed dict."""
    receipt: Dict[str, Any] = {
        "receipt_id": receipt_id,
        "audit_id": audit_id,
        "version": "v1",
        "tenant_id": tenant_id,
        "consumer_id": consumer_id,
        "purpose": purpose,
        "timestamp": timestamp,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "de_id_summary": de_id_summary,
        "dilution_score": dilution_score,
        "exposure_reduction_score": exposure_reduction_score,
        "request_hash": request_hash,
        "response_hash": response_hash,
    }
    receipt["signature"] = sign(receipt, tenant_id=tenant_id)
    return receipt
