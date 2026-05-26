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
    """F.2 — fire a simple "you've been added to a task" audit row per
    team member. Email send via Resend is deferred to F.5 (Contributor
    modes). For now the audit log is the durable record.
    """
    ctx_id = task.get("context_id")
    for m in (task.get("team") or []):
        try:
            await db.audit_log.insert_one({
                "id":            str(uuid.uuid4()),
                "context_id":    ctx_id,
                "account_id":    task.get("account_id"),
                "action":        "task.contributor.added",
                "resource_type": "task",
                "resource_id":   task.get("id"),
                "metadata": {
                    "contributor_email": m.get("email"),
                    "contribution_mode": m.get("contribution_mode") or "akki_account",
                    "task_name":         task.get("name"),
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:  # noqa: BLE001
            log.warning("contributor notify audit failed: %s", e)


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
    # On commission (state=active), fire contributor notifications.
    if body.state == "active":
        await _notify_contributors(task)
    return _sanitize_task(task)


# ═════════════════════════════════════════════════════════════════════
# GET /api/tasks?state=...&context_id=...
# ═════════════════════════════════════════════════════════════════════
@router.get("/tasks")
async def list_tasks(
    state: Optional[str] = Query(None, pattern="^(active|draft|closed)$"),
    context_id: Optional[str] = None,
    current: Dict[str, Any] = Depends(get_current_account),
):
    """List tasks scoped to the caller. Filter by state (Active /
    Draft / Closed) — used by the 3-tab listing surface."""
    q: Dict[str, Any] = {"account_id": current["id"]}
    if state:
        q["state"] = state
    if context_id:
        q["context_id"] = context_id
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
        await _notify_contributors(t2)

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
