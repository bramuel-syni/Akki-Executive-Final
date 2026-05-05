"""M12 — Briefings. Auto-compose briefings from generated signals, export PDF/DOCX."""
from __future__ import annotations

import io
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from briefings_service import build_briefing_prompt, render_pdf, render_docx, render_board_deck_pdf
from llm_service import call_llm as llm_call_llm, parse_json_response
from citation_refs import build_references

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
    # Reading Viewer Phase 1: per-item `references[]` rolls each item's
    # `sources[]` into the new shape, plus a top-level union of all refs.
    items = out.get("items") or []
    union: List[Dict[str, Any]] = []
    seen_doc_ids: set = set()
    for it in items:
        item_refs = build_references(it.get("sources") or [])
        it["references"] = item_refs
        for r in item_refs:
            if r["doc_id"] not in seen_doc_ids:
                seen_doc_ids.add(r["doc_id"])
                union.append(r)
    out["references"] = union
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

    latest = await db.boardpacks.find_one(
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
        "shielding": llm_out.get("shielding", {}),
        "created_by": ctx["account"]["id"],
        "created_at": created_at,
        "status": "active",
    }
    # Iter64 — Studio sensitivity score, identical pattern to decks.
    try:
        from studio_sensitivity import score_sensitivity
        doc["sensitivity"] = score_sensitivity(doc)
    except Exception:  # noqa: BLE001
        doc["sensitivity"] = None
    await db.boardpacks.insert_one(doc)
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
    rows = await db.boardpacks.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    # Annotate each row with is_read for the current account so the rail can
    # show read/unread state. Read = explicit "Mark as read" OR ≥70%
    # scroll-depth (frontend stamps either via /mark-read).
    if rows:
        ids = [r["id"] for r in rows]
        read_cursor = db.briefing_reads.find(
            {"briefing_id": {"$in": ids}, "account_id": ctx["account"]["id"]},
            {"_id": 0, "briefing_id": 1, "read_at": 1, "read_via": 1},
        )
        read_map: Dict[str, Dict[str, Any]] = {}
        async for rr in read_cursor:
            read_map[rr["briefing_id"]] = {
                "read_at": rr.get("read_at"),
                "read_via": rr.get("read_via") or "manual",
            }
        for r in rows:
            rd = read_map.get(r["id"])
            r["is_read"] = bool(rd)
            r["read_at"] = (rd or {}).get("read_at")
            r["read_via"] = (rd or {}).get("read_via")
    return [_serialise_briefing(r) for r in rows]


class MarkReadIn(BaseModel):
    via: str = Field(default="manual", pattern=r"^(manual|scroll)$")


