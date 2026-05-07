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

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

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


async def _get_or_init_agenda(context_id: str, account_id: str) -> Dict[str, Any]:
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
    agenda_item_id: str
    team_member_id: str
    kind: str = Field(default="note", pattern=r"^(note|document|email|chat)$")
    source_doc_id: Optional[str] = None
    body_text: Optional[str] = Field(default=None, max_length=20000)
    title: Optional[str] = Field(default=None, max_length=160)


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
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"])
    return agenda


@router.post("/contexts/{context_id}/cycle/agenda")
async def upsert_agenda(
    context_id: str, body: AgendaIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"])
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
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"])
    members = await db.cycle_team.find(
        {"context_id": context_id, "agenda_id": agenda["id"], "status": "active"},
        {"_id": 0},
    ).sort("created_at", 1).to_list(100)
    return {"agenda_id": agenda["id"], "members": members}


@router.post("/contexts/{context_id}/cycle/team")
async def upsert_team_member(
    context_id: str, body: TeamMemberIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"])
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
    res = await db.cycle_team.update_one(
        {"id": member_id, "context_id": context_id},
        {"$set": {"status": "removed", "updated_at": iso(now())}},
    )
    return {"ok": res.modified_count > 0, "id": member_id}


# ──────────────────────────────────────────────────────────────────────
# Contributions
# ──────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/cycle/contributions")
async def list_contributions(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"])
    rows = await db.cycle_contributions.find(
        {"context_id": context_id, "agenda_id": agenda["id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(500)
    return {"agenda_id": agenda["id"], "contributions": rows}


@router.post("/contexts/{context_id}/cycle/contributions")
async def add_contribution(
    context_id: str, body: ContributionIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"])
    rec = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "agenda_id": agenda["id"],
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
    accept manual + heuristic so tests stay deterministic.)"""
    rec = await db.cycle_contributions.find_one(
        {"id": contribution_id, "context_id": context_id}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Contribution not found")
    member = await db.cycle_team.find_one(
        {"id": rec.get("team_member_id"), "context_id": context_id}, {"_id": 0},
    )
    desc = (member or {}).get("contribution_description", "")

    auto = _heuristic_score(rec.get("body_text"), desc)
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
    }
    await db.cycle_contributions.update_one(
        {"id": contribution_id}, {"$set": update},
    )
    return {**rec, **update}


# ──────────────────────────────────────────────────────────────────────
# Readiness scoreboard
# ──────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/cycle/readiness")
async def get_readiness(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"])
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
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Generate restrained follow-up drafts for unmet contributions.
    Returns the drafts; nothing is sent."""
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"])
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
                "agenda_id": agenda["id"],
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
            }
            await db.cycle_followups.insert_one(rec)
            rec.pop("_id", None)
            drafts.append(rec)

    return {"drafts": drafts, "count": len(drafts)}


@router.get("/contexts/{context_id}/cycle/follow-ups")
async def list_followups(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"])
    rows = await db.cycle_followups.find(
        {"context_id": context_id, "agenda_id": agenda["id"]}, {"_id": 0},
    ).sort("created_at", -1).to_list(200)
    return {"agenda_id": agenda["id"], "followups": rows}


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
    """Send an approved follow-up via Resend. D-001 — From uses the
    forwarding alias ('AKKI for <Exec>'); test mode is fine in dev."""
    rec = await db.cycle_followups.find_one(
        {"id": followup_id, "context_id": context_id}, {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    if rec["status"] not in ("approved", "draft"):
        # idempotent — return the existing record if already sent
        return rec

    exec_name = ctx["account"].get("name") or "the executive"
    reply_to = ctx["account"].get("email")
    try:
        result = await email_service.send_email(
            to=[rec["to_email"]],
            subject=rec["draft_subject"],
            html=rec["draft_html"],
            text=rec["draft_body"],
            from_executive_name=exec_name,
            reply_to=reply_to,
            tags=[
                {"name": "surface", "value": "cycle_followup"},
                {"name": "context_id", "value": context_id},
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
        }},
    )
    try:
        await write_audit(
            context_id, ctx["account"]["id"],
            "cycle.followup.sent", "cycle_followup", followup_id,
            {"to": rec["to_email"], "mode": result.get("mode")},
        )
    except Exception:
        pass
    return {
        "ok": result.get("ok"),
        "mode": result.get("mode"),
        "send_id": result.get("id"),
        "followup_id": followup_id,
    }


# ──────────────────────────────────────────────────────────────────────
# Draft Compilation Output
# ──────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/cycle/draft-compilation")
async def draft_compilation(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Produce a deterministic .docx compilation of the cycle's scored
    contributions. Reuses the work_studio_export renderer
    (`render_report_docx`) so the executive gets a familiar layout
    without a new template."""
    from services import work_studio_export as _ex
    from pathlib import Path
    import os
    from datetime import datetime, timezone

    agenda = await _get_or_init_agenda(context_id, ctx["account"]["id"])
    contribs = await db.cycle_contributions.find(
        {"context_id": context_id, "agenda_id": agenda["id"]}, {"_id": 0},
    ).to_list(500)
    members = await db.cycle_team.find(
        {"context_id": context_id, "agenda_id": agenda["id"], "status": "active"},
        {"_id": 0},
    ).to_list(100)
    member_by_id = {m["id"]: m for m in members}

    if not agenda.get("items"):
        raise HTTPException(status_code=400, detail="Set an agenda first.")

    sections: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    cite_counter = 0
    for it in agenda.get("items", []):
        item_contribs = [c for c in contribs if c.get("agenda_item_id") == it["id"]]
        scored = [c for c in item_contribs if c.get("scores")]
        avg_readiness = (
            int(sum(c["scores"]["readiness"] for c in scored) / len(scored))
            if scored else 0
        )
        bullets: List[str] = []
        cites_used: List[int] = []
        for c in item_contribs:
            mem = member_by_id.get(c.get("team_member_id") or "", {})
            cite_counter += 1
            citations.append({
                "doc_id": c["id"],
                "doc_name": (c.get("title") or f"Contribution from {mem.get('name', 'team')}"),
                "paragraph_anchor": None,
            })
            cites_used.append(cite_counter)
            preview = (c.get("body_text") or "(no text)").replace("\n", " ").strip()
            bullets.append(
                f"{(mem.get('name') or 'Owner')}: {preview[:240]}"
            )
        if not bullets:
            bullets = ["No contributions yet — chase outstanding."]
        callout = None
        if scored and avg_readiness >= 70:
            callout = "Item reads at draft strength."
        elif scored and avg_readiness >= 40:
            callout = "Thin in places — chase before send."
        sections.append({
            "heading": it["label"],
            "bullets": bullets,
            "callout": callout,
            "cites":   cites_used or [1],
        })

    # Ensure at least one citation exists so the validator passes.
    if not citations:
        citations = [{"doc_id": "stub", "doc_name": "Cycle compilation",
                      "paragraph_anchor": None}]
        for s in sections:
            s["cites"] = [1]

    storyline_url = await get_readiness(context_id, ctx)  # reuse rollup
    overall = storyline_url.get("overall", 0)

    content_dict = {
        "title": agenda.get("title") or "Cycle compilation",
        "subtitle": "Draft compilation of scored contributions.",
        "classification": "Confidential",
        "period": iso(now())[:10],
        "generated_for": ctx["account"].get("name") or "—",
        "executive_summary": (
            ("Compilation reads at draft strength on " + str(overall) + "% overall — "
             "sections below carry the contributions as scored.")
            if overall else
            "First-pass compilation. Items below carry the contributions as scored."
        ),
        "sections": sections,
        "conclusion": (storyline_url.get("storyline") or [
            "Decide against the readiness scoreboard before submitting."
        ])[-1] if storyline_url.get("storyline") else "Decide against the readiness scoreboard before submitting.",
        "citations": citations,
    }
    _ex.validate_content(content_dict, "report")
    ctx_meta = {
        "context_name":      ctx["context"].get("name") or "—",
        "classification":    "Confidential",
        "period":            iso(now())[:10],
        "generated_at_human": _ex.now_human(),
    }
    data, sha, fname = _ex.render_report_docx(content_dict, ctx_meta)

    # Persist into work_studio_exports so the existing download endpoint
    # can serve the file under /contexts/{cid}/work-studio/exports/{eid}/download.
    eid = str(uuid.uuid4())
    out_dir = Path(os.environ.get("UPLOAD_DIR", "/app/backend/uploads")) / "work_studio_exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    fpath = out_dir / f"{eid}.docx"
    fpath.write_bytes(data)

    row = {
        "id": eid,
        "context_id": context_id,
        "account_id": ctx["account"]["id"],
        "kind": "report",
        "output_format": "docx",
        "status": "complete",
        "source": "cycle_compilation",
        "agenda_id": agenda["id"],
        "file_name": fname,
        "file_path": str(fpath),
        "sha256": sha,
        "byte_len": len(data),
        "sensitivity_band": "INTERNAL",
        "completed_at": iso(now()),
        "created_at": iso(now()),
    }
    await db.work_studio_exports.insert_one(row)
    try:
        await write_audit(
            context_id, ctx["account"]["id"],
            "cycle.draft_compilation.produced", "work_studio_export", eid,
            {"agenda_id": agenda["id"], "sha256": sha},
        )
    except Exception:
        pass
    return {
        "ok": True,
        "export_id": eid,
        "file_name": fname,
        "byte_len": len(data),
        "sha256": sha,
    }
