"""P5.16 — Per-route-kind dispatch functions.

Each function takes:
  • `message`        — the admin_inbox_messages row.
  • `envelope`       — ClassificationEnvelope.
  • `target_hint`    — explicit override hint (from manual routes) or
                       falls back to `envelope.target_hint`.
  • `actor_id`       — admin id for human/override decisions; `None`
                       for auto routes.
  • `decision_source` — "auto" | "human" | "override".

Returns a dict with `route_kind`, `target_kind`, `target_id`, and
the routing-log row id.

Idempotency:
  Per `(account_id, source_message_id, route_kind)` — a re-run with
  the same message + same route_kind returns the EXISTING target
  without creating a duplicate. The idempotency lookup hits a
  small index on `(message_id, route_kind, account_id)` in
  `inbox_routing_log`.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core import db, iso as _iso, now as _now

from .schema import (
    ClassificationEnvelope,
    InboxRoutingLogEntry,
    TargetHint,
)
from .audit_log import write_routing_log

log = logging.getLogger(__name__)


class RouteFailure(RuntimeError):
    """Raised when a route-kind dispatcher cannot complete."""


# ── Idempotency precheck ────────────────────────────────────────


async def _existing_route(*, message_id: str, route_kind: str,
                           account_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Look up an existing routing-log row for this message_id +
    route_kind + tenant. Returns the row dict or None."""
    query: Dict[str, Any] = {
        "message_id": message_id,
        "route_kind": route_kind,
    }
    if account_id:
        query["account_id"] = account_id
    return await db.inbox_routing_log.find_one(query, {"_id": 0})


# ── Route: task_create ──────────────────────────────────────────


async def route_to_task(
    *,
    message: Dict[str, Any],
    envelope: ClassificationEnvelope,
    target_hint: Optional[TargetHint] = None,
    actor_id: Optional[str] = None,
    decision_source: str = "auto",
) -> Dict[str, Any]:
    """Create a draft task in the resolved tenant. Idempotent on
    `(message_id, task_create, account_id)`.

    The "task" surface here is the lightweight `inbox_routing_tasks`
    collection — a route-local placeholder collection that the
    AKKI Task Manager / Cohort Cycle widgets can pick up. We do NOT
    write to upstream Solva/Cycle collections directly; that
    upstream integration is deferred (single-line note in the
    deferred list)."""
    hint = target_hint or envelope.target_hint
    account_id = hint.account_id
    if not account_id:
        raise RouteFailure("task_create requires target_hint.account_id")

    prev = await _existing_route(
        message_id=message["id"], route_kind="task_create", account_id=account_id,
    )
    if prev:
        return {
            "route_kind": "task_create",
            "target_kind": prev.get("target_kind"),
            "target_id": prev.get("target_id"),
            "routing_log_id": prev.get("id"),
            "status": "exists",
        }

    task_doc = {
        "id": "tsk-" + uuid.uuid4().hex[:12],
        "account_id": account_id,
        "source": "inbox_routing",
        "source_message_id": message["id"],
        "title": (hint.task_title or (message.get("subject") or "Inbound task"))[:240],
        "body_snippet": (message.get("body_snippet") or "")[:480],
        "due_hint": hint.due_hint or None,
        "from_email": message.get("from_email") or None,
        "created_at": _iso(_now()),
        "status": "draft",
    }
    await db.inbox_routing_tasks.insert_one(dict(task_doc))

    # Phase P5.17 (2026-02) — write the parallel row into the
    # primary `tasks` collection so the Task Manager surface picks
    # the routed task up without a separate backfill pass. The
    # sibling row above is the canonical audit-store; the primary
    # row is the read-side surface. Idempotency on the primary side
    # is provided by the existing `_existing_route` log check that
    # short-circuits this whole function on a repeat call.
    try:
        from .upstream_adapter import build_origin_envelope
        origin_env = build_origin_envelope(
            message_id=message["id"],
            confidence_band=envelope.confidence,
            decision_source=decision_source,
        )
        primary_task = {
            "id": "tsk-" + uuid.uuid4().hex[:12],
            "account_id": account_id,
            "context_id": None,
            "name": task_doc["title"],
            "objective": "",
            "success_criteria": "",
            "output_spec": None,
            "team": [],
            "state": "draft",
            "due_date": task_doc.get("due_hint"),
            "readiness_score": 0,
            "created_at": task_doc["created_at"],
            "updated_at": task_doc["created_at"],
            "status_history": [],
            "origin": origin_env,
        }
        await db.tasks.insert_one(dict(primary_task))
    except Exception as _e:  # noqa: BLE001
        log.warning("[P5.17] primary tasks insert failed for %s: %s",
                    task_doc["id"], _e)

    log_entry = InboxRoutingLogEntry(
        message_id=message["id"],
        account_id=account_id,
        route_kind="task_create",
        confidence=envelope.confidence,
        target_kind="task",
        target_id=task_doc["id"],
        rationale=envelope.rationale,
        model_id=envelope.model_id,
        shield_invoke_id=envelope.shield_invoke_id,
        classifier_version=envelope.classifier_version,
        decision_source=decision_source,  # type: ignore[arg-type]
        actor_id=actor_id,
    )
    log_id = await write_routing_log(log_entry)
    return {
        "route_kind": "task_create",
        "target_kind": "task",
        "target_id": task_doc["id"],
        "routing_log_id": log_id,
        "status": "created",
    }


