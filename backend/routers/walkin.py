"""'Walk in with this question' — sharpening companion across artefacts.

Single-purpose endpoint that, given any AKKI artefact (brief, minutes
narrative, deck), generates exactly ONE crystalline question the user
should walk into their next conversation with. Cheap (Sonnet, no deep
budget), cached on the artefact, idempotent.

This is the iter58 improvement: a calm, repeated touch across every
generated artefact that turns AKKI from "tool that wrote you something"
into "colleague that handed you the next question". Surfaced at the
bottom of the brief detail, the minutes narrative panel, and the deck
review step.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, get_current_account, iso, now

logger = logging.getLogger("akki.walkin")

router = APIRouter(prefix="/api/walkin", tags=["walkin"])


# Three artefact kinds we currently support. Adding a kind = adding a
# (collection_name, content_extractor) entry below.
ARTEFACT_HANDLERS: Dict[str, Dict[str, Any]] = {
    "brief": {
        "collection": "briefs",
        "title_field": "title",
        "content_field": "body",
    },
    "minutes": {
        "collection": "documents",
        "title_field": "name",
        # For minutes the narrative lives at minutes_narrative.body
        "content_path": ["minutes_narrative", "body"],
    },
    "deck": {
        "collection": "decks",
        "title_field": "title",
        # We assemble the deck content client-side from slides.
        "content_path": ["__deck__"],
    },
}


class WalkinIn(BaseModel):
    kind: Literal["brief", "minutes", "deck"]
    artefact_id: str = Field(min_length=4, max_length=80)
    context_id: str = Field(min_length=4, max_length=80)


def _extract_content(kind: str, doc: Dict[str, Any]) -> tuple[str, str]:
    handler = ARTEFACT_HANDLERS[kind]
    title = doc.get(handler["title_field"], "(untitled)")
    if "content_field" in handler:
        return title, (doc.get(handler["content_field"]) or "")
    if handler.get("content_path") == ["__deck__"]:
        slides = doc.get("slides") or []
        text = "\n\n".join(
            f"## {s.get('title','')}\n{s.get('body_md','')}"
            for s in slides if isinstance(s, dict)
        )
        return title, text
    if "content_path" in handler:
        v: Any = doc
        for k in handler["content_path"]:
            if not isinstance(v, dict):
                v = None
                break
            v = v.get(k)
        return title, (v or "")
    return title, ""


@router.post("")
async def walkin_question(
    body: WalkinIn,
    account: Dict[str, Any] = Depends(get_current_account),
):
    handler = ARTEFACT_HANDLERS.get(body.kind)
    if not handler:
        raise HTTPException(status_code=400, detail=f"Unsupported artefact kind: {body.kind}")

    coll = db[handler["collection"]]
    artefact = await coll.find_one(
        {"id": body.artefact_id, "context_id": body.context_id},
        {"_id": 0},
    )
    if not artefact:
        raise HTTPException(status_code=404, detail="Artefact not found.")

    # Membership check — same gate as everywhere else.
    membership = await db.memberships.find_one(
        {"account_id": account["id"], "context_id": body.context_id, "status": "active"},
        {"_id": 0, "role": 1},
    )
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of that context.")

    # If we've cached one already, return it. The user can ask for a fresh
    # one via ?regenerate=true if they want.
    cached = artefact.get("walkin_question")
    if cached and isinstance(cached, dict) and cached.get("body"):
        return {"ok": True, "walkin_question": cached, "cached": True}

    title, content = _extract_content(body.kind, artefact)
    if not content or len(content.strip()) < 80:
        raise HTTPException(
            status_code=400,
            detail="Artefact content too short to extract a meaningful walk-in question.",
        )

    # Iter61 — context hint: pull the active context's name + 3 most recent
    # un-archived signals so the question feels like it's coming from
    # someone who actually sits on this board, not a generic helper. Same
    # tier (Sonnet, free of deep budget) — we just give the planner more
    # to work with.
    ctx = await db.contexts.find_one(
        {"id": body.context_id}, {"_id": 0, "name": 1}
    )
    ctx_name = (ctx or {}).get("name") or "the company"
    recent_signals = await db.signals.find(
        {"context_id": body.context_id, "status": {"$ne": "archived"}},
        {"_id": 0, "title": 1, "kind": 1},
    ).sort("created_at", -1).to_list(length=3)
    signal_lines = "\n".join(
        f"  · {s.get('title','(untitled)')} ({s.get('kind') or 'signal'})"
        for s in recent_signals
    )
    context_hint = (
        f"\nCONTEXT: {ctx_name}\n"
        + (f"RECENT SIGNALS in this room:\n{signal_lines}\n" if signal_lines else "")
        + "\nThe question should feel like it's coming from someone who sits "
        "on this board and remembers what's actually been discussed lately, "
        "not a generic helper. Where natural, lean into the room's specifics.\n"
    )

    prompt = (
        "Read the artefact below. Return ONE crystalline question the user "
        "should walk into their next conversation with — the kind that "
        "earns a sharper answer than the artefact itself contains. Calm, "
        "specific, no jargon. AKKI editorial voice. Maximum 30 words.\n"
        + context_hint
        + f"\nARTEFACT TITLE: {title}\n\n"
        f"ARTEFACT CONTENT:\n{content[:10000]}\n\n"
        "Return STRICT JSON: {\"question\": \"<the question>\", \"why\": \"<one short line on why this question>\"}"
    )

    from llm_service import call_llm
    llm_out = await call_llm(
        module="walkin.question",
        user_query=prompt,
        response_format="json",
        tier="standard",  # Sonnet — cheap, never charges deep budget.
    )

    import json
    import re
    raw = (llm_out.get("response") or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        parsed = json.loads(m.group(0)) if m else None

    if not parsed or not parsed.get("question"):
        raise HTTPException(status_code=502, detail="Walk-in generator returned malformed response.")

    qrec = {
        "id": str(uuid.uuid4()),
        "body": parsed["question"].strip()[:300],
        "why": (parsed.get("why") or "").strip()[:200] or None,
        "model": llm_out.get("model"),
        "generated_at": iso(now()),
        "generated_by": account["id"],
    }
    await coll.update_one(
        {"id": body.artefact_id, "context_id": body.context_id},
        {"$set": {"walkin_question": qrec, "updated_at": iso(now())}},
    )
    return {"ok": True, "walkin_question": qrec, "cached": False}


@router.post("/regenerate")
async def walkin_regenerate(
    body: WalkinIn,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Force a fresh question (clears cache, then calls walkin_question)."""
    handler = ARTEFACT_HANDLERS.get(body.kind)
    if not handler:
        raise HTTPException(status_code=400, detail="Unsupported artefact kind.")
    await db[handler["collection"]].update_one(
        {"id": body.artefact_id, "context_id": body.context_id},
        {"$unset": {"walkin_question": ""}},
    )
    return await walkin_question(body, account)
