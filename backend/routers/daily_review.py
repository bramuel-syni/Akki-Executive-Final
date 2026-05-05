"""Daily Review — Phase 3 (Advisory 4, Phase A).

The load-bearing modality. A unified queue across the user's contexts
that surfaces:
  - Inbound docs awaiting triage (`db.inbound_queue` status='pending_review')
  - Briefings awaiting review (`db.boardpacks` status='active' with no
    read receipt for the current account in `db.briefing_reads`)

Phase B (drafted emails, extracted cycle questions) is still deferred
behind the stubs noted in `/app/docs/ux-advisories-v1.md`.

Endpoints:
  GET  /api/me/review-queue
  GET  /api/me/review-queue/counts
  POST /api/me/review-queue/items/{kind}/{id}/approve
  POST /api/me/review-queue/items/{kind}/{id}/reject
  POST /api/me/review-queue/items/{kind}/{id}/edit

Approve / reject dispatch to the same DB writes as the existing per-kind
handlers (we don't double-import to avoid circular Depends), and every
action lands in `db.audit_log`. Each item can only be acted on once;
second call returns 409.
"""
from __future__ import annotations

import base64
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account, iso, now, write_audit
from documents_service import (
    extract_text, make_preview, save_to_storage,
)
from services import clamav_service
from services.clamav_service import ClamAVUnreachable

router = APIRouter(prefix="/api/me/review-queue", tags=["daily_review"])
logger = logging.getLogger("akki.daily_review")

INBOUND_KIND = "inbound_doc"
BRIEFING_KIND = "briefing"
STUDIO_KIND = "studio_artefact"  # composed briefings / decks / reports awaiting review (Phase 8)
STUDIO_SUBKINDS = ("briefing", "deck", "report")
STUDIO_COLLECTIONS = {"briefing": "briefings", "deck": "decks", "report": "reports"}
# Phase 15.1 — Solva v2 cycle handoff queue items. `_handoff_cycle_via_review`
# in routers/solva_v2.py writes one row per session into
# db.solva_cycle_handoff_queue with status='pending_review' and surfaces it
# here. Approve = write each question into db.questions and flip status to
# 'approved'. Reject / edit follow the same three-state contract used by the
# other kinds.
SOLVA_CYCLE_KIND = "solva_cycle_action"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _user_context_ids(account_id: str) -> List[str]:
    """All context IDs the user is a member of (across the whole account)."""
    ids: List[str] = []
    async for m in db.memberships.find(
        {"account_id": account_id, "status": {"$ne": "removed"}},
        {"_id": 0, "context_id": 1},
    ):
        if m.get("context_id"):
            ids.append(m["context_id"])
    # Owners can show up via ownership too; merge to be safe.
    async for c in db.contexts.find(
        {"owner_account_id": account_id, "deleted": {"$ne": True}},
        {"_id": 0, "id": 1},
    ):
        if c.get("id") and c["id"] not in ids:
            ids.append(c["id"])
    return ids


async def _context_name_map(context_ids: List[str]) -> Dict[str, str]:
    if not context_ids:
        return {}
    out: Dict[str, str] = {}
    async for c in db.contexts.find(
        {"id": {"$in": context_ids}}, {"_id": 0, "id": 1, "name": 1},
    ):
        out[c["id"]] = c.get("name") or "(unnamed context)"
    return out


async def _read_briefing_ids(account_id: str) -> set:
    """Briefings the user has already marked as read."""
    ids = set()
    async for r in db.briefing_reads.find(
        {"account_id": account_id}, {"_id": 0, "briefing_id": 1},
    ):
        if r.get("briefing_id"):
            ids.add(r["briefing_id"])
    return ids


def _inbound_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "from": row.get("inbound_from_email") or row.get("inbound_from_name") or "(unknown sender)",
        "from_name": row.get("inbound_from_name"),
        "subject": row.get("inbound_subject") or "(no subject)",
        "snippet": (row.get("inbound_text_preview") or row.get("review_reason") or "")[:600],
        "attachments": int(row.get("inbound_attachment_count") or 0),
        "trust_tier": row.get("inbound_trust_tier"),
        "review_reason": row.get("review_reason"),
        "suggested_action": {
            "type": "file",
            "target_collection": "documents",
        },
    }


def _briefing_payload(b: Dict[str, Any]) -> Dict[str, Any]:
    items = b.get("items") or []
    word_count = 0
    for it in items:
        for fld in ("evidence", "signal_summary", "signal_headline"):
            if it.get(fld):
                word_count += len((it[fld] or "").split())
    if not word_count and b.get("opening_paragraph"):
        word_count = len(b["opening_paragraph"].split())
    primary_doc_id = None
    primary_doc_title = None
    for it in items:
        for s in (it.get("sources") or []):
            if s.get("doc_id"):
                primary_doc_id = s["doc_id"]
                primary_doc_title = s.get("doc_name") or s.get("doc_title")
                break
        if primary_doc_id:
            break
    return {
        "title": b.get("title") or "Briefing",
        "doc_id": primary_doc_id,
        "doc_title": primary_doc_title,
        "word_count": word_count,
        "validator_score": b.get("validator_score"),
        "items_count": len(items),
        "opening_paragraph": (b.get("opening_paragraph") or "")[:600],
    }