# ── Route: cycle_update ─────────────────────────────────────────


async def route_to_cycle_update(
    *,
    message: Dict[str, Any],
    envelope: ClassificationEnvelope,
    target_hint: Optional[TargetHint] = None,
    actor_id: Optional[str] = None,
    decision_source: str = "auto",
) -> Dict[str, Any]:
    """Append a discussion-only timeline entry for a cycle update.

    We do NOT auto-create a new operating cycle (that's a
    user-driven action). Instead we write a lightweight entry to
    `inbox_routing_cycle_updates` keyed by `(account_id, cycle_id?)`
    that the cycle UI can surface as a discussion thread item.
    Idempotent on `(message_id, cycle_update, account_id)`."""
    hint = target_hint or envelope.target_hint
    account_id = hint.account_id
    if not account_id:
        raise RouteFailure("cycle_update requires target_hint.account_id")

    prev = await _existing_route(
        message_id=message["id"], route_kind="cycle_update", account_id=account_id,
    )
    if prev:
        return {
            "route_kind": "cycle_update",
            "target_kind": prev.get("target_kind"),
            "target_id": prev.get("target_id"),
            "routing_log_id": prev.get("id"),
            "status": "exists",
        }

    update_doc = {
        "id": "cyu-" + uuid.uuid4().hex[:12],
        "account_id": account_id,
        "cycle_id": hint.cycle_id,
        "company_id": hint.company_id,
        "source": "inbox_routing",
        "source_message_id": message["id"],
        "subject": (message.get("subject") or "Cycle update")[:240],
        "body_snippet": (message.get("body_snippet") or "")[:480],
        "from_email": message.get("from_email") or None,
        "created_at": _iso(_now()),
    }
    await db.inbox_routing_cycle_updates.insert_one(dict(update_doc))

    log_entry = InboxRoutingLogEntry(
        message_id=message["id"],
        account_id=account_id,
        route_kind="cycle_update",
        confidence=envelope.confidence,
        target_kind="cycle_update",
        target_id=update_doc["id"],
        rationale=envelope.rationale,
        model_id=envelope.model_id,
        shield_invoke_id=envelope.shield_invoke_id,
        classifier_version=envelope.classifier_version,
        decision_source=decision_source,  # type: ignore[arg-type]
        actor_id=actor_id,
    )
    log_id = await write_routing_log(log_entry)
    return {
        "route_kind": "cycle_update",
        "target_kind": "cycle_update",
        "target_id": update_doc["id"],
        "routing_log_id": log_id,
        "status": "created",
    }


# ── Route: signal_post ──────────────────────────────────────────


async def route_to_signal(
    *,
    message: Dict[str, Any],
    envelope: ClassificationEnvelope,
    target_hint: Optional[TargetHint] = None,
    actor_id: Optional[str] = None,
    decision_source: str = "auto",
) -> Dict[str, Any]:
    """Post a Pulse signal carrying the email excerpt + a citation
    pointing back to the inbox message_id. Idempotent on
    `(message_id, signal_post, account_id)`."""
    hint = target_hint or envelope.target_hint
    account_id = hint.account_id
    if not account_id:
        raise RouteFailure("signal_post requires target_hint.account_id")

    prev = await _existing_route(
        message_id=message["id"], route_kind="signal_post", account_id=account_id,
    )
    if prev:
        return {
            "route_kind": "signal_post",
            "target_kind": prev.get("target_kind"),
            "target_id": prev.get("target_id"),
            "routing_log_id": prev.get("id"),
            "status": "exists",
        }

    signal_doc = {
        "id": "isg-" + uuid.uuid4().hex[:12],
        "account_id": account_id,
        "source": "inbox_routing",
        "source_message_id": message["id"],
        "signal_kind": hint.signal_kind or "observation",
        "subject": (message.get("subject") or "Inbound signal")[:240],
        "body_snippet": (message.get("body_snippet") or "")[:480],
        "from_email": message.get("from_email") or None,
        "created_at": _iso(_now()),
        "citation": {
            "message_id": message["id"],
            "excerpt": envelope.citations[0].excerpt if envelope.citations else "",
        },
    }
    await db.inbox_routing_signals.insert_one(dict(signal_doc))

    log_entry = InboxRoutingLogEntry(
        message_id=message["id"],
        account_id=account_id,
        route_kind="signal_post",
        confidence=envelope.confidence,
        target_kind="signal",
        target_id=signal_doc["id"],
        rationale=envelope.rationale,
        model_id=envelope.model_id,
        shield_invoke_id=envelope.shield_invoke_id,
        classifier_version=envelope.classifier_version,
        decision_source=decision_source,  # type: ignore[arg-type]
        actor_id=actor_id,
    )
    log_id = await write_routing_log(log_entry)
    return {
        "route_kind": "signal_post",
        "target_kind": "signal",
        "target_id": signal_doc["id"],
        "routing_log_id": log_id,
        "status": "created",
    }


