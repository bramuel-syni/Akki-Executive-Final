"""P5.16 — Schema for the inbox-routing classifier + audit log.

Pydantic models that land on the wire AND in Mongo. Field names
stay identical between the two so the FE can read the same shape
returned by the classify endpoint as the one stored in
`inbox_routing_log`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


ROUTE_KINDS = ("cycle_update", "task_create", "signal_post", "discussion_only", "unclassified")
CONFIDENCE_BANDS = ("low", "medium", "high")

RouteKind = Literal["cycle_update", "task_create", "signal_post", "discussion_only", "unclassified"]
ConfidenceBand = Literal["low", "medium", "high"]
DecisionSource = Literal["auto", "human", "override"]


class ClassificationCitation(BaseModel):
    """A single excerpt-and-source pair anchoring the classification.
    Every envelope MUST carry at least one citation pointing back to
    the source `message_id` (verified by `InboxRoutingCitationResolver`)."""
    message_id: str
    excerpt: str = Field(..., min_length=1, max_length=480)
    field: Literal["subject", "body", "from", "to"] = "body"


class TargetHint(BaseModel):
    """Tenant-scoped structured suggestion for the route target.

    Shape is route-kind specific and intentionally open (extra fields
    allowed). The router takes a hint as guidance; the actual create
    operation always re-validates tenant ownership before writing."""
    model_config = ConfigDict(extra="allow")
    account_id: Optional[str] = None
    # cycle_update hints
    company_id: Optional[str] = None
    cycle_id: Optional[str] = None
    # task_create hints
    task_title: Optional[str] = None
    due_hint: Optional[str] = None
    # signal_post hints
    signal_kind: Optional[str] = None  # e.g. "concern", "observation"
    # discussion_only — no extra fields needed


class ClassificationEnvelope(BaseModel):
    """The full classifier output. Persisted verbatim on
    `admin_inbox_messages.classification` for the message it
    describes, and re-emitted by `/api/admin/inbox/{id}/classify`."""
    message_id: str
    route_kind: RouteKind
    confidence: ConfidenceBand
    rationale: str = Field(..., max_length=240)
    target_hint: TargetHint = Field(default_factory=TargetHint)
    citations: List[ClassificationCitation] = Field(..., min_length=1, max_length=8)
    # Provenance
    model_id: str = "deterministic-v1"
    shield_invoke_id: Optional[str] = None
    classifier_version: str = "p5.16.0"
    classified_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: Literal["inbox.classification.1.0"] = "inbox.classification.1.0"

    @field_validator("rationale")
    @classmethod
    def _rationale_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("rationale must be non-blank")
        return v


class InboxRoutingLogEntry(BaseModel):
    """One row in `inbox_routing_log`.

    Tenant-scoped via `account_id` — every routing decision binds
    to the tenant that owns the routed target. Cross-tenant reads
    are rejected at the endpoint layer.
    """
    id: str = Field(default_factory=lambda: uuid4().hex)
    message_id: str
    account_id: str
    route_kind: RouteKind
    confidence: ConfidenceBand
    target_kind: Optional[str] = None  # e.g. "task" | "cycle_update" | "signal" | "discussion"
    target_id: Optional[str] = None
    rationale: str = Field(..., max_length=240)
    model_id: str = "deterministic-v1"
    shield_invoke_id: Optional[str] = None
    classifier_version: str = "p5.16.0"
    decision_source: DecisionSource = "auto"
    actor_id: Optional[str] = None  # admin id for human/override decisions
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: Literal["inbox.routing_log.1.0"] = "inbox.routing_log.1.0"
    # Free-form metadata bucket for route-specific fields (e.g. error trace,
    # source link). NOT persisted to the wire unless explicitly opted in.
    extra: Dict[str, Any] = Field(default_factory=dict)
