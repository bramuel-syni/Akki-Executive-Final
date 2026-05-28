"""Migration 0003 — Phase Z (2026-05-27) — Document category + origin backfill.

Idempotent. Runs once per server startup, gated by `_migrations`
marker `{"id": "0003_phase_z_document_category"}`.

What it does
============

Phase Z introduces the orthogonal `category` × `origin` classification
on the `documents` collection. The schema already carries `origin` and
`doc_kind`; this migration:

  1. Adds a `category` field to every existing document row,
     derived via `services.documents.origin_display.resolve_category`.
  2. Backfills `origin` on rows where it's missing, via
     `services.documents.origin_display.resolve_origin`.
  3. Creates two indexes for the new GET `/api/documents` filters:
       (`context_id`, `category`)
       (`context_id`, `origin`)

Per the locked Q2=(a) decision, `doc_kind` is left UNTOUCHED — it
becomes legacy-read-only and Z.2 (filed in PHASE_LEDGER) covers its
retirement on a separate dispatch.

Per the locked Q1=(b) decision, origin values keep the raw backend
form `"akki_generated" | "upload" | "email_receipt"`. We do NOT
migrate `upload` → `uploaded` or `email_receipt` → `emailed`.

The category backfill resolution carries one cross-collection lookup:
for Akki-generated docs the corresponding `work_studio_exports.kind`
is the strongest category signal. We do a single batched lookup
(`{"$in": doc_ids}`) to keep the migration fast even on >10k corpora.

Idempotency
===========

Re-running this migration is a no-op on documents that already carry
`category`. The Mongo updates use a filter that excludes already-
backfilled rows.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from core import db, iso, now
from services.documents.origin_display import (
    resolve_category, resolve_origin, CATEGORY_VALUES,
)


MIGRATION_ID = "0003_phase_z_document_category"
logger = logging.getLogger("akki.migration.0003_phase_z_document_category")


async def _already_applied() -> bool:
    row = await db["_migrations"].find_one(
        {"id": MIGRATION_ID}, {"_id": 0, "applied_at": 1},
    )
    return bool(row)


async def _mark_applied(stats: Dict[str, int]) -> None:
    await db["_migrations"].update_one(
        {"id": MIGRATION_ID},
        {"$set": {
            "id": MIGRATION_ID,
            "applied_at": iso(now()),
            "stats": stats,
        }},
        upsert=True,
    )


async def _resolve_export_kinds_for(
    doc_ids: List[str],
) -> Dict[str, str]:
    """Batched lookup: for the given set of document ids, return a
    map `{doc_id: work_studio_exports.kind}` for any doc whose id
    corresponds to a work_studio_exports row (the Akki-gen synthesis
    path sets `documents.id = work_studio_exports.id`).

    The handful of exports without a matching doc are silently
    skipped — they don't have a documents row to backfill anyway.
    """
    if not doc_ids:
        return {}
    cursor = db.work_studio_exports.find(
        {"id": {"$in": doc_ids}},
        {"_id": 0, "id": 1, "kind": 1},
    )
    out: Dict[str, str] = {}
    async for row in cursor:
        if row.get("kind"):
            out[row["id"]] = row["kind"]
    return out


async def run() -> Dict[str, Any]:
    if await _already_applied():
        return {"applied": False, "reason": "already_applied"}

    stats: Dict[str, int] = {
        "docs_seen":               0,
        "category_backfilled":     0,
        "origin_backfilled":       0,
        "category_per_bucket":     {},
    }

    # Pre-create the indexes — no-op when already present.
    await db.documents.create_index(
        [("context_id", 1), ("category", 1)],
        name="ix_documents_category",
    )
    await db.documents.create_index(
        [("context_id", 1), ("origin", 1)],
        name="ix_documents_origin",
    )

    # Walk every document. We do this in batches of 200 to keep
    # memory bounded for very large corpora.
    BATCH = 200
    cursor = db.documents.find(
        # Only touch rows that don't already carry category — the rest
        # are already backfilled and we don't want to clobber them.
        {"$or": [
            {"category": {"$exists": False}},
            {"origin":   {"$exists": False}},
            {"origin":   None},
        ]},
        {"_id": 0, "id": 1, "source_channel": 1, "doc_kind": 1,
         "state": 1, "origin": 1, "category": 1},
        no_cursor_timeout=False,
    )

    batch: List[Dict[str, Any]] = []
    bucket_counts: Dict[str, int] = {c: 0 for c in CATEGORY_VALUES}
    bucket_counts["null"] = 0

    async for doc in cursor:
        stats["docs_seen"] += 1
        batch.append(doc)
        if len(batch) >= BATCH:
            applied = await _apply_batch(batch, bucket_counts)
            stats["category_backfilled"] += applied["category_set"]
            stats["origin_backfilled"]   += applied["origin_set"]
            batch.clear()

    if batch:
        applied = await _apply_batch(batch, bucket_counts)
        stats["category_backfilled"] += applied["category_set"]
        stats["origin_backfilled"]   += applied["origin_set"]

    stats["category_per_bucket"] = bucket_counts
    await _mark_applied(stats)
    logger.info(
        "migration 0003_phase_z_document_category applied: %s",
        {k: v for k, v in stats.items() if v},
    )
    return {"applied": True, "stats": stats}


async def _apply_batch(
    batch: List[Dict[str, Any]], bucket_counts: Dict[str, int],
) -> Dict[str, int]:
    """Apply category + origin backfill for a single batch."""
    doc_ids = [d["id"] for d in batch]
    export_kinds = await _resolve_export_kinds_for(doc_ids)

    category_set = 0
    origin_set = 0

    for doc in batch:
        updates: Dict[str, Any] = {}

        if "category" not in doc:
            ws_kind: Optional[str] = export_kinds.get(doc["id"])
            cat = resolve_category(doc, ws_export_kind=ws_kind)
            updates["category"] = cat
            bucket = cat if cat else "null"
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
            category_set += 1

        if not doc.get("origin"):
            updates["origin"] = resolve_origin(doc)
            origin_set += 1

        if updates:
            await db.documents.update_one(
                {"id": doc["id"]}, {"$set": updates},
            )

    return {"category_set": category_set, "origin_set": origin_set}
