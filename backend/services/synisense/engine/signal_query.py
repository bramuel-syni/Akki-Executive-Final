"""Synisense Engine — paginated signal retrieval.

Strict `tenant_id` scoping on every query. Cursor-based pagination
uses (created_at DESC, signal_id ASC) so deletions during paging don't
shift the window.
"""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional, Tuple

from core import db

from services.synisense.engine.signal_seeder import SIGNAL_COLLECTION
from services.synisense.models import (
    Signal,
    SignalQueryFilter,
    SignalQueryPagination,
    SignalQueryResponse,
)


def _encode_cursor(created_at: str, signal_id: str) -> str:
    raw = json.dumps({"c": created_at, "s": signal_id}).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_cursor(cursor: Optional[str]) -> Optional[Tuple[str, str]]:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        body = json.loads(raw)
        return (body["c"], body["s"])
    except Exception:  # noqa: BLE001
        # Malformed cursor → ignore (treat as no cursor).
        return None


async def query(
    *,
    tenant_id: str,
    filter_: SignalQueryFilter,
    pagination: SignalQueryPagination,
) -> SignalQueryResponse:
    mongo_filter: Dict[str, Any] = {"tenant_id": tenant_id}
    if filter_.signal_category:
        mongo_filter["signal_category"] = filter_.signal_category
    if filter_.signal_type:
        mongo_filter["signal_type"] = filter_.signal_type
    if filter_.entity_ref:
        mongo_filter["entity_ref"] = filter_.entity_ref
    if filter_.confidence_min is not None:
        mongo_filter["confidence"] = {"$gte": filter_.confidence_min}
    if filter_.derivation_source:
        mongo_filter["derivation_source"] = filter_.derivation_source

    cursor_decoded = _decode_cursor(pagination.cursor)
    if cursor_decoded is not None:
        c_iso, c_sig = cursor_decoded
        mongo_filter["$or"] = [
            {"created_at": {"$lt": c_iso}},
            {"created_at": c_iso, "signal_id": {"$gt": c_sig}},
        ]

    # Total estimate — count_documents on the unbounded (no cursor) version.
    estimate_filter = {k: v for k, v in mongo_filter.items() if k != "$or"}
    total_estimate = await db[SIGNAL_COLLECTION].count_documents(estimate_filter)

    cursor = db[SIGNAL_COLLECTION].find(
        mongo_filter, {"_id": 0},
    ).sort([("created_at", -1), ("signal_id", 1)]).limit(pagination.limit + 1)
    rows = [r async for r in cursor]

    next_cursor: Optional[str] = None
    if len(rows) > pagination.limit:
        last = rows[pagination.limit - 1]
        next_cursor = _encode_cursor(last["created_at"], last["signal_id"])
        rows = rows[: pagination.limit]

    signals: List[Signal] = [Signal(**r) for r in rows]
    return SignalQueryResponse(
        signals=signals, next_cursor=next_cursor, total_estimate=total_estimate,
    )