@router.post("/contexts/{context_id}/briefings/{briefing_id}/mark-read")
async def mark_briefing_read(
    briefing_id: str,
    body: MarkReadIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Stamp this briefing as read for the current account. Idempotent —
    upserts on (briefing_id, account_id) so repeated calls just refresh
    the timestamp + via channel.

    "Read" is now a real signal:
      • via='manual' — user clicked "Mark as read"
      • via='scroll' — frontend reached ≥70% scroll depth
    Either is enough to flip the rail badge.
    """
    doc = await db.boardpacks.find_one(
        {"id": briefing_id, "context_id": ctx["context"]["id"], "status": "active"},
        {"_id": 0, "id": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Briefing not found")
    now_iso = iso(now())
    await db.briefing_reads.update_one(
        {"briefing_id": briefing_id, "account_id": ctx["account"]["id"]},
        {
            "$set": {
                "briefing_id": briefing_id,
                "account_id": ctx["account"]["id"],
                "context_id": ctx["context"]["id"],
                "read_at": now_iso,
                "read_via": body.via,
            },
            "$setOnInsert": {"first_read_at": now_iso},
        },
        upsert=True,
    )
    return {"ok": True, "read_at": now_iso, "read_via": body.via}


@router.get("/contexts/{context_id}/briefings/{briefing_id}")
async def get_briefing(
    briefing_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    doc = await db.boardpacks.find_one(
        {"id": briefing_id, "context_id": ctx["context"]["id"], "status": "active"},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Briefing not found")
    return _serialise_briefing(doc)


@router.delete("/contexts/{context_id}/briefings/{briefing_id}")
async def archive_briefing(
    briefing_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.boardpacks.update_one(
        {"id": briefing_id, "context_id": ctx["context"]["id"], "status": "active"},
        {"$set": {"status": "archived", "archived_at": iso(now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Briefing not found")
    await write_audit(
        ctx["context"]["id"], ctx["account"]["id"], "briefing.archived", "briefing", briefing_id, {},
    )
    return {"ok": True}


@router.post("/contexts/{context_id}/briefings/{briefing_id}/speaking-notes")
async def draft_speaking_notes(
    briefing_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Generate 3 speaker-note bullets per briefing item.

    What you would actually *say* when each slide is on screen. Persists onto
    briefing.items[i].speaking_notes so subsequent board-deck exports render
    them under the slide. Re-calling overwrites the notes for every item.
    """
    context_id = ctx["context"]["id"]
    context_name = ctx["context"]["name"]
    doc = await db.boardpacks.find_one(
        {"id": briefing_id, "context_id": context_id, "status": "active"}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Briefing not found")

    items = doc.get("items", []) or []
    if not items:
        raise HTTPException(status_code=400, detail="Briefing has no items to narrate.")

    ctx_obj = await gather_context_object(context_id)
    co_answers = (ctx_obj or {}).get("answers") or {}
    persona_bits = []
    for k in ("q1_role", "q3_focus_areas", "q6_lens_preference", "q7_analytical_style"):
        v = co_answers.get(k)
        if v:
            persona_bits.append(f"  · {v}")
    persona_block = "\n".join(persona_bits) if persona_bits else "  · (generic board lens)"

    # Build a single prompt that returns notes for every item — one LLM call per
    # briefing keeps latency + cost predictable.
    items_block_lines: List[str] = []
    for i, it in enumerate(items, 1):
        items_block_lines.append(
            f"[item {i}] {it.get('signal_type','signal').upper()} · "
            f"{it.get('confidence','medium')} confidence\n"
            f"HEADLINE: {it.get('signal_headline','')}\n"
            f"EVIDENCE: {(it.get('evidence') or '')[:800]}\n"
            f"QUESTION: {it.get('question','')}\n"
        )
    items_block = "\n---\n".join(items_block_lines)

    prompt = (
        f"You are writing the speaker notes for a board deck — the lines "
        f"directly under each slide the presenter will glance at while the "
        f"slide is on screen. Not narration, not a script. Three short, "
        f"spoken-voice bullets per item. How a sharp chair or CFO would "
        f"frame the number, land the implication, and set up the question.\n\n"
        f"[WHO'S PRESENTING]\n{persona_block}\n\n"
        f"[BOARD / CONTEXT]\n  · {context_name}\n\n"
        f"[ITEMS — {len(items)} in total]\n{items_block}\n\n"
        f"For every item produce exactly 3 bullets. Each bullet ≤ 22 words, "
        f"spoken voice, no lists of lists, no filler. The first bullet "
        f"states the fact/number. The second bullet lands why it matters. "
        f"The third bullet flags what to watch / escalate next.\n\n"
        'Return JSON only: {"notes":[{"item":1,"bullets":["...","...","..."]},...]}. '
        f"Produce notes for every item from 1..{len(items)} in order."
    )

    llm_out = await llm_call_llm(
        module="briefing.speaking_notes",
        user_query=prompt,
        context_object=ctx_obj,
        session_context={"session_id": f"notes-{briefing_id}"},
        data_trust={"overall": "mixed"},
        response_format="json",
    )
    parsed = parse_json_response(llm_out.get("response", ""))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("notes"), list):
        raise HTTPException(
            status_code=502,
            detail=f"LLM did not return valid speaking notes. Mode={llm_out.get('mode')}.",
        )

    notes_by_item = {}
    for n in parsed["notes"]:
        if not isinstance(n, dict):
            continue
        idx = n.get("item")
        bullets = n.get("bullets")
        if isinstance(idx, int) and isinstance(bullets, list):
            clean = [str(b).strip()[:200] for b in bullets if str(b).strip()][:3]
            if clean:
                notes_by_item[idx] = clean

    # Stamp notes onto items (by index; item idx is 1-based above)
    updated_items: List[Dict[str, Any]] = []
    for i, it in enumerate(items, 1):
        new_it = dict(it)
        new_it["speaking_notes"] = notes_by_item.get(i, [])
        updated_items.append(new_it)

    await db.boardpacks.update_one(
        {"id": briefing_id, "context_id": context_id},
        {"$set": {"items": updated_items, "speaking_notes_at": iso(now()),
                  "shielding": llm_out.get("shielding", {})}},
    )
    await write_audit(
        context_id, ctx["account"]["id"], "briefing.speaking_notes.drafted",
        "briefing", briefing_id,
        {"items_narrated": sum(1 for b in notes_by_item.values() if b),
         "mode": llm_out.get("mode")},
    )

    refreshed = await db.boardpacks.find_one(
        {"id": briefing_id, "context_id": context_id}, {"_id": 0},
    )
    return {
        "briefing": refreshed,
        "items_narrated": sum(1 for b in notes_by_item.values() if b),
        "mode": llm_out.get("mode"),
        "shielding": llm_out.get("shielding", {}),
    }


@router.get("/contexts/{context_id}/briefings/{briefing_id}/export")
async def export_briefing(
    briefing_id: str,
    fmt: str = "pdf",
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    context_id = ctx["context"]["id"]
    doc = await db.boardpacks.find_one(
        {"id": briefing_id, "context_id": context_id, "status": "active"}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Briefing not found")
    if fmt not in ("pdf", "docx", "board_deck"):
        raise HTTPException(status_code=400, detail="fmt must be 'pdf', 'docx', or 'board_deck'")

    docs = await db.documents.find(
        {"context_id": context_id, "id": {"$in": doc.get("source_doc_ids", [])}},
        {"_id": 0, "id": 1, "name": 1, "data_trust": 1},
    ).to_list(50)
    docs_by_id = {d["id"]: d for d in docs}

    if fmt == "pdf":
        payload = render_pdf(doc, docs_by_id)
        media = "application/pdf"
        suffix = "pdf"
    elif fmt == "board_deck":
        payload = render_board_deck_pdf(doc, docs_by_id)
        media = "application/pdf"
        suffix = "deck.pdf"
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


# ═════════════════════════════════════════════════════════════════════════
#  Phase M.3 — Boardpack endpoints
#
#  The old "Briefing" terminology becomes "Boardpack" (semantic shift, not
#  just a rename — boardpacks aggregate documents across one cycle and
#  carry Akki commentary on the whole pack). We mount the new endpoints
#  alongside the legacy `/briefings/*` URLs to keep external bookmarks +
#  outbound emails working for 30 days. The data lives in the renamed
#  `boardpacks` collection (Mongo migration migrate_phase_m3_boardpack.py).
# ═════════════════════════════════════════════════════════════════════════


def _serialise_boardpack(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Serialise a boardpack row for the M.3 list/detail endpoints.

    Adds the M.3 fields (cycle_label, document_ids, commentary excerpt)
    to the existing serialisation. The existing legacy fields stay so
    Daily Review and the legacy /briefings UIs keep working until the
    30-day backward-compat window closes."""
    out = _serialise_briefing(doc)  # carry forward references[]
    out["cycle_label"] = doc.get("cycle_label") or "Uncycled"
    out["cycle_id"] = doc.get("cycle_id")
    out["document_ids"] = doc.get("document_ids") or []
    out["commentary"] = doc.get("commentary") or doc.get("body") or ""
    out["commentary_redacted"] = (
        doc.get("commentary_redacted") or doc.get("body_redacted") or ""
    )
    out["commentary_synisense_version"] = doc.get(
        "commentary_synisense_version", doc.get("synisense_version", 0)
    )
    return out


@router.get("/contexts/{context_id}/boardpacks")
async def list_boardpacks(
    context_id: str,
    cycle_id: Optional[str] = None,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """List boardpacks for the active context, optionally filtered by
    `cycle_id`. Default sort: most recent first."""
    q: Dict[str, Any] = {"context_id": context_id}
    if cycle_id is not None:
        q["cycle_id"] = cycle_id
    rows = await db.boardpacks.find(
        q, {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    return {"items": [_serialise_boardpack(r) for r in rows]}


@router.get("/contexts/{context_id}/boardpacks/{bpid}")
async def get_boardpack(
    bpid: str,
    refresh: bool = False,  # noqa: ARG001 — reserved for forced regen
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    context_id = ctx["context"]["id"]
    doc = await db.boardpacks.find_one(
        {"id": bpid, "context_id": context_id}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Boardpack not found.")
    return _serialise_boardpack(doc)


@router.post("/contexts/{context_id}/boardpacks/{bpid}/regenerate-commentary")
async def regenerate_boardpack_commentary(
    bpid: str,
    ctx: Dict[str, Any] = Depends(require_context_membership(owner_only=True)),
):
    """Synthesise FT-voice commentary across the documents in the
    boardpack, run it through Synisense (surface=briefing for parity
    with existing Daily Review approval queue), persist the result.

    Real LLM call — uses the Emergent universal LLM gateway. ~600-1200
    word target. Cached on the row; subsequent reads return cached
    output unless this endpoint is called again or `?refresh=true` is
    passed to GET (the refresh flag is currently advisory; explicit
    POST is the supported path).
    """
    context_id = ctx["context"]["id"]
    doc = await db.boardpacks.find_one(
        {"id": bpid, "context_id": context_id}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Boardpack not found.")

    # Resolve referenced documents (if any document_ids are populated).
    doc_ids = doc.get("document_ids") or []
    src_docs: List[Dict[str, Any]] = []
    if doc_ids:
        cursor = db.documents.find(
            {"context_id": context_id, "id": {"$in": doc_ids}},
            {"_id": 0, "name": 1, "extracted_text": 1, "doc_kind": 1, "data_trust": 1},
        )
        src_docs = await cursor.to_list(50)

    # Build the prompt — concise, FT-voice. We intentionally keep this
    # in-router rather than another helper module: the prompt's whole
    # job is to produce the commentary text and it's <50 ll.
    title = doc.get("title") or doc.get("cycle_label") or "Untitled boardpack"
    excerpts = []
    for sd in src_docs[:8]:
        excerpts.append(
            f"### {sd.get('name','(untitled)')} [{sd.get('doc_kind','')}]\n"
            + (sd.get("extracted_text") or "")[:2400]
        )
    materials_block = "\n\n".join(excerpts) if excerpts else "(no source documents attached to this pack)"

    system = (
        "You are Akki, an analytical co-pilot for board directors. Your "
        "voice is Financial Times: dry, specific, plain. Never editorial, "
        "never gushing. Always grounded in the materials. When evidence "
        "is thin, say so. Refuse to weight scenarios you cannot ground."
    )
    user = (
        f"Boardpack: {title}\n\n"
        "Write a 600–1000 word commentary on this pack for the board's "
        "next session. Cover: (1) what the pack tells the board that the "
        "previous pack did not; (2) the two or three signals that warrant "
        "discussion time; (3) anything in the pack that contradicts the "
        "current strategic narrative; (4) what is conspicuously absent. "
        "No headlines. No recommendations the documents do not support. "
        "Reference document titles inline when you cite them.\n\n"
        f"=== MATERIALS ===\n\n{materials_block}\n"
    )

    from llm_service import call_llm
    try:
        llm_resp = await call_llm(
            module="boardpack_commentary",
            user_query=user,
            system_override=system,
            session_context={"context_id": context_id, "account_id": ctx["account"]["id"]},
            tier="standard",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"LLM commentary failed: {exc}")
    commentary = (llm_resp.get("response") if isinstance(llm_resp, dict) else "") or ""
    commentary = commentary.strip()
    if not commentary:
        raise HTTPException(status_code=502, detail="LLM returned empty commentary.")

    # Run through Synisense at the briefing surface — same trust profile.
    from services.synisense import pipeline as synisense_pipeline
    syn_out = await synisense_pipeline.run(
        commentary, context_id=context_id, surface="briefing",
        mode="redact", account_id=ctx["account"]["id"],
    )

    new_version = (doc.get("commentary_synisense_version") or 0) + 1
    update = {
        "commentary": commentary,
        "commentary_redacted": syn_out.get("redacted_text") or commentary,
        "commentary_synisense_version": new_version,
        "commentary_generated_at": iso(now()),
        "updated_at": iso(now()),
    }
    await db.boardpacks.update_one({"id": bpid}, {"$set": update})

    await write_audit(
        context_id, ctx["account"]["id"], "boardpack.commentary_regenerated",
        "boardpack", bpid,
        {"synisense_version": new_version, "doc_count": len(src_docs)},
    )

    refreshed = await db.boardpacks.find_one({"id": bpid}, {"_id": 0})
    return _serialise_boardpack(refreshed)
