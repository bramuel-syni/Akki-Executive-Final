"""Human-to-human collaboration — threaded comments + @mentions on artefacts.

Artefacts supported: signal, briefing, document, simulation. A comment always
lives inside a context_id and is scoped to members of that context. Comments
are flat with optional `parent_id` (single-level replies) to keep the UX simple.

@mentions are parsed from the body text (@name or @email) and resolved to
account ids against current context members; resolved mentions trigger a
`mention.created` event that frontends can render as a bell/inbox later.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, now, iso, write_audit, require_context_membership

router = APIRouter(prefix="/api")


ARTEFACT_COLLECTIONS = {
    "signal":     "signals",
    "briefing":   "briefings",
    "document":   "documents",
    "simulation": "simulations",
    "share":      "shares",
}

MENTION_RE = re.compile(r"@([A-Za-z0-9_.\-@]+)")


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    parent_id: Optional[str] = Field(default=None, max_length=64)


def _strip(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    out.pop("_id", None)
    return out


async def _assert_artefact_exists(
    *, context_id: str, artefact_type: str, artefact_id: str,
) -> None:
    coll = ARTEFACT_COLLECTIONS.get(artefact_type)
    if not coll:
        raise HTTPException(status_code=400, detail=f"Unsupported artefact type '{artefact_type}'")
    if artefact_type == "simulation":
        ok = await db.simulations.find_one(
            {"id": artefact_id, "context_id": context_id, "status": "active"}, {"_id": 0, "id": 1}
        )
    elif artefact_type == "document":
        ok = await db.documents.find_one(
            {"id": artefact_id, "context_id": context_id}, {"_id": 0, "id": 1}
        )
    elif artefact_type == "briefing":
        ok = await db.briefings.find_one(
            {"id": artefact_id, "context_id": context_id, "status": "active"}, {"_id": 0, "id": 1}
        )
    elif artefact_type == "share":
        # Shares are cross-context artefacts — we still require the caller is a
        # member of the share's *source* context_id (standard membership dep).
        ok = await db.shares.find_one(
            {"id": artefact_id, "context_id": context_id, "revoked_at": None},
            {"_id": 0, "id": 1},
        )
    else:  # signal
        ok = await db.signals.find_one(
            {"id": artefact_id, "context_id": context_id, "status": "active"}, {"_id": 0, "id": 1}
        )
    if not ok:
        raise HTTPException(status_code=404, detail=f"{artefact_type.title()} not found")


async def _resolve_mentions(context_id: str, body: str) -> List[Dict[str, str]]:
    """Scan body text for @tokens, resolve to {account_id, display}."""
    tokens = MENTION_RE.findall(body)
    if not tokens:
        return []
    # Normalise: strip trailing punctuation
    cleaned = list({t.rstrip(".,;:!?") for t in tokens if t})
    if not cleaned:
        return []
    # Find context members
    member_rows = await db.memberships.find(
        {"context_id": context_id, "status": "active"},
        {"_id": 0, "account_id": 1},
    ).to_list(500)
    account_ids = [m["account_id"] for m in member_rows]
    if not account_ids:
        return []
    # Find accounts matching any token by email-prefix or name first-name (case-insensitive)
    accounts = await db.accounts.find(
        {"id": {"$in": account_ids}},
        {"_id": 0, "id": 1, "email": 1, "name": 1},
    ).to_list(500)
    resolved: List[Dict[str, str]] = []
    seen_ids: set = set()
    lc_tokens = {t.lower() for t in cleaned}
    for a in accounts:
        email = (a.get("email") or "").lower()
        email_prefix = email.split("@")[0]
        name = (a.get("name") or "").lower()
        first_name = name.split(" ")[0] if name else ""
        matched = False
        for tok in lc_tokens:
            if not tok:
                continue
            if tok == email or tok == email_prefix or (first_name and tok == first_name):
                matched = True
                break
        if matched and a["id"] not in seen_ids:
            seen_ids.add(a["id"])
            resolved.append({
                "account_id": a["id"],
                "email": a.get("email", ""),
                "name": a.get("name", ""),
            })
    return resolved


@router.get("/contexts/{context_id}/{artefact_type}/{artefact_id}/comments")
async def list_comments(
    artefact_type: str,
    artefact_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if artefact_type not in ARTEFACT_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Unsupported artefact type")
    rows = await db.comments.find(
        {
            "context_id": ctx["context"]["id"],
            "artefact_type": artefact_type,
            "artefact_id": artefact_id,
            "status": "active",
        },
        {"_id": 0},
    ).sort("created_at", 1).to_list(500)
    return rows


@router.post("/contexts/{context_id}/{artefact_type}/{artefact_id}/comments")
async def create_comment(
    artefact_type: str,
    artefact_id: str,
    body: CommentIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    context_id = ctx["context"]["id"]
    if artefact_type not in ARTEFACT_COLLECTIONS:
        raise HTTPException(status_code=400, detail="Unsupported artefact type")
    await _assert_artefact_exists(
        context_id=context_id, artefact_type=artefact_type, artefact_id=artefact_id,
    )
    if body.parent_id:
        parent = await db.comments.find_one(
            {"id": body.parent_id, "context_id": context_id, "status": "active"},
            {"_id": 0, "id": 1, "artefact_id": 1},
        )
        if not parent or parent.get("artefact_id") != artefact_id:
            raise HTTPException(status_code=400, detail="parent_id does not reference a valid comment on this artefact")

    mentions = await _resolve_mentions(context_id, body.body)

    comment_id = str(uuid.uuid4())
    created_at = iso(now())
    doc = {
        "id": comment_id,
        "context_id": context_id,
        "artefact_type": artefact_type,
        "artefact_id": artefact_id,
        "parent_id": body.parent_id,
        "author_id": ctx["account"]["id"],
        "author_name": ctx["account"].get("name") or ctx["account"].get("email", ""),
        "author_email": ctx["account"].get("email", ""),
        "body": body.body,
        "mentions": mentions,
        "created_at": created_at,
        "status": "active",
    }
    await db.comments.insert_one(doc)

    # Drop a "mention" record per resolved user so they can be pulled into an inbox later.
    for m in mentions:
        if m["account_id"] == ctx["account"]["id"]:
            continue  # don't notify self-mentions
        await db.mentions.insert_one({
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "target_account_id": m["account_id"],
            "source_account_id": ctx["account"]["id"],
            "source_name": doc["author_name"],
            "artefact_type": artefact_type,
            "artefact_id": artefact_id,
            "comment_id": comment_id,
            "preview": (body.body[:160] + "…") if len(body.body) > 160 else body.body,
            "created_at": created_at,
            "read": False,
        })

    await write_audit(
        context_id, ctx["account"]["id"], "comment.created", artefact_type, artefact_id,
        {"comment_id": comment_id, "mentions": len(mentions), "is_reply": bool(body.parent_id)},
    )
    return _strip(doc)


@router.delete("/contexts/{context_id}/comments/{comment_id}")
async def delete_comment(
    comment_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    context_id = ctx["context"]["id"]
    doc = await db.comments.find_one(
        {"id": comment_id, "context_id": context_id, "status": "active"}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Comment not found")
    # Only the author or a context admin/owner may delete.
    is_author = doc.get("author_id") == ctx["account"]["id"]
    is_admin = (
        ctx["context"].get("owner_account_id") == ctx["account"]["id"]
        or ctx.get("membership", {}).get("sub_role") == "admin"
    )
    if not (is_author or is_admin):
        raise HTTPException(status_code=403, detail="Only the author or a context admin may delete")
    await db.comments.update_one(
        {"id": comment_id, "context_id": context_id},
        {"$set": {"status": "deleted", "deleted_at": iso(now())}},
    )
    await write_audit(
        context_id, ctx["account"]["id"], "comment.deleted",
        doc.get("artefact_type", "comment"), doc.get("artefact_id"),
        {"comment_id": comment_id},
    )
    return {"ok": True}


@router.get("/contexts/{context_id}/mentions")
async def list_my_mentions(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    unread_only: bool = False,
    limit: int = 50,
):
    q: Dict[str, Any] = {
        "context_id": ctx["context"]["id"],
        "target_account_id": ctx["account"]["id"],
    }
    if unread_only:
        q["read"] = False
    rows = await db.mentions.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return rows


@router.post("/contexts/{context_id}/mentions/{mention_id}/read")
async def mark_mention_read(
    mention_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.mentions.update_one(
        {
            "id": mention_id,
            "context_id": ctx["context"]["id"],
            "target_account_id": ctx["account"]["id"],
        },
        {"$set": {"read": True, "read_at": iso(now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mention not found")
    return {"ok": True}
