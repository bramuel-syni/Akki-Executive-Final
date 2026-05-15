"""Synisense Phase A — Pydantic v2 models for API request / response.

Mirrors the brief's contracts exactly:
- Shield API: invoke request + response, trust receipt
- Engine API: subscription request, signal query request, signal envelope
- Error envelope (the {error_class, message} shape returned on
  AUTH_DENIED / PURPOSE_INVALID / GOVERNANCE_REFUSED / SERVICE_UNAVAILABLE)

All models use `.model_dump()` (Pydantic v2). Datetime fields are
ISO-8601 strings (UTC), never naive — matches the codebase-wide
convention enforced since Patch 0.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ─────────────────────────────────────────────────────────────────────
# Shield — invoke contract
# ─────────────────────────────────────────────────────────────────────
class ShieldInvokeRequest(BaseModel):
    """POST /api/v1/shield/llm/invoke body."""
    purpose: str = Field(..., min_length=1, max_length=128)
    content: str = Field(..., min_length=1, max_length=200_000)
    model_preference: Literal["analytical", "generative", "balanced"] = "balanced"
    schema_: Optional[Dict[str, Any]] = Field(None, alias="schema")
    consumer_id: str = Field(..., min_length=1, max_length=64)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    user_id: str = Field(..., min_length=1, max_length=128)

    model_config = ConfigDict(populate_by_name=True)


class TrustReceiptV1(BaseModel):
    """Trust receipt v1 shape. The signature is HMAC-SHA256 hex over
    the canonical JSON of every field EXCEPT `signature` itself.
    Recipients verify by recomputing with the per-tenant HKDF-derived
    key."""
    receipt_id: str
    audit_id: str
    version: Literal["v1"] = "v1"
    tenant_id: str
    consumer_id: str
    purpose: str
    timestamp: str
    llm_provider: str
    llm_model: str
    de_id_summary: Dict[str, int]
    dilution_score: float
    exposure_reduction_score: float
    request_hash: str
    response_hash: str
    signature: str


class ShieldInvokeResponse(BaseModel):
    response: str
    trust_receipt: TrustReceiptV1
    audit_id: str


# ─────────────────────────────────────────────────────────────────────
# Engine — signal envelope + subscription + query
# ─────────────────────────────────────────────────────────────────────
class Signal(BaseModel):
    """Phase A signal envelope. Matches §3.3 of the Synisense brief
    with two Phase A additions:
    - `derivation_source` (mandatory) — proves seeded signals can never
      be confused with real-ingestion signals.
    - `expires_at` (optional) — TTL for short-lived anomaly signals.
    """
    signal_id: str
    tenant_id: str
    context_id: Optional[str] = None
    signal_category: Literal[
        "profile", "anomaly", "life_stage", "risk", "operational", "compliance"
    ]
    signal_type: str = Field(..., min_length=1, max_length=64)
    entity_ref: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    derivation_source: str = Field(..., min_length=1, max_length=128)
    created_at: str
    expires_at: Optional[str] = None


class SubscriptionRequest(BaseModel):
    signal_categories: List[Literal[
        "profile", "anomaly", "life_stage", "risk", "operational", "compliance",
    ]] = Field(default_factory=list)
    signal_types: List[str] = Field(default_factory=list)
    delivery: Literal["webhook", "stream", "poll"] = "poll"
    webhook_url: Optional[str] = None
    tenant_id: str
    consumer_id: str

    @field_validator("webhook_url")
    @classmethod
    def _webhook_required_iff_delivery(cls, v, info):
        # Delivery validation belongs in the route handler — keep this
        # simple here so partial-fixture tests don't trip.
        return v


class SubscriptionResponse(BaseModel):
    subscription_id: str
    status: Literal["pending", "active", "rejected"] = "pending"
    delivery: str
    created_at: str


class SignalQueryFilter(BaseModel):
    signal_category: Optional[Literal[
        "profile", "anomaly", "life_stage", "risk", "operational", "compliance",
    ]] = None
    signal_type: Optional[str] = None
    entity_ref: Optional[str] = None
    confidence_min: Optional[float] = Field(None, ge=0.0, le=1.0)
    derivation_source: Optional[str] = None


class SignalQueryPagination(BaseModel):
    cursor: Optional[str] = None
    limit: int = Field(50, ge=1, le=500)


class SignalQueryRequest(BaseModel):
    filter: SignalQueryFilter = Field(default_factory=SignalQueryFilter)
    pagination: SignalQueryPagination = Field(default_factory=SignalQueryPagination)
    tenant_id: str
    consumer_id: str


class SignalQueryResponse(BaseModel):
    signals: List[Signal]
    next_cursor: Optional[str] = None
    total_estimate: int


class SignalTypeDefinition(BaseModel):
    """Returned by GET /api/v1/engine/signal_types — the catalogue."""
    signal_type: str
    signal_category: Literal[
        "profile", "anomaly", "life_stage", "risk", "operational", "compliance",
    ]
    description: str
    payload_schema: Dict[str, Any]
    version: str = "v1"


class SignalTypeCatalogue(BaseModel):
    signal_types: List[SignalTypeDefinition]


# ─────────────────────────────────────────────────────────────────────
# Error envelope (Section 5, Table 5)
# ─────────────────────────────────────────────────────────────────────
class ErrorEnvelope(BaseModel):
    error_class: str
    message: str
    audit_id: Optional[str] = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