# ── Route: discussion_only ──────────────────────────────────────


async def route_to_discussion(
    *,
    message: Dict[str, Any],
    envelope: ClassificationEnvelope,
    target_hint: Optional[TargetHint] = None,
    actor_id: Optional[str] = None,
    decision_source: str = "auto",
) -> Dict[str, Any]:
    """Attach as a discussion-only artifact. No target row is
    created in any first-class surface; the routing-log row IS the
    target (admins can review it in the routing-log modal).
    Idempotent on `(message_id, discussion_only, account_id?)`.

    `account_id` is optional for this route — it stays None when
    the sender is unknown / has no tenant binding. The routing-log
    row in that case is admin-only."""
    hint = target_hint or envelope.target_hint
    account_id = hint.account_id  # may be None

    prev = await _existing_route(
        message_id=message["id"], route_kind="discussion_only",
        account_id=account_id,
    )
    if prev:
        return {
            "route_kind": "discussion_only",
            "target_kind": "routing_log",
            "target_id": prev.get("id"),
            "routing_log_id": prev.get("id"),
            "status": "exists",
        }

    log_entry = InboxRoutingLogEntry(
        message_id=message["id"],
        account_id=account_id or "",  # empty-string for unrouted
        route_kind="discussion_only",
        confidence=envelope.confidence,
        target_kind="routing_log",
        target_id=None,
        rationale=envelope.rationale,
        model_id=envelope.model_id,
        shield_invoke_id=envelope.shield_invoke_id,
        classifier_version=envelope.classifier_version,
        decision_source=decision_source,  # type: ignore[arg-type]
        actor_id=actor_id,
    )
    log_id = await write_routing_log(log_entry)
    return {
        "route_kind": "discussion_only",
        "target_kind": "routing_log",
        "target_id": log_id,
        "routing_log_id": log_id,
        "status": "created",
    }


# ── Top-level dispatcher ────────────────────────────────────────


async def dispatch_route(
    *,
    message: Dict[str, Any],
    envelope: ClassificationEnvelope,
    target_hint: Optional[TargetHint] = None,
    actor_id: Optional[str] = None,
    decision_source: str = "auto",
) -> Dict[str, Any]:
    """Pick the right per-route-kind function based on
    `envelope.route_kind`. Returns the same dict the underlying
    function returns.

    `unclassified` is a no-op routing: we write a log row with
    `target_kind=None` so the audit trail captures the
    not-routed decision, but no first-class target is created.
    """
    rk = envelope.route_kind
    if rk == "task_create":
        return await route_to_task(
            message=message, envelope=envelope, target_hint=target_hint,
            actor_id=actor_id, decision_source=decision_source,
        )
    if rk == "cycle_update":
        return await route_to_cycle_update(
            message=message, envelope=envelope, target_hint=target_hint,
            actor_id=actor_id, decision_source=decision_source,
        )
    if rk == "signal_post":
        return await route_to_signal(
            message=message, envelope=envelope, target_hint=target_hint,
            actor_id=actor_id, decision_source=decision_source,
        )
    if rk == "discussion_only":
        return await route_to_discussion(
            message=message, envelope=envelope, target_hint=target_hint,
            actor_id=actor_id, decision_source=decision_source,
        )
    # unclassified — emit a log row only.
    hint = target_hint or envelope.target_hint
    log_entry = InboxRoutingLogEntry(
        message_id=message["id"],
        account_id=hint.account_id or "",
        route_kind="unclassified",
        confidence=envelope.confidence,
        target_kind=None,
        target_id=None,
        rationale=envelope.rationale,
        model_id=envelope.model_id,
        shield_invoke_id=envelope.shield_invoke_id,
        classifier_version=envelope.classifier_version,
        decision_source=decision_source,  # type: ignore[arg-type]
        actor_id=actor_id,
    )
    log_id = await write_routing_log(log_entry)
    return {
        "route_kind": "unclassified",
        "target_kind": None,
        "target_id": None,
        "routing_log_id": log_id,
        "status": "logged",
    }


__all__ = [
    "RouteFailure",
    "dispatch_route",
    "route_to_cycle_update",
    "route_to_task",
    "route_to_signal",
    "route_to_discussion",
]