def _studio_payload(a: Dict[str, Any], subkind: str) -> Dict[str, Any]:
    """Payload for a composed-artefact awaiting review (Phase 8)."""
    classification = a.get("classification") or {}
    if isinstance(classification, str):
        cls_label = classification
        cls_key = classification.lower()
    else:
        cls_label = classification.get("label") or "Internal"
        cls_key = (classification.get("classification") or "internal").lower()
    body_preview = (a.get("opening_paragraph") or a.get("body") or "")[:600]
    return {
        "subkind": subkind,
        "title": a.get("title") or f"{subkind.capitalize()} draft",
        "submitted_at": a.get("submitted_at"),
        "submission_note": (a.get("submission_note") or "")[:240],
        "classification": cls_key,
        "classification_label": cls_label,
        "preview": body_preview,
    }


# ---------------------------------------------------------------------------
# GET /api/me/review-queue
# ---------------------------------------------------------------------------
@router.get("")
async def list_review_queue(
    limit: int = 50,
    cursor: Optional[str] = None,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Aggregate pending items across all of the user's contexts.

    `cursor` is an opaque iso-datetime string — items strictly older
    than `cursor` are returned. `limit` is capped at 100.
    """
    cap = max(1, min(int(limit or 50), 100))
    cids = await _user_context_ids(account["id"])
    if not cids:
        return {"items": [], "next_cursor": None, "total_pending": 0}

    name_map = await _context_name_map(cids)
    read_ids = await _read_briefing_ids(account["id"])

    inbound_q: Dict[str, Any] = {
        "context_id": {"$in": cids},
        "status": "pending_review",
    }
    briefing_q: Dict[str, Any] = {
        "context_id": {"$in": cids},
        "status": "active",
        "id": {"$nin": list(read_ids)} if read_ids else {"$exists": True},
    }
    if cursor:
        inbound_q["created_at"] = {"$lt": cursor}
        briefing_q["created_at"] = {"$lt": cursor}

    # Pull both — overshoot the cap so we can sort + slice.
    over = cap * 2
    inbound_rows = await db.inbound_queue.find(
        inbound_q, {"_id": 0},
    ).sort("created_at", -1).to_list(over)
    briefing_rows = await db.boardpacks.find(
        briefing_q, {"_id": 0},
    ).sort("created_at", -1).to_list(over)

    # Studio-composed artefacts awaiting review (Phase 8). Scan all three
    # kinds; volume is small. Ordered by submitted_at fallback created_at.
    studio_rows: List[Dict[str, Any]] = []
    for sub in STUDIO_SUBKINDS:
        coll = db[STUDIO_COLLECTIONS[sub]]
        async for a in coll.find(
            {"context_id": {"$in": cids}, "block_status": "in_review"},
            {"_id": 0},
        ).sort("submitted_at", -1).limit(over):
            a["__subkind"] = sub
            studio_rows.append(a)

    items: List[Dict[str, Any]] = []
    for row in inbound_rows:
        items.append({
            "id": f"{INBOUND_KIND}:{row['id']}",
            "kind": INBOUND_KIND,
            "created_at": row.get("created_at"),
            "context_id": row.get("context_id"),
            "context_name": name_map.get(row.get("context_id"), "(unknown)"),
            "payload": _inbound_payload(row),
        })
    for b in briefing_rows:
        items.append({
            "id": f"{BRIEFING_KIND}:{b['id']}",
            "kind": BRIEFING_KIND,
            "created_at": b.get("created_at"),
            "context_id": b.get("context_id"),
            "context_name": name_map.get(b.get("context_id"), "(unknown)"),
            "payload": _briefing_payload(b),
        })
    for s in studio_rows:
        sub = s.pop("__subkind", "briefing")
        # Composed-artefact items use a sub-prefix so the UID encodes both
        # the queue-kind (studio_artefact) and the underlying artefact kind
        # (briefing/deck/report). Format: "studio_artefact:<sub>:<id>".
        items.append({
            "id": f"{STUDIO_KIND}:{sub}:{s['id']}",
            "kind": STUDIO_KIND,
            "subkind": sub,
            "created_at": s.get("submitted_at") or s.get("created_at"),
            "context_id": s.get("context_id"),
            "context_name": name_map.get(s.get("context_id"), "(unknown)"),
            "payload": _studio_payload(s, sub),
        })

    # Phase 15.1 — Solva v2 cycle handoff queue items.
    solva_cycle_q: Dict[str, Any] = {
        "account_id": account["id"],
        "status": "pending_review",
    }
    if cursor:
        solva_cycle_q["created_at"] = {"$lt": cursor}
    solva_cycle_rows = await db.solva_cycle_handoff_queue.find(
        solva_cycle_q, {"_id": 0},
    ).sort("created_at", -1).to_list(over)
    for row in solva_cycle_rows:
        items.append({
            "id": f"{SOLVA_CYCLE_KIND}:{row['id']}",
            "kind": SOLVA_CYCLE_KIND,
            "created_at": row.get("created_at"),
            "context_id": row.get("context_id"),
            "context_name": name_map.get(row.get("context_id"), "(unknown)"),
            "payload": {
                "cluster_label": row.get("cluster_label"),
                "session_id": row.get("session_id"),
                "question_count": len(row.get("questions") or []),
                "questions": row.get("questions") or [],
                "note": row.get("note") or "",
            },
        })

    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    page = items[:cap]
    next_cursor = page[-1]["created_at"] if len(items) > cap else None
    total_inbound = await db.inbound_queue.count_documents({
        "context_id": {"$in": cids}, "status": "pending_review",
    })
    total_briefing = await db.boardpacks.count_documents({
        "context_id": {"$in": cids}, "status": "active",
        "id": {"$nin": list(read_ids)} if read_ids else {"$exists": True},
    })
    total_studio = 0
    for sub in STUDIO_SUBKINDS:
        total_studio += await db[STUDIO_COLLECTIONS[sub]].count_documents({
            "context_id": {"$in": cids}, "block_status": "in_review",
        })
    total_solva_cycle = await db.solva_cycle_handoff_queue.count_documents({
        "account_id": account["id"], "status": "pending_review",
    })
    total_pending = total_inbound + total_briefing + total_studio + total_solva_cycle

    return {"items": page, "next_cursor": next_cursor, "total_pending": total_pending}


# ---------------------------------------------------------------------------
# GET /api/me/review-queue/counts
# ---------------------------------------------------------------------------
@router.get("/counts")
async def review_queue_counts(
    account: Dict[str, Any] = Depends(get_current_account),
):
    cids = await _user_context_ids(account["id"])
    # Solva-cycle items are scoped to account_id (not context_id), so a
    # brand-new account with Solva v2 sessions but no contexts can still
    # have queue items. Compute that count first, then short-circuit only
    # if every kind is empty.
    solva_cycle_total = await db.solva_cycle_handoff_queue.count_documents({
        "account_id": account["id"], "status": "pending_review",
    })
    if not cids:
        return {
            "total": solva_cycle_total,
            "by_kind": {
                INBOUND_KIND: 0,
                BRIEFING_KIND: 0,
                STUDIO_KIND: 0,
                SOLVA_CYCLE_KIND: solva_cycle_total,
            },
            "by_context": [],
        }

    read_ids = await _read_briefing_ids(account["id"])
    name_map = await _context_name_map(cids)

    inbound_total = await db.inbound_queue.count_documents({
        "context_id": {"$in": cids}, "status": "pending_review",
    })
    briefing_total = await db.boardpacks.count_documents({
        "context_id": {"$in": cids}, "status": "active",
        "id": {"$nin": list(read_ids)} if read_ids else {"$exists": True},
    })
    studio_total = 0
    for sub in STUDIO_SUBKINDS:
        studio_total += await db[STUDIO_COLLECTIONS[sub]].count_documents({
            "context_id": {"$in": cids}, "block_status": "in_review",
        })

    # by_context aggregation — one round-trip per kind.
    by_ctx: Dict[str, int] = {cid: 0 for cid in cids}
    async for row in db.inbound_queue.aggregate([
        {"$match": {"context_id": {"$in": cids}, "status": "pending_review"}},
        {"$group": {"_id": "$context_id", "n": {"$sum": 1}}},
    ]):
        by_ctx[row["_id"]] = by_ctx.get(row["_id"], 0) + row["n"]
    async for row in db.boardpacks.aggregate([
        {"$match": {"context_id": {"$in": cids}, "status": "active",
                    "id": {"$nin": list(read_ids)} if read_ids else {"$exists": True}}},
        {"$group": {"_id": "$context_id", "n": {"$sum": 1}}},
    ]):
        by_ctx[row["_id"]] = by_ctx.get(row["_id"], 0) + row["n"]

    by_context = [
        {"context_id": cid, "context_name": name_map.get(cid, "(unknown)"), "count": n}
        for cid, n in by_ctx.items() if n > 0
    ]
    by_context.sort(key=lambda r: r["count"], reverse=True)

    return {
        "total": inbound_total + briefing_total + studio_total + solva_cycle_total,
        "by_kind": {
            INBOUND_KIND: inbound_total,
            BRIEFING_KIND: briefing_total,
            STUDIO_KIND: studio_total,
            SOLVA_CYCLE_KIND: solva_cycle_total,
        },
        "by_context": by_context,
    }


# ---------------------------------------------------------------------------
# Approve / reject / edit
# ---------------------------------------------------------------------------
class ApproveIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=400)


class RejectIn(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=200)


async def _next_pending_item_id(account_id: str, exclude_uid: str) -> Optional[str]:
    """Cheap "what's next" probe — pick the most-recent pending item that
    isn't the one we just acted on. Used by the UI to advance the queue."""
    cids = await _user_context_ids(account_id)
    candidates: List[Dict[str, Any]] = []
    if cids:
        read_ids = await _read_briefing_ids(account_id)
        next_ib = await db.inbound_queue.find_one(
            {"context_id": {"$in": cids}, "status": "pending_review"},
            sort=[("created_at", -1)],
        )
        next_br = await db.boardpacks.find_one(
            {"context_id": {"$in": cids}, "status": "active",
             "id": {"$nin": list(read_ids)} if read_ids else {"$exists": True}},
            sort=[("created_at", -1)],
        )
        if next_ib:
            candidates.append({"id": f"{INBOUND_KIND}:{next_ib['id']}",
                               "created_at": next_ib.get("created_at") or ""})
        if next_br:
            candidates.append({"id": f"{BRIEFING_KIND}:{next_br['id']}",
                               "created_at": next_br.get("created_at") or ""})
    # Phase 15.1 — Solva-cycle items are scoped to account_id, not
    # context_id, so they always need to be considered (even when the
    # user has no contexts yet).
    next_sc = await db.solva_cycle_handoff_queue.find_one(
        {"account_id": account_id, "status": "pending_review"},
        sort=[("created_at", -1)],
    )
    if next_sc:
        candidates.append({"id": f"{SOLVA_CYCLE_KIND}:{next_sc['id']}",
                           "created_at": next_sc.get("created_at") or ""})
    candidates = [c for c in candidates if c["id"] != exclude_uid]
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["created_at"], reverse=True)
    return candidates[0]["id"]


