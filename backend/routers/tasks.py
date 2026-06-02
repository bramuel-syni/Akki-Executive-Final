"""Phase F (Task Manager) — backend router.

Introduced 2026-05-26. Implements the new `tasks` collection + CRUD
endpoints called by the new /app/task-manager surface. Distinct from
the legacy /api/cycle* surfaces (Reporting Cycle, drafts, checklists,
reports) which retain their own schema and stay mounted on
/app/cycle.

F.1 + F.2 only:
  - POST   /api/tasks                      — create (draft or active)
  - GET    /api/tasks?state=active|draft|closed
  - GET    /api/tasks/{task_id}
  - PATCH  /api/tasks/{task_id}            — inline edits
  - POST   /api/tasks/agent-prefill        — Shield-bounded LLM pre-fill
                                             for the wizard's Step 1
                                             (objective + success
                                             criteria template)

F.3 (Task Drawer) / F.4 (Compile) / F.5 (Contributor modes) / F.6
(Side panel polish) are queued — not implemented here.

All LLM calls route through Shield. No `emergentintegrations` direct
import. The agent-prefill helper falls back to a static template
shelf on Shield failure so the wizard is never blocked.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field, conint, conlist

from core import (
    db, now as _now, iso as _iso, write_audit,
    require_context_membership, get_current_account,
)


log = logging.getLogger("akki.tasks")
router = APIRouter(prefix="/api")


# ═════════════════════════════════════════════════════════════════════
# Schemas
# ═════════════════════════════════════════════════════════════════════
TASK_STATES = ("draft", "active", "closed")
CONTRIB_MODES = ("akki_account", "magic_link", "email_reply")


class _TeamMemberIn(BaseModel):
    name: str
    role: Optional[str] = ""
    email: str
    contribution: Optional[str] = ""
    due_date: Optional[str] = None
    contribution_mode: str = "akki_account"
    contributor_id: Optional[str] = None
    # Phase F.3 (2026-05-26) — status is set by the contributions
    # PATCH endpoint at runtime. Allow it through on create so seeded
    # demo/test tasks can land with realistic statuses.
    status: Optional[str] = None
    adherence_score: Optional[int] = None
    # Phase F.5 (2026-05-26) — coexistence flag. When True, the
    # contributor receives BOTH the primary-mode invite AND an
    # email_reply fallback invite. Default False.
    allow_email_reply: Optional[bool] = False


class _OutputSpecIn(BaseModel):
    kind: str = "template"           # "template" | "free_text"
    template_id: Optional[str] = None
    free_text: Optional[str] = None
    formats: List[str] = Field(default_factory=lambda: ["pdf"])
    final_due_date: Optional[str] = None


class _TaskIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    objective: Optional[str] = ""
    success_criteria: Optional[str] = ""
    output_spec: Optional[_OutputSpecIn] = None
    team: List[_TeamMemberIn] = Field(default_factory=list)
    state: str = "draft"             # "draft" | "active"
    context_id: Optional[str] = None
    due_date: Optional[str] = None


class _TaskPatch(BaseModel):
    name: Optional[str] = None
    objective: Optional[str] = None
    success_criteria: Optional[str] = None
    output_spec: Optional[_OutputSpecIn] = None
    team: Optional[List[_TeamMemberIn]] = None
    state: Optional[str] = None
    due_date: Optional[str] = None


class _AgentPrefillIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════
def _sanitize_task(t: Dict[str, Any]) -> Dict[str, Any]:
    """Strip MongoDB internals and shape the response payload."""
    return {
        "id":               t.get("id"),
        "name":             t.get("name"),
        "objective":        t.get("objective", ""),
        "success_criteria": t.get("success_criteria", ""),
        "output_spec":      t.get("output_spec") or None,
        "team":             t.get("team") or [],
        "state":            t.get("state", "draft"),
        "context_id":       t.get("context_id"),
        "account_id":       t.get("account_id"),
        "due_date":         t.get("due_date"),
        "readiness_score":  t.get("readiness_score", 0),
        "created_at":       t.get("created_at"),
        "updated_at":       t.get("updated_at"),
        "status_history":   t.get("status_history") or [],
        # Phase P5.17 (2026-02) — origin envelope when this task was
        # backfilled from an inbox-routing decision (or routed live
        # via the P5.16 inbound-hook auto-classify path). Existing
        # tasks without an origin field return `None` here; FE
        # treats `None` as "no chip" — backward-compat clean.
        "origin":           t.get("origin") or None,
    }


def _compute_readiness(task: Dict[str, Any]) -> int:
    """Phase F.3 (2026-05-26) — readiness uses the orchestrator-locked
    60/25/15 formula via the shared `readiness_breakdown` helper.
    Before F.3 this was a placeholder; once contributor status is
    trackable end-to-end the placeholder is no longer needed.
    """
    from services.tasks.intelligence_service import readiness_breakdown
    return readiness_breakdown(task)["score"]


async def _notify_contributors(task: Dict[str, Any]) -> None:
    """F.2-era stub kept for backwards-compat — F.5 (2026-05-26)
    replaces this with the real `contributor_invitation_service.
    fan_out_invitations`. This function is no longer called from
    the create/patch paths; left in place to avoid breaking any
    external callers that may import it."""
    return None


# ═════════════════════════════════════════════════════════════════════
# POST /api/tasks — create
# ═════════════════════════════════════════════════════════════════════
@router.post("/tasks")
async def create_task(
    body: _TaskIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Create a task (state=draft or state=active). Active tasks fire
    the contributor-added audit row per team member."""
    if body.state not in ("draft", "active"):
        raise HTTPException(status_code=400, detail="state must be draft or active")
    tid = f"task-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    task = {
        "id":               tid,
        "account_id":       current["id"],
        "context_id":       body.context_id,
        "name":             body.name.strip(),
        "objective":        (body.objective or "").strip(),
        "success_criteria": (body.success_criteria or "").strip(),
        "output_spec":      body.output_spec.model_dump() if body.output_spec else None,
        "team":             [m.model_dump() for m in body.team],
        "state":            body.state,
        "due_date":         body.due_date,
        "created_at":       now_iso,
        "updated_at":       now_iso,
        "status_history":   [{"state": body.state, "at": now_iso}],
    }
    task["readiness_score"] = _compute_readiness(task)
    await db.tasks.insert_one(dict(task))      # copy: insert_one mutates
    # Best-effort audit row.
    try:
        await db.audit_log.insert_one({
            "id":            str(uuid.uuid4()),
            "context_id":    task["context_id"],
            "account_id":    current["id"],
            "action":        "task.created",
            "resource_type": "task",
            "resource_id":   tid,
            "metadata": {"state": body.state, "name": task["name"]},
            "created_at":    now_iso,
        })
    except Exception as e:  # noqa: BLE001
        log.warning("task.created audit failed: %s", e)
    # On commission (state=active), fire contributor invitations.
    # F.5 (2026-05-26) replaces the F.2 placeholder audit-only path
    # with the real Postmark fan-out across all 3 modes.
    if body.state == "active":
        from services.tasks.contributor_invitation_service import fan_out_invitations
        await fan_out_invitations(db, task=task)
    return _sanitize_task(task)


