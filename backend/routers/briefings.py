"""M12 — Briefings. Auto-compose briefings from generated signals, export PDF/DOCX."""
from __future__ import annotations

import io
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("akki.briefings")

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from briefings_service import build_briefing_prompt, render_pdf, render_docx, render_board_deck_pdf
from llm_service import call_llm as llm_call_llm, parse_json_response
from citation_refs import build_references

from core import (
    db, now, iso, write_audit, require_context_membership,
    gather_context_object, docs_overall_trust,
)
from services.job_queue import (
    create_job as _create_job, mark_running as _mark_running,
    mark_completed as _mark_completed, mark_failed as _mark_failed,
    spawn as _spawn,
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


@router.post("/contexts/{context_id}/briefings", status_code=202)
async def create_briefing(
    body: BriefingCreateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Chunk 2 (DJ-R03) — async pattern.

    Returns **202 + `job_id`** immediately. The LLM-heavy compose
    work runs as a `BackgroundTasks` worker; the frontend polls
    `GET /api/jobs/{job_id}` and consumes `result` (the serialised
    briefing row) when status → `completed`. Sync legacy callers
    can still hit `_create_briefing_worker(...)` directly.
    """
    context_id = ctx["context"]["id"]

    # Cheap pre-flight: surface "no signals" synchronously so the user
    # sees the error immediately instead of after a polling round-trip.
    q: Dict[str, Any] = {"context_id": context_id, "status": "active"}
    if body.signal_ids:
        q["id"] = {"$in": body.signal_ids}
    signal_count = await db.signals.count_documents(q)
    if signal_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No signals to brief on. Generate signals first, or select specific signal ids.",
        )

    job_id = await _create_job(
        kind="briefing.create",
        account_id=ctx["account"]["id"],
        context_id=context_id,
        input_summary={
            "signal_ids": list(body.signal_ids or []),
            "title": body.title or None,
            "signal_count": signal_count,
        },
    )

    background_account_id = ctx["account"]["id"]
    background_context_name = ctx["context"]["name"]

    async def _runner():
        await _mark_running(job_id)
        try:
            result = await _create_briefing_worker(
                body=body,
                account_id=background_account_id,
                context_id=context_id,
                context_name=background_context_name,
            )
            await _mark_completed(job_id, result)
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, str) else str(e.detail)
            await _mark_failed(job_id, f"http_{e.status_code}: {detail}")
        except Exception as e:
            logger.exception("briefing.create worker crashed (job=%s)", job_id)
            await _mark_failed(job_id, f"{type(e).__name__}: {str(e)[:400]}")

    _spawn(_runner())
    return {"job_id": job_id, "status": "queued"}


async def _create_briefing_worker(
    *, body: BriefingCreateIn, account_id: str, context_id: str, context_name: str,
) -> Dict[str, Any]:
    my_membership = await db.memberships.find_one(
        {"context_id": context_id, "account_id": account_id, "status": "active"},
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

    # Phase B.3 — strategic failover lives in llm_service.call_llm itself
    # (direct Anthropic / Gemini SDKs first, universal LLM proxy on failure).
    # The previous briefings-local Claude→Gemini band-aid is gone. We
    # still surface `fallback_triggered` on the persisted row + audit
    # metadata so ops can spot post-facto when Claude flapped.
    fallback_meta: Optional[Dict[str, Any]] = None
    if llm_out.get("fallback_triggered"):
        fallback_meta = {
            "provider_used": llm_out.get("provider_used"),
            "reason": "direct_provider_failover",
        }

    parsed = parse_json_response(llm_out.get("response", ""))
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=502,
            detail=(
                f"LLM did not return a valid briefing. Mode={llm_out.get('mode')} "
                f"provider={llm_out.get('provider_used')} "
                f"fallback={llm_out.get('fallback_triggered')}. "
                f"Raw: {llm_out.get('response', '')[:500]}"
            ),
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
        # Phase B post-D — option (b) audit flag. Present iff the
        # standard-tier call 502'd through the universal LLM proxy and the
        # fast-tier (Gemini) retry succeeded. Absent on the happy path,
        # so existing rows and the briefing serialiser are unaffected.
        "llm_fallback": fallback_meta,
        "created_by": account_id,
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
        context_id, account_id, "briefing.created", "briefing", briefing_id,
        {"version": version, "items": len(items), "mode": llm_out.get("mode"),
         "llm_fallback": fallback_meta},
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


@router.get("/contexts/{context_id}/briefings/aggregates")
async def list_brief_aggregates(
    context_id: str,
    kind: str,
    q: Optional[str] = Query(default=None, max_length=200),
    status: Optional[str] = Query(
        default=None,
        pattern=r"^(all|draft|in_progress|compiled|shipped)$",
    ),
    sort: str = Query(default="recent", pattern=r"^(recent|oldest|alpha|type)$"),
    page: int = Query(default=1, ge=1, le=1000),
    page_size: int = Query(default=5, ge=1, le=100),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Phase C.1 — aggregate listing for the Workspace rewire.

    Registered BEFORE the `/{briefing_id}` route below so FastAPI's
    in-order matcher resolves `/aggregates` to this handler instead of
    treating "aggregates" as a briefing id.

    Cycle Manager Feel pass (2026-02) added:
      • `q` — case-insensitive substring match on the row's name.
      • `status` ∈ {all, draft, in_progress, compiled, shipped} — filter
        by the derived artefact lifecycle status. `all` is a no-op.
      • `sort` ∈ {recent, oldest, alpha, type} — recent / oldest sorts
        by meeting_date desc / asc; alpha by name; type by kind then date.
      • `page` / `page_size` — paginate the post-filter result.
    The response now includes `total` + `page` + `page_size` + `total_pages`
    + `counts_by_status` for ListingShell consumption.
    """
    if kind not in _AGG_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown aggregate kind. Allowed: {', '.join(_AGG_KINDS)}.",
        )
    if kind == "cycle_board_pack":
        items = await _list_cycle_board_packs(context_id)
    elif kind == "cycle_minutes":
        items = await _list_cycle_minutes(context_id)
    elif kind == "cycle_committee_pack":
        items = await _list_cycle_committee_packs(context_id)
    elif kind == "deck":
        items = await _list_decks(context_id)
    elif kind == "report":
        items = await _list_reports(context_id)
    elif kind == "briefing":
        items = await _list_briefings(context_id)
    else:
        # Defensive: should be unreachable because of the kind whitelist above.
        items = []

    # Counts pre-filter (for the FilterTabs count badges).
    counts_by_status = {
        "all": len(items),
        "draft": sum(1 for r in items if r.get("status") == "draft"),
        "in_progress": sum(1 for r in items if r.get("status") == "in_progress"),
        "compiled": sum(1 for r in items if r.get("status") == "compiled"),
        "shipped": sum(1 for r in items if r.get("status") == "shipped"),
    }

    # Search filter (case-insensitive substring on name).
    if q:
        q_lc = q.strip().lower()
        if q_lc:
            items = [r for r in items if q_lc in (r.get("name") or "").lower()]

    # Status filter.
    if status and status != "all":
        items = [r for r in items if r.get("status") == status]

    # Sort.
    if sort == "alpha":
        items.sort(key=lambda r: (r.get("name") or "").lower())
    elif sort == "oldest":
        items.sort(key=lambda r: r.get("meeting_date") or "")
    elif sort == "type":
        items.sort(key=lambda r: (r.get("kind") or "", r.get("meeting_date") or ""), reverse=True)
    else:  # recent (default)
        items.sort(key=lambda r: r.get("meeting_date") or "", reverse=True)

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = items[start:end]
    total_pages = max(1, (total + page_size - 1) // page_size)

    return {
        "kind": kind,
        "items": page_items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "counts_by_status": counts_by_status,
        "q": q or "",
        "status": status or "all",
        "sort": sort,
    }


@router.get("/contexts/{context_id}/briefings/aggregates/{aggregate_id}")
async def get_brief_aggregate(
    context_id: str,
    aggregate_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Phase C.1 — aggregate detail for the Workspace drawer.

    Chunk 6 (2026-05-13, WS-R01 / WS-R17): added explicit dispatch for
    `briefing`, `deck`, and `report` kinds. Pre-fix the fall-through
    sent every non-cycle kind to `_detail_cycle_committee_pack` which
    required a `<committee_id>::<quarter>` internal id and raised
    `Bad aggregate id.` 400 for any plain uuid. Net effect: clicking
    any deck / report / brief row in Work Studio returned 400. The
    drawer also lacked an Open-in-composer CTA; the new handlers
    surface `composer_url` so the BriefDrawer can wire a working
    primary action.
    """
    parsed = _split_agg_id(aggregate_id)
    if not parsed:
        raise HTTPException(status_code=400, detail="Bad aggregate id.")
    kind = parsed["kind"]
    internal_id = parsed["internal_id"]
    if kind == "cycle_board_pack":
        return await _detail_cycle_board_pack(context_id, internal_id)
    if kind == "cycle_minutes":
        return await _detail_cycle_minutes(context_id, internal_id)
    if kind == "cycle_committee_pack":
        return await _detail_cycle_committee_pack(context_id, internal_id)
    if kind == "briefing":
        return await _detail_briefing(context_id, internal_id)
    if kind == "deck":
        return await _detail_deck(context_id, internal_id)
    if kind == "report":
        return await _detail_report(context_id, internal_id)
    # _split_agg_id already gated on _AGG_KINDS, so this is unreachable
    # in practice — kept as a defensive 400 for forward compat.
    raise HTTPException(status_code=400, detail=f"Unsupported aggregate kind: {kind}")


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

    Real LLM call — uses the universal LLM gateway. ~600-1200
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


# =============================================================================
# Phase C.1 — Workspace rewire — aggregate listings (memo Item 2)
#
# Three aggregate kinds shown as a single tabbed listing on /app/work-studio:
#   • cycle_board_pack        — sourced from db.boardpacks (authoritative)
#   • cycle_minutes           — derived from db.documents matching minutes
#                               heuristics, grouped by quarter
#   • cycle_committee_pack    — derived from db.committees (+ associated docs)
#
# Each row carries the memo's required markers: meeting_date,
# document_count, contributor_count, plus a period_start/period_end so
# the UI can render a clean "Q1 2026 · Jan–Mar" subtitle.
#
# C.1 is read-only scaffolding. No new collections are created. The
# detail endpoint is permissive on missing fields — it serialises what
# is there and leaves blanks where the upstream data has not yet
# settled. The UI shows an empty-state when a kind returns zero rows.
# =============================================================================
_AGG_KINDS = (
    "cycle_board_pack",
    "cycle_minutes",
    "cycle_committee_pack",
    # Patch 2B.1 — Work Studio 6-tab expansion. Decks/Reports/Briefing
    # surface from their canonical collections; empty list when no rows.
    "deck",
    "report",
    "briefing",
)
_MINUTES_NAME_RE = None  # lazy
_MINUTES_KINDS = {"minutes", "meeting_minutes", "minutes_main_board"}


def _quarter_label(d: Any) -> str:
    """Return 'Q1 2026' from a datetime / iso string. Defensive on Nones."""
    from datetime import datetime
    if not d:
        return "Uncycled"
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d.replace("Z", "+00:00"))
        except Exception:
            return "Uncycled"
    try:
        q = (d.month - 1) // 3 + 1
        return f"Q{q} {d.year}"
    except Exception:
        return "Uncycled"


def _quarter_bounds(d: Any) -> Dict[str, Optional[str]]:
    """Return iso start/end for the calendar quarter containing `d`."""
    from datetime import datetime, timezone
    if not d:
        return {"period_start": None, "period_end": None}
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d.replace("Z", "+00:00"))
        except Exception:
            return {"period_start": None, "period_end": None}
    try:
        q = (d.month - 1) // 3 + 1
        sm = (q - 1) * 3 + 1
        em = sm + 2
        from calendar import monthrange
        last_day = monthrange(d.year, em)[1]
        start = datetime(d.year, sm, 1, tzinfo=timezone.utc)
        end = datetime(d.year, em, last_day, 23, 59, 59, tzinfo=timezone.utc)
        return {"period_start": start.isoformat(), "period_end": end.isoformat()}
    except Exception:
        return {"period_start": None, "period_end": None}


def _agg_id(kind: str, internal_id: str) -> str:
    """Compose the URL-safe aggregate id used by the per-aggregate
    detail endpoint. The kind prefix lets the GET handler dispatch
    without needing a query parameter."""
    return f"{kind}::{internal_id}"


def _split_agg_id(aid: str) -> Optional[Dict[str, str]]:
    if "::" not in aid:
        return None
    kind, _, internal = aid.partition("::")
    if kind not in _AGG_KINDS or not internal:
        return None
    return {"kind": kind, "internal_id": internal}


async def _list_cycle_board_packs(context_id: str) -> List[Dict[str, Any]]:
    """Query db.boardpacks (post-M.3 authoritative source). The
    `meeting_date` falls back to created_at when an explicit meeting_date
    is absent — most boardpacks pre-date the C.1 markers."""
    rows = await db.boardpacks.find(
        {"context_id": context_id}, {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    out: List[Dict[str, Any]] = []
    for r in rows:
        doc_ids = r.get("document_ids") or [it.get("doc_id") for it in (r.get("items") or []) if it.get("doc_id")]
        doc_ids = [d for d in doc_ids if d]
        contributor_count = len(r.get("contributors") or [])
        if contributor_count == 0 and doc_ids:
            # Derive contributor count from the documents' uploaders.
            cursor = db.documents.find(
                {"id": {"$in": doc_ids}, "context_id": context_id},
                {"_id": 0, "uploaded_by": 1},
            )
            uploaders = {d.get("uploaded_by") for d in await cursor.to_list(500) if d.get("uploaded_by")}
            contributor_count = len(uploaders)
        meeting_date = r.get("meeting_date") or r.get("cycle_meeting_date") or r.get("created_at")
        # Cycle v7 ListingShell — derive an artefact lifecycle status.
        # Order matters: shipped > compiled > in_progress > draft.
        brief_id = r.get("brief_id")
        bp_status = (r.get("status") or "").lower()
        if brief_id:
            brief = await db.work_studio_briefs.find_one(
                {"id": brief_id, "context_id": context_id},
                {"_id": 0, "board_status": 1},
            )
            if (brief or {}).get("board_status") == "shipped":
                lifecycle_status = "shipped"
            else:
                lifecycle_status = "compiled"
        elif len(doc_ids) > 0:
            lifecycle_status = "in_progress"
        elif bp_status == "draft":
            lifecycle_status = "draft"
        else:
            lifecycle_status = "draft" if bp_status != "active" else "in_progress"
        out.append({
            "id": _agg_id("cycle_board_pack", r["id"]),
            "kind": "cycle_board_pack",
            "name": r.get("title") or r.get("cycle_label") or "Board Pack",
            "meeting_date": meeting_date,
            "document_count": len(doc_ids),
            "contributor_count": contributor_count,
            "status": lifecycle_status,
            "created_at": r.get("created_at"),
            **_quarter_bounds(meeting_date),
            "cycle_label": r.get("cycle_label"),
        })
    return out


async def _list_cycle_minutes(context_id: str) -> List[Dict[str, Any]]:
    """Group documents that look like minutes by quarter. Identification:
        • doc_kind in MINUTES_KINDS, OR
        • name contains the word 'minutes' (case-insensitive).
    Returns one virtual aggregate per quarter that has minutes."""
    import re as _re
    rx = _re.compile(r"\bminutes\b", _re.IGNORECASE)
    cursor = db.documents.find(
        {"context_id": context_id},
        {"_id": 0, "id": 1, "name": 1, "doc_kind": 1, "uploaded_by": 1, "created_at": 1, "updated_at": 1},
    )
    by_q: Dict[str, Dict[str, Any]] = {}
    async for d in cursor:
        kind = (d.get("doc_kind") or "").lower()
        nm = d.get("name") or ""
        if kind not in _MINUTES_KINDS and not rx.search(nm):
            continue
        when = d.get("updated_at") or d.get("created_at")
        ql = _quarter_label(when)
        bucket = by_q.setdefault(ql, {
            "doc_ids": [], "uploaders": set(), "latest": when,
            "earliest": when, **_quarter_bounds(when),
        })
        bucket["doc_ids"].append(d["id"])
        if d.get("uploaded_by"):
            bucket["uploaders"].add(d["uploaded_by"])
        if when and (bucket["latest"] is None or str(when) > str(bucket["latest"])):
            bucket["latest"] = when
        if when and (bucket["earliest"] is None or str(when) < str(bucket["earliest"])):
            bucket["earliest"] = when
    out: List[Dict[str, Any]] = []
    for ql, b in sorted(by_q.items(), key=lambda kv: kv[1]["latest"] or "", reverse=True):
        out.append({
            "id": _agg_id("cycle_minutes", ql.replace(" ", "_")),
            "kind": "cycle_minutes",
            "name": f"{ql} Minutes",
            "meeting_date": b["latest"],
            "document_count": len(b["doc_ids"]),
            "contributor_count": len(b["uploaders"]),
            "period_start": b.get("period_start"),
            "period_end": b.get("period_end"),
            "cycle_label": ql,
            # Minutes aggregates have no compile pipeline today, so the
            # ListingShell status is always 'in_progress' (documents present)
            # or 'draft' (none — should never appear because the bucket
            # only exists when at least one doc matches).
            "status": "in_progress" if b["doc_ids"] else "draft",
            "created_at": b["latest"],
        })
    return out


async def _list_cycle_committee_packs(context_id: str) -> List[Dict[str, Any]]:
    """Group committee documents by (committee, quarter). Sources:
        • db.committees (committee names per context)
        • db.documents joined by committee_id when present.
    Returns one virtual aggregate per (committee, quarter) tuple that
    has at least one document."""
    cursor = db.committees.find({"context_id": context_id}, {"_id": 0})
    committees = await cursor.to_list(50)
    if not committees:
        return []
    out: List[Dict[str, Any]] = []
    for cm in committees:
        cm_id = cm.get("id")
        cm_name = cm.get("name") or "Committee"
        if not cm_id:
            continue
        d_cursor = db.documents.find(
            {"context_id": context_id, "committee_id": cm_id},
            {"_id": 0, "id": 1, "uploaded_by": 1, "created_at": 1, "updated_at": 1},
        )
        by_q: Dict[str, Dict[str, Any]] = {}
        async for d in d_cursor:
            when = d.get("updated_at") or d.get("created_at")
            ql = _quarter_label(when)
            b = by_q.setdefault(ql, {"doc_ids": [], "uploaders": set(), "latest": when, **_quarter_bounds(when)})
            b["doc_ids"].append(d["id"])
            if d.get("uploaded_by"):
                b["uploaders"].add(d["uploaded_by"])
            if when and (b["latest"] is None or str(when) > str(b["latest"])):
                b["latest"] = when
        for ql, b in by_q.items():
            out.append({
                "id": _agg_id("cycle_committee_pack", f"{cm_id}::{ql.replace(' ', '_')}"),
                "kind": "cycle_committee_pack",
                "name": f"{cm_name} {ql}",
                "meeting_date": b["latest"],
                "document_count": len(b["doc_ids"]),
                "contributor_count": len(b["uploaders"]),
                "period_start": b.get("period_start"),
                "period_end": b.get("period_end"),
                "cycle_label": ql,
                "committee_id": cm_id,
                "status": "in_progress" if b["doc_ids"] else "draft",
                "created_at": b["latest"],
            })
    out.sort(key=lambda r: r.get("meeting_date") or "", reverse=True)
    return out


# -----------------------------------------------------------------------------
# Patch 2B.1 — Work Studio 6-tab expansion. Decks / Reports / Briefing.
# Each list reads from its canonical collection and renders into the
# same aggregate envelope as the cycle kinds. Empty list when no rows.
# -----------------------------------------------------------------------------
async def _list_decks(context_id: str) -> List[Dict[str, Any]]:
    """Surface rows from db.decks scoped to this context."""
    rows = await db.decks.find(
        {"context_id": context_id},
        {"_id": 0},
    ).sort("updated_at", -1).to_list(200)
    out: List[Dict[str, Any]] = []
    for r in rows:
        when = r.get("updated_at") or r.get("created_at")
        slide_count = len(r.get("slides") or [])
        # Lifecycle: status field on the row, mapped to the artefact lifecycle.
        s = (r.get("status") or "draft").lower()
        if s in ("sent", "shipped", "complete", "completed"):
            lifecycle = "shipped"
        elif s in ("approved", "compiled"):
            lifecycle = "compiled"
        elif s in ("review", "in_review", "in_progress"):
            lifecycle = "in_progress"
        else:
            lifecycle = "draft"
        out.append({
            "id": _agg_id("deck", r["id"]),
            "kind": "deck",
            "name": r.get("title") or "Untitled deck",
            # Chunk 5 (2026-05-13, WS-R09→R14 follow-on) — surface the
            # row's `description` so the Work Studio listing carries
            # the Patch 28D `preview → description → placeholder` chain.
            "description": r.get("description"),
            "meeting_date": when,
            "document_count": slide_count,
            "contributor_count": 1,  # author only; deck collaboration is a future feature
            "period_start": None,
            "period_end": None,
            "cycle_label": None,
            "status": lifecycle,
            "created_at": r.get("created_at"),
        })
    return out


async def _list_reports(context_id: str) -> List[Dict[str, Any]]:
    """Surface rows from db.reports scoped to this context."""
    rows = await db.reports.find(
        {"context_id": context_id, "status": {"$ne": "withdrawn"}},
        {"_id": 0},
    ).sort("updated_at", -1).to_list(200)
    out: List[Dict[str, Any]] = []
    for r in rows:
        when = r.get("updated_at") or r.get("created_at")
        chain = r.get("chain") or []
        s = (r.get("status") or "draft").lower()
        if s in ("sent", "finalised", "finalized"):
            lifecycle = "shipped"
        elif s == "compiled":
            lifecycle = "compiled"
        elif s in ("in_review", "review"):
            lifecycle = "in_progress"
        else:
            lifecycle = "draft"
        out.append({
            "id": _agg_id("report", r["id"]),
            "kind": "report",
            "name": r.get("title") or "Untitled report",
            # Chunk 5 — description chain (Patch 28D parity).
            "description": r.get("description"),
            "meeting_date": when,
            "document_count": 0,
            "contributor_count": len(chain),
            "period_start": None,
            "period_end": None,
            "cycle_label": None,
            "status": lifecycle,
            "created_at": r.get("created_at"),
        })
    return out


async def _list_briefings(context_id: str) -> List[Dict[str, Any]]:
    """Surface rows from db.work_studio_briefs scoped to this context.
    A "briefing" in Work Studio == a brief artefact (the editorial,
    one-page output that gets attached to a board pack or sent on its
    own). Empty list when no briefs exist yet."""
    rows = await db.work_studio_briefs.find(
        {"context_id": context_id},
        {"_id": 0},
    ).sort("updated_at", -1).to_list(200)
    out: List[Dict[str, Any]] = []
    for r in rows:
        when = r.get("updated_at") or r.get("created_at")
        board_status = (r.get("board_status") or "").lower()
        s = (r.get("status") or "draft").lower()
        if board_status == "shipped" or s in ("shipped", "sent"):
            lifecycle = "shipped"
        elif board_status == "compiled" or s == "compiled":
            lifecycle = "compiled"
        elif s in ("in_progress", "in_review", "review"):
            lifecycle = "in_progress"
        else:
            lifecycle = "draft"
        out.append({
            "id": _agg_id("briefing", r["id"]),
            "kind": "briefing",
            "name": r.get("title") or "Untitled brief",
            # Chunk 5 — description chain (Patch 28D parity). Briefs
            # use `subtitle` as their description-equivalent.
            "description": r.get("subtitle") or r.get("description"),
            "meeting_date": when,
            "document_count": 0,
            "contributor_count": 1,
            "period_start": None,
            "period_end": None,
            "cycle_label": None,
            "status": lifecycle,
            "created_at": r.get("created_at"),
        })
    return out


def _topic_split_commentary(text: str) -> List[Dict[str, Any]]:
    """Split the boardpack commentary into topic notes. C.1 is a UI
    scaffold so we use a permissive heuristic: paragraphs separated by
    blank lines, with the first sentence taken as the topic label.
    Future C.2 will replace this with real topic classification."""
    if not text:
        return []
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    out: List[Dict[str, Any]] = []
    for p in paras:
        # Prefer markdown-style heading lines (## Heading) as topic.
        topic = ""
        body = p
        if p.startswith("##"):
            line, _, rest = p.partition("\n")
            topic = line.lstrip("# ").strip()
            body = rest.strip() or topic
        elif "\n" in p and len(p.split("\n", 1)[0]) <= 80:
            line, _, rest = p.partition("\n")
            topic = line.strip().rstrip(":")
            body = rest.strip() or topic
        else:
            # Take the first 8 words as the topic label.
            words = p.split()
            topic = " ".join(words[:8]).rstrip(".:;,") + ("…" if len(words) > 8 else "")
            body = p
        out.append({"topic": topic, "body": body, "citations": []})
    return out


def _attach_citations(notes: List[Dict[str, Any]], doc_meta: List[Dict[str, Any]]) -> None:
    """Phase C.1 citations: every note carries the union of documents in
    the aggregate so the user can see the source set immediately. C.2
    will produce per-note resolution. We mark citations with `paragraph_anchor=None`
    here (resolution lands in Phase E)."""
    citations = [
        {"doc_id": d["id"], "doc_name": d.get("name") or "Untitled", "paragraph_anchor": None}
        for d in doc_meta
    ]
    for n in notes:
        n["citations"] = citations


async def _detail_cycle_board_pack(context_id: str, internal_id: str) -> Dict[str, Any]:
    bp = await db.boardpacks.find_one({"id": internal_id, "context_id": context_id}, {"_id": 0})
    if not bp:
        raise HTTPException(status_code=404, detail="Aggregate not found.")
    doc_ids = bp.get("document_ids") or [
        it.get("doc_id") for it in (bp.get("items") or []) if it.get("doc_id")
    ]
    doc_ids = [d for d in doc_ids if d]
    docs: List[Dict[str, Any]] = []
    if doc_ids:
        cursor = db.documents.find(
            {"context_id": context_id, "id": {"$in": doc_ids}},
            {"_id": 0, "id": 1, "name": 1, "uploaded_by": 1, "created_at": 1},
        )
        docs = await cursor.to_list(500)
    contributors = {d.get("uploaded_by") for d in docs if d.get("uploaded_by")}
    commentary = bp.get("commentary") or bp.get("body") or ""
    notes = _topic_split_commentary(commentary)
    _attach_citations(notes, docs)
    meeting_date = bp.get("meeting_date") or bp.get("cycle_meeting_date") or bp.get("created_at")
    return {
        "id": _agg_id("cycle_board_pack", internal_id),
        "kind": "cycle_board_pack",
        "name": bp.get("title") or bp.get("cycle_label") or "Board Pack",
        "topline": {
            "doc_count": len(doc_ids),
            "contributor_count": len(contributors),
            "period": bp.get("cycle_label") or _quarter_label(meeting_date),
        },
        "meeting_date": meeting_date,
        **_quarter_bounds(meeting_date),
        "notes": notes,
    }


async def _detail_cycle_minutes(context_id: str, internal_id: str) -> Dict[str, Any]:
    """`internal_id` is the underscored quarter label, e.g. 'Q1_2026'."""
    import re as _re
    rx = _re.compile(r"\bminutes\b", _re.IGNORECASE)
    quarter_label = internal_id.replace("_", " ")
    cursor = db.documents.find(
        {"context_id": context_id},
        {"_id": 0, "id": 1, "name": 1, "doc_kind": 1, "uploaded_by": 1, "created_at": 1, "updated_at": 1, "extracted_text": 1},
    )
    docs: List[Dict[str, Any]] = []
    async for d in cursor:
        kind = (d.get("doc_kind") or "").lower()
        nm = d.get("name") or ""
        if kind not in _MINUTES_KINDS and not rx.search(nm):
            continue
        when = d.get("updated_at") or d.get("created_at")
        if _quarter_label(when) != quarter_label:
            continue
        docs.append(d)
    if not docs:
        raise HTTPException(status_code=404, detail="Aggregate not found.")
    contributors = {d.get("uploaded_by") for d in docs if d.get("uploaded_by")}
    notes = [
        {
            "topic": d.get("name") or "Minutes document",
            "body": ((d.get("extracted_text") or "")[:600] + "…")
            if (d.get("extracted_text") and len(d.get("extracted_text") or "") > 600)
            else (d.get("extracted_text") or "—"),
            "citations": [{
                "doc_id": d["id"],
                "doc_name": d.get("name") or "Untitled",
                "paragraph_anchor": None,
            }],
        }
        for d in docs
    ]
    latest = max((d.get("updated_at") or d.get("created_at") or "" for d in docs), default=None)
    return {
        "id": _agg_id("cycle_minutes", internal_id),
        "kind": "cycle_minutes",
        "name": f"{quarter_label} Minutes",
        "topline": {
            "doc_count": len(docs),
            "contributor_count": len(contributors),
            "period": quarter_label,
        },
        "meeting_date": latest,
        **_quarter_bounds(latest),
        "notes": notes,
    }


async def _detail_cycle_committee_pack(context_id: str, internal_id: str) -> Dict[str, Any]:
    """`internal_id` is `<committee_id>::<Q?_YYYY>`."""
    if "::" not in internal_id:
        raise HTTPException(status_code=400, detail="Bad aggregate id.")
    cm_id, _, ql = internal_id.partition("::")
    quarter_label = ql.replace("_", " ")
    committee = await db.committees.find_one({"context_id": context_id, "id": cm_id}, {"_id": 0})
    if not committee:
        raise HTTPException(status_code=404, detail="Aggregate not found.")
    cursor = db.documents.find(
        {"context_id": context_id, "committee_id": cm_id},
        {"_id": 0, "id": 1, "name": 1, "uploaded_by": 1, "created_at": 1, "updated_at": 1, "extracted_text": 1},
    )
    docs: List[Dict[str, Any]] = []
    async for d in cursor:
        when = d.get("updated_at") or d.get("created_at")
        if _quarter_label(when) != quarter_label:
            continue
        docs.append(d)
    if not docs:
        raise HTTPException(status_code=404, detail="Aggregate not found.")
    contributors = {d.get("uploaded_by") for d in docs if d.get("uploaded_by")}
    notes = [
        {
            "topic": d.get("name") or "Committee document",
            "body": ((d.get("extracted_text") or "")[:600] + "…")
            if (d.get("extracted_text") and len(d.get("extracted_text") or "") > 600)
            else (d.get("extracted_text") or "—"),
            "citations": [{
                "doc_id": d["id"],
                "doc_name": d.get("name") or "Untitled",
                "paragraph_anchor": None,
            }],
        }
        for d in docs
    ]
    latest = max((d.get("updated_at") or d.get("created_at") or "" for d in docs), default=None)
    return {
        "id": _agg_id("cycle_committee_pack", internal_id),
        "kind": "cycle_committee_pack",
        "name": f"{committee.get('name') or 'Committee'} {quarter_label}",
        "topline": {
            "doc_count": len(docs),
            "contributor_count": len(contributors),
            "period": quarter_label,
        },
        "meeting_date": latest,
        **_quarter_bounds(latest),
        "notes": notes,
    }



# ─────────────────────────────────────────────────────────────────────
# Chunk 6 (2026-05-13) — WS-R01 / WS-R17 fix.
#
# Aggregate detail for `briefing`, `deck`, `report` kinds. Each returns
# a uniform shape the Work Studio BriefDrawer can render:
#
#   {
#     id, kind, name, meeting_date,
#     topline:       {doc_count, contributor_count, period | None},
#     period_start:  iso | None,
#     period_end:    iso | None,
#     notes:         [{type, body, citations: []}],
#     composer_url:  "/app/studio/composer/{kind}/{artefact_id}",
#     artefact_id:   "<raw uuid>",
#   }
#
# `composer_url` is the new field — the BriefDrawer primary CTA reads
# it to route the user into the block composer (Chunk 5 redirect
# convention). Citations are empty for now (Work-Studio-native rows
# don't carry a `documents` snapshot the way cycle aggregates do).
# ─────────────────────────────────────────────────────────────────────
async def _detail_briefing(context_id: str, internal_id: str) -> Dict[str, Any]:
    brief = await db.work_studio_briefs.find_one(
        {"id": internal_id, "context_id": context_id},
        {"_id": 0},
    )
    if not brief:
        raise HTTPException(status_code=404, detail="Briefing not found.")
    when = brief.get("updated_at") or brief.get("created_at")
    subtitle = (brief.get("subtitle") or "").strip()
    return {
        "id": _agg_id("briefing", internal_id),
        "kind": "briefing",
        "name": brief.get("title") or "Untitled briefing",
        "topline": {
            "doc_count": 0,
            "contributor_count": 1,
            "period": None,
        },
        "meeting_date": when,
        "period_start": None,
        "period_end": None,
        "notes": ([{"type": "subtitle", "body": subtitle, "citations": []}]
                  if subtitle else []),
        "composer_url": f"/app/studio/composer/briefing/{internal_id}",
        "artefact_id": internal_id,
    }


async def _detail_deck(context_id: str, internal_id: str) -> Dict[str, Any]:
    deck = await db.decks.find_one(
        {"id": internal_id, "context_id": context_id},
        {"_id": 0},
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found.")
    when = deck.get("updated_at") or deck.get("created_at")
    description = (deck.get("description") or "").strip()
    slide_count = len(deck.get("slides") or [])
    return {
        "id": _agg_id("deck", internal_id),
        "kind": "deck",
        "name": deck.get("title") or "Untitled deck",
        "topline": {
            "doc_count": slide_count,
            "contributor_count": 1,
            "period": None,
        },
        "meeting_date": when,
        "period_start": None,
        "period_end": None,
        "notes": ([{"type": "description", "body": description, "citations": []}]
                  if description else []),
        "composer_url": f"/app/studio/composer/deck/{internal_id}",
        "artefact_id": internal_id,
    }


async def _detail_report(context_id: str, internal_id: str) -> Dict[str, Any]:
    report = await db.reports.find_one(
        {"id": internal_id, "context_id": context_id},
        {"_id": 0},
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    when = report.get("updated_at") or report.get("created_at")
    description = (report.get("description") or "").strip()
    chain = report.get("chain") or []
    return {
        "id": _agg_id("report", internal_id),
        "kind": "report",
        "name": report.get("title") or "Untitled report",
        "topline": {
            "doc_count": 0,
            "contributor_count": max(len(chain), 1),
            "period": None,
        },
        "meeting_date": when,
        "period_start": None,
        "period_end": None,
        "notes": ([{"type": "description", "body": description, "citations": []}]
                  if description else []),
        "composer_url": f"/app/studio/composer/report/{internal_id}",
        "artefact_id": internal_id,
    }
