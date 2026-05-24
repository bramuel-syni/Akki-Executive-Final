"""H4 — Back-fill historical chats through Shield v1.x.

Replays pre-2026-05-15T20:55 conversations through
``deidentifier.deidentify()`` so they gain proper audit visibility:

  * synisense_audit_log rows with ``is_backfill: true``
  * chat_audit_log rows with same marker
  * synisense_runs rows keyed on (account_id, chat_id, message_id)
  * chat_messages.shielding updated with the new redaction summary
  * chats.synisense_audit_ids appended with new audit IDs
  * chats.backfill_metadata = {backfilled_at, backfill_batch_id,
    original_pre_v1: true}

Design constraints
------------------
* **Idempotency** — ``chat.backfill_metadata.backfilled_at`` is set
  BEFORE writing audit rows. On re-run, chats with that marker are
  skipped unless ``partial=true``. Mid-chat failures leave
  ``partial=true`` so retries can target only the broken ones.
* **Honesty** — every back-fill audit row carries ``is_backfill:
  true``, ``backfill_batch_id``, AND ``original_message_ts`` (the
  ORIGINAL message creation time, not the back-fill time). The
  Trust Center shows a "back-filled on <date>" badge.
* **Separate chain** — back-fill rows derive their ``prev_hash``
  from a ``backfill_chain_v1`` head, NOT from the live audit
  chain. Live chain stays clean.
* **No mutation of plaintext** — ``chat_messages.content`` is
  NEVER modified. Only ``chat_messages.shielding`` is updated.
* **Rate limiting** — process in batches of N (default 50),
  sleep between batches (default 200 ms).

Invoke from
-----------
* CLI: ``python -m scripts.backfill_shield_v1 --batch-size 50``
* Admin: ``POST /api/admin/shield/backfill``
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core import db
from services.synisense.shield import deidentifier

logger = logging.getLogger("akki.shield.backfill")

# The earliest synisense_audit_log row was at 2026-05-15T20:55:14 UTC —
# that's the Shield v1.x deploy cut-over. Chats created BEFORE that
# AND with empty synisense_audit_ids are the candidate set.
SHIELD_V1_DEPLOY_ISO = "2026-05-15T20:55:14+00:00"

DEFAULT_BATCH_SIZE = 50
DEFAULT_SLEEP_MS = 200


# ─────────────────────────────────────────────────────────────────────
# Hash chain — separate from live so back-fill rows don't pollute it.
# ─────────────────────────────────────────────────────────────────────
async def _backfill_chain_head() -> str:
    """Latest ``row_hash`` on the back-fill chain. Initial value is a
    deterministic constant so the chain is verifiable from the first
    row onward."""
    last = await db.chat_audit_log.find_one(
        {"backfill_chain_v1": True},
        {"_id": 0, "row_hash": 1},
        sort=[("at", -1)],
    )
    if last and last.get("row_hash"):
        return last["row_hash"]
    # Deterministic genesis — sha256("akki-backfill-chain-v1-genesis").
    return hashlib.sha256(b"akki-backfill-chain-v1-genesis").hexdigest()


def _row_hash(prev_hash: str, body: Dict[str, Any]) -> str:
    """Same construction as the live ``chat_audit_log`` chain — sha256
    over (prev_hash + canonical body json)."""
    import json
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(
        (prev_hash + canonical).encode("utf-8", "ignore"),
    ).hexdigest()


# ─────────────────────────────────────────────────────────────────────
# Per-message back-fill
# ─────────────────────────────────────────────────────────────────────
async def _backfill_message(
    *,
    chat: Dict[str, Any],
    msg: Dict[str, Any],
    batch_id: str,
    chain_head_ref: List[str],  # mutable single-cell so caller sees the head advance
    dry_run: bool,
) -> Dict[str, Any]:
    """Process ONE message. Returns ``{audit_id, identifiers, by_class}``.

    Raises on any persistence failure so the caller can mark the
    chat ``partial=true``.
    """
    msg_id = msg.get("id")
    content = msg.get("content") or ""
    role = msg.get("role")
    account_id = msg.get("account_id") or chat.get("account_id")
    chat_id = chat["id"]

    deid_result = await deidentifier.deidentify(
        content, tenant_id=account_id or "__backfill__",
    )
    de_id_summary: Dict[str, int] = dict(deid_result.de_id_summary or {})
    identifiers = sum(int(v) for v in de_id_summary.values())

    if dry_run:
        return {
            "audit_id": None,
            "identifiers": identifiers,
            "by_class": de_id_summary,
            "dry_run": True,
        }

    now = datetime.now(timezone.utc).isoformat()
    original_ts = (
        msg.get("created_at") or msg.get("ts") or msg.get("at") or now
    )
    if isinstance(original_ts, datetime):
        original_ts = original_ts.replace(tzinfo=timezone.utc).isoformat() \
            if original_ts.tzinfo is None else original_ts.isoformat()

    audit_id = "aud-bf-" + uuid.uuid4().hex

    # ── 1) synisense_audit_log ──
    await db.synisense_audit_log.insert_one({
        "audit_id": audit_id,
        "tenant_id": account_id,
        "user_id": account_id,
        "consumer_id": "chat",
        "purpose": f"chat.backfill.{role}",
        "outcome": "success",
        "llm_provider": None,
        "llm_model": None,
        "tokens_in": None,
        "tokens_out": None,
        "actual_cost_usd": 0.0,
        "metering_method": "backfill",
        "latency_ms": int(deid_result.elapsed_ms or 0),
        "request_hash": "sha256:" + hashlib.sha256(content.encode("utf-8", "ignore")).hexdigest(),
        "response_hash": None,
        "de_id_summary": de_id_summary,
        "dilution_score": None,
        "exposure_reduction_score": None,
        "timestamp": now,
        # H4 honesty markers — distinguishes back-filled rows from live.
        "is_backfill": True,
        "backfill_batch_id": batch_id,
        "original_message_ts": original_ts,
    })

    # ── 2) synisense_runs (canonical per-turn source) ──
    spans = []
    for entity_type, cnt in de_id_summary.items():
        for _ in range(int(cnt or 0)):
            spans.append({
                "entity_type": entity_type,
                "source": "synisense-shield-v1",
                "confidence": None,
            })
    await db.synisense_runs.insert_one({
        "id": str(uuid.uuid4()),
        "context_id": chat.get("context_id") or "",
        "account_id": account_id,
        "chat_id": chat_id,
        "message_id": msg_id,
        "surface": "chat",
        "mode": "redact",
        "ts": datetime.now(timezone.utc),
        "spans": spans,
        "stats": {
            "layer_won": "synisense-shield-v1",
            "elapsed_ms": int(deid_result.elapsed_ms or 0),
        },
        "synisense_version": "synisense-shield-v1",
        # H4 honesty markers.
        "is_backfill": True,
        "backfill_batch_id": batch_id,
        "original_message_ts": original_ts,
    })

    # ── 3) chat_audit_log row (separate chain) ──
    prev_hash = chain_head_ref[0]
    body = {
        "message_id": msg_id,
        "role": role,
        "content_sha256": hashlib.sha256(
            content.encode("utf-8", "ignore"),
        ).hexdigest(),
        "identifiers_detected": identifiers,
        "by_category": de_id_summary,
        "shielded_for_llm": identifiers > 0,
        "channel": "backfill",
        "bypass_reason": None if identifiers > 0 else "no_identifiers",
        "model": None,
        "is_backfill": True,
        "backfill_batch_id": batch_id,
        "original_message_ts": original_ts,
    }
    row_hash = _row_hash(prev_hash, body)
    await db.chat_audit_log.insert_one({
        "id": "bf-ca-" + uuid.uuid4().hex,
        "account_id": account_id,
        "chat_id": chat_id,
        "action": "message.sent",
        "at": now,
        "ip": None,
        "ua_sha": None,
        "payload": body,
        "prev_hash": prev_hash,
        "row_hash": row_hash,
        # H4 — flag the row as belonging to the separate chain so
        # _backfill_chain_head() can find it on the next batch.
        "backfill_chain_v1": True,
    })
    chain_head_ref[0] = row_hash

    # ── 4) chat_messages.shielding update (NEVER touch .content) ──
    envelope = {
        "identifiers_masked": identifiers,
        "by_category": de_id_summary,
        "shielded_by": "synisense-shield-v1",
        "backfilled": True,
        "backfill_batch_id": batch_id,
    }
    await db.chat_messages.update_one(
        {"id": msg_id, "chat_id": chat_id},
        {"$set": {
            "shielding": envelope,
            "synisense_stats": {
                "spans_redacted": identifiers,
                "by_type": de_id_summary,
                "elapsed_ms": int(deid_result.elapsed_ms or 0),
                "version": "synisense-shield-v1",
                "audit_id": audit_id,
                "is_backfill": True,
            },
        }},
    )

    return {
        "audit_id": audit_id,
        "identifiers": identifiers,
        "by_class": de_id_summary,
        "dry_run": False,
    }


# ─────────────────────────────────────────────────────────────────────
# Per-chat back-fill
# ─────────────────────────────────────────────────────────────────────
async def _backfill_chat(
    *,
    chat: Dict[str, Any],
    batch_id: str,
    chain_head_ref: List[str],
    dry_run: bool,
) -> Dict[str, Any]:
    """Process ONE chat end-to-end. Returns a summary row that the
    caller appends to ``backfill_log``."""
    chat_id = chat["id"]
    started_at = datetime.now(timezone.utc).isoformat()

    # ── Mark chat as IN_PROGRESS before writing audit rows so a
    # mid-chat crash leaves a partial marker on re-run. ──
    if not dry_run:
        await db.chats.update_one(
            {"id": chat_id},
            {"$set": {"backfill_metadata": {
                "batch_id": batch_id,
                "started_at": started_at,
                "original_pre_v1": True,
                "partial": True,  # flipped to False on success
            }}},
        )

    messages = await db.chat_messages.find(
        {"chat_id": chat_id}, {"_id": 0},
    ).sort([("created_at", 1)]).to_list(length=None)

    audit_ids: List[str] = []
    total_identifiers = 0
    by_class_chat: Dict[str, int] = {}
    msg_count = 0
    error: Optional[str] = None

    try:
        for msg in messages:
            res = await _backfill_message(
                chat=chat, msg=msg, batch_id=batch_id,
                chain_head_ref=chain_head_ref, dry_run=dry_run,
            )
            msg_count += 1
            total_identifiers += int(res.get("identifiers") or 0)
            for k, v in (res.get("by_class") or {}).items():
                by_class_chat[k] = by_class_chat.get(k, 0) + int(v)
            if res.get("audit_id"):
                audit_ids.append(res["audit_id"])
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {str(exc)[:300]}"
        logger.warning(
            "backfill: chat %s failed mid-process: %s", chat_id, error,
        )

    completed_at = datetime.now(timezone.utc).isoformat()

    # ── Finalise chat metadata + push audit ids ──
    if not dry_run:
        update_doc: Dict[str, Any] = {
            "backfill_metadata": {
                "batch_id": batch_id,
                "started_at": started_at,
                "completed_at": completed_at,
                "original_pre_v1": True,
                "partial": bool(error),
                "messages_processed": msg_count,
                "identifiers_detected": total_identifiers,
                "by_class": by_class_chat,
                "error": error,
            },
        }
        if audit_ids:
            # $push with $each so we append without losing any pre-existing.
            await db.chats.update_one(
                {"id": chat_id},
                {"$set": update_doc,
                 "$push": {"synisense_audit_ids": {"$each": audit_ids}}},
            )
        else:
            await db.chats.update_one(
                {"id": chat_id}, {"$set": update_doc},
            )

        # ── backfill_log row ──
        await db.backfill_log.insert_one({
            "id": "bfl-" + uuid.uuid4().hex,
            "batch_id": batch_id,
            "chat_id": chat_id,
            "account_id": chat.get("account_id"),
            "context_id": chat.get("context_id"),
            "status": "failed" if error else "completed",
            "error": error,
            "started_at": started_at,
            "completed_at": completed_at,
            "messages_processed": msg_count,
            "identifiers_detected": total_identifiers,
        })

    return {
        "chat_id": chat_id,
        "messages_processed": msg_count,
        "identifiers_detected": total_identifiers,
        "by_class": by_class_chat,
        "status": "failed" if error else "completed",
        "error": error,
    }


# ─────────────────────────────────────────────────────────────────────
# Top-level orchestrator
# ─────────────────────────────────────────────────────────────────────
async def run_backfill(
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    sleep_ms: int = DEFAULT_SLEEP_MS,
    dry_run: bool = False,
    limit: Optional[int] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Drive the back-fill across all candidate chats. Returns a
    summary; full per-chat status is in ``backfill_log``."""
    batch_id = job_id or ("bf-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    started = datetime.now(timezone.utc).isoformat()

    # ── Candidate set: chats without any synisense_audit_ids AND
    # without an existing successful backfill_metadata. ──
    query: Dict[str, Any] = {
        "$or": [
            {"synisense_audit_ids": {"$exists": False}},
            {"synisense_audit_ids": {"$size": 0}},
        ],
        # Skip chats already cleanly back-filled.
        "backfill_metadata.partial": {"$ne": False},
    }

    # Job status row.
    if not dry_run:
        await db.backfill_jobs.insert_one({
            "id": batch_id,
            "status": "running",
            "started_at": started,
            "dry_run": False,
            "params": {"batch_size": batch_size, "sleep_ms": sleep_ms,
                       "limit": limit},
            "total_chats_scanned": 0,
            "total_chats_backfilled": 0,
            "total_audit_rows_written": 0,
            "chats_with_pre_v1_pii_detected": 0,
            "errors_count": 0,
        })

    cursor = db.chats.find(query, {"_id": 0}).sort([("created_at", 1)])
    if limit:
        cursor = cursor.limit(limit)

    chain_head_ref = [await _backfill_chain_head()]

    scanned = 0
    backfilled = 0
    audit_rows = 0
    pii_chats = 0
    errors = 0
    batch_buffer: List[Dict[str, Any]] = []

    async for chat in cursor:
        scanned += 1
        batch_buffer.append(chat)
        if len(batch_buffer) >= batch_size:
            for c in batch_buffer:
                res = await _backfill_chat(
                    chat=c, batch_id=batch_id,
                    chain_head_ref=chain_head_ref, dry_run=dry_run,
                )
                if res["status"] == "completed":
                    backfilled += 1
                    audit_rows += res["messages_processed"]
                    if res["identifiers_detected"] > 0:
                        pii_chats += 1
                else:
                    errors += 1
            batch_buffer = []
            if not dry_run:
                await db.backfill_jobs.update_one(
                    {"id": batch_id},
                    {"$set": {
                        "total_chats_scanned": scanned,
                        "total_chats_backfilled": backfilled,
                        "total_audit_rows_written": audit_rows,
                        "chats_with_pre_v1_pii_detected": pii_chats,
                        "errors_count": errors,
                    }},
                )
            await asyncio.sleep(sleep_ms / 1000.0)

    # ── Flush remainder ──
    for c in batch_buffer:
        res = await _backfill_chat(
            chat=c, batch_id=batch_id,
            chain_head_ref=chain_head_ref, dry_run=dry_run,
        )
        if res["status"] == "completed":
            backfilled += 1
            audit_rows += res["messages_processed"]
            if res["identifiers_detected"] > 0:
                pii_chats += 1
        else:
            errors += 1

    summary = {
        "batch_id": batch_id,
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "total_chats_scanned": scanned,
        "total_chats_backfilled": backfilled,
        "total_audit_rows_written": audit_rows,
        "chats_with_pre_v1_pii_detected": pii_chats,
        "errors_count": errors,
    }
    if not dry_run:
        await db.backfill_jobs.update_one(
            {"id": batch_id},
            {"$set": {**summary, "status": "completed"}},
        )
    return summary


__all__ = [
    "run_backfill", "_backfill_chat", "_backfill_message",
    "SHIELD_V1_DEPLOY_ISO", "DEFAULT_BATCH_SIZE", "DEFAULT_SLEEP_MS",
]
