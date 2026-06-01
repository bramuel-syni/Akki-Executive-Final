"""P5.16 — `inbox_routing_log` audit-log helpers.

Single source of truth for writes + reads against
`inbox_routing_log`. The collection carries every routing decision
(auto, human, override) with full traceability + tenant scope.

Schema: see `InboxRoutingLogEntry` in `schema.py`.

Read endpoint enforces tenant scope: a routing-log row from
tenant A is unreadable to tenant B. Superadmins see all rows
(by `account_id=None` filter override).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core import db

from .schema import InboxRoutingLogEntry


async def write_routing_log(entry: InboxRoutingLogEntry) -> str:
    """Persist one routing-log row. Returns the row id."""
    doc = entry.model_dump()
    await db.inbox_routing_log.insert_one(dict(doc))
    return doc["id"]


async def read_routing_log(
    *,
    message_id: str,
    account_id: Optional[str] = None,
    is_superadmin: bool = False,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Return the routing-log rows for one message_id, tenant-scoped.

    Superadmins (caller passes `is_superadmin=True`) see every row.
    Non-superadmin callers MUST pass their own `account_id`; rows
    bound to a different tenant are excluded.

    The router endpoint that wraps this returns 404 (not 403) on
    cross-tenant access so the existence of a foreign tenant's row
    is not leaked — that contract is enforced at the endpoint
    layer, not here.
    """
    query: Dict[str, Any] = {"message_id": message_id}
    if not is_superadmin:
        if not account_id:
            return []
        query["account_id"] = account_id
    cursor = db.inbox_routing_log.find(
        query, {"_id": 0}
    ).sort("created_at", -1).limit(max(1, min(limit, 200)))
    rows: List[Dict[str, Any]] = []
    async for r in cursor:
        rows.append(r)
    return rows


__all__ = ["write_routing_log", "read_routing_log"]
