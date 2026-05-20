"""Cycle Manager — Phase D Executive flow (MEMO Item 3, D-001).

Extends the existing cycle.py / cycle_config.py / committees.py
endpoints with the rewire endpoints the Phase D brief calls out:

    POST   /api/contexts/{cid}/cycle/agenda
    GET    /api/contexts/{cid}/cycle/agenda
    GET    /api/contexts/{cid}/cycle/team
    POST   /api/contexts/{cid}/cycle/team
    DELETE /api/contexts/{cid}/cycle/team/{member_id}
    POST   /api/contexts/{cid}/cycle/contributions
    GET    /api/contexts/{cid}/cycle/contributions
    POST   /api/contexts/{cid}/cycle/contributions/{cid_contribution}/score
    GET    /api/contexts/{cid}/cycle/readiness
    POST   /api/contexts/{cid}/cycle/follow-ups/draft
    GET    /api/contexts/{cid}/cycle/follow-ups
    POST   /api/contexts/{cid}/cycle/follow-ups/{fid}/approve
    POST   /api/contexts/{cid}/cycle/follow-ups/{fid}/send
    POST   /api/contexts/{cid}/cycle/draft-compilation

D-001 — outbound follow-ups go through Resend with the forwarding
alias `akki+<slug>@syni.ai` as the From; Resend test-mode is fine in
dev.

D-003 — NED-side flow ships as design only (see
docs/NED_CYCLE_MANAGER_DESIGN.md), so no NED endpoints here.

NEW collections
---------------
db.cycle_agendas        one row per cycle (per active context)
db.cycle_team           team members with contribution descriptions
db.cycle_contributions  uploaded/forwarded items mapped to agenda items
db.cycle_followups      draft + sent follow-ups (Akki-for-<exec>)

The existing committees / cycle_config / questions / submissions
collections are NOT touched — D-Phase is additive.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from core import db, iso, now, require_context_membership, write_audit
import email_service

logger = logging.getLogger("akki.cycle_manager")

router = APIRouter(prefix="/api")


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
def _ctx_slug(name: Optional[str]) -> str:
    """Per D-001 — forwarding alias body, e.g. 'Bram' → 'bram'."""
    s = (name or "exec").lower()
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s or "exec"


async def _get_or_init_agenda(
    context_id: str,
    account_id: str,
    cycle_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve the agenda row for a cycle.

    Multi-cycle (v2) call paths: pass `cycle_id` explicitly. Legacy
    (single-cycle) call paths: leave `cycle_id` as None — we resolve
    the unique active cycle for the context via
    `services.cycle_lifecycle.resolve_implicit_cycle_id`.
    """
    from services.cycle_lifecycle import resolve_implicit_cycle_id  # noqa: WPS433

    cycle_id = await resolve_implicit_cycle_id(context_id, cycle_id)
    if cycle_id:
        row = await db.cycle_agendas.find_one({"id": cycle_id}, {"_id": 0})
        if row:
            return row
        # The cycle exists in `db.cycles` but the agenda shell hasn't
        # been created — create it now so downstream queries succeed.
        rec = {
            "id": cycle_id,
            "cycle_id": cycle_id,
            "context_id": context_id,
            "account_id": account_id,
            "title": "Main board reporting cycle",
            "items": [],
            "status": "active",
            "created_at": iso(now()),
            "updated_at": iso(now()),
        }
        await db.cycle_agendas.insert_one(rec)
        rec.pop("_id", None)
        return rec
    # Truly legacy fallback — no cycle, no cycles row. Auto-create on first hit.
    row = await db.cycle_agendas.find_one(
        {"context_id": context_id, "status": "active"}, {"_id": 0},
    )
    if row:
        return row
    rec = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "account_id": account_id,
        "title": "Main board reporting cycle",
        "items": [],
        "status": "active",
        "created_at": iso(now()),
        "updated_at": iso(now()),
    }
    rec["cycle_id"] = rec["id"]
    await db.cycle_agendas.insert_one(rec)
    rec.pop("_id", None)
    return rec


# ──────────────────────────────────────────────────────────────────────
# Request bodies
# ──────────────────────────────────────────────────────────────────────
class AgendaItemIn(BaseModel):
    id: Optional[str] = None
    label: str = Field(min_length=1, max_length=200)
    owner_label: Optional[str] = Field(default=None, max_length=120)


class AgendaIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    items: List[AgendaItemIn] = Field(default_factory=list, max_length=30)


class TeamMemberIn(BaseModel):
    id: Optional[str] = None
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    role: Optional[str] = Field(default=None, max_length=80)
    contribution_description: str = Field(min_length=1, max_length=600)
    owns_item_ids: List[str] = Field(default_factory=list)


class ContributionIn(BaseModel):
    # QA-2026-05-16-005 (2026-05-18): doc-attached contributions from
    # Document Journal don't carry a team_member_id or agenda_item_id
    # at the entry point — the user picks the document first and the
    # cycle/contributor mapping is supplied later from the dedicated
    # 3-step modal (-005 P1 scope). Both fields are now optional and
    # `document` is a first-class kind so the unblocking path can land
    # immediately without the full modal redesign.
    agenda_item_id: Optional[str] = None
    team_member_id: Optional[str] = None
    kind: str = Field(default="note", pattern=r"^(note|document|email|chat)$")
    source_doc_id: Optional[str] = None
    body_text: Optional[str] = Field(default=None, max_length=20000)
    title: Optional[str] = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def _qa_021_at_least_one_input(self) -> "ContributionIn":
        # QA-2026-05-16-021 (Chunk-9, 2026-05-18) — defensive backend
        # echo of the frontend CTA-gating rule. The Record-Contribution
        # button is disabled until the user provides at least one
        # input, but the backend MUST enforce the contract too — never
        # accept an empty contribution row that the scorer can't
        # meaningfully grade.
        has_body = bool((self.body_text or "").strip())
        has_doc = bool(self.source_doc_id)
        if not (has_body or has_doc):
            raise ValueError(
                "Contribution must include at least one of `body_text` or "
                "`source_doc_id` (QA-2026-05-16-021)."
            )
        return self