# ═════════════════════════════════════════════════════════════════════
# GET /api/tasks?state=...&context_id=...
# ═════════════════════════════════════════════════════════════════════
@router.get("/tasks")
async def list_tasks(
    state: Optional[str] = Query(None, pattern="^(active|draft|closed)$"),
    context_id: Optional[str] = None,
    origin: Optional[str] = Query(None, pattern="^(email_akki|manual)$"),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """List tasks scoped to the caller. Filter by state (Active /
    Draft / Closed) — used by the 3-tab listing surface.

    Phase P5.17 (2026-02) — added `?origin=email_akki|manual` filter.
    `email_akki` narrows to tasks that carry the P5.17 origin
    envelope with `source == "email_akki"`; `manual` excludes those.
    Default (no `origin` query) → returns everything.
    """
    q: Dict[str, Any] = {"account_id": current["id"]}
    if state:
        q["state"] = state
    if context_id:
        q["context_id"] = context_id
    if origin == "email_akki":
        q["origin.source"] = "email_akki"
    elif origin == "manual":
        # Exclude rows with any origin envelope (today only email_akki
        # exists; future origin classes get added to this $nor list as
        # they ship).
        q["$or"] = [
            {"origin": {"$exists": False}},
            {"origin": None},
        ]
    rows = await db.tasks.find(q, {"_id": 0}).sort("created_at", -1).to_list(length=200)
    return [_sanitize_task(r) for r in rows]


# ═════════════════════════════════════════════════════════════════════
# GET /api/tasks/{task_id}
# ═════════════════════════════════════════════════════════════════════
@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    return _sanitize_task(t)


# ═════════════════════════════════════════════════════════════════════
# PATCH /api/tasks/{task_id} — inline edits
# ═════════════════════════════════════════════════════════════════════
@router.patch("/tasks/{task_id}")
async def patch_task(
    task_id: str,
    body: _TaskPatch,
    current: Dict[str, Any] = Depends(get_current_account),
):
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")

    update: Dict[str, Any] = {}
    state_changed = False
    if body.name is not None:
        update["name"] = body.name.strip()
    if body.objective is not None:
        update["objective"] = body.objective.strip()
    if body.success_criteria is not None:
        update["success_criteria"] = body.success_criteria.strip()
    if body.output_spec is not None:
        update["output_spec"] = body.output_spec.model_dump()
    if body.team is not None:
        update["team"] = [m.model_dump() for m in body.team]
    if body.due_date is not None:
        update["due_date"] = body.due_date
    if body.state is not None:
        if body.state not in TASK_STATES:
            raise HTTPException(status_code=400, detail=f"state must be one of {TASK_STATES}")
        if body.state != t.get("state"):
            update["state"] = body.state
            state_changed = True

    if not update:
        return _sanitize_task(t)

    now_iso = datetime.now(timezone.utc).isoformat()
    update["updated_at"] = now_iso

    # Recompute readiness on any data change.
    merged = {**t, **update}
    merged["_id"] = t.get("_id")
    update["readiness_score"] = _compute_readiness(merged)

    push: Dict[str, Any] = {}
    if state_changed:
        push["status_history"] = {"state": body.state, "at": now_iso}

    op: Dict[str, Any] = {"$set": update}
    if push:
        op["$push"] = push
    await db.tasks.update_one({"id": task_id}, op)

    t2 = await db.tasks.find_one({"id": task_id}, {"_id": 0})

    # Audit + contributor notify when freshly commissioned.
    try:
        await db.audit_log.insert_one({
            "id":            str(uuid.uuid4()),
            "context_id":    t2.get("context_id"),
            "account_id":    current["id"],
            "action":        "task.updated",
            "resource_type": "task",
            "resource_id":   task_id,
            "metadata": {"keys": list(update.keys())},
            "created_at":    now_iso,
        })
    except Exception as e:  # noqa: BLE001
        log.warning("task.updated audit failed: %s", e)
    if state_changed and body.state == "active":
        # F.5 (2026-05-26) — real invitation fan-out on draft→active.
        from services.tasks.contributor_invitation_service import fan_out_invitations
        await fan_out_invitations(db, task=t2)

    return _sanitize_task(t2)


# ═════════════════════════════════════════════════════════════════════
# POST /api/tasks/agent-prefill — Shield-bounded LLM helper
# ═════════════════════════════════════════════════════════════════════
# Static template shelf — used as the fallback when the LLM call fails
# AND as the seed prompt grounding for the LLM. Keyed by a stem
# substring matched case-insensitively.
_PREFILL_TEMPLATES: List[Dict[str, str]] = [
    {
        "match":            "board pack",
        "objective":        "Produce a board-ready pack covering performance, risk, strategy progress, and governance updates for the upcoming meeting.",
        "success_criteria": "Pack delivered ≥ 48h before the meeting; every section tied to a board-relevant decision; no open data gaps.",
    },
    {
        "match":            "committee pack",
        "objective":        "Assemble a committee-scoped pack of reading, recommendations, and decisions for the next sitting.",
        "success_criteria": "Pack delivered to committee members ≥ 5 days ahead; one decision-ready item per agenda line; chair sign-off captured.",
    },
    {
        "match":            "monthly report",
        "objective":        "Deliver a monthly executive report covering operating performance, in-flight risks, and three forward-looking choices.",
        "success_criteria": "Report shipped within 5 business days of month-end; numbers reconciled against the source ledger; CEO sign-off captured.",
    },
    {
        "match":            "strategy",
        "objective":        "Sharpen the strategy narrative into a single decision-ready document the board can challenge.",
        "success_criteria": "One clear ask per option; assumptions named explicitly; 3-year financial implications quantified.",
    },
    {
        "match":            "fundraising",
        "objective":        "Build the fundraising deck and supporting model the team can take to investors.",
        "success_criteria": "Deck + model + data room index ready; pre-read circulated to 3 friendly investors; objection list answered.",
    },
]


def _template_lookup(name: str) -> Optional[Dict[str, str]]:
    lo = (name or "").lower()
    for t in _PREFILL_TEMPLATES:
        if t["match"] in lo:
            return {"objective": t["objective"], "success_criteria": t["success_criteria"]}
    return None


@router.post("/tasks/agent-prefill")
async def agent_prefill(
    body: _AgentPrefillIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Agent pre-fill for the wizard's Step 1. Returns suggested
    `{objective, success_criteria, source}` strings. Source is
    `"template"` (static shelf hit) or `"llm"` (Shield-bounded
    rewrite) or `"none"` (no match + LLM failure)."""
    static = _template_lookup(body.name)
    if static:
        return {**static, "source": "template"}

    # Fall through to a Shield-bounded LLM ask. If Shield is down,
    # return a generic template so the wizard is never blocked.
    try:
        from services.synisense.shield.client import invoke as shield_invoke
        prompt = (
            "You are a senior executive coach. The user is setting up a task "
            "called the following; propose: (a) a single-paragraph OBJECTIVE "
            "(what does this task achieve?) and (b) a single-paragraph "
            "SUCCESS CRITERIA (how will they know it's done well?). Return "
            "strict JSON only — no preamble — shape:\n"
            "{\"objective\": \"...\", \"success_criteria\": \"...\"}\n\n"
            f"TASK NAME: {body.name}"
        )
        result = await shield_invoke(
            purpose="task_manager.wizard.prefill",
            content=prompt,
            tenant_id=current["id"],
            consumer_id="tasks",
            user_id=current["id"],
            model_preference="balanced",
        )
        raw = (result.get("response") or "").strip()
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            import json as _json
            parsed = _json.loads(m.group(0))
            obj = (parsed.get("objective") or "").strip()
            sc  = (parsed.get("success_criteria") or "").strip()
            if obj and sc:
                return {"objective": obj, "success_criteria": sc, "source": "llm"}
    except Exception as e:  # noqa: BLE001
        log.warning("agent_prefill shield failed: %s", e)

    # Last-resort generic.
    return {
        "objective":        "Define what this task achieves and who benefits from it.",
        "success_criteria": "Name the concrete artefact(s) produced and the sign-off criterion.",
        "source":           "none",
    }



# ═════════════════════════════════════════════════════════════════════
# Phase F.3 (2026-05-26) — Task Drawer endpoints
# ═════════════════════════════════════════════════════════════════════
CONTRIBUTION_STATUS_ALLOWED = (
    "not_started", "in_progress", "submitted",
    "approved", "needs_revision",
)


class _ContributionPatchIn(BaseModel):
    """Status changes on a single contributor row of a task."""
    status: str = Field(min_length=1, max_length=40)
    note:   Optional[str] = Field(default=None, max_length=2000)


def _find_contributor(team: List[Dict[str, Any]], contributor_id: str) -> Optional[int]:
    """Locate a contributor row by email (canonical) or name (fallback).
    Returns the index in the team list or None."""
    for i, m in enumerate(team or []):
        if (m.get("email") or "").lower() == contributor_id.lower():
            return i
        if (m.get("name") or "").lower() == contributor_id.lower():
            return i
        if (m.get("contributor_id") or "") == contributor_id:
            return i
    return None


# ─────────────────────────────────────────────────────────────────────
# GET /api/tasks/{task_id}/drafts — task-linked documents
# ─────────────────────────────────────────────────────────────────────
@router.get("/tasks/{task_id}/drafts")
async def list_task_drafts(
    task_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Documents linked to this task (via `documents.task_id`).
    Returns both Akki-generated drafts AND contributor uploads."""
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0, "id": 1, "context_id": 1})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    docs = await db.documents.find(
        {"task_id": task_id},
        {"_id": 0, "id": 1, "name": 1, "original_filename": 1, "state": 1,
         "origin": 1, "uploader_id": 1, "uploader_name": 1, "created_at": 1,
         "doc_type": 1},
    ).sort("created_at", -1).to_list(length=200)
    return docs


