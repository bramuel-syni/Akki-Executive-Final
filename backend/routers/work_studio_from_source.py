"""
Phase C.3 — Work Studio: From-source bridge.

Bridges Solva sessions and chat artefacts into the kind-aware Work
Studio storage so the existing block composer + Enhance + Export can
operate on Solva-originated artefacts without parallel pipelines.

  POST /api/contexts/{cid}/work-studio/from-source

Body shape:
  {
    source_type: "solva_session" | "chat_artefact",
    source_id:   str,
    kind:        "briefing" | "deck" | "report",
    company_label: str (optional),
    document_type: str (optional),
    programme:     str | null
  }

What the route does, atomically:
  1. Resolves the source. solva_session → require synthesis.body.
                          chat_artefact → assemble Solva-shaped envelope
                          from the chat's assistant messages.
  2. Builds a Brief via C.1 `build_brief_from_solva` at depth=board_summary,
     fidelity=low (board-edit-friendly seed; export fidelity stays an
     independent choice at export time).
  3. Persists the Brief via C.2 `ensure_brief_persisted` — yields a
     stable `brief_id`.
  4. Inserts a kind-row in db.boardpacks / db.decks / db.reports with:
       - id, context_id, account_id, kind-specific metadata
       - title, opening_paragraph, body  (so the existing
         _seed_blocks_from_artefact picks them up cleanly when the user
         first opens the composer)
       - top-level brief_id field      (per the user's directive — no
         nested metadata; subsequent reads are simpler)
       - origin = {source_type, source_id}    (audit-friendly trail)
  5. Returns:
       {
         kind, artefact_id, brief_id,
         redirect_url: "/app/studio/composer/{kind}/{artefact_id}"
       }

This route does NOT touch the C.1 generators or Solva engines. It
reads and writes only.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, require_context_membership, write_audit
from work_studio import (
    build_brief_from_solva,
    ensure_brief_persisted,
    brief_to_dict,
)

logger = logging.getLogger("akki.work_studio.from_source")

router = APIRouter(prefix="/api")

_VALID_KINDS = {"briefing", "deck", "report"}
_VALID_SOURCES = {"solva_session", "chat_artefact"}

# Kind-aware Mongo collection map. Mirrors `studio_blocks._artefact_collection`.
_KIND_COLLECTION = {
    "briefing": "boardpacks",
    "deck": "decks",
    "report": "reports",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Brief → artefact prose assembly (so studio_blocks._seed_blocks_from_artefact
# does the right thing on first composer open).
# ---------------------------------------------------------------------------
def _assemble_prose(brief_dict: Dict[str, Any]) -> Dict[str, str]:
    """Flatten the Brief sections into title / opening_paragraph / body
    that the existing seed-blocks helper already understands.

    The block composer's `_seed_blocks_from_artefact` reads:
       briefing → title, opening_paragraph, items[], body
       deck     → title, slides[], body
       report   → title, body
    We hand it title + opening_paragraph + body and let the seeder
    paragraph-split the body. Sections with kicker labels become inline
    headings via blank-line breaks (the splitter respects them)."""
    title = brief_dict.get("title") or "Untitled brief"
    opening = brief_dict.get("cover_lead_paragraph") or ""
    chunks: List[str] = []
    for sec in brief_dict.get("sections") or []:
        sec_title = (sec.get("title") or "").strip()
        kicker = (sec.get("kicker") or "").strip()
        if sec_title:
            chunks.append(sec_title)
        if kicker:
            chunks.append(f"({kicker})")
        for para in sec.get("body_paragraphs") or []:
            if para and para.strip():
                chunks.append(para.strip())
        for b in sec.get("bullets") or []:
            if b and b.strip():
                chunks.append(f"• {b.strip()}")
        for tbl in sec.get("tables") or []:
            tbl_title = (tbl.get("title") or "").strip()
            if tbl_title:
                chunks.append(tbl_title)
            headers = tbl.get("headers") or []
            if headers:
                chunks.append(" | ".join(str(h) for h in headers))
            for row in tbl.get("rows") or []:
                chunks.append(" | ".join(str(c) for c in row))
        chunks.append("")  # blank line — paragraph break for the seeder
    closing = brief_dict.get("closing_recap") or ""
    if closing:
        chunks.append(closing)
    body = "\n\n".join(c for c in chunks if c.strip())
    return {
        "title": title,
        "opening_paragraph": opening,
        "body": body,
    }


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------
class FromSourceRequest(BaseModel):
    source_type: Literal["solva_session", "chat_artefact"]
    source_id: str = Field(..., min_length=1, max_length=128)
    kind: Literal["briefing", "deck", "report"]
    company_label: str = Field("Akki", max_length=80)
    document_type: str = Field("", max_length=80)
    programme: Optional[str] = Field(None, max_length=80)


# ---------------------------------------------------------------------------
# Source resolvers
# ---------------------------------------------------------------------------
async def _resolve_solva_session(account_id: str, source_id: str) -> Dict[str, Any]:
    session = await db.solva_v2_sessions.find_one(
        {"id": source_id, "account_id": account_id},
    )
    if not session:
        raise HTTPException(status_code=404, detail="solva_session_not_found")
    if not (session.get("synthesis") or {}).get("body"):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "synthesis_not_ready",
                "message": ("Run this Solva session through synthesis "
                            "before composing from it."),
            },
        )
    return session


async def _resolve_chat_envelope(account_id: str, source_id: str) -> Dict[str, Any]:
    """Reduce a chat down to a Solva-shaped envelope so the C.1 builder
    works without a parallel code path. Mirrors the same shaping the C.1
    export endpoint already does for `chat_artefact`."""
    chat = await db.chats.find_one({"id": source_id, "account_id": account_id})
    if not chat:
        raise HTTPException(status_code=404, detail="chat_not_found")
    msgs_cursor = db.chat_messages.find({"chat_id": source_id}).sort("created_at", 1)
    msgs = await msgs_cursor.to_list(2000)
    full = "\n\n".join((m.get("content") or "").strip()
                       for m in msgs if m.get("role") == "assistant")
    if not full.strip():
        raise HTTPException(
            status_code=409,
            detail={
                "code": "chat_empty",
                "message": "This chat has no assistant content to compose from yet.",
            },
        )
    return {
        "id": chat["id"],
        "submodule": "seek_clarity",
        "intent": chat.get("title") or "Chat artefact",
        "synthesis": {
            "body": full,
            "claims": [],
            "recommendations": [],
            "validation": {
                "verdict": "informational", "confidence": 0,
                "validator_provider": "—", "validator_model": "—",
            },
        },
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.post("/contexts/{context_id}/work-studio/from-source")
async def create_from_source(
    context_id: str,
    body: FromSourceRequest,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    if body.kind not in _VALID_KINDS:
        raise HTTPException(status_code=422, detail="unsupported_kind")
    if body.source_type not in _VALID_SOURCES:
        raise HTTPException(status_code=422, detail="unsupported_source_type")

    account = ctx["account"]
    account_id = account["id"]

    # 1) Resolve source -----------------------------------------------------
    if body.source_type == "solva_session":
        envelope = await _resolve_solva_session(account_id, body.source_id)
    else:
        envelope = await _resolve_chat_envelope(account_id, body.source_id)

    # 2) Build Brief at LOW fidelity (per user's call #2 — composer-edit
    # friendly seed; export fidelity is independent at export time).
    document_type = body.document_type or {
        "briefing": "Board Briefing",
        "deck": "Board Deck",
        "report": "Report",
    }[body.kind]

    brief = build_brief_from_solva(
        envelope,
        company_label=body.company_label or "Akki",
        document_type=document_type,
        programme=body.programme,
        depth="board_summary",
        fidelity="low",
    )

    # 3) Persist Brief — yields a stable brief_id (idempotent).
    parent = await ensure_brief_persisted(
        db,
        brief=brief,
        account_id=account_id,
        context_id=context_id,
        source_type=body.source_type,
        source_id=body.source_id,
    )
    brief_id = parent["id"]
    revision_id = parent["active_revision_id"]

    # 4) Insert kind-row.  The block composer's existing
    # _seed_blocks_from_artefact reads title / opening_paragraph / body
    # — assemble them from the Brief snapshot now.
    brief_dict = brief_to_dict(brief)
    prose = _assemble_prose(brief_dict)
    artefact_id = str(uuid.uuid4())
    now = _now_iso()

    artefact_row: Dict[str, Any] = {
        "id": artefact_id,
        "context_id": context_id,
        "account_id": account_id,
        "title": prose["title"],
        "opening_paragraph": prose["opening_paragraph"],
        "body": prose["body"],
        "status": "draft",
        # Top-level brief_id pointer per the user's directive.
        "brief_id": brief_id,
        "active_revision_id": revision_id,
        # Audit-friendly trail of where this came from.
        "origin": {
            "source_type": body.source_type,
            "source_id": body.source_id,
            "company_label": body.company_label or "Akki",
            "document_type": document_type,
            "programme": body.programme,
        },
        "created_at": now,
        "updated_at": now,
    }
    # Decks have a few legacy fields the existing UI expects; populate
    # them defensively with the Brief title so list views render cleanly.
    if body.kind == "deck":
        artefact_row["slides"] = []
        artefact_row["subject"] = prose["title"]
    if body.kind == "report":
        artefact_row["subject"] = prose["title"]

    coll_name = _KIND_COLLECTION[body.kind]
    coll = getattr(db, coll_name)
    await coll.insert_one(artefact_row)

    # 5) Audit and return.
    try:
        await write_audit(
            account_id=account_id, context_id=context_id,
            action="work_studio.from_source.created", target_id=artefact_id,
            metadata={
                "kind": body.kind,
                "artefact_id": artefact_id,
                "brief_id": brief_id,
                "source_type": body.source_type,
                "source_id": body.source_id,
            },
        )
    except Exception:
        logger.exception("from_source: audit write failed (non-fatal)")

    return {
        "kind": body.kind,
        "artefact_id": artefact_id,
        "brief_id": brief_id,
        "active_revision_id": revision_id,
        "redirect_url": f"/app/studio/composer/{body.kind}/{artefact_id}",
    }
