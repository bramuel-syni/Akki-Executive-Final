"""First Session state machine (Advisory 5 — Phase 4).

Replaces the legacy 7-question Onboarding with a 3-question intake + 3-door
pick + one AKKI-generated artefact. Target end-to-end time: ≤10 minutes.

State lives on `db.accounts.{id}.first_session`:
    {
      status: "not_started" | "in_progress" | "completed" | "skipped",
      started_at: iso-str | null,
      completed_at: iso-str | null,
      current_step: "intake" | "door" | "working" | "done",
      door_taken: "email" | "upload" | "solve" | null,
      artefact: {kind: "briefing"|"solve_session", id: str} | null,
      intake: {role, primary_context_name, top_of_mind} | null
    }

Every transition writes an audit row with action `first_session.{step}`.

J1 (2026-05-25) additions — ratified spec gaps:
  * **G18 — Shield routing on `top_of_mind`**. The Q3 intake answer is
    routed through `deidentifier.deidentify()` BEFORE it is persisted
    to `context_objects.answers`. The redacted text is stored in
    `top_of_mind`; the token-map is stored alongside in
    `top_of_mind_token_map` so re-identification at presentation time
    remains possible. If Shield is `ServiceUnavailable`, the intake
    POST fails closed with HTTP 503 (matching the Shield audit chain
    semantics).
  * **G20 — Context-type emission per role**. `ned` and `chair` roles
    emit a context of type `ned_personal`; `executive` and `dual`
    continue to emit `executive_personal`. The default context was
    provisioned at register time as `executive_personal`; this hook
    re-types it on intake submission when the declared role implies
    `ned_personal`.

Both additions route through existing guardrail code paths
(`deidentifier`, `db.contexts` writes) without modifying any
guardrail file.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core import (
    db,
    get_current_account,
    iso as _iso,
    now as _now,
    provision_default_context,
    write_audit,
)
from services.synisense.exceptions import ServiceUnavailable
from services.synisense.shield import deidentifier as _shield_deidentifier

log = logging.getLogger("akki.first_session")

# G20 — context-type mapping per declared role (ratified 2026-05-25).
# `ned` and `chair` produce `ned_personal`; `executive` and `dual`
# (current default) produce `executive_personal`.
_ROLE_TO_CONTEXT_TYPE = {
    "executive": "executive_personal",
    "ned": "ned_personal",
    "chair": "ned_personal",
    "dual": "executive_personal",
}

router = APIRouter(prefix="/api/me/first-session", tags=["first-session"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class IntakeIn(BaseModel):
    role: str = Field(min_length=1, max_length=32)  # "executive" | "ned" | "chair" | "dual"
    primary_context_name: str = Field(min_length=1, max_length=80)
    top_of_mind: str = Field(min_length=1, max_length=240)


class DoorIn(BaseModel):
    door: str = Field(min_length=1, max_length=16)  # "email" | "upload" | "solve"


class ArtefactIn(BaseModel):
    kind: str = Field(min_length=1, max_length=32)  # "briefing" | "solve_session"
    id: str = Field(min_length=1, max_length=64)


class CompleteIn(BaseModel):
    artefact: ArtefactIn


ALLOWED_ROLES = {"executive", "ned", "chair", "dual"}
ALLOWED_DOORS = {"email", "upload", "solve"}
ALLOWED_ARTEFACTS = {"briefing", "solve_session"}


# ---------------------------------------------------------------------------
# Intake question catalogue (sent on GET when not-started)
# ---------------------------------------------------------------------------
INTAKE_QUESTIONS = [
    {
        "id": "role",
        "type": "single",
        "question": "Which best describes your role?",
        "options": [
            {"value": "executive", "label": "Executive"},
            {"value": "ned", "label": "Non-Executive Director"},
            {"value": "chair", "label": "Chair"},
            {"value": "dual", "label": "Dual (Exec + NED)"},
        ],
    },
    {
        "id": "primary_context_name",
        "type": "text",
        "question": "What's the primary board or company you sit on?",
        "max_length": 80,
    },
    {
        "id": "top_of_mind",
        "type": "textarea",
        "question": "What's on your mind for the next meeting? One sentence.",
        "max_length": 240,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _default_state() -> Dict[str, Any]:
    return {
        "status": "not_started",
        "started_at": None,
        "completed_at": None,
        "current_step": "intake",
        "door_taken": None,
        "artefact": None,
        "intake": None,
        "grandfathered": False,
    }


def _sanitize_state(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not raw:
        return _default_state()
    out = _default_state()
    out.update({k: v for k, v in raw.items() if k in out})
    return out


async def _get_or_provision_context_id(account: Dict[str, Any]) -> str:
    """Return an existing owned/personal context id, or provision one."""
    m = await db.memberships.find_one(
        {"account_id": account["id"], "status": "active"},
        {"_id": 0, "context_id": 1, "role": 1, "sub_role": 1},
        sort=[("created_at", 1)],
    )
    if m and m.get("context_id"):
        return m["context_id"]
    # Provision a default personal context using the existing helper.
    name = (account.get("name") or account.get("email") or "Personal").split("@")[0]
    ctx = await provision_default_context(account, f"{name}'s workspace")
    return ctx["id"]


async def _persist_state(account_id: str, state: Dict[str, Any]) -> None:
    await db.accounts.update_one(
        {"id": account_id}, {"$set": {"first_session": state}}
    )


async def _write_context_object_from_intake(
    account_id: str, context_id: str, intake: Dict[str, Any]
) -> None:
    """Persist a sparse context_object v1 with only the 3 intake fields.

    The 4 deferred fields (jurisdiction / board_count / sector_depth /
    industry_depth) stay null — they're surfaced on-demand when the user
    uploads their first document.
    """
    latest = await db.context_objects.find_one(
        {"context_id": context_id}, {"_id": 0}, sort=[("version", -1)]
    )
    new_version = (latest["version"] + 1) if latest else 1
    created_at = _iso(_now())
    role = intake["role"]
    # Map first-session role → legacy MembershipRole for the context_object
    legacy_role = {
        "executive": "executive",
        "dual": "executive",
        "chair": "ned",
        "ned": "ned",
    }.get(role, "executive")
    import uuid as _uuid
    doc = {
        "id": str(_uuid.uuid4()),
        "context_id": context_id,
        "version": new_version,
        "industry": None,
        "sector": None,
        "jurisdiction": None,
        "role": legacy_role,
        "answers": {
            "first_session": {
                "role": role,
                "primary_context_name": intake["primary_context_name"],
                "top_of_mind": intake["top_of_mind"],
                # G18 (2026-05-25, ratified) — store the Shield token-map
                # + summary alongside the redacted text so re-identification
                # at presentation time remains possible. The raw answer is
                # NEVER persisted.
                "top_of_mind_token_map": intake.get("top_of_mind_token_map") or {},
                "top_of_mind_shield_summary": intake.get("top_of_mind_shield_summary") or {},
            }
        },
        "step": 1,
        "completed": False,  # stays false until the 4 deferred are filled
        "created_by": account_id,
        "created_at": created_at,
        "updated_at": created_at,
    }
    await db.context_objects.insert_one(doc)
    # Also stamp the context itself for quick access
    await db.contexts.update_one(
        {"id": context_id},
        {
            "$set": {
                "name": intake["primary_context_name"],
                "progress_state": {
                    "onboarding_step": 1,
                    "onboarding_completed": False,
                    "context_object_version": new_version,
                    "first_session_intake_captured": True,
                },
            }
        },
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("")
async def get_first_session(current: Dict[str, Any] = Depends(get_current_account)):
    state = _sanitize_state(current.get("first_session"))
    return {
        "state": state,
        "questions": INTAKE_QUESTIONS if state["status"] in ("not_started", "in_progress") else None,
    }


@router.post("/start")
async def start_first_session(current: Dict[str, Any] = Depends(get_current_account)):
    state = _sanitize_state(current.get("first_session"))
    if state["status"] in ("completed", "skipped"):
        return {"state": state}
    # Ensure a context exists so the intake has somewhere to write.
    ctx_id = await _get_or_provision_context_id(current)
    state["status"] = "in_progress"
    state["current_step"] = "intake"
    state["started_at"] = state["started_at"] or _iso(_now())
    await _persist_state(current["id"], state)
    await write_audit(
        ctx_id, current["id"], "first_session.started",
        "account", current["id"], {},
    )
    return {"state": state}


@router.post("/intake")
async def submit_intake(
    body: IntakeIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    if body.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role.")
    state = _sanitize_state(current.get("first_session"))
    if state["status"] in ("completed", "skipped"):
        # Idempotent — just return current state.
        return {"state": state}

    ctx_id = await _get_or_provision_context_id(current)

    # G18 (2026-05-25) — Shield routing on `top_of_mind`. The Q3 answer
    # is routed through `deidentifier.deidentify()` BEFORE storage so
    # any future LLM access automatically operates on a Shield-clean
    # copy (defence-in-depth on top of the `llm_router` boundary).
    raw_top_of_mind = body.top_of_mind.strip()
    try:
        shield_result = await _shield_deidentifier.deidentify(
            raw_top_of_mind, tenant_id=ctx_id,
        )
    except ServiceUnavailable as exc:
        # Shield is fail-closed per services/synisense/shield/deidentifier.py
        # — bubble up as 503 so the user can retry. NEVER persist the raw
        # answer when Shield can't reach a clean state.
        log.warning(
            "first_session.intake — Shield unavailable for account=%s ctx=%s",
            current["id"], ctx_id,
        )
        raise HTTPException(status_code=503, detail=str(exc))

    intake = {
        "role": body.role,
        "primary_context_name": body.primary_context_name.strip(),
        "top_of_mind": shield_result.redacted_text,
        "top_of_mind_token_map": shield_result.token_map,
        "top_of_mind_shield_summary": {
            "de_id_summary": shield_result.de_id_summary,
            "dilution_score": shield_result.dilution_score,
            "exposure_reduction_score": shield_result.exposure_reduction_score,
            "elapsed_ms": shield_result.elapsed_ms,
        },
    }
    await _write_context_object_from_intake(current["id"], ctx_id, intake)

    # Mirror the role onto the account if not already declared.
    declared = {
        "executive": "executive",
        "ned": "ned",
        "chair": "ned",
        "dual": "dual",
    }.get(body.role, "executive")
    await db.accounts.update_one(
        {"id": current["id"]},
        {"$set": {"declared_role": declared}},
    )

    # G20 (2026-05-25) — re-type the user's default context if the
    # declared role implies a NED workspace. Default contexts are
    # provisioned at register time as `executive_personal`; this hook
    # promotes them to `ned_personal` when role ∈ {ned, chair}. The
    # change is idempotent (set-if-different) and audited.
    new_type = _ROLE_TO_CONTEXT_TYPE.get(body.role, "executive_personal")
    ctx_row = await db.contexts.find_one(
        {"id": ctx_id}, {"_id": 0, "id": 1, "type": 1, "name": 1},
    )
    if ctx_row and ctx_row.get("type") != new_type:
        await db.contexts.update_one(
            {"id": ctx_id},
            {"$set": {"type": new_type}},
        )
        # Also update the matching membership role so role-gated
        # surfaces (NED inbox, committee surfaces) light up.
        if body.role in ("ned", "chair"):
            await db.memberships.update_one(
                {"context_id": ctx_id, "account_id": current["id"]},
                {"$set": {"role": "ned"}},
            )
        await write_audit(
            ctx_id, current["id"], "context.retyped",
            "context", ctx_id,
            {"from": ctx_row.get("type"), "to": new_type, "reason": "G20_role_intake"},
        )

    state["status"] = "in_progress"
    state["current_step"] = "door"
    state["intake"] = intake
    state["started_at"] = state["started_at"] or _iso(_now())
    await _persist_state(current["id"], state)
    await write_audit(
        ctx_id, current["id"], "first_session.intake",
        "account", current["id"], {"role": body.role},
    )
    return {"state": state, "context_id": ctx_id}


@router.post("/choose-door")
async def choose_door(
    body: DoorIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    if body.door not in ALLOWED_DOORS:
        raise HTTPException(status_code=400, detail="Invalid door.")
    state = _sanitize_state(current.get("first_session"))
    if state["status"] in ("completed", "skipped"):
        return {"state": state}
    ctx_id = await _get_or_provision_context_id(current)

    # Solve is a one-way exit: the Solve session IS the artefact-creation
    # flow. Flip to `completed` immediately so the FirstSessionGuard stops
    # redirecting `/app/solve` back to `/app/first-session`. We don't pin
    # an artefact id here — the user hasn't run Solve yet; when they do,
    # the session lives in `db.solve_sessions` under their account_id and
    # there's nothing for us to backwire to first_session.
    if body.door == "solve":
        state["door_taken"] = "solve"
        state["current_step"] = "done"
        state["status"] = "completed"
        state["completed_at"] = _iso(_now())
        await _persist_state(current["id"], state)
        await write_audit(
            ctx_id, current["id"], "first_session.door_solve",
            "account", current["id"], {"door": "solve"},
        )
        await write_audit(
            ctx_id, current["id"], "first_session.completed",
            "account", current["id"], {"door": "solve", "exit": "solve_door"},
        )
        return {"state": state}

    # email / upload — normal working-step flow.
    state["status"] = "in_progress"
    state["door_taken"] = body.door
    state["current_step"] = "working"
    await _persist_state(current["id"], state)
    await write_audit(
        ctx_id, current["id"], f"first_session.door_{body.door}",
        "account", current["id"], {"door": body.door},
    )
    return {"state": state}


@router.post("/complete")
async def complete_first_session(
    body: CompleteIn,
    current: Dict[str, Any] = Depends(get_current_account),
):
    if body.artefact.kind not in ALLOWED_ARTEFACTS:
        raise HTTPException(status_code=400, detail="Invalid artefact kind.")
    state = _sanitize_state(current.get("first_session"))
    if state["status"] == "completed":
        return {"state": state}

    # Validate artefact existence in user's contexts.
    ctx_ids = [
        m["context_id"] async for m in db.memberships.find(
            {"account_id": current["id"], "status": "active"},
            {"_id": 0, "context_id": 1},
        )
    ]
    if body.artefact.kind == "briefing":
        found = await db.boardpacks.find_one(
            {"id": body.artefact.id, "context_id": {"$in": ctx_ids}}, {"_id": 0, "id": 1}
        )
    else:  # solve_session — Solva v2 sessions are user-scoped, not
           # context-scoped. M.4 repointed the lookup at solva_v2_sessions
           # (the v1 collection was archived as solva_v1_sessions_archive).
        found = await db.solva_v2_sessions.find_one(
            {"id": body.artefact.id, "account_id": current["id"]}, {"_id": 0, "id": 1}
        )
    if not found:
        raise HTTPException(status_code=404, detail="Artefact not found in your contexts.")

    state["status"] = "completed"
    state["completed_at"] = _iso(_now())
    state["current_step"] = "done"
    state["artefact"] = {"kind": body.artefact.kind, "id": body.artefact.id}
    await _persist_state(current["id"], state)
    await write_audit(
        ctx_ids[0] if ctx_ids else None,
        current["id"],
        "first_session.completed",
        "account",
        current["id"],
        {"artefact": state["artefact"]},
    )
    return {"state": state}


@router.post("/skip")
async def skip_first_session(current: Dict[str, Any] = Depends(get_current_account)):
    state = _sanitize_state(current.get("first_session"))
    if state["status"] == "completed":
        return {"state": state}
    state["status"] = "skipped"
    state["completed_at"] = state["completed_at"] or _iso(_now())
    await _persist_state(current["id"], state)
    await write_audit(
        None, current["id"], "first_session.skipped",
        "account", current["id"], {},
    )
    return {"state": state}