async def _is_member(context_id: str, account_id: str) -> bool:
    """Cheap membership check (we already know the account; this confirms
    the linked context still has the user as an active member or owner)."""
    if await db.memberships.find_one({
        "context_id": context_id, "account_id": account_id, "status": {"$ne": "removed"},
    }):
        return True
    if await db.contexts.find_one({"id": context_id, "owner_account_id": account_id}):
        return True
    return False


async def _approve_inbound(qid: str, account: Dict[str, Any], note: Optional[str]) -> Dict[str, Any]:
    """Mirror of `inbound_queue.accept_inbound_queue_item` but reachable
    via the unified queue. Same DB writes + audit shape."""
    row = await db.inbound_queue.find_one({"id": qid}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    if not await _is_member(row["context_id"], account["id"]):
        raise HTTPException(status_code=403, detail="Not a member of this context.")
    if row["status"] != "pending_review":
        raise HTTPException(
            status_code=409,
            detail={"prior_decision": row["status"], "decided_at": row.get("accepted_at") or row.get("rejected_at")},
        )
    raw = await db.inbound_queue_raw.find_one({"queue_id": qid}, {"_id": 0})
    if not raw:
        raise HTTPException(status_code=410, detail="Queue payload is no longer available.")

    # Promote to db.documents — same logic as inbound_queue.accept.
    primary = raw.get("primary_attachment")
    text_body = raw.get("text_body") or ""
    html_body = raw.get("html_body") or ""
    doc_id = str(uuid.uuid4())
    created_at = iso(now())

    if primary:
        try:
            data = base64.b64decode(primary.get("Content") or "")
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Attachment payload corrupt.") from None
        filename = primary.get("Name") or "attachment"
        # Real virus scan (Phase 10). Unreachable → 503 + audit; block on match.
        try:
            scan_result = clamav_service.scan(data, filename)
        except ClamAVUnreachable as e:
            await write_audit(
                row["context_id"], account["id"],
                "upload.virus_scan.unreachable",
                "inbound_queue", qid, {"error": str(e)[:200]},
            )
            raise HTTPException(
                status_code=503,
                detail={"error": "scanner_unavailable", "reason": "virus scanner offline"},
            )
        if not scan_result.clean:
            await db.inbound_queue.update_one({"id": qid}, {"$set": {
                "status": "rejected", "rejected_by": account["id"],
                "rejected_at": iso(now()), "reject_reason": f"virus_scan · {scan_result.signature}",
            }})
            await write_audit(
                row["context_id"], account["id"],
                "upload.virus_scan.blocked",
                "inbound_queue", qid,
                {"signature": scan_result.signature, "size_bytes": len(data)},
            )
            raise HTTPException(
                status_code=422,
                detail={"error": "blocked", "reason": "malware_suspected", "signature": scan_result.signature},
            )
        storage_key = save_to_storage(row["context_id"], doc_id, filename, data)
        text, err = extract_text(data, filename, primary.get("ContentType") or "")
        size = len(data)
        mime = primary.get("ContentType") or "application/octet-stream"
        original_filename = filename
        display_name = row.get("inbound_subject") or filename
    else:
        body_txt = text_body or html_body or "(empty email)"
        data = body_txt.encode("utf-8", errors="replace")
        filename = f"email-{(row.get('inbound_message_id') or doc_id)[:24]}.txt"
        storage_key = save_to_storage(row["context_id"], doc_id, filename, data)
        text, err = extract_text(data, filename, "text/plain")
        size = len(data)
        mime = "text/plain"
        original_filename = filename
        display_name = row.get("inbound_subject") or "Forwarded email"

    doc = {
        "id": doc_id,
        "context_id": row["context_id"],
        "name": (display_name or "Forwarded email")[:200],
        "description": (text_body or "")[:280],
        "original_filename": original_filename,
        "mime_type": mime,
        "size_bytes": size,
        "storage_key": storage_key,
        "status": "extracted" if (text and not err) else ("failed" if err else "empty"),
        "extracted_text": text,
        "extracted_chars": len(text or ""),
        "preview": make_preview(text or text_body or ""),
        "data_trust": "mixed",
        "uploaded_by": account["id"],
        "uploaded_by_email": account.get("email"),
        "error": err,
        "created_at": created_at,
        "updated_at": created_at,
        "source": "inbound_email",
        "inbound_message_id": row.get("inbound_message_id"),
        "inbound_from_email": row.get("inbound_from_email"),
        "inbound_subject": row.get("inbound_subject"),
        "inbound_attachment_count": row.get("inbound_attachment_count") or 0,
        "inbound_trust_tier": "unknown_promoted",
        "inbound_queue_id": qid,
        "inbound_promoted_via": "daily_review",
        "inbound_promoted_at": iso(now()),
        "inbound_promoted_note": note,
    }
    await db.documents.insert_one(doc)
    await db.inbound_queue.update_one({"id": qid}, {"$set": {
        "status": "accepted", "accepted_by": account["id"],
        "accepted_at": iso(now()), "promoted_doc_id": doc_id,
        "accept_via": "daily_review", "accept_note": note,
    }})
    await write_audit(
        row["context_id"], account["id"],
        "review.inbound_doc.approve", "inbound_queue", qid,
        {"promoted_doc_id": doc_id, "via": "daily_review"},
    )
    return {"promoted_doc_id": doc_id}


async def _reject_inbound(qid: str, account: Dict[str, Any], reason: Optional[str]) -> Dict[str, Any]:
    row = await db.inbound_queue.find_one({"id": qid}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    if not await _is_member(row["context_id"], account["id"]):
        raise HTTPException(status_code=403, detail="Not a member of this context.")
    if row["status"] != "pending_review":
        raise HTTPException(
            status_code=409,
            detail={"prior_decision": row["status"]},
        )
    reason_clean = (reason or "not_relevant").strip()[:200]
    await db.inbound_queue.update_one({"id": qid}, {"$set": {
        "status": "rejected", "rejected_by": account["id"],
        "rejected_at": iso(now()), "reject_reason": reason_clean,
        "reject_via": "daily_review",
    }})
    await write_audit(
        row["context_id"], account["id"],
        "review.inbound_doc.reject", "inbound_queue", qid,
        {"reason": reason_clean, "via": "daily_review"},
    )
    return {"reason": reason_clean}


async def _approve_briefing(bid: str, account: Dict[str, Any]) -> Dict[str, Any]:
    """Approve = mark-as-read for the current account."""
    b = await db.boardpacks.find_one(
        {"id": bid, "status": "active"}, {"_id": 0, "id": 1, "context_id": 1},
    )
    if not b:
        raise HTTPException(status_code=404, detail="Briefing not found.")
    if not await _is_member(b["context_id"], account["id"]):
        raise HTTPException(status_code=403, detail="Not a member of this context.")
    existing = await db.briefing_reads.find_one(
        {"briefing_id": bid, "account_id": account["id"]},
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"prior_decision": "read", "decided_at": existing.get("read_at")},
        )
    now_iso = iso(now())
    await db.briefing_reads.update_one(
        {"briefing_id": bid, "account_id": account["id"]},
        {"$set": {
            "briefing_id": bid, "account_id": account["id"],
            "context_id": b["context_id"], "read_at": now_iso,
            "read_via": "daily_review",
        }, "$setOnInsert": {"first_read_at": now_iso}},
        upsert=True,
    )
    await write_audit(
        b["context_id"], account["id"],
        "review.briefing.approve", "briefing", bid,
        {"via": "daily_review"},
    )
    return {"read_at": now_iso}


async def _reject_briefing(bid: str, account: Dict[str, Any], reason: Optional[str]) -> Dict[str, Any]:
    b = await db.boardpacks.find_one(
        {"id": bid, "status": "active"}, {"_id": 0, "id": 1, "context_id": 1},
    )
    if not b:
        raise HTTPException(status_code=404, detail="Briefing not found.")
    if not await _is_member(b["context_id"], account["id"]):
        raise HTTPException(status_code=403, detail="Not a member of this context.")
    res = await db.boardpacks.update_one(
        {"id": bid, "status": "active"},
        {"$set": {"status": "archived", "archived_at": iso(now()),
                  "archived_via": "daily_review",
                  "archive_reason": (reason or "")[:200]}},
    )
    if res.matched_count == 0:
        raise HTTPException(
            status_code=409,
            detail={"prior_decision": "archived"},
        )
    await write_audit(
        b["context_id"], account["id"],
        "review.briefing.reject", "briefing", bid,
        {"reason": (reason or "")[:200], "via": "daily_review"},
    )
    return {"reason": (reason or "")[:200]}


def _split_uid(kind: str, item_id: str) -> str:
    """Defensive — strip any leading 'kind:' prefix the UI may double-send."""
    if ":" in item_id and item_id.split(":", 1)[0] == kind:
        return item_id.split(":", 1)[1]
    return item_id


async def _resolve_studio_artefact(subkind: str, aid: str, account: Dict[str, Any]) -> Dict[str, Any]:
    if subkind not in STUDIO_SUBKINDS:
        raise HTTPException(status_code=400, detail=f"Unknown studio subkind: {subkind}")
    coll = db[STUDIO_COLLECTIONS[subkind]]
    a = await coll.find_one({"id": aid}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail=f"{subkind} not found")
    if not await _is_member(a["context_id"], account["id"]):
        raise HTTPException(status_code=403, detail="Not a member of this context.")
    return a


async def _approve_studio(uid_payload: str, account: Dict[str, Any], note: Optional[str]) -> Dict[str, Any]:
    """uid_payload is '<subkind>:<artefact_id>'."""
    parts = uid_payload.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Studio item id must be '<subkind>:<artefact_id>'.")
    subkind, aid = parts
    a = await _resolve_studio_artefact(subkind, aid, account)
    if (a.get("block_status") or "draft") != "in_review":
        raise HTTPException(status_code=409, detail={"prior_decision": a.get("block_status") or "draft"})
    coll = db[STUDIO_COLLECTIONS[subkind]]
    now_iso = iso(now())
    await coll.update_one(
        {"id": aid},
        {"$set": {
            "block_status": "approved",
            "approved_at": now_iso,
            "approved_by": account["id"],
            "approval_note": (note or "")[:600],
        }},
    )
    await write_audit(
        a["context_id"], account["id"],
        "review.studio.approve", subkind, aid,
        {"via": "daily_review", "note": (note or "")[:200]},
    )
    return {"subkind": subkind, "approved_at": now_iso}


async def _reject_studio(uid_payload: str, account: Dict[str, Any], reason: Optional[str]) -> Dict[str, Any]:
    parts = uid_payload.split(":", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Studio item id must be '<subkind>:<artefact_id>'.")
    subkind, aid = parts
    a = await _resolve_studio_artefact(subkind, aid, account)
    if (a.get("block_status") or "draft") != "in_review":
        raise HTTPException(status_code=409, detail={"prior_decision": a.get("block_status") or "draft"})
    coll = db[STUDIO_COLLECTIONS[subkind]]
    now_iso = iso(now())
    reason_clean = (reason or "needs_revision")[:200]
    await coll.update_one(
        {"id": aid},
        {"$set": {
            "block_status": "draft",
            "rejected_at": now_iso,
            "rejected_by": account["id"],
            "reject_reason": reason_clean,
        }},
    )
    await write_audit(
        a["context_id"], account["id"],
        "review.studio.reject", subkind, aid,
        {"via": "daily_review", "reason": reason_clean},
    )
    return {"subkind": subkind, "reason": reason_clean}



# ---------------------------------------------------------------------------
# Phase 15.1 — Solva v2 cycle handoff queue handlers
# ---------------------------------------------------------------------------
class SolvaCycleEditIn(BaseModel):
    """Optional payload on the edit endpoint: when present for the
    solva_cycle_action kind, the questions list replaces the queue item's
    questions and the handler immediately calls approve."""
    questions: Optional[List[Dict[str, Any]]] = None
    note: Optional[str] = None


async def _approve_solva_cycle(
    iid: str, account: Dict[str, Any], note: Optional[str] = None,
    questions_override: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Approve a solva_cycle_action queue item: write each question into
    db.questions, mark the queue item approved, mark solve_handoffs approved.
    Idempotent: a second approve returns ok=True without re-writing."""
    item = await db.solva_cycle_handoff_queue.find_one(
        {"id": iid, "account_id": account["id"]}, {"_id": 0}
    )
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    if item.get("status") == "approved":
        return {"ok": True, "idempotent": True, "questions_inserted": 0}
    if item.get("status") == "rejected":
        raise HTTPException(status_code=409, detail="Queue item was already rejected.")

    questions = questions_override or item.get("questions") or []
    if not questions:
        raise HTTPException(status_code=422, detail="No questions to approve.")

    # Phase 15.2 — null-context fallback. Sessions started without an
    # active context (e.g. from /app/solva/v2-poc when the picker
    # bypassed the context selection) land here with item.context_id=
    # None. Without a fallback the inserted db.questions rows would be
    # orphaned (un-retrievable via GET /api/contexts/{cid}/questions
    # because that endpoint scopes by context_id). Resolve from the
    # owner's default_context_id; if THAT is also null fail fast with
    # 422 so the user gets a clear actionable error instead of silent
    # orphaning.
    target_context_id = item.get("context_id")
    if not target_context_id:
        owner = await db.accounts.find_one(
            {"id": item.get("account_id") or account["id"]},
            {"_id": 0, "default_context_id": 1},
        )
        target_context_id = (owner or {}).get("default_context_id")
    if not target_context_id:
        raise HTTPException(
            status_code=422,
            detail=(
                "Cannot approve Solva cycle handoff — session has no "
                "context and account has no default context set."
            ),
        )

    # Insert into db.questions one row per question, mirroring v1's shape.
    inserted_ids: List[str] = []
    for q in questions:
        qid = q.get("id") or str(uuid.uuid4())
        doc = {
            "id": qid,
            "context_id": target_context_id,
            "text": (q.get("text") or "").strip(),
            "category": q.get("category") or "strategic",
            "source": f"AKKI Solva v2 · {item.get('cluster_label') or item.get('cluster_id') or 'session'}",
            "source_session_id": item.get("session_id"),
            "ordinal": q.get("ordinal"),
            "created_at": iso(now()),
            "created_by": account["id"],
        }
        if not doc["text"]:
            continue
        await db.questions.insert_one(doc)
        inserted_ids.append(qid)

    await db.solva_cycle_handoff_queue.update_one(
        {"id": iid},
        {"$set": {
            "status": "approved",
            "reviewed_at": iso(now()),
            "questions": questions,
            "approve_note": (note or "").strip(),
            "inserted_question_ids": inserted_ids,
            "resolved_context_id": target_context_id,
        }},
    )
    await db.solva_handoffs.update_many(
        {"review_queue_id": iid},
        {"$set": {"status": "approved", "approved_at": iso(now())}},
    )
    return {"ok": True, "idempotent": False, "questions_inserted": len(inserted_ids)}


async def _reject_solva_cycle(
    iid: str, account: Dict[str, Any], reason: Optional[str] = None,
) -> Dict[str, Any]:
    item = await db.solva_cycle_handoff_queue.find_one(
        {"id": iid, "account_id": account["id"]}, {"_id": 0, "id": 1, "status": 1}
    )
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    if item.get("status") == "rejected":
        return {"ok": True, "idempotent": True}
    if item.get("status") == "approved":
        raise HTTPException(status_code=409, detail="Queue item was already approved.")

    await db.solva_cycle_handoff_queue.update_one(
        {"id": iid},
        {"$set": {
            "status": "rejected",
            "reviewed_at": iso(now()),
            "reject_reason": (reason or "").strip(),
        }},
    )
    await db.solva_handoffs.update_many(
        {"review_queue_id": iid},
        {"$set": {"status": "rejected", "rejected_at": iso(now())}},
    )
    return {"ok": True, "idempotent": False}


async def _edit_solva_cycle(
    iid: str, account: Dict[str, Any], body: Optional[SolvaCycleEditIn],
) -> Dict[str, Any]:
    """Persist edited questions (if provided) then immediately approve.

    If no questions[] is provided in the body, this returns the existing
    queue item so the UI can offer an inline editor and call edit again
    with the edited list. The contract from the brief is:
        'Daily Review's edit handler persists the edited question(s) and
         then approves.'
    """
    item = await db.solva_cycle_handoff_queue.find_one(
        {"id": iid, "account_id": account["id"]}, {"_id": 0}
    )
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found.")
    questions = body.questions if body else None
    note = body.note if body else None
    if questions is None:
        # Provide the current questions so the UI can offer an editor.
        return {
            "ok": True,
            "kind": SOLVA_CYCLE_KIND,
            "id": iid,
            "inline": True,
            "edit_url": None,
            "current_questions": item.get("questions") or [],
        }
    # Sanitise edited questions.
    cleaned: List[Dict[str, Any]] = []
    for i, q in enumerate(questions, start=1):
        text = (q.get("text") if isinstance(q, dict) else "") or ""
        text = text.strip()
        if not text:
            continue
        cleaned.append({
            "id": (q.get("id") if isinstance(q, dict) else None) or str(uuid.uuid4()),
            "ordinal": i,
            "text": text,
            "category": (q.get("category") if isinstance(q, dict) else None) or "strategic",
            "source_tier": (q.get("source_tier") if isinstance(q, dict) else None),
            "confidence_band": (q.get("confidence_band") if isinstance(q, dict) else None),
        })
    if not cleaned:
        raise HTTPException(status_code=422, detail="Edited list contained no usable questions.")
    return await _approve_solva_cycle(iid, account, note=note, questions_override=cleaned)


@router.post("/items/{kind}/{item_id}/approve")
async def approve_review_item(
    kind: str, item_id: str,
    body: Optional[ApproveIn] = None,
    account: Dict[str, Any] = Depends(get_current_account),
):
    iid = _split_uid(kind, item_id)
    note = body.note if body else None
    if kind == INBOUND_KIND:
        result = await _approve_inbound(iid, account, note)
    elif kind == BRIEFING_KIND:
        result = await _approve_briefing(iid, account)
    elif kind == STUDIO_KIND:
        result = await _approve_studio(iid, account, note)
    elif kind == SOLVA_CYCLE_KIND:
        result = await _approve_solva_cycle(iid, account, note)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown kind '{kind}'.")
    next_id = await _next_pending_item_id(account["id"], exclude_uid=f"{kind}:{iid}")
    return {"ok": True, "kind": kind, "id": iid, "next_item_id": next_id, **result}


@router.post("/items/{kind}/{item_id}/reject")
async def reject_review_item(
    kind: str, item_id: str,
    body: Optional[RejectIn] = None,
    account: Dict[str, Any] = Depends(get_current_account),
):
    iid = _split_uid(kind, item_id)
    reason = body.reason if body else None
    if kind == INBOUND_KIND:
        result = await _reject_inbound(iid, account, reason)
    elif kind == BRIEFING_KIND:
        result = await _reject_briefing(iid, account, reason)
    elif kind == STUDIO_KIND:
        result = await _reject_studio(iid, account, reason)
    elif kind == SOLVA_CYCLE_KIND:
        result = await _reject_solva_cycle(iid, account, reason)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown kind '{kind}'.")
    next_id = await _next_pending_item_id(account["id"], exclude_uid=f"{kind}:{iid}")
    return {"ok": True, "kind": kind, "id": iid, "next_item_id": next_id, **result}


@router.post("/items/{kind}/{item_id}/edit")
async def edit_review_item(
    kind: str, item_id: str,
    body: Optional[SolvaCycleEditIn] = None,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Returns a deep-link to the existing edit surface for this kind.
    The UI navigates there in-place (or opens it in an overlay).

    Phase 15.1: solva_cycle_action accepts an optional body with
    `questions: [...]` to persist edits and then approve in one step
    (per build brief decision #5)."""
    iid = _split_uid(kind, item_id)
    if kind == SOLVA_CYCLE_KIND:
        return await _edit_solva_cycle(iid, account, body)
    if kind == INBOUND_KIND:
        row = await db.inbound_queue.find_one({"id": iid}, {"_id": 0, "id": 1, "context_id": 1, "status": 1})
        if not row:
            raise HTTPException(status_code=404, detail="Queue item not found.")
        if not await _is_member(row["context_id"], account["id"]):
            raise HTTPException(status_code=403, detail="Not a member of this context.")
        # Inbound docs don't have a free-form edit surface today; the
        # routing knobs (target context / kind) live inline in the queue
        # card. The UI handles this via in-card form, so we simply
        # acknowledge the request.
        return {"ok": True, "kind": kind, "id": iid, "edit_url": None,
                "inline": True}
    if kind == BRIEFING_KIND:
        b = await db.boardpacks.find_one({"id": iid}, {"_id": 0, "id": 1, "context_id": 1})
        if not b:
            raise HTTPException(status_code=404, detail="Briefing not found.")
        if not await _is_member(b["context_id"], account["id"]):
            raise HTTPException(status_code=403, detail="Not a member of this context.")
        return {
            "ok": True, "kind": kind, "id": iid,
            "edit_url": f"/app/prepare?briefing={iid}",
            "inline": False,
        }
    if kind == STUDIO_KIND:
        # Studio edit deep-links to the block composer for the underlying
        # artefact kind. iid format: '<subkind>:<artefact_id>'.
        parts = iid.split(":", 1)
        if len(parts) != 2:
            raise HTTPException(status_code=400, detail="Studio item id must be '<subkind>:<artefact_id>'.")
        subkind, aid = parts
        a = await _resolve_studio_artefact(subkind, aid, account)
        return {
            "ok": True, "kind": kind, "id": iid,
            "edit_url": f"/app/studio/composer/{subkind}/{aid}",
            "inline": False,
            "context_id": a["context_id"],
        }
    raise HTTPException(status_code=400, detail=f"Unknown kind '{kind}'.")