class ScoreIn(BaseModel):
    relevance: Optional[int] = Field(default=None, ge=0, le=100)
    fullness:  Optional[int] = Field(default=None, ge=0, le=100)
    readiness: Optional[int] = Field(default=None, ge=0, le=100)
    rationale: Optional[str] = Field(default=None, max_length=600)


class FollowUpsDraftIn(BaseModel):
    item_ids: Optional[List[str]] = None  # if None → all unmet


# ──────────────────────────────────────────────────────────────────────
# Agenda endpoints
# ──────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/cycle/agenda")
async def get_agenda(
    context_id: str,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"], cycle_id)
    return agenda


@router.post("/contexts/{context_id}/cycle/agenda")
async def upsert_agenda(
    context_id: str, body: AgendaIn,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"], cycle_id)
    from services.cycle_lifecycle import require_cycle_writable as _rcw  # noqa: WPS433
    await _rcw(context_id, agenda["id"])
    items: List[Dict[str, Any]] = []
    for it in body.items:
        items.append({
            "id": it.id or str(uuid.uuid4()),
            "label": it.label.strip(),
            "owner_label": (it.owner_label or "").strip() or None,
        })
    await db.cycle_agendas.update_one(
        {"id": agenda["id"]},
        {"$set": {
            "title": body.title.strip(),
            "items": items,
            "updated_at": iso(now()),
        }},
    )
    try:
        await write_audit(
            context_id, ctx["account"]["id"],
            "cycle.agenda.updated", "cycle_agenda", agenda["id"],
            {"title": body.title.strip(), "items_count": len(items)},
        )
    except Exception:
        pass
    return await db.cycle_agendas.find_one({"id": agenda["id"]}, {"_id": 0})


# ──────────────────────────────────────────────────────────────────────
# Team endpoints
# ──────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/cycle/team")
async def list_team(
    context_id: str,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"], cycle_id)
    members = await db.cycle_team.find(
        {"context_id": context_id, "agenda_id": agenda["id"], "status": "active"},
        {"_id": 0},
    ).sort("created_at", 1).to_list(100)
    return {"agenda_id": agenda["id"], "cycle_id": agenda["id"], "members": members}


@router.post("/contexts/{context_id}/cycle/team")
async def upsert_team_member(
    context_id: str, body: TeamMemberIn,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"], cycle_id)
    from services.cycle_lifecycle import require_cycle_writable as _rcw  # noqa: WPS433
    await _rcw(context_id, agenda["id"])
    if body.id:
        existing = await db.cycle_team.find_one(
            {"id": body.id, "context_id": context_id}, {"_id": 0},
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Team member not found")
        upd = {
            "name": body.name.strip(),
            "email": body.email.strip().lower(),
            "role": (body.role or "").strip() or None,
            "contribution_description": body.contribution_description.strip(),
            "owns_item_ids": body.owns_item_ids,
            "updated_at": iso(now()),
        }
        await db.cycle_team.update_one({"id": body.id}, {"$set": upd})
        return await db.cycle_team.find_one({"id": body.id}, {"_id": 0})
    rec = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "agenda_id": agenda["id"],
        "cycle_id": agenda["id"],
        "name": body.name.strip(),
        "email": body.email.strip().lower(),
        "role": (body.role or "").strip() or None,
        "contribution_description": body.contribution_description.strip(),
        "owns_item_ids": body.owns_item_ids,
        "status": "active",
        "created_at": iso(now()),
        "updated_at": iso(now()),
    }
    await db.cycle_team.insert_one(rec)
    rec.pop("_id", None)
    return rec


@router.delete("/contexts/{context_id}/cycle/team/{member_id}")
async def delete_team_member(
    context_id: str, member_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    existing = await db.cycle_team.find_one(
        {"id": member_id, "context_id": context_id}, {"_id": 0, "agenda_id": 1, "cycle_id": 1},
    )
    if existing:
        from services.cycle_lifecycle import require_cycle_writable as _rcw  # noqa: WPS433
        await _rcw(context_id, existing.get("agenda_id") or existing.get("cycle_id"))
    res = await db.cycle_team.update_one(
        {"id": member_id, "context_id": context_id},
        {"$set": {"status": "removed", "updated_at": iso(now())}},
    )
    return {"ok": res.modified_count > 0, "id": member_id}


# Phase D.3 — explicit PATCH for clean inline-edit UX in the Team step.
# Idempotent edit of a single team member; honours every field the
# upsert path accepts, but expressed as a plain PATCH so the frontend
# doesn't need to round-trip a full body on every save. Returns 404
# when the member doesn't exist, 410 when it has been removed.
class TeamMemberPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[str] = Field(default=None, min_length=3, max_length=200)
    role: Optional[str] = Field(default=None, max_length=80)
    contribution_description: Optional[str] = Field(default=None, min_length=1, max_length=600)
    owns_item_ids: Optional[List[str]] = None


@router.patch("/contexts/{context_id}/cycle/team/{member_id}")
async def patch_team_member(
    context_id: str, member_id: str, body: TeamMemberPatch,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    existing = await db.cycle_team.find_one(
        {"id": member_id, "context_id": context_id}, {"_id": 0},
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Team member not found")
    if existing.get("status") == "removed":
        raise HTTPException(status_code=410, detail="Team member has been removed")

    from services.cycle_lifecycle import require_cycle_writable as _rcw  # noqa: WPS433
    await _rcw(context_id, existing.get("agenda_id") or existing.get("cycle_id"))

    upd: Dict[str, Any] = {"updated_at": iso(now())}
    if body.name is not None:
        upd["name"] = body.name.strip()
    if body.email is not None:
        upd["email"] = body.email.strip().lower()
    if body.role is not None:
        upd["role"] = body.role.strip() or None
    if body.contribution_description is not None:
        upd["contribution_description"] = body.contribution_description.strip()
    if body.owns_item_ids is not None:
        upd["owns_item_ids"] = body.owns_item_ids

    # No-op patch (no editable fields supplied) — return the row unchanged.
    if len(upd) == 1:  # just updated_at
        return existing

    await db.cycle_team.update_one({"id": member_id}, {"$set": upd})
    try:
        await write_audit(
            context_id, ctx["account"]["id"],
            "cycle.team.member.updated", "cycle_team_member", member_id,
            {"changed_fields": [k for k in upd if k != "updated_at"]},
        )
    except Exception:
        pass
    fresh = await db.cycle_team.find_one({"id": member_id}, {"_id": 0})
    return fresh


# ──────────────────────────────────────────────────────────────────────
# Contributions
# ──────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/cycle/contributions")
async def list_contributions(
    context_id: str,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"], cycle_id)
    rows = await db.cycle_contributions.find(
        {"context_id": context_id, "agenda_id": agenda["id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(500)
    return {"agenda_id": agenda["id"], "cycle_id": agenda["id"], "contributions": rows}


@router.post("/contexts/{context_id}/cycle/contributions")
async def add_contribution(
    context_id: str, body: ContributionIn,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"], cycle_id)
    from services.cycle_lifecycle import require_cycle_writable as _rcw  # noqa: WPS433
    await _rcw(context_id, agenda["id"])
    rec = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "agenda_id": agenda["id"],
        "cycle_id": agenda["id"],
        "agenda_item_id": body.agenda_item_id,
        "team_member_id": body.team_member_id,
        "kind": body.kind,
        "title": (body.title or "").strip() or None,
        "source_doc_id": body.source_doc_id,
        "body_text": (body.body_text or "").strip() or None,
        "scores": None,
        "scored_at": None,
        "scored_by": None,
        "status": "pending",
        "created_at": iso(now()),
    }
    await db.cycle_contributions.insert_one(rec)
    rec.pop("_id", None)
    return rec


# ──────────────────────────────────────────────────────────────────────
# Eligible contributors — PO decision #2 (filtered dropdown)
# ──────────────────────────────────────────────────────────────────────
@router.get(
    "/contexts/{context_id}/cycles/{cycle_id}/agenda-items/"
    "{agenda_item_id}/eligible-contributors",
)
async def list_eligible_contributors(
    context_id: str,
    cycle_id: str,
    agenda_item_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Return team members assigned to a specific agenda item on a
    specific cycle. Used to scope the Contributions tab contributor
    dropdown per PO decision #2."""
    rows = await db.cycle_team.find(
        {
            "context_id": context_id,
            "agenda_id": cycle_id,
            "status": "active",
            "owns_item_ids": agenda_item_id,
        },
        {"_id": 0, "id": 1, "name": 1, "email": 1, "role": 1,
         "contribution_description": 1, "owns_item_ids": 1},
    ).sort("name", 1).to_list(200)
    return {
        "cycle_id": cycle_id,
        "agenda_item_id": agenda_item_id,
        "contributors": rows,
        "count": len(rows),
    }


# ──────────────────────────────────────────────────────────────────────
# Scoring — three-dim (relevance / fullness / readiness)
# ──────────────────────────────────────────────────────────────────────
def _heuristic_score(body_text: Optional[str], description: Optional[str]) -> Dict[str, int]:
    """Deterministic backstop when the LLM stage is unavailable. Phase D
    treats the LLM scorer as the canonical path; this heuristic gives
    callers a useful fallback that preserves the three-dimension shape
    (and lets the test path be deterministic)."""
    text = (body_text or "").strip()
    desc = (description or "").strip().lower()
    char_len = len(text)
    # Fullness — purely length-based, capped.
    fullness = min(100, int((char_len / 800.0) * 100))
    # Readiness — penalised when text contains "draft", "tbc", "todo".
    drafty = any(t in text.lower() for t in ("draft", "tbc", "todo", "tbd", "wip"))
    readiness = max(10, fullness - (40 if drafty else 0))
    # Relevance — token overlap with the team member's contribution
    # description; falls back to mid-band if no description.
    if desc:
        desc_tokens = set(re.findall(r"[a-z]{4,}", desc))
        text_tokens = set(re.findall(r"[a-z]{4,}", text.lower()))
        overlap = len(desc_tokens & text_tokens)
        relevance = min(100, 30 + overlap * 12)
    else:
        relevance = 55
    return {
        "relevance": int(relevance),
        "fullness":  int(fullness),
        "readiness": int(readiness),
    }


@router.post("/contexts/{context_id}/cycle/contributions/{contribution_id}/score")
async def score_contribution(
    context_id: str, contribution_id: str, body: ScoreIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Score a contribution on relevance / fullness / readiness.
    If the request omits any dimension, the heuristic backstop fills it
    in. (LLM-driven scoring is the future-canonical path; for D1 we
    accept manual + heuristic so tests stay deterministic.)

    QA-2026-05-16-020 (2026-05-18, Chunk-9): when the contribution
    carries a `source_doc_id`, the scorer concatenates the document's
    `extracted_text` after the pasted body_text — single combined
    string, single rubric pass — so an attachment alone OR pasted
    text alone OR both score against the same combined-content
    fullness/relevance/readiness rubric.
    """
    rec = await db.cycle_contributions.find_one(
        {"id": contribution_id, "context_id": context_id}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Contribution not found")
    from services.cycle_lifecycle import require_cycle_writable as _rcw  # noqa: WPS433
    await _rcw(context_id, rec.get("agenda_id") or rec.get("cycle_id"))
    member = await db.cycle_team.find_one(
        {"id": rec.get("team_member_id"), "context_id": context_id}, {"_id": 0},
    )
    desc = (member or {}).get("contribution_description", "")

    # QA-2026-05-16-020 — combined-content build: body_text + a
    # marker + the attached doc's extracted_text. Decision (a) from
    # the Chunk-9 dispatch: concatenate, single heuristic pass.
    combined_text = await _build_combined_contribution_text(
        context_id=context_id,
        body_text=rec.get("body_text"),
        source_doc_id=rec.get("source_doc_id"),
    )

    auto = _heuristic_score(combined_text, desc)
    scores = {
        "relevance": body.relevance if body.relevance is not None else auto["relevance"],
        "fullness":  body.fullness  if body.fullness  is not None else auto["fullness"],
        "readiness": body.readiness if body.readiness is not None else auto["readiness"],
    }
    update = {
        "scores": scores,
        "score_rationale": (body.rationale or "").strip() or None,
        "scored_at": iso(now()),
        "scored_by": ("user" if (body.relevance is not None
                                 or body.fullness is not None
                                 or body.readiness is not None) else "akki-heuristic"),
        "status": "scored",
        # QA-2026-05-16-020 — surface the combined-scoring decision on
        # the row so the UI can render "Scored: attached document +
        # pasted text" if both contributed. Also useful for tests +
        # any future audit.
        "scoring_input": {
            "has_body_text": bool((rec.get("body_text") or "").strip()),
            "has_attachment": bool(rec.get("source_doc_id")),
            "combined_char_count": len(combined_text),
        },
    }
    await db.cycle_contributions.update_one(
        {"id": contribution_id}, {"$set": update},
    )
    return {**rec, **update}


async def _build_combined_contribution_text(
    *,
    context_id: str,
    body_text: Optional[str],
    source_doc_id: Optional[str],
) -> str:
    """QA-2026-05-16-020 combined-content build (decision a).

    Returns the pasted body_text + attached doc's extracted_text
    concatenated with a separator. Either side may be empty — if
    the doc lookup fails we silently fall back to body_text alone
    (a missing attachment shouldn't 500 the score endpoint).
    """
    parts: List[str] = []
    body = (body_text or "").strip()
    if body:
        parts.append(body)
    if source_doc_id:
        doc = await db.documents.find_one(
            {"id": source_doc_id, "context_id": context_id},
            {"_id": 0, "name": 1, "original_filename": 1, "extracted_text": 1},
        )
        if doc:
            title = doc.get("name") or doc.get("original_filename") or "attached document"
            extracted = (doc.get("extracted_text") or "").strip()
            if extracted:
                parts.append(f"[Attached: {title}]\n{extracted}")
            else:
                # Doc exists but no text extracted (e.g. binary image
                # before OCR completes). Still surface the title so
                # the heuristic can pick up the doc's name tokens in
                # the relevance overlap.
                parts.append(f"[Attached: {title}]")
    return "\n\n".join(parts)


# ──────────────────────────────────────────────────────────────────────
# Readiness scoreboard
# ──────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/cycle/readiness")
async def get_readiness(
    context_id: str,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"], cycle_id)
    contribs = await db.cycle_contributions.find(
        {"context_id": context_id, "agenda_id": agenda["id"]}, {"_id": 0},
    ).to_list(500)
    members = await db.cycle_team.find(
        {"context_id": context_id, "agenda_id": agenda["id"], "status": "active"},
        {"_id": 0},
    ).to_list(100)

    item_rows: List[Dict[str, Any]] = []
    weak_items = []
    pending_items = []
    for it in agenda.get("items", []):
        item_contribs = [c for c in contribs if c.get("agenda_item_id") == it["id"]]
        scored = [c for c in item_contribs if c.get("scores")]
        owners = [m for m in members if it["id"] in (m.get("owns_item_ids") or [])]
        if scored:
            avg = {
                k: int(sum(c["scores"][k] for c in scored) / len(scored))
                for k in ("relevance", "fullness", "readiness")
            }
            overall = int((avg["relevance"] + avg["fullness"] + avg["readiness"]) / 3)
        else:
            avg = {"relevance": 0, "fullness": 0, "readiness": 0}
            overall = 0
        item_row = {
            "item_id":      it["id"],
            "label":        it["label"],
            "contribs":     len(item_contribs),
            "scored":       len(scored),
            "owners":       [{"id": m["id"], "name": m["name"], "email": m["email"]} for m in owners],
            "avg_relevance": avg["relevance"],
            "avg_fullness":  avg["fullness"],
            "avg_readiness": avg["readiness"],
            "overall":       overall,
            "status": (
                "ready"   if overall >= 75 else
                "thin"    if overall >= 40 else
                "missing" if not item_contribs else
                "weak"
            ),
        }
        item_rows.append(item_row)
        if item_row["status"] in ("missing", "weak"):
            weak_items.append(item_row)
        if item_row["status"] == "missing":
            pending_items.append(item_row)

    overall_avg = (
        int(sum(r["overall"] for r in item_rows) / len(item_rows))
        if item_rows else 0
    )

    # Summary storyline — voiced for restraint, not chase-the-tail.
    storyline_lines: List[str] = []
    if not item_rows:
        storyline_lines.append("No agenda items yet — start with two or three the board needs in front of them.")
    else:
        ready = [r for r in item_rows if r["status"] == "ready"]
        if ready:
            storyline_lines.append(
                f"{len(ready)} item{'s' if len(ready)!=1 else ''} read at draft strength: "
                + ", ".join(r["label"] for r in ready[:3]) + "."
            )
        if weak_items:
            storyline_lines.append(
                f"{len(weak_items)} item{'s' if len(weak_items)!=1 else ''} still thin or missing: "
                + ", ".join(r["label"] for r in weak_items[:3]) + "."
            )
        if pending_items:
            storyline_lines.append(
                "Pending owners: " + ", ".join(
                    f"{r['label']} · " + ", ".join(o["name"] for o in r["owners"])
                    for r in pending_items[:3]
                ) + "."
            )
        if overall_avg >= 65 and not pending_items:
            storyline_lines.append(
                "Compilation can stand on its own as a draft — judgement call when to send."
            )

    return {
        "agenda":     agenda,
        "items":      item_rows,
        "overall":    overall_avg,
        "storyline":  storyline_lines,
        "weak_count": len(weak_items),
        "pending_count": len(pending_items),
    }


# ──────────────────────────────────────────────────────────────────────
# Akki-for-<exec> follow-ups
# ──────────────────────────────────────────────────────────────────────
def _draft_email_text(*, exec_name: str, member_name: str, item_label: str,
                      contribution_desc: str) -> Dict[str, str]:
    """Deterministic restrained draft. The user reviews + approves
    before any send; voice is preserved by short, plain-prose copy."""
    subject = f"Quick chase on {item_label} for the next cycle"
    body = (
        f"Hi {member_name},\n\n"
        f"AKKI is helping me pull the next cycle together on {exec_name}'s behalf.\n"
        f"On {item_label}, we have you down for: {contribution_desc}.\n\n"
        f"Could you send through what you have so far? A draft is fine — "
        f"we'll score it and come back to you if anything's missing.\n\n"
        f"Thanks,\nAKKI for {exec_name}"
    )
    html = (
        "<p>Hi " + member_name + ",</p>"
        + "<p>AKKI is helping me pull the next cycle together on "
        + exec_name + "'s behalf.</p>"
        + "<p>On <strong>" + item_label + "</strong>, we have you down for: "
        + contribution_desc + ".</p>"
        + "<p>Could you send through what you have so far? A draft is fine — "
        + "we'll score it and come back to you if anything's missing.</p>"
        + "<p>Thanks,<br>AKKI for " + exec_name + "</p>"
    )
    return {"subject": subject, "body": body, "html": html}


@router.post("/contexts/{context_id}/cycle/follow-ups/draft")
async def draft_followups(
    context_id: str, body: FollowUpsDraftIn,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Generate restrained follow-up drafts for unmet contributions.
    Returns the drafts; nothing is sent."""
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"], cycle_id)
    from services.cycle_lifecycle import require_cycle_writable as _rcw  # noqa: WPS433
    await _rcw(context_id, agenda["id"])
    members = await db.cycle_team.find(
        {"context_id": context_id, "agenda_id": agenda["id"], "status": "active"},
        {"_id": 0},
    ).to_list(100)
    contribs = await db.cycle_contributions.find(
        {"context_id": context_id, "agenda_id": agenda["id"]}, {"_id": 0},
    ).to_list(500)

    exec_name = ctx["account"].get("name") or ctx["account"].get("email") or "the executive"
    requested_items = set(body.item_ids or [it["id"] for it in agenda.get("items", [])])

    drafts: List[Dict[str, Any]] = []
    for it in agenda.get("items", []):
        if it["id"] not in requested_items:
            continue
        item_contribs = [c for c in contribs if c.get("agenda_item_id") == it["id"]]
        # Unmet = no contributions, or all scored < 50 readiness on average
        if item_contribs:
            scored = [c for c in item_contribs if c.get("scores")]
            avg_readiness = (
                int(sum(c["scores"]["readiness"] for c in scored) / len(scored))
                if scored else 0
            )
            if scored and avg_readiness >= 60:
                continue  # already strong
        owners = [m for m in members if it["id"] in (m.get("owns_item_ids") or [])]
        if not owners:
            continue
        for owner in owners:
            text = _draft_email_text(
                exec_name=exec_name,
                member_name=owner.get("name") or "there",
                item_label=it["label"],
                contribution_desc=owner.get("contribution_description") or "your section",
            )
            rec = {
                "id": str(uuid.uuid4()),
                "context_id": context_id,
                "account_id": ctx["account"]["id"],
                "agenda_id": agenda["id"],
                "cycle_id": agenda["id"],
                "agenda_item_id": it["id"],
                "agenda_item_label": it["label"],
                "team_member_id": owner["id"],
                "to_email": owner["email"],
                "to_name": owner.get("name"),
                "draft_subject": text["subject"],
                "draft_body": text["body"],
                "draft_html": text["html"],
                "status": "draft",
                "created_at": iso(now()),
                "approved_at": None,
                "sent_at": None,
                "send_mode": None,
                "send_id": None,
                # Phase D.2 — replies array starts empty; gets populated
                # by the cycle-reply branch in routers/inbound_email.py.
                "replies": [],
                "last_reply_at": None,
            }
            await db.cycle_followups.insert_one(rec)
            rec.pop("_id", None)
            drafts.append(rec)

    return {"drafts": drafts, "count": len(drafts)}


@router.get("/contexts/{context_id}/cycle/follow-ups")
async def list_followups(
    context_id: str,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"], cycle_id)
    rows = await db.cycle_followups.find(
        {"context_id": context_id, "agenda_id": agenda["id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    return {"agenda_id": agenda["id"], "cycle_id": agenda["id"], "followups": rows}


@router.post("/contexts/{context_id}/cycle/follow-ups/{followup_id}/approve")
async def approve_followup(
    context_id: str, followup_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    rec = await db.cycle_followups.find_one(
        {"id": followup_id, "context_id": context_id}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    from services.cycle_lifecycle import require_cycle_writable as _rcw  # noqa: WPS433
    await _rcw(context_id, rec.get("agenda_id") or rec.get("cycle_id"))
    if rec["status"] not in ("draft",):
        return rec
    await db.cycle_followups.update_one(
        {"id": followup_id},
        {"$set": {"status": "approved", "approved_at": iso(now())}},
    )
    rec["status"] = "approved"
    rec["approved_at"] = iso(now())
    return rec


@router.post("/contexts/{context_id}/cycle/follow-ups/{followup_id}/send")
async def send_followup(
    context_id: str, followup_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Phase D.2 — send an approved follow-up via Resend using the
    Cycle Manager outbound posture:

      From      :  '<Executive Name> (via Akki)' <noreply@cycles.akki.ai>
      Reply-To  :  <account-uuid>@cycles.akki.ai     (opaque alias)

    The reply-to alias is deterministic per account (UUIDv5). Inbound
    replies hit the Postmark webhook (`routers/inbound_email.py`) and
    are threaded back to this `cycle_followups` row by alias→account
    lookup + most-recent-unanswered-followup-to-this-recipient match.
    """
    rec = await db.cycle_followups.find_one(
        {"id": followup_id, "context_id": context_id}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    if rec["status"] not in ("approved", "draft"):
        return rec  # idempotent

    exec_name = ctx["account"].get("name") or "the executive"
    reply_to = email_service.cycles_alias_for(ctx["account"]["id"])

    try:
        result = await email_service.send_email(
            to=[rec["to_email"]],
            subject=rec["draft_subject"],
            html=rec["draft_html"],
            text=rec["draft_body"],
            from_executive_name=exec_name,
            reply_to=reply_to,
            posture="cycle",
            tags=[
                {"name": "surface", "value": "cycle_followup"},
                {"name": "context_id", "value": context_id},
                {"name": "followup_id", "value": followup_id},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("cycle follow-up send failed")
        await db.cycle_followups.update_one(
            {"id": followup_id},
            {"$set": {
                "status": "send_failed",
                "send_mode": "error",
                "send_error": str(exc)[:300],
                "sent_at": iso(now()),
            }},
        )
        return {"ok": False, "error": str(exc)[:300]}

    await db.cycle_followups.update_one(
        {"id": followup_id},
        {"$set": {
            "status": "sent" if result.get("ok") else "send_skipped",
            "send_mode": result.get("mode"),
            "send_id": result.get("id"),
            "sent_at": iso(now()),
            "from_header": result.get("from"),
            "reply_to_alias": reply_to,
        }},
    )
    try:
        await write_audit(
            context_id, ctx["account"]["id"],
            "cycle.followup.sent", "cycle_followup", followup_id,
            {
                "to": rec["to_email"],
                "mode": result.get("mode"),
                "from_header": result.get("from"),
                "reply_to_alias": reply_to,
                "send_id": result.get("id"),
            },
        )
    except Exception:
        pass
    return {
        "ok": result.get("ok"),
        "mode": result.get("mode"),
        "send_id": result.get("id"),
        "from_header": result.get("from"),
        "reply_to_alias": reply_to,
        "followup_id": followup_id,
    }


# ──────────────────────────────────────────────────────────────────────
# Draft Compilation Output — Phase D.1 rebuild
# ──────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/cycle/draft-compilation", status_code=202)
async def draft_compilation(
    context_id: str,
    cycle_id: Optional[str] = Query(default=None),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Chunk 2 (CM-R04) — async pattern.

    Returns **202 + `job_id`** immediately. The two-pass LLM compile
    (drafter Sonnet 4.5 → validator Gemini 2.5 Flash) + brief
    persistence + DOCX render runs as a fire-and-forget asyncio task.
    Frontend polls `GET /api/jobs/{job_id}` until terminal and then
    consumes `result` (which carries `redirect_url`, `export_id`,
    `byte_len`, etc. — the legacy sync response shape preserved).

    The pre-flight checks (agenda exists + contributions exist) run
    synchronously so the user sees those 400s instantly without a
    polling round-trip.
    """
    from services.job_queue import (
        create_job as _create_job, mark_running as _mark_running,
        mark_completed as _mark_completed, mark_failed as _mark_failed,
        spawn as _spawn,
    )

    # Pre-flight (synchronous, < 100 ms — surface 400s immediately).
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"], cycle_id)
    if not agenda.get("items"):
        raise HTTPException(status_code=400, detail="Set an agenda first.")
    contrib_count = await db.cycle_contributions.count_documents(
        {"context_id": context_id, "agenda_id": agenda["id"]},
    )
    if contrib_count == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "no_contributions",
                "message": "Add at least one contribution before compiling.",
            },
        )

    job_id = await _create_job(
        kind="cycle.draft_compilation",
        account_id=ctx["account"]["id"],
        context_id=context_id,
        input_summary={
            "agenda_id": agenda["id"],
            "cycle_id": cycle_id or agenda["id"],
            "contrib_count": contrib_count,
        },
    )

    background_account_id = ctx["account"]["id"]
    background_context_name = ctx["context"].get("name") or "Akki"
    background_executive_name = ctx["account"].get("name") or "—"

    async def _runner():
        await _mark_running(job_id)
        try:
            result = await _draft_compilation_worker(
                context_id=context_id, cycle_id=cycle_id,
                account_id=background_account_id,
                context_name=background_context_name,
                executive_name=background_executive_name,
            )
            await _mark_completed(job_id, result)
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, (str, dict)) else str(e.detail)
            await _mark_failed(job_id, f"http_{e.status_code}: {detail}")
        except Exception as e:
            logger.exception("cycle.draft_compilation worker crashed (job=%s)", job_id)
            await _mark_failed(job_id, f"{type(e).__name__}: {str(e)[:400]}")

    _spawn(_runner())
    return {"job_id": job_id, "status": "queued", "agenda_id": agenda["id"]}


async def _draft_compilation_worker(
    *, context_id: str, cycle_id: Optional[str],
    account_id: str, context_name: str, executive_name: str,
) -> Dict[str, Any]:
    """Phase D.1 — produce a real, board-grade compilation of the cycle's
    scored contributions and persist it as a Work Studio Brief.

    The compilation flows through the same pipeline as Solva-originated
    Briefs (C.1 → C.2 → C.3) so the executive can Refine via two-pass
    enhance and Export at any of the 18 (Format × Depth × Fidelity)
    combinations. The pre-D.1 heuristic concat-of-bullets path has been
    deleted — that was the spec's P0 cohort blocker.

    Cycle Manager v2 (2026-02): explicitly permitted on **completed**
    cycles — re-download is an Acceptance criterion. The completed-cycle
    write-guard is therefore NOT applied here.

    Pipeline:
      1. Gather agenda, scored contributions, team, readiness, prior cycles.
      2. Two-pass LLM via services.cycle_synthesis.synthesise_cycle.
         Drafter (Sonnet 4.5) emits a strict-JSON envelope with executive
         summary, per-item synthesis, outstanding items, next-cycle
         adjustments, and (when prior cycles exist) cross-cycle
         observations. Validator (Gemini 2.5 Flash) scores drift.
      3. Convert to a Solva-shaped envelope so build_brief_from_solva
         produces a normal Brief dataclass.
      4. ensure_brief_persisted (C.2) — yields a stable brief_id.
      5. Render an immediate DOCX (Board Summary / High Fidelity) via the
         C.1 generator so the executive gets a download chip and the
         existing UI keeps working. The export_id round-trip via the
         legacy collection is gone.
      6. Audit. Continue-in-Chat handoff still mints a chat seeded with
         the compilation prose (kept for parity with prior UX).
    """
    from work_studio import (
        build_brief_from_solva, ensure_brief_persisted, render_docx,
    )
    from work_studio.persistence import compute_brief_id
    from services.cycle_synthesis import synthesise_cycle
    from datetime import datetime, timezone
    import hashlib

    agenda = await _get_or_init_agenda(context_id, account_id, cycle_id)
    # Pre-flight already verified — but be defensive in case the
    # job ran a long time and state mutated.
    if not agenda.get("items"):
        raise HTTPException(status_code=400, detail="Set an agenda first.")

    contribs = await db.cycle_contributions.find(
        {"context_id": context_id, "agenda_id": agenda["id"]}, {"_id": 0},
    ).to_list(500)
    members = await db.cycle_team.find(
        {"context_id": context_id, "agenda_id": agenda["id"], "status": "active"},
        {"_id": 0},
    ).to_list(100)

    if not contribs:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "no_contributions",
                "message": "Add at least one contribution before compiling.",
            },
        )

    # Readiness rollup (the existing endpoint shape). `get_readiness` is
    # an endpoint handler that expects a dependency-injected `ctx` dict.
    # We synthesise the minimum shape it actually reads.
    synthetic_ctx = {"account": {"id": account_id},
                     "context": {"id": context_id, "name": context_name}}
    readiness = await get_readiness(context_id, agenda["id"], synthetic_ctx)

    # Prior cycles for cross-cycle observations (omit when first cycle —
    # spec call #2: honest empty, no placeholder text). Pull at most the
    # 3 most-recent compiled cycles for this context.
    prior_cycles = await db.cycle_history.find(
        {"context_id": context_id, "status": "completed"},
        {"_id": 0, "id": 1, "title": 1, "completed_at": 1, "summary": 1},
    ).sort("completed_at", -1).to_list(3)

    envelope = {
        "context_name": context_name,
        "executive_name": executive_name,
        "period": iso(now())[:10],
        "agenda_id": agenda["id"],
        "source_id": agenda["id"],
        "agenda": {
            "id": agenda["id"],
            "title": agenda.get("title") or "Cycle compilation",
            "items": agenda.get("items") or [],
        },
        "team": [
            {"id": m["id"], "name": m.get("name", ""),
             "role": m.get("role", ""), "owns_item_ids": m.get("owns_item_ids", []),
             "contribution_description": m.get("contribution_description", "")}
            for m in members
        ],
        "contributions": [
            {"id": c["id"],
             "agenda_item_id": c.get("agenda_item_id", ""),
             "team_member_id": c.get("team_member_id", ""),
             "title": c.get("title", ""),
             "body_text": c.get("body_text", ""),
             "scores": c.get("scores") or {},
             "score_rationale": c.get("score_rationale", "")}
            for c in contribs
        ],
        "readiness": readiness,
        "prior_cycles": prior_cycles,
    }

    # Two-pass LLM synthesis.
    synth_result = await synthesise_cycle(
        envelope=envelope,
        account_id=account_id,
        context_id=context_id,
    )
    if not synth_result.get("ok"):
        raise HTTPException(
            status_code=502,
            detail={
                "code": "compilation_drafter_failed",
                "message": "The two-pass drafter could not produce a valid envelope. Try again, or split overly long contributions.",
                "drafter_excerpt": synth_result.get("drafter_raw_excerpt", "")[:300],
            },
        )

    # Build the Brief and persist via C.2 — yields a deterministic brief_id
    # keyed on (account_id, "cycle_compilation", agenda_id) so re-running
    # the compilation against the same agenda is idempotent at the brief
    # level. Each call still creates a fresh revision through the normal
    # C.2 flow when the user hits Refine.
    company_label = context_name
    brief = build_brief_from_solva(
        synth_result["solva_shaped_envelope"],
        company_label=company_label,
        document_type="Cycle Compilation",
        programme=agenda.get("title") or None,
        depth="board_summary",
        fidelity="low",   # composer-edit-friendly seed (per Phase D rule)
    )
    # Cycle-specific overrides on the Solva-shaped builder output:
    # the subtitle and closing default to "Synthesised from a Solva ..."
    # which is wrong for a cycle compilation. Patch them in-place before
    # persistence so the brief subtitle/closing read correctly.
    brief.subtitle = (
        f"Compiled from {len(envelope['contributions'])} scored "
        f"contribution(s) across {len(envelope['agenda']['items'])} agenda item(s)."
    )
    if envelope.get("readiness", {}).get("storyline"):
        brief.closing_recap = (envelope["readiness"]["storyline"][-1]
                               if envelope["readiness"]["storyline"] else None) or brief.closing_recap
    brief.closing_brand_line = f"{company_label} · Cycle Compilation"
    # Cover lead — promote the executive_summary to the cover so the
    # board reader gets the headline before any sections. The Solva
    # builder uses `intent` for cover; for cycle compilation we want
    # the synth's executive_summary to be the cover.
    exec_summary = (synth_result.get("synth") or {}).get("executive_summary") or ""
    if exec_summary:
        brief.cover_lead_paragraph = exec_summary
    parent = await ensure_brief_persisted(
        db, brief=brief, account_id=account_id,
        context_id=context_id,
        source_type="cycle_compilation",
        source_id=agenda["id"],
    )
    brief_id = parent["id"]
    revision_id = parent["active_revision_id"]

    # Render an immediate DOCX (Board Summary / High Fidelity) so the
    # existing UI's download chip keeps working without forcing a
    # follow-up call.
    try:
        from work_studio import dict_to_brief, get_active_revision
        active_rev = await get_active_revision(
            db, brief_id=brief_id, account_id=account_id,
        )
        snap = (active_rev or {}).get("snapshot") or {}
        if snap:
            snap = dict(snap)
            snap["depth"] = "board_summary"
            snap["fidelity"] = "high"
            export_brief = dict_to_brief(snap)
        else:
            export_brief = brief
        binary = render_docx(export_brief)
    except Exception:
        logger.exception("draft_compilation: deterministic render failed; falling back to seed brief")
        binary = render_docx(brief)

    sha = hashlib.sha256(binary).hexdigest()
    export_id = str(uuid.uuid4())
    fname = (
        f"{(company_label or 'Akki').replace(' ', '_')}_Cycle_Compilation_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d')}.docx"
    )

    # Persist into the C.1 export collection so the existing
    # /api/work_studio/exports/{id}/download endpoint serves the file.
    await db.work_studio_phase_c_exports.insert_one({
        "id": export_id,
        "account_id": account_id,
        "context_id": context_id,
        "source_id": agenda["id"],
        "source_type": "cycle_compilation",
        "format": "docx",
        "depth": "board_summary",
        "fidelity": "high",
        "company_label": company_label,
        "document_type": "Cycle Compilation",
        "programme": agenda.get("title"),
        "brief_id": brief_id,
        "revision_id": revision_id,
        "filename": fname,
        "size_bytes": len(binary),
        "sha256": sha,
        "binary": binary,
        "created_at": iso(now()),
    })

    # Audit.
    try:
        await write_audit(
            context_id, account_id,
            "cycle.draft_compilation.produced",
            "work_studio_brief", brief_id,
            {
                "agenda_id": agenda["id"],
                "brief_id": brief_id,
                "revision_id": revision_id,
                "export_id": export_id,
                "sha256": sha,
                "validator_verdict": (synth_result.get("validation") or {}).get("verdict"),
                "drafter_model": (synth_result.get("llm_audit") or {}).get("drafter", {}).get("model"),
            },
        )
    except Exception:
        logger.exception("draft_compilation: audit write failed (non-fatal)")

    # Continue-in-Chat handoff (kept for parity with prior UX).
    continue_chat_id = None
    try:
        from services.continue_chat import create_continue_chat
        continue_chat_id, _continue_doc_id = await create_continue_chat(
            account_id=account_id,
            context_id=context_id,
            kind="cycle_compilation",
            source="cycle_compilation",
            export_id=export_id,
            file_name=fname,
            file_path="",
            output_format="docx",
            extracted_text=brief.cover_lead_paragraph or "",
            sensitivity_band="INTERNAL",
        )
    except Exception:
        logger.warning("continue_chat creation failed (non-fatal)")

    return {
        "ok": True,
        # New (canonical) — surface the C.2/C.3-aware brief.
        "brief_id": brief_id,
        "revision_id": revision_id,
        "redirect_url": f"/app/studio/composer/briefing/{brief_id}",
        "validation": synth_result.get("validation") or {},
        # Cycle context (used by the ship-step assignment UI in
        # frontend/src/components/cycle/BoardSubmitPanel.jsx).
        "agenda_id": agenda["id"],
        "cycle_id": agenda["id"],   # for now, agenda_id IS the cycle_id
        "board_status": "draft",     # brief is persisted as draft until submit
        # Legacy field names — preserved so the existing CompilationStep
        # download/continue-in-chat UI keeps working unchanged.
        "export_id": export_id,
        "file_name": fname,
        "byte_len": len(binary),
        "sha256": sha,
        "continue_chat_id": continue_chat_id,
    }

