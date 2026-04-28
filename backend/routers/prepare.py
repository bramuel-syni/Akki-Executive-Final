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
    # this never blocks a happy-path brief from saving.
    from llm_service import validate_independent
    validation = await validate_independent(
        kind=body.kind, content=md_body, objective=body.objective.strip(),
    )

    doc = {
        "id": str(uuid.uuid4()),
        "context_id": ctx["context"]["id"],
        "account_id": ctx["account"]["id"],
        "kind": body.kind,
        "objective": body.objective.strip(),
        "title": title[:120],
        "body": md_body,
        "model": llm_out.get("mode"),
        "validated": True,  # stamps the shielded pass for the chip
        "validation": validation,  # NEW: real second-model verdict
        "created_at": iso(now()),
    }
    await db.briefs.insert_one(doc)
    doc.pop("_id", None)

    await write_audit(
        ctx["context"]["id"], ctx["account"]["id"],
        "brief.created", "brief", doc["id"],
        {"kind": body.kind, "objective_chars": len(body.objective)},
    )
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
