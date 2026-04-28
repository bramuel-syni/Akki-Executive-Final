"""Prepare — saved-brief retrieval + on-demand generation router.

Backs the Apr-2026 "Prepare" page redesign. Two surfaces share one URL
(/app/prepare with line tabs):

  · Signals — on-demand generation by FILTER (period, source doc, cycle).
  · Brief   — short on-demand "Brief me on …" answers saved with a title +
              timestamp for retrieval. Distinct from full board briefings
              (which remain at /api/contexts/{cid}/briefings).

This module adds the **brief** surface; signal generation already exists at
/api/contexts/{cid}/signals/generate and we re-use that. The user's filter
shape is just stored on the existing signals doc as `filter_label`.

Brief shape (collection: `briefs`):
    {id, context_id, account_id, kind, objective, title, body[markdown],
     model, validated, created_at}
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso, now, require_context_membership, write_audit
from llm_service import call_llm

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Saved Brief — ON-DEMAND, short, retrievable.
# ---------------------------------------------------------------------------
BRIEF_KINDS = [
    {"id": "claim",    "label": "Claim",
     "blurb": "A specific claim, finding, or assertion you want a quick orientation on."},
    {"id": "proposal", "label": "Proposal",
     "blurb": "A proposal or recommendation you need to evaluate quickly."},
    {"id": "topic",    "label": "Topic",
     "blurb": "A theme or subject area for general orientation."},
    {"id": "period",   "label": "Period",
     "blurb": "What happened in a specific time window — Q2 2026, the last 30 days, etc."},
    {"id": "report",   "label": "Report",
     "blurb": "A specific report or document — give me the one-pager."},
]


@router.get("/prepare/brief-kinds")
async def list_brief_kinds():
    """Static list of brief kinds — used to populate the kind picker
    on /app/prepare. Open to any authenticated request."""
    return {"kinds": BRIEF_KINDS}


class BriefIn(BaseModel):
    kind: str = Field(min_length=1, max_length=40)
    objective: str = Field(min_length=8, max_length=600)


def _brief_prompt(kind: str, objective: str, ctx_name: str) -> str:
    kind_label = next((k["label"] for k in BRIEF_KINDS if k["id"] == kind), kind.title())
    return (
        f"You are AKKI, an executive intelligence partner. Compose a short "
        f"editorial brief in the AKKI house style: serif tone, ~250–400 words, "
        f"calm, confident, direct. No bullet stuffing. Open with a one-line "
        f"orientation, then 2–3 short paragraphs that answer the executive's "
        f"actual question. Close with one suggested next step phrased as a "
        f"sharp question for the room.\n\n"
        f"Context: {ctx_name}\n"
        f"Brief kind: {kind_label}\n"
        f"Executive's objective: {objective}\n\n"
        f"Return STRICT JSON ONLY:\n"
        f"{{\"title\": \"<<headline ≤80 chars, sentence case>>\","
        f"\"body\": \"<<full brief body, markdown allowed>>\"}}"
    )


@router.post("/contexts/{context_id}/briefs")
async def create_brief(
    body: BriefIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """On-demand brief. Generates editorial copy via LLM, persists to
    `briefs` collection, returns the saved doc."""
    if body.kind not in {k["id"] for k in BRIEF_KINDS}:
        raise HTTPException(status_code=422, detail="Unknown brief kind")

    ctx_name = ctx["context"].get("name") or "the company"
    prompt = _brief_prompt(body.kind, body.objective.strip(), ctx_name)

    # Use the existing shielded LLM pipeline so this brief carries the
    # same Synisense-shielded validation pass that the ValidatedBadge chip
    # promises across the product.
    llm_out = await call_llm(
        module="prepare.brief",
        user_query=prompt,
        response_format="json",
    )
    raw = llm_out.get("response") or "{}"
    from helpers.llm_json import safe_parse_json
    parsed, raw_str = safe_parse_json(raw)

    title = (parsed.get("title") or body.objective[:80]).strip()
    md_body = (parsed.get("body") or "").strip()
    # Fallback: if the model answered in prose despite the JSON instruction,
    # treat the whole response as the brief body rather than 502'ing.
    if not md_body and len(raw_str.strip()) >= 40:
        md_body = raw_str.strip()
    if not md_body:
        raise HTTPException(status_code=502, detail="AKKI couldn't draft this brief — try again.")

    # Real second-LLM countercheck — independent of the drafter (Claude →
    # Gemini). Soft-fails to a "qualified" verdict on validator outage so
    # this never blocks a happy-path brief from saving. Iter50: we now
    # issue the validator concurrently with the insert + audit-write so
    # validate latency is masked behind those two writes.
    from llm_service import validate_independent
    import asyncio as _asyncio

    brief_id = str(uuid.uuid4())
    placeholder_validation = {
        "verdict": "pending", "confidence": 0,
        "notes": ["Validating with an independent model…"],
        "validator_provider": "n/a", "validator_model": "n/a",
    }
    doc = {
        "id": brief_id,
        "context_id": ctx["context"]["id"],
        "account_id": ctx["account"]["id"],
        "kind": body.kind,
        "objective": body.objective.strip(),
        "title": title[:120],
        "body": md_body,
        "model": llm_out.get("mode"),
        "validation": placeholder_validation,
        "created_at": iso(now()),
    }

    # Fan-out: insert + audit + validate in parallel.
    insert_task = db.briefs.insert_one(doc.copy())
    audit_task = write_audit(
        ctx["context"]["id"], ctx["account"]["id"],
        "brief.created", "brief", brief_id,
        {"kind": body.kind, "objective_chars": len(body.objective)},
    )
    validate_task = validate_independent(
        kind=body.kind, content=md_body, objective=body.objective.strip(),
    )
    _, _, validation = await _asyncio.gather(insert_task, audit_task, validate_task)

    # Stamp the live verdict back onto the saved document.
    await db.briefs.update_one(
        {"id": brief_id}, {"$set": {"validation": validation}}
    )
    doc["validation"] = validation
    doc.pop("_id", None)
    return doc


@router.get("/contexts/{context_id}/briefs")
async def list_briefs(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    limit: int = 50,
    kind: Optional[str] = None,
):
    """Most-recent-first list for the saved-brief history rail."""
    q: Dict[str, Any] = {
        "context_id": ctx["context"]["id"],
        "account_id": ctx["account"]["id"],
    }
    if kind:
        q["kind"] = kind
    rows = await db.briefs.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return {"items": rows, "count": len(rows)}


@router.get("/contexts/{context_id}/briefs/{brief_id}")
async def get_brief(
    brief_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    doc = await db.briefs.find_one(
        {"id": brief_id, "context_id": ctx["context"]["id"],
         "account_id": ctx["account"]["id"]},
        {"_id": 0},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Brief not found")
    return doc


@router.delete("/contexts/{context_id}/briefs/{brief_id}")
async def delete_brief(
    brief_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.briefs.delete_one(
        {"id": brief_id, "context_id": ctx["context"]["id"],
         "account_id": ctx["account"]["id"]},
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Brief not found")
    return {"ok": True}



# -----------------------------------------------------------------------------
# Minutes — first-class meeting-minutes surface (iter50 v1).
#
# Shape: minutes are documents with `doc_type == "minutes"` plus a small
# `minutes_meta` block we materialise on demand:
#   {meeting_date, attendees[], decisions[], actions[], questions[]}
#
# v1 listing only — actual structured-extraction is deferred to a follow-up
# session along with the action-item↔Cycle linkage. This endpoint already
# treats any document tagged `doc_type=minutes` (or whose filename contains
# "minutes") as a minute, so existing uploads are surfaced immediately.
# -----------------------------------------------------------------------------
@router.get("/contexts/{context_id}/minutes")
async def list_minutes(
    context_id: str,
    limit: int = 50,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    or_clause: List[Dict[str, Any]] = [
        {"doc_type": "minutes"},
        {"name": {"$regex": "minutes", "$options": "i"}},
        {"original_filename": {"$regex": "minutes", "$options": "i"}},
    ]
    docs = await db.documents.find(
        {"context_id": context_id, "$or": or_clause},
        {"_id": 0, "id": 1, "name": 1, "original_filename": 1,
         "created_at": 1, "doc_type": 1, "minutes_meta": 1, "trust_level": 1},
    ).sort("created_at", -1).to_list(max(1, min(limit, 200)))

    out = []
    for d in docs:
        out.append({
            "id": d.get("id"),
            "title": d.get("name") or d.get("original_filename") or "Minutes",
            "filename": d.get("original_filename"),
            "created_at": d.get("created_at"),
            "doc_type": d.get("doc_type") or "minutes",
            "trust_level": d.get("trust_level"),
            "extracted": bool(d.get("minutes_meta")),
            "minutes_meta": d.get("minutes_meta") or None,
        })
    return {"items": out, "count": len(out)}


@router.post("/contexts/{context_id}/minutes/{doc_id}/extract")
async def extract_minutes(
    context_id: str,
    doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """LLM-extract structured minutes data from the document.

    Pulls: meeting_date, attendees[], decisions[], actions[], questions[].
    Caches the result on the document under `minutes_meta` so the structured
    view loads instantly on subsequent reads.
    """
    doc = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id},
        {"_id": 0, "id": 1, "extracted_text": 1, "name": 1,
         "original_filename": 1, "minutes_meta": 1},
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    text = (doc.get("extracted_text") or "").strip()
    if len(text) < 80:
        raise HTTPException(status_code=400, detail="Document has no readable text to extract from.")

    # Build the extraction prompt — strict schema, JSON-only response.
    prompt = (
        "You are reading meeting minutes for an executive who wasn't in the "
        "room. Extract the structured artefacts they need. Be precise. Don't "
        "invent attendees, decisions, or actions that aren't in the text.\n\n"
        f"DOCUMENT TITLE: {doc.get('name') or doc.get('original_filename') or 'Minutes'}\n\n"
        "MINUTES TEXT (truncated to first 12000 chars):\n"
        f"{text[:12000]}\n\n"
        "Return STRICT JSON ONLY with this exact shape:\n"
        "{\"meeting_date\": \"YYYY-MM-DD or null\","
        " \"attendees\": [\"Name (Role if stated)\"],"
        " \"decisions\": [\"<<one sentence each, ≤25 words>>\"],"
        " \"actions\": [{\"who\": \"Name\", \"what\": \"<<verb-led action>>\","
        " \"when\": \"YYYY-MM-DD or 'next meeting' or null\"}],"
        " \"questions\": [\"<<open questions raised but not resolved>>\"]}"
    )
    try:
        from llm_service import call_llm
        llm_out = await call_llm(
            module="minutes_extract",
            user_query=prompt,
            system_override=(
                "You are AKKI's structured-extraction model. Strict JSON only. "
                "Never invent. If a field is genuinely absent from the source, return [] or null."
            ),
            response_format="json",
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Extractor unavailable: {e}") from e

    from helpers.llm_json import safe_parse_json
    parsed, _ = safe_parse_json(llm_out.get("response") or "{}")
    if not parsed:
        raise HTTPException(status_code=502, detail="Extractor returned no usable JSON.")

    minutes_meta = {
        "meeting_date": parsed.get("meeting_date") or None,
        "attendees": [str(a)[:120] for a in (parsed.get("attendees") or []) if str(a).strip()][:20],
        "decisions": [str(d)[:280] for d in (parsed.get("decisions") or []) if str(d).strip()][:30],
        "actions": [
            {
                "who": str(a.get("who") or "")[:80],
                "what": str(a.get("what") or "")[:280],
                "when": (str(a.get("when"))[:40] if a.get("when") else None),
            }
            for a in (parsed.get("actions") or [])
            if isinstance(a, dict) and a.get("what")
        ][:30],
        "questions": [str(q)[:280] for q in (parsed.get("questions") or []) if str(q).strip()][:20],
        "extracted_at": iso(now()),
        "extractor_model": llm_out.get("mode"),
    }

    await db.documents.update_one(
        {"id": doc_id, "context_id": context_id},
        {"$set": {"doc_type": "minutes", "minutes_meta": minutes_meta,
                  "updated_at": iso(now())}},
    )
    await write_audit(
        context_id, ctx["account"]["id"],
        "minutes.extracted", "document", doc_id,
        {"actions": len(minutes_meta["actions"]), "decisions": len(minutes_meta["decisions"])},
    )
    return {"ok": True, "doc_id": doc_id, "minutes_meta": minutes_meta}