# ─────────────────────────────────────────────────────────────────────
# PATCH /api/tasks/{task_id}/contributions/{contributor_id} — status
# ─────────────────────────────────────────────────────────────────────
@router.patch("/tasks/{task_id}/contributions/{contributor_id}")
async def patch_contribution(
    task_id: str, contributor_id: str,
    body: _ContributionPatchIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Update a single contributor row's status. Status changes trigger
    a readiness recompute + audit row. Notifications fire on
    approve / request-revision when contribution_mode is `akki_account`
    or `email_reply` (live email send is wired in F.5; today we write
    the audit row as the durable record)."""
    if body.status not in CONTRIBUTION_STATUS_ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {CONTRIBUTION_STATUS_ALLOWED}",
        )
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    team = list(t.get("team") or [])
    idx = _find_contributor(team, contributor_id)
    if idx is None:
        raise HTTPException(status_code=404, detail="Contributor not found on this task")
    # Sprint Z1.3 (2026-05-29) — premature-approval defence.
    # Approve transitions are only valid from submitted / in_review.
    # Reject (409) if the contributor has nothing for the founder to
    # approve. The frontend `disabled` flag is the first defence; this
    # is the server-side belt-and-braces stop in case an out-of-band
    # call (curl / cross-tab race / scripted client) tries to skip it.
    _APPROVE_ELIGIBLE_FROM = {"submitted", "in_review"}
    current_status = (team[idx].get("status") or "not_started").lower()
    if body.status == "approved" and current_status not in _APPROVE_ELIGIBLE_FROM:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot approve a contribution in status '{current_status}'. "
                f"Approve unlocks once the contributor moves to submitted or in_review."
            ),
        )
    team[idx] = {**team[idx], "status": body.status}
    if body.note:
        team[idx]["status_note"] = body.note
    now_iso = datetime.now(timezone.utc).isoformat()
    # Recompute readiness via the F.3 formula.
    from services.tasks.intelligence_service import readiness_breakdown
    rb = readiness_breakdown({**t, "team": team})
    await db.tasks.update_one(
        {"id": task_id},
        {"$set": {"team": team, "updated_at": now_iso, "readiness_score": rb["score"]}},
    )
    # Audit row.
    try:
        await db.audit_log.insert_one({
            "id":            str(uuid.uuid4()),
            "context_id":    t.get("context_id"),
            "account_id":    current["id"],
            "action":        f"task.contribution.{body.status}",
            "resource_type": "task",
            "resource_id":   task_id,
            "metadata": {
                "contributor_email": team[idx].get("email"),
                "contributor_name":  team[idx].get("name"),
                "note":              body.note,
                "readiness_after":   rb["score"],
            },
            "created_at": now_iso,
        })
    except Exception as e:  # noqa: BLE001
        log.warning("task contribution audit failed: %s", e)
    return {
        "task_id":         task_id,
        "contributor_id":  contributor_id,
        "team":            team,
        "readiness_score": rb["score"],
    }


# ─────────────────────────────────────────────────────────────────────
# GET /api/tasks/{task_id}/intelligence — cached or pending
# ─────────────────────────────────────────────────────────────────────
@router.get("/tasks/{task_id}/intelligence")
async def get_task_intelligence(
    task_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Returns the cached intelligence row keyed by (task_id, task_hash).
    Cache MISS → returns {status: "pending"} and triggers a synchronous
    build (small enough to run inline; LLM Recommendations are best-
    effort with rule-based fallback)."""
    from services.tasks.intelligence_service import task_hash, build_intelligence
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    th = task_hash(t)
    cached = await db.task_intelligence.find_one(
        {"task_id": task_id, "task_hash": th}, {"_id": 0},
    )
    if cached:
        return cached
    # Compute inline. LLM is best-effort; rule-based fallback covers any failure.
    payload = await build_intelligence(t, user_id=current["id"])
    try:
        await db.task_intelligence.insert_one(dict(payload))
    except Exception as e:  # noqa: BLE001
        log.warning("task intel cache insert failed: %s", e)
    return payload


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/{task_id}/intelligence/regenerate — force rebuild
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/intelligence/regenerate")
async def regenerate_task_intelligence(
    task_id: str,
    background_tasks: BackgroundTasks,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Force a fresh build. Drops the cache row for the current task_hash
    and triggers a background rebuild. Returns {status:"queued"}; the
    UI polls /intelligence to pick up the new payload."""
    from services.tasks.intelligence_service import task_hash, build_intelligence
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    th = task_hash(t)
    await db.task_intelligence.delete_many({"task_id": task_id, "task_hash": th})

    async def _rebuild() -> None:
        try:
            payload = await build_intelligence(t, user_id=current["id"])
            await db.task_intelligence.insert_one(dict(payload))
        except Exception as e:  # noqa: BLE001
            log.warning("task intel rebuild failed: %s", e)

    background_tasks.add_task(_rebuild)
    return {"status": "queued", "task_id": task_id, "task_hash": th}



# ═════════════════════════════════════════════════════════════════════
# Phase F.4 (2026-05-26) — Compile Flow (5 stages)
# ═════════════════════════════════════════════════════════════════════
class _CirculationSendIn(BaseModel):
    reviewer_emails: List[str] = Field(min_length=1, max_length=20)
    message: Optional[str] = Field(default=None, max_length=2000)
    base_url: Optional[str] = Field(default=None, max_length=300)


class _CirculationSpan(BaseModel):
    """Inline-comment span — characters relative to the document's
    rendered text content (NOT raw HTML)."""
    start: int = Field(ge=0)
    end:   int = Field(ge=0)
    text:  str = Field(min_length=1, max_length=2000)


class _CirculationCommentIn(BaseModel):
    """Public endpoint body — used by the magic-link review surface.

    `span` is optional. When omitted the comment is a general /
    whole-document note. When provided the comment is anchored at a
    text span (Debt W4 — inline-comment span resolution).
    """
    comment: str = Field(min_length=1, max_length=4000)
    doc_id:  Optional[str] = None
    span:    Optional[_CirculationSpan] = None


class _ApplyCommentIn(BaseModel):
    comment_id: str
    action: str = Field(min_length=1, max_length=40)


class _ReviewCompleteIn(BaseModel):
    skip_circulation: bool = False


def _resolve_base_url(provided: Optional[str]) -> str:
    """Caller may provide their browser origin (`window.location.origin`)
    so the magic-link URL points at the right host. Falls back to env."""
    if provided and provided.startswith(("http://", "https://")):
        return provided
    import os
    return os.environ.get("REACT_APP_BACKEND_URL") or os.environ.get("PUBLIC_BASE_URL") or ""


# ─────────────────────────────────────────────────────────────────────
# GET /api/tasks/{task_id}/compile — current session state
# ─────────────────────────────────────────────────────────────────────
@router.get("/tasks/{task_id}/compile")
async def get_compile_state(
    task_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    from services.tasks.compile_service import _empty_session
    return t.get("compile_session") or _empty_session()


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/{task_id}/compile/draft — Stage 1
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/compile/draft")
async def start_compile_drafting(
    task_id: str,
    background_tasks: BackgroundTasks,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Kicks off Stage 1 (Drafting). Synchronous if the output_spec is
    single-section; runs in the background for multi-section packs."""
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    from services.tasks.compile_service import run_drafting, _TEMPLATE_PACK_SHAPES
    tpl_id = (t.get("output_spec") or {}).get("template_id")
    sections = _TEMPLATE_PACK_SHAPES.get(tpl_id, [t.get("name")])
    if len(sections) <= 1:
        ids = await run_drafting(db, task=t, account_id=current["id"])
        return {"status": "completed", "draft_artefact_ids": ids}

    async def _bg() -> None:
        await run_drafting(db, task=t, account_id=current["id"])
    background_tasks.add_task(_bg)
    return {"status": "queued", "n_sections": len(sections)}


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/{task_id}/compile/review/complete — Stage 2 → 3/4
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/compile/review/complete")
async def complete_review_stage(
    task_id: str,
    body: _ReviewCompleteIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    from services.tasks.compile_service import complete_review
    session = await complete_review(db, task=t, account_id=current["id"],
                                     skip_circulation=body.skip_circulation)
    return session


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/{task_id}/compile/circulation/send — Stage 3 start
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/compile/circulation/send")
async def send_compile_circulation(
    task_id: str,
    body: _CirculationSendIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    from services.tasks.compile_service import send_circulation
    return await send_circulation(
        db, task=t, account_id=current["id"],
        reviewer_emails=body.reviewer_emails, message=body.message,
        base_url=_resolve_base_url(body.base_url),
    )


# ─────────────────────────────────────────────────────────────────────
# GET /api/tasks/circulation/{token} — PUBLIC reviewer landing
# ─────────────────────────────────────────────────────────────────────
@router.get("/tasks/circulation/{token}")
async def circulation_view(token: str):
    """Public — no auth. Magic-link token is the only credential."""
    row = await db.task_circulation_tokens.find_one(
        {"token": token, "used": False}, {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    try:
        exp = datetime.fromisoformat((row.get("expires_at") or "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        exp = None
    if exp and exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Link expired")
    doc_ids = row.get("draft_artefact_ids") or []
    docs = await db.documents.find(
        {"id": {"$in": doc_ids}},
        {"_id": 0, "id": 1, "name": 1, "extracted_text": 1, "doc_type": 1, "state": 1},
    ).to_list(length=20)
    t = await db.tasks.find_one(
        {"id": row["task_id"]},
        {"_id": 0, "name": 1, "objective": 1, "id": 1, "compile_session.circulation.comments": 1},
    )
    own = [
        c for c in ((t or {}).get("compile_session", {}).get("circulation", {}).get("comments") or [])
        if c.get("reviewer") == row["reviewer_email"]
    ]
    return {
        "task":           {"id": t["id"], "name": t.get("name"), "objective": t.get("objective")} if t else None,
        "reviewer_email": row["reviewer_email"],
        "docs":           docs,
        "expires_at":     row.get("expires_at"),
        "own_comments":   own,
    }


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/circulation/{token}/comment — PUBLIC reviewer route
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/circulation/{token}/comment")
async def circulation_comment(
    token: str,
    body: _CirculationCommentIn,
):
    from services.tasks.compile_service import add_circulation_comment
    span_dict = None
    if body.span is not None:
        span_dict = {
            "start": body.span.start,
            "end":   body.span.end,
            "text":  body.span.text,
        }
    result = await add_circulation_comment(
        db, token=token, comment_text=body.comment, doc_id=body.doc_id,
        span=span_dict,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("reason"))
    return result


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/{task_id}/compile/circulation/close — Stage 3 → 4
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/compile/circulation/close")
async def close_compile_circulation(
    task_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    from services.tasks.compile_service import close_circulation
    return await close_circulation(db, task=t, account_id=current["id"])


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/{task_id}/compile/final-production/apply-comment
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/compile/final-production/apply-comment")
async def apply_final_comment(
    task_id: str,
    body: _ApplyCommentIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if body.action not in ("apply", "discard", "edit_manual"):
        raise HTTPException(status_code=400, detail="action must be apply, discard, or edit_manual")
    from services.tasks.compile_service import apply_comment
    return await apply_comment(db, task=t, account_id=current["id"],
                                comment_id=body.comment_id, action=body.action)


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/{task_id}/compile/final-production/complete — Stage 4 → 5
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/compile/final-production/complete")
async def complete_final_production_stage(
    task_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    from services.tasks.compile_service import complete_final_production
    return await complete_final_production(db, task=t, account_id=current["id"])


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/{task_id}/compile/commit — Stage 5
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/compile/commit")
async def commit_compile(
    task_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    from services.tasks.compile_service import run_commit
    result = await run_commit(db, task=t, account_id=current["id"])
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result)
    return result


# ═════════════════════════════════════════════════════════════════════
# Phase F.5 (2026-05-26) — Contributor public endpoints + Re-invite
# ═════════════════════════════════════════════════════════════════════
from fastapi import File, UploadFile, Form  # noqa: E402


class _ContributorCommentIn(BaseModel):
    comment: str = Field(min_length=1, max_length=4000)


class _ContributorSubmitIn(BaseModel):
    final_note: Optional[str] = Field(default=None, max_length=2000)


async def _resolve_contributor_token(token: str) -> Dict[str, Any]:
    """C1-revised Phase B (2026-02) — distinguish error codes so the
    public contributor portal can render a precise narrative instead
    of a catch-all "Link not valid".

    Error map:
      • Token never existed → 404 link_invalid
      • Token revoked via re-invite (used=True + revoked_reason set)
        → 410 link_revoked
      • Token spent (used=True, no revoked_reason) → 410 link_used
      • Token past expires_at → 410 link_expired

    Happy path returns the token row unchanged. Same shape callers
    expect (just-row Dict[str, Any]).
    """
    # 1. Look up by token regardless of used flag so we can
    #    distinguish revoked vs missing.
    row = await db.task_contributor_tokens.find_one(
        {"token": token}, {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail={
            "code":    "link_invalid",
            "message": "This invitation link doesn't match anything we issued.",
        })
    if row.get("used") is True:
        if row.get("revoked_reason"):
            raise HTTPException(status_code=410, detail={
                "code":    "link_revoked",
                "message": ("This invitation was replaced by a newer one. "
                            "Use the most recent email from the task owner."),
            })
        raise HTTPException(status_code=410, detail={
            "code":    "link_used",
            "message": "This invitation has already been submitted.",
        })
    try:
        exp = datetime.fromisoformat((row.get("expires_at") or "").replace("Z", "+00:00"))
    except (ValueError, TypeError):
        exp = None
    if exp and exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail={
            "code":    "link_expired",
            "message": "This invitation has expired. Ask the task owner for a fresh one.",
        })
    return row


# ─────────────────────────────────────────────────────────────────────
# GET /api/tasks/contribute/{token} — PUBLIC contributor landing
# ─────────────────────────────────────────────────────────────────────
@router.get("/tasks/contribute/{token}")
async def contributor_view(token: str):
    """Public — no auth header. Magic-link token IS the credential.
    Returns task summary + this contributor's specific contribution
    + peers (names + roles only, no emails) + docs already uploaded
    under this token."""
    row = await _resolve_contributor_token(token)
    t = await db.tasks.find_one(
        {"id": row["task_id"]},
        {"_id": 0, "id": 1, "name": 1, "objective": 1, "success_criteria": 1,
         "due_date": 1, "team": 1, "output_spec": 1},
    )
    if not t:
        # C1-revised Phase B (2026-02) — the token row exists and is
        # valid but its task has been deleted. Return 410 with a
        # distinct code so the FE narrative says "this task no longer
        # exists" instead of the catch-all "invalid link".
        raise HTTPException(status_code=410, detail={
            "code":    "task_gone",
            "message": ("The task this invitation pointed to has been "
                        "deleted. Ask the task owner for a fresh invite."),
        })
    me = next(
        (m for m in (t.get("team") or [])
         if (m.get("email") or "").lower() == row["contributor_email"]),
        None,
    )
    if me is None:
        # C1-revised Phase B (2026-02) — token valid + task exists but
        # the contributor has been removed from the team. Distinct
        # 410 so the FE can render a precise narrative.
        raise HTTPException(status_code=410, detail={
            "code":    "not_on_team",
            "message": ("You're no longer on the team for this task. "
                        "Ask the task owner if this was a mistake."),
        })
    peers = [
        {"name": m.get("name"), "role": m.get("role")}
        for m in (t.get("team") or [])
        if (m.get("email") or "").lower() != row["contributor_email"]
    ]
    docs = await db.documents.find(
        {"task_id": row["task_id"], "contributor_token": token},
        {"_id": 0, "id": 1, "name": 1, "original_filename": 1, "state": 1, "created_at": 1},
    ).to_list(length=20)
    return {
        "task": {
            "id":               t["id"],
            "name":             t.get("name"),
            "objective":        t.get("objective"),
            "success_criteria": t.get("success_criteria"),
            "due_date":         t.get("due_date"),
            "output_formats":   (t.get("output_spec") or {}).get("formats") or [],
        },
        "contributor_email": row["contributor_email"],
        "contribution":      (me or {}).get("contribution") or "",
        "your_due_date":     (me or {}).get("due_date"),
        "your_status":       (me or {}).get("status") or "not_started",
        "peers":             peers,
        "docs":              docs,
        "expires_at":        row.get("expires_at"),
    }


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/contribute/{token}/upload — PUBLIC file upload
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/contribute/{token}/upload")
async def contributor_upload(
    token: str,
    file: UploadFile = File(...),
    note: Optional[str] = Form(default=None),
):
    """Accepts a file upload from a magic-link contributor. Creates a
    document row with `task_id` + `contributor_token` set + `origin=
    "magic_link"`."""
    row = await _resolve_contributor_token(token)
    payload = await file.read()
    if len(payload) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 25 MB).")
    did = f"doc-{uuid.uuid4().hex[:10]}"
    doc = {
        "id":                   did,
        "task_id":               row["task_id"],
        "account_id":            row["task_account_id"],
        "contributor_email":     row["contributor_email"],
        "contributor_id":        row.get("contributor_id"),
        "contributor_token":     token,
        "name":                  file.filename or "Contribution",
        "original_filename":     file.filename,
        "mime_type":             file.content_type,
        "size_bytes":            len(payload),
        "state":                 "draft",
        "origin":                "magic_link",
        "status":                "ready",
        "extracted_text":        payload.decode("utf-8", errors="replace") if (file.content_type or "").startswith("text/") else "",
        "contributor_note":      note,
        "created_at":            datetime.now(timezone.utc).isoformat(),
    }
    await db.documents.insert_one(dict(doc))
    try:
        await db.audit_log.insert_one({
            "id":            str(uuid.uuid4()),
            "account_id":    row["task_account_id"],
            "action":        "task.contribution.uploaded",
            "resource_type": "task",
            "resource_id":   row["task_id"],
            "metadata": {
                "contributor_email": row["contributor_email"],
                "doc_id":            did,
                "filename":          file.filename,
                "size_bytes":        len(payload),
            },
            "created_at":    datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:  # noqa: BLE001
        log.warning("contribution.uploaded audit failed: %s", e)
    return {"ok": True, "doc_id": did, "name": file.filename}


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/contribute/{token}/comment — PUBLIC comment add
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/contribute/{token}/comment")
async def contributor_comment(token: str, body: _ContributorCommentIn):
    row = await _resolve_contributor_token(token)
    cmt = {
        "id":         str(uuid.uuid4()),
        "reviewer":   row["contributor_email"],
        "comment":    body.comment.strip()[:4000],
        "kind":       "contributor",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.tasks.update_one(
        {"id": row["task_id"]},
        {"$push": {"contributor_comments": cmt}, "$set": {"updated_at": cmt["created_at"]}},
    )
    return {"ok": True, "comment_id": cmt["id"]}


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/contribute/{token}/submit — PUBLIC finalize
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/contribute/{token}/submit")
async def contributor_submit(token: str, body: _ContributorSubmitIn):
    """Flip the contributor's status to `submitted` + fire audit."""
    row = await _resolve_contributor_token(token)
    t = await db.tasks.find_one({"id": row["task_id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    team = list(t.get("team") or [])
    target_email = row["contributor_email"]
    idx = next(
        (i for i, m in enumerate(team) if (m.get("email") or "").lower() == target_email),
        None,
    )
    if idx is None:
        raise HTTPException(status_code=404, detail="Contributor not on this task")
    if team[idx].get("status") in ("approved",):
        return {"ok": True, "noop_reason": "already_approved"}
    team[idx] = {**team[idx], "status": "submitted"}
    if body.final_note:
        team[idx]["final_note"] = body.final_note
    now_iso = datetime.now(timezone.utc).isoformat()
    from services.tasks.intelligence_service import readiness_breakdown
    rb = readiness_breakdown({**t, "team": team})
    await db.tasks.update_one(
        {"id": row["task_id"]},
        {"$set": {"team": team, "updated_at": now_iso, "readiness_score": rb["score"]}},
    )
    try:
        await db.audit_log.insert_one({
            "id":            str(uuid.uuid4()),
            "account_id":    row["task_account_id"],
            "action":        "task.contribution.submitted",
            "resource_type": "task",
            "resource_id":   row["task_id"],
            "metadata": {
                "contributor_email": target_email,
                "via":               "magic_link",
                "readiness_after":   rb["score"],
            },
            "created_at": now_iso,
        })
    except Exception as e:  # noqa: BLE001
        log.warning("contribution.submitted audit failed: %s", e)
    return {"ok": True, "readiness_score": rb["score"]}


# ─────────────────────────────────────────────────────────────────────
# POST /api/tasks/{task_id}/contributors/{contributor_id}/reinvite
# ─────────────────────────────────────────────────────────────────────
@router.post("/tasks/{task_id}/contributors/{contributor_id}/reinvite")
async def reinvite_contributor(
    task_id: str, contributor_id: str,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Re-fire the invitation email for one contributor. Rotates the
    magic-link token if applicable (revokes the previous one so old
    links go dead)."""
    t = await db.tasks.find_one({"id": task_id, "account_id": current["id"]}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    cid_lower = contributor_id.lower()
    member = next(
        (m for m in (t.get("team") or [])
         if (m.get("email") or "").lower() == cid_lower
         or (m.get("name") or "").lower() == cid_lower
         or m.get("contributor_id") == contributor_id),
        None,
    )
    if not member:
        raise HTTPException(status_code=404, detail="Contributor not on this task")
    from services.tasks.contributor_invitation_service import (
        invite_akki_account, invite_magic_link, invite_email_reply,
    )
    import os as _os
    app_base = _os.environ.get("PUBLIC_BASE_URL") or _os.environ.get("REACT_APP_BACKEND_URL") or ""
    mode = (member.get("contribution_mode") or "akki_account").lower()
    if mode == "magic_link":
        result = await invite_magic_link(db, task=t, contributor=member, app_base=app_base)
    elif mode == "email_reply":
        result = await invite_email_reply(db, task=t, contributor=member, app_base=app_base)
    else:
        result = await invite_akki_account(db, task=t, contributor=member, app_base=app_base)
    try:
        await db.audit_log.insert_one({
            "id":            str(uuid.uuid4()),
            "account_id":    current["id"],
            "action":        "task.contributor.reinvited",
            "resource_type": "task",
            "resource_id":   task_id,
            "metadata": {
                "contributor_email": member.get("email"),
                "mode":              mode,
                "delivery_status":   result.get("mode"),
            },
            "created_at":    datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:  # noqa: BLE001
        log.warning("contributor.reinvited audit failed: %s", e)
    return {"ok": True, "delivery_status": result.get("mode"), "mode": mode}



# ═════════════════════════════════════════════════════════════════════
# Phase F.6 (2026-05-26) — Account-scoped task activity feed
# ═════════════════════════════════════════════════════════════════════
@router.get("/accounts/{account_id}/task-activity/recent")
async def list_account_task_activity(
    account_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    current: Dict[str, Any] = Depends(get_current_account),
):
    """Account-scoped task activity feed.

    The existing `/api/contexts/{cid}/activity/recent` is context-scoped
    — it drops events for tasks created without a `context_id`. This
    endpoint serves the Task Manager right rail's "Recent Task
    Activity" card, listing every `task.*` event owned by the
    account regardless of `context_id` association.

    Authorization: the requesting account MUST match `account_id`."""
    if account_id != current["id"]:
        raise HTTPException(status_code=403, detail="Cross-account task activity not permitted")
    rows = await db.audit_log.find(
        {"account_id": account_id, "action": {"$regex": "^task\\."}},
        {"_id": 0, "id": 1, "action": 1, "resource_id": 1, "metadata": 1, "created_at": 1},
    ).sort("created_at", -1).to_list(length=limit)
    task_ids = sorted({r.get("resource_id") for r in rows if r.get("resource_id")})
    name_by_id: Dict[str, str] = {}
    if task_ids:
        async for t in db.tasks.find(
            {"id": {"$in": list(task_ids)}, "account_id": account_id},
            {"_id": 0, "id": 1, "name": 1},
        ):
            name_by_id[t["id"]] = t.get("name") or t["id"]
    return [
        {
            "id":          r.get("id"),
            "action":      r.get("action"),
            "task_id":     r.get("resource_id"),
            "task_name":   name_by_id.get(r.get("resource_id"), "(deleted or unrelated)"),
            "metadata":    r.get("metadata") or {},
            "created_at":  r.get("created_at"),
        }
        for r in rows
    ]

