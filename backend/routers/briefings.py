"""M12 — Briefings. Auto-compose briefings from generated signals, export PDF/DOCX."""
from __future__ import annotations

import io
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from briefings_service import build_briefing_prompt, render_pdf, render_docx
from llm_service import call_llm as llm_call_llm, parse_json_response

from core import (
    db, now, iso, write_audit, require_context_membership,
    gather_context_object, docs_overall_trust,
)

router = APIRouter(prefix="/api")


class BriefingCreateIn(BaseModel):
    signal_ids: Optional[List[str]] = None
    title: Optional[str] = Field(default=None, max_length=120)


def _serialise_briefing(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    out.pop("_id", None)
    return out


@router.post("/contexts/{context_id}/briefings")
async def create_briefing(
    body: BriefingCreateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    context_id = ctx["context"]["id"]
    context_name = ctx["context"]["name"]

    my_membership = await db.memberships.find_one(
        {"context_id": context_id, "account_id": ctx["account"]["id"], "status": "active"},
        {"_id": 0, "role": 1},
    )
    my_role = (my_membership or {}).get("role") or "executive"

    q: Dict[str, Any] = {"context_id": context_id, "status": "active"}
    if body.signal_ids:
        q["id"] = {"$in": body.signal_ids}
    signals = await db.signals.find(q, {"_id": 0}).sort("created_at", -1).to_list(20)
    if not signals:
        raise HTTPException(
            status_code=400,
            detail="No signals to brief on. Generate signals first, or select specific signal ids.",
        )

    all_doc_ids: List[str] = []
    for s in signals:
        for src in (s.get("sources") or []):
            d = src.get("doc_id")
            if d and d not in all_doc_ids:
                all_doc_ids.append(d)
    docs = await db.documents.find(
        {"context_id": context_id, "id": {"$in": all_doc_ids}, "status": {"$ne": "archived"}},
        {"_id": 0, "id": 1, "name": 1, "data_trust": 1},
    ).to_list(50)
    docs_by_id = {d["id"]: d for d in docs}

    ctx_obj = await gather_context_object(context_id)

    prompt = build_briefing_prompt(
        context_name=context_name,
        role=my_role,
        context_object=ctx_obj,
        signals=[{**s, "id_for_prompt": s["id"]} for s in signals],
        doc_ids_in_scope=all_doc_ids,
    )
    llm_out = await llm_call_llm(
        module="briefing",
        user_query=prompt,
        context_object=ctx_obj,
        session_context={"session_id": f"briefing-{context_id}"},
        data_trust={"overall": docs_overall_trust(docs)},
        response_format="json",
    )
    parsed = parse_json_response(llm_out.get("response", ""))
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=502,
            detail=f"LLM did not return a valid briefing. Mode={llm_out.get('mode')}. Raw: {llm_out.get('response', '')[:500]}",
        )

    sig_by_id = {s["id"]: s for s in signals}
    items_raw = parsed.get("items") or []
    items: List[Dict[str, Any]] = []
    for raw in items_raw[:10]:
        sid = raw.get("signal_id")
        sig = sig_by_id.get(sid) if isinstance(sid, str) else None
        if not sig:
            continue
        items.append({
            "signal_id": sig["id"],
            "signal_type": sig.get("type"),
            "signal_headline": sig.get("headline"),
            "confidence": sig.get("confidence"),
            "sources": sig.get("sources", []),
            "evidence": (raw.get("evidence") or "")[:1500],
            "question": (raw.get("question") or "")[:600],
        })

    if not items:
        raise HTTPException(status_code=502, detail="Briefing produced no usable items.")

    latest = await db.briefings.find_one(
        {"context_id": context_id}, {"_id": 0, "version": 1}, sort=[("version", -1)]
    )
    version = (latest or {}).get("version", 0) + 1

    created_at = iso(now())
    briefing_id = str(uuid.uuid4())
    title = (body.title or parsed.get("title") or f"{context_name} — briefing")[:120]
    doc = {
        "id": briefing_id,
        "context_id": context_id,
        "context_name": context_name,
        "version": version,
        "title": title,
        "role": my_role,
        "opening_paragraph": (parsed.get("opening_paragraph") or "")[:2500],
        "items": items,
        "closing_note": (parsed.get("closing_note") or None),
        "source_doc_ids": list(docs_by_id.keys()),
        "signal_ids": [s["id"] for s in signals],
        "data_trust": docs_overall_trust(docs),
        "mode": llm_out.get("mode"),
        "shielding_masked": llm_out.get("shielding", {}).get("identifiers_masked", 0),
        "created_by": ctx["account"]["id"],
        "created_at": created_at,
        "status": "active",
    }
    await db.briefings.insert_one(doc)
    await write_audit(
        context_id, ctx["account"]["id"], "briefing.created", "briefing", briefing_id,
        {"version": version, "items": len(items), "mode": llm_out.get("mode")},
    )
    return _serialise_briefing(doc)


@router.get("/contexts/{context_id}/briefings")
async def list_briefings(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    limit: int = 50,
    committee_id: Optional[str] = None,
):
    q: Dict[str, Any] = {"context_id": ctx["context"]["id"], "status": "active"}
    if committee_id:
        q["committee_id"] = committee_id
    rows = await db.briefings.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return rows


@router.get("/contexts/{context_id}/briefings/{briefing_id}")
async def get_briefing(
    briefing_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    doc = await db.briefings.find_one(
        {"id": briefing_id, "context_id": ctx["context"]["id"], "status": "active"},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Briefing not found")
    return doc


@router.delete("/contexts/{context_id}/briefings/{briefing_id}")
async def archive_briefing(
    briefing_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.briefings.update_one(
        {"id": briefing_id, "context_id": ctx["context"]["id"], "status": "active"},
        {"$set": {"status": "archived", "archived_at": iso(now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Briefing not found")
    await write_audit(
        ctx["context"]["id"], ctx["account"]["id"], "briefing.archived", "briefing", briefing_id, {},
    )
    return {"ok": True}


@router.get("/contexts/{context_id}/briefings/{briefing_id}/export")
async def export_briefing(
    briefing_id: str,
    fmt: str = "pdf",
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    context_id = ctx["context"]["id"]
    doc = await db.briefings.find_one(
        {"id": briefing_id, "context_id": context_id, "status": "active"}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Briefing not found")
    if fmt not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="fmt must be 'pdf' or 'docx'")

    docs = await db.documents.find(
        {"context_id": context_id, "id": {"$in": doc.get("source_doc_ids", [])}},
        {"_id": 0, "id": 1, "name": 1, "data_trust": 1},
    ).to_list(50)
    docs_by_id = {d["id"]: d for d in docs}

    if fmt == "pdf":
        payload = render_pdf(doc, docs_by_id)
        media = "application/pdf"
        suffix = "pdf"
    else:
        payload = render_docx(doc, docs_by_id)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        suffix = "docx"

    safe_title = "".join(c for c in (doc.get("title") or "briefing") if c.isalnum() or c in " -_.")[:60].strip() or "briefing"
    filename = f"{safe_title}_v{doc.get('version', 1)}.{suffix}"

    await write_audit(
        context_id, ctx["account"]["id"], "briefing.exported", "briefing", briefing_id,
        {"format": fmt},
    )
    return StreamingResponse(
        io.BytesIO(payload),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
