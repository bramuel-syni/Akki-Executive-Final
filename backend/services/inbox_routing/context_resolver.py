"""Phase P5.19 — Context + cycle ID precedence-chain resolver.

Resolves the `context_id` (for signals) and `cycle_id` (for cycle
updates) that the upstream-adapter materialisation needs, even when
the classifier's `target_hint` is structurally insufficient.

Precedence chains documented in `/app/memory/sprints/P5_19_signal_cycle_adapter.md`.

The default-inbox-context fallback is a singleton-per-tenant
auto-created on first use. The collection `default_inbox_contexts`
holds the mapping; the actual context lives in the standard
`contexts` collection so every existing reader (Pulse, Cycle,
membership-aware endpoints) sees it as a normal context.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from core import db as _db_global, iso as _iso, now as _now

logger = logging.getLogger(__name__)

DEFAULT_INBOX_CONTEXT_NAME = "Email Akki — unassigned"


# ── Default inbox context (singleton-per-tenant) ──────────────────


async def get_or_create_default_inbox_context(db, *, account_id: str) -> Dict[str, Any]:
    """Idempotent singleton per tenant. Returns the `contexts` row
    (always loaded so the caller can use `context["id"]`)."""
    pointer = await db.default_inbox_contexts.find_one(
        {"account_id": account_id}, {"_id": 0},
    )
    if pointer:
        ctx_id = pointer["context_id"]
        existing = await db.contexts.find_one({"id": ctx_id}, {"_id": 0})
        if existing:
            return existing
        # Pointer dangled — rebuild below.

    # Create a new context inside the tenant's account.
    ctx_id = "ctx-akki-inbox-" + uuid.uuid4().hex[:10]
    now_iso = _iso(_now())
    context_doc = {
        "id": ctx_id,
        "account_id": account_id,
        "name": DEFAULT_INBOX_CONTEXT_NAME,
        "kind": "default_inbox",
        "is_default_inbox": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.contexts.insert_one(dict(context_doc))
    # Add the tenant owner as an active member so the standard
    # `require_context_membership` gate lets them read the
    # default-inbox context just like any normal context. The
    # collection is `memberships` (not `members`), `status="active"`
    # is the gate.
    membership_doc = {
        "id": "mem-akki-inbox-" + uuid.uuid4().hex[:12],
        "context_id": ctx_id,
        "account_id": account_id,
        "status": "active",
        "role": "owner",
        "sub_role": "admin",
        "created_at": now_iso,
    }
    try:
        await db.memberships.insert_one(dict(membership_doc))
    except Exception as e:  # noqa: BLE001 — duplicate fixtures OK
        logger.warning("[P5.19] default-inbox membership insert: %s", e)
    await db.default_inbox_contexts.update_one(
        {"account_id": account_id},
        {"$set": {
            "account_id": account_id, "context_id": ctx_id,
            "created_at": now_iso,
        }},
        upsert=True,
    )
    return context_doc


async def _seed_default_cycle_agenda_and_member(
    db, *, account_id: str, context_id: str, cycle_id: str,
) -> Dict[str, int]:
    """P5.20 — Idempotent seed of one agenda item + one team member
    onto a default-inbox cycle. Returns counters
    `{agenda_created: 0|1, member_created: 0|1}` so the caller can
    write audit-log rows for non-zero outcomes.

    Agenda item: title "Inbound from Email Akki", voice-lint clean.
    Team member: the tenant's primary admin — earliest-created
    superadmin if any, else the tenant owner. Idempotency keyed by
    the cycle_id."""
    counters = {"agenda_created": 0, "member_created": 0}

    # ── Agenda ───────────────────────────────────────────────
    agenda = await db.agendas.find_one({"id": cycle_id}, {"_id": 0, "items": 1})
    seed_item_id = "ai-akki-inbox-" + uuid.uuid4().hex[:10]
    item_doc = {
        "id": seed_item_id,
        "label": "Inbound from Email Akki",
        "description": "Routed contributions from email arrive here for triage.",
        "is_default_inbox_item": True,
    }
    if not agenda:
        await db.agendas.insert_one({
            "id": cycle_id,
            "context_id": context_id,
            "items": [dict(item_doc)],
            "is_default_inbox_agenda": True,
            "created_at": _iso(_now()),
        })
        counters["agenda_created"] = 1
    else:
        # Re-seed only if no default-inbox item already exists.
        items = agenda.get("items") or []
        has_seed = any(it.get("is_default_inbox_item") for it in items)
        if not has_seed:
            items.append(dict(item_doc))
            await db.agendas.update_one(
                {"id": cycle_id},
                {"$set": {"items": items,
                          "is_default_inbox_agenda": True,
                          "updated_at": _iso(_now())}},
            )
            counters["agenda_created"] = 1

    # ── Team member ──────────────────────────────────────────
    # Resolve the tenant's primary admin: earliest-created
    # superadmin tied to this account; otherwise the account owner.
    primary = await db.accounts.find_one(
        {"id": account_id}, {"_id": 0, "id": 1, "email": 1, "name": 1},
    )
    if primary:
        existing_mem = await db.cycle_team.find_one(
            {"cycle_id": cycle_id, "account_id": primary["id"]},
            {"_id": 0, "id": 1},
        )
        if not existing_mem:
            await db.cycle_team.insert_one({
                "id": "ct-akki-inbox-" + uuid.uuid4().hex[:10],
                "cycle_id": cycle_id,
                "context_id": context_id,
                "account_id": primary["id"],
                "name": primary.get("name") or primary.get("email") or "Primary admin",
                "email": primary.get("email"),
                "role": "owner",
                "is_default_inbox_seed": True,
                "created_at": _iso(_now()),
            })
            counters["member_created"] = 1

    return counters


async def get_or_create_default_inbox_cycle(db, *, account_id: str,
                                              context_id: str) -> Dict[str, Any]:
    """Idempotent singleton OPEN cycle inside the default inbox context.
    Reuses the `cycles` collection so every cycle reader picks it up.

    P5.20 — On first creation (and re-runs for cycles that previously
    lacked agenda/team), the cycle is scaffolded with one agenda item
    "Inbound from Email Akki" and one team member (the tenant's
    primary admin) so the ContributionsStep wizard can render without
    requiring user setup. Audit rows land in `inbox_routing_log` with
    `seed_action` markers.
    """
    existing = await db.cycles.find_one(
        {"context_id": context_id, "status": "open",
         "is_default_inbox_cycle": True},
        {"_id": 0},
    )
    if existing:
        # P5.20 — backward-compat: ensure agenda + member exist on
        # pre-P5.20 default cycles too. Idempotent — no-op when
        # already seeded.
        counters = await _seed_default_cycle_agenda_and_member(
            db, account_id=account_id, context_id=context_id,
            cycle_id=existing["id"],
        )
        await _log_seed_audit(
            db, account_id=account_id, cycle_id=existing["id"],
            counters=counters,
        )
        return existing
    cyc_id = "cyc-akki-inbox-" + uuid.uuid4().hex[:10]
    now_iso = _iso(_now())
    cycle_doc = {
        "id": cyc_id,
        "context_id": context_id,
        "account_id": account_id,
        "name": "Email Akki — open cycle",
        "status": "open",
        "is_default_inbox_cycle": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.cycles.insert_one(dict(cycle_doc))
    counters = await _seed_default_cycle_agenda_and_member(
        db, account_id=account_id, context_id=context_id, cycle_id=cyc_id,
    )
    await _log_seed_audit(
        db, account_id=account_id, cycle_id=cyc_id, counters=counters,
    )
    return cycle_doc


async def _log_seed_audit(db, *, account_id: str, cycle_id: str,
                            counters: Dict[str, int]) -> None:
    """P5.20 — Write `seed_action` entries to `inbox_routing_log`
    only when non-zero seeding occurred. Tenant-scoped via
    `account_id`."""
    now_iso = _iso(_now())
    if counters.get("agenda_created"):
        await db.inbox_routing_log.insert_one({
            "id": uuid.uuid4().hex,
            "message_id": None, "account_id": account_id,
            "route_kind": "default_cycle_seed",
            "confidence": "low",
            "target_kind": "agenda", "target_id": cycle_id,
            "rationale": "Default-inbox cycle scaffolded with seed agenda item.",
            "model_id": "deterministic-v1",
            "classifier_version": "p5.20.0",
            "decision_source": "auto",
            "extra": {"seed_action": "default_cycle_agenda",
                      "cycle_id": cycle_id},
            "created_at": now_iso,
            "schema_version": "inbox.routing_log.1.0",
        })
    if counters.get("member_created"):
        await db.inbox_routing_log.insert_one({
            "id": uuid.uuid4().hex,
            "message_id": None, "account_id": account_id,
            "route_kind": "default_cycle_seed",
            "confidence": "low",
            "target_kind": "cycle_team", "target_id": cycle_id,
            "rationale": "Default-inbox cycle scaffolded with primary admin team member.",
            "model_id": "deterministic-v1",
            "classifier_version": "p5.20.0",
            "decision_source": "auto",
            "extra": {"seed_action": "default_cycle_member",
                      "cycle_id": cycle_id},
            "created_at": now_iso,
            "schema_version": "inbox.routing_log.1.0",
        })


# ── Tenant ownership validators ───────────────────────────────────


async def _context_is_tenant_owned(db, *, context_id: str,
                                     account_id: str) -> bool:
    if not context_id or not account_id:
        return False
    row = await db.contexts.find_one(
        {"id": context_id, "account_id": account_id}, {"_id": 0, "id": 1},
    )
    return row is not None


async def _cycle_is_tenant_owned(db, *, cycle_id: str,
                                   context_id: str) -> bool:
    if not cycle_id or not context_id:
        return False
    row = await db.cycles.find_one(
        {"id": cycle_id, "context_id": context_id}, {"_id": 0, "id": 1},
    )
    return row is not None


# ── Sender → context lookup ───────────────────────────────────────


async def _sender_known_context(db, *, account_id: str,
                                  from_email: str) -> Optional[str]:
    """Look up a `members` row keyed by sender email scoped to the
    tenant. Returns the bound context_id if exactly one exists."""
    if not from_email:
        return None
    member = await db.members.find_one(
        {"email": from_email.lower(),
         "context_id": {"$exists": True}},
        {"_id": 0, "context_id": 1, "account_id": 1},
    )
    if not member:
        return None
    # Cross-tenant guard — never return a context_id we don't own.
    if member.get("account_id") and member["account_id"] != account_id:
        return None
    return member.get("context_id")


# ── Signal context resolver ───────────────────────────────────────


async def resolve_signal_context(
    db,
    *,
    account_id: str,
    target_hint: Dict[str, Any],
    from_email: Optional[str] = None,
) -> Tuple[str, str]:
    """Return `(context_id, source_label)` where source_label is one
    of {`hint`, `sender_member`, `default_inbox`} so the caller can
    annotate the origin envelope for debugging.

    Precedence:
      1. `target_hint.context_id` if tenant-owned.
      2. Sender's known members.context_id if tenant-owned.
      3. Default inbox context singleton (auto-created).
    """
    hint = target_hint or {}
    # 1. Explicit hint.
    hint_ctx = hint.get("context_id")
    if hint_ctx and await _context_is_tenant_owned(
        db, context_id=hint_ctx, account_id=account_id,
    ):
        return (hint_ctx, "hint")

    # 2. Sender's known context.
    sender_ctx = await _sender_known_context(
        db, account_id=account_id, from_email=(from_email or ""),
    )
    if sender_ctx and await _context_is_tenant_owned(
        db, context_id=sender_ctx, account_id=account_id,
    ):
        return (sender_ctx, "sender_member")

    # 3. Default inbox context.
    default_ctx = await get_or_create_default_inbox_context(
        db, account_id=account_id,
    )
    return (default_ctx["id"], "default_inbox")


# ── Cycle ID resolver ─────────────────────────────────────────────


async def resolve_cycle_id(
    db,
    *,
    account_id: str,
    target_hint: Dict[str, Any],
    context_id: str,
) -> Tuple[Optional[str], str]:
    """Return `(cycle_id, resolution_status)` where status is one of:
      * `"resolved"`        — concrete cycle_id chosen.
      * `"resolved_default"` — landed on the default inbox cycle.
      * `"pending"`          — no open cycle on a non-default context;
                               caller should mark the routing log
                               `resolution_pending` + downgrade.
    Precedence:
      1. `target_hint.cycle_id` if tenant-owned + status==open.
      2. Pick latest OPEN cycle for `context_id`.
      3. If `context_id` IS the default inbox context, auto-create
         its singleton open cycle.
      4. Else: pending.
    """
    hint = target_hint or {}
    hint_cyc = hint.get("cycle_id")
    if hint_cyc and await _cycle_is_tenant_owned(
        db, cycle_id=hint_cyc, context_id=context_id,
    ):
        cyc = await db.cycles.find_one(
            {"id": hint_cyc, "context_id": context_id},
            {"_id": 0, "status": 1},
        )
        if cyc and cyc.get("status") == "open":
            return (hint_cyc, "resolved")

    open_cyc = await db.cycles.find_one(
        {"context_id": context_id, "status": "open"},
        {"_id": 0, "id": 1, "is_default_inbox_cycle": 1},
        sort=[("created_at", -1)],
    )
    if open_cyc:
        return (open_cyc["id"], "resolved")

    # No open cycle. If this is the default inbox context, mint one.
    ctx_row = await db.contexts.find_one(
        {"id": context_id}, {"_id": 0, "is_default_inbox": 1},
    )
    if ctx_row and ctx_row.get("is_default_inbox"):
        cyc = await get_or_create_default_inbox_cycle(
            db, account_id=account_id, context_id=context_id,
        )
        return (cyc["id"], "resolved_default")

    return (None, "pending")


__all__ = [
    "DEFAULT_INBOX_CONTEXT_NAME",
    "get_or_create_default_inbox_context",
    "get_or_create_default_inbox_cycle",
    "resolve_signal_context",
    "resolve_cycle_id",
]
