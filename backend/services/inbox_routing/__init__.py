"""Phase P5.16 — Email Akki auto-routing service.

Sibling package (NOT an extension of Solva v1/v2, Ideas, or
workbook_analyzer). Owns the classifier, citation resolver,
confidence calibrator, and per-route-kind dispatchers that turn
an inbound email row in `admin_inbox_messages` into useful work
inside the application.

Architecture:
  classifier.py        — `classify_message(message) → ClassificationEnvelope`
  citation_resolver.py — verifies `message_id` citations exist within tenant scope
  confidence.py        — calibrated low/medium/high band from signal strength
  refuse_to_decide.py  — re-export of workbook_analyzer's validator (single source)
  routers.py           — per-route-kind idempotent dispatch functions
  audit_log.py         — `inbox_routing_log` write helpers + read query

v1 ships with the **deterministic-v1** classifier path enabled. The
shielded-LLM round-trip stays scaffolded behind
`INBOX_ROUTING_LLM_ENABLED=false`.
"""
from .schema import (
    ROUTE_KINDS,
    CONFIDENCE_BANDS,
    ClassificationCitation,
    ClassificationEnvelope,
    InboxRoutingLogEntry,
    TargetHint,
)
from .refuse_to_decide import (
    RefuseToDecideViolation,
    validate_no_imperatives,
    safe_neutral_fallback,
)
from .confidence import (
    CONFIDENCE_THRESHOLDS,
    calibrate_band,
)
from .citation_resolver import (
    CitationUnverifiable,
    InboxRoutingCitationResolver,
)
from .classifier import (
    ClassifierFailure,
    classify_message,
    is_llm_enabled,
)
from .routers import (
    RouteFailure,
    dispatch_route,
    route_to_cycle_update,
    route_to_task,
    route_to_signal,
    route_to_discussion,
)
from .audit_log import (
    write_routing_log,
    read_routing_log,
)
from .upstream_adapter import (
    ORIGIN_EMAIL_AKKI,
    build_origin_envelope,
    is_email_akki_origin,
)
from .backfill import backfill_tasks, run as run_backfill

__all__ = [
    # schema
    "ROUTE_KINDS",
    "CONFIDENCE_BANDS",
    "ClassificationCitation",
    "ClassificationEnvelope",
    "InboxRoutingLogEntry",
    "TargetHint",
    # refuse-to-decide
    "RefuseToDecideViolation",
    "validate_no_imperatives",
    "safe_neutral_fallback",
    # confidence
    "CONFIDENCE_THRESHOLDS",
    "calibrate_band",
    # citation resolver
    "CitationUnverifiable",
    "InboxRoutingCitationResolver",
    # classifier
    "ClassifierFailure",
    "classify_message",
    "is_llm_enabled",
    # routers
    "RouteFailure",
    "dispatch_route",
    "route_to_cycle_update",
    "route_to_task",
    "route_to_signal",
    "route_to_discussion",
    # audit log
    "write_routing_log",
    "read_routing_log",
    # P5.17 — upstream adapter
    "ORIGIN_EMAIL_AKKI",
    "build_origin_envelope",
    "is_email_akki_origin",
    "backfill_tasks",
    "run_backfill",
]
