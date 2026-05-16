"""Solva Phase D — context-scoped REST endpoints.

Mounted at `/api/contexts/{context_id}/solva/v2/...` — distinct from
the legacy `/api/solva/v2/...` paths in `routers/solva_v2.py`. New
sessions written here flow through the Phase D state machine
(`services/solva/`) and persist into the `solva_phase_d_sessions`
Mongo collection.

Strict scoping: every endpoint enforces `account_id == tenant_id ==
session.account_id` AND `context_id == session.context_id`.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core import db, require_context_membership

from services.solva import (
    SUB_MODULES,
    LAYER_SEQUENCE,
    TERMINAL_STATES,
)
from services.solva.orchestration.state_machine import (
    advance,
    InvalidLayerTransition,
)
from services.solva.reasoning import (
    run_frame_audit,
    classify_situation,
    generate_candidates,
    run_triangulation,
    detect_tensions,
    weight_scenarios,
    evaluate_refusal,
    RefusalReason,
)
from services.solva.reasoning.candidate_generation import refine_candidates
from services.solva.voice import (
    next_question,
    LOCKED_REFLECTION_QUESTIONS,
    render_synthesis,
    render_acknowledgement,
    render_refusal,
)


logger = logging.getLogger("akki.solva.phase_d")

router = APIRouter(prefix="/api/contexts/{context_id}/solva/v2", tags=["solva-phase-d"])

COLLECTION = "solva_phase_d_sessions"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coll():
    return getattr(db, COLLECTION)


# ─────────────────────────────────────────────────────────────────────
# Request / response models.
# ─────────────────────────────────────────────────────────────────────
class CreateSessionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sub_module: str = Field(min_length=4, max_length=40)

    @field_validator("sub_module")
    @classmethod
    def _check_sub_module(cls, v: str) -> str:
        if v not in SUB_MODULES:
            raise ValueError(f"sub_module must be one of {SUB_MODULES}")
        return v


class SubmitFramingIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    framing_text: str = Field(min_length=20, max_length=4000)


class SubmitAnswerIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    answer_text: str = Field(min_length=2, max_length=4000)


class RefuseIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    operator_reason: Optional[str] = Field(default=None, max_length=200)


# ─────────────────────────────────────────────────────────────────────
# Helpers.
# ─────────────────────────────────────────────────────────────────────
async def _get_session(context_id: str, session_id: str, account_id: str) -> Dict[str, Any]:
    row = await _coll().find_one(
        {"session_id": session_id, "context_id": context_id, "account_id": account_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Solva session not found.")
    return row


async def _push_audit(session_id: str, audit_ids: List[str], orch_entries: List[Dict[str, Any]]):
    """Append audit_ids + orchestration entries to the session in one update."""
    ai = [a for a in audit_ids if a]
    if not ai and not orch_entries:
        return
    update: Dict[str, Any] = {"$set": {"updated_at": _utc_now()}}
    push: Dict[str, Any] = {}
    if ai:
        push["synisense_audit_ids"] = {"$each": ai}
    if orch_entries:
        push["orchestration_audit_log"] = {"$each": orch_entries}
    if push:
        update["$push"] = push
    await _coll().update_one({"session_id": session_id}, update)


def _next_question_payload(session: Dict[str, Any]) -> Dict[str, Any]:
    """Pick the right question for the current layer state."""
    sm = session.get("sub_module", "seek_clarity")
    sid = session.get("session_id", "")
    state = session.get("layer_state", "entry")

    if state == "layer_1":
        l1 = session.get("layer_1") or {}
        asked = int(l1.get("questions_count", 0))
        if asked == 0:
            far = session.get("layer_0") or {}
            key = (far.get("routing_decision") or {}).get(
                "layer_1_opening_question_key",
                f"{sm}.layer_1.opening.default",
            )
        else:
            # Subsequent layer_1 question — derive from FAR probe list,
            # then fall back to generic probe.
            probes = (
                (session.get("layer_0") or {}).get("routing_decision", {}).get(
                    "additional_probes", []
                )
            )
            key = probes[asked - 1] if asked - 1 < len(probes) else f"{sm}.layer_2.probe.evidence_grounding"
        q = next_question(key=key, session_id=sid, asked_so_far=asked)
        return {
            "layer": "layer_1",
            "question_key": q.key,
            "question_text": q.text,
            "questions_asked_so_far": asked,
            "questions_remaining_in_layer": max(0, 3 - asked),
        }

    if state == "layer_2":
        l2 = session.get("layer_2") or {}
        asked = int(l2.get("questions_count", 0))
        key = f"{sm}.layer_2.probe.evidence_grounding"
        if asked > 0:
            key = f"{sm}.layer_2.probe.evidence_grounding"
        q = next_question(key=key, session_id=sid, asked_so_far=asked)
        return {
            "layer": "layer_2",
            "question_key": q.key,
            "question_text": q.text,
            "questions_asked_so_far": asked,
            "questions_remaining_in_layer": max(0, 3 - asked),
        }

    if state == "layer_4":
        l4 = session.get("layer_4") or {}
        asked = len(l4.get("answers", []))
        if asked >= 3:
            return {"layer": "layer_4", "question_text": None, "questions_remaining_in_layer": 0}
        return {
            "layer": "layer_4",
            "question_key": f"reflection.q{asked + 1}",
            "question_text": LOCKED_REFLECTION_QUESTIONS[asked],
            "questions_asked_so_far": asked,
            "questions_remaining_in_layer": 3 - asked,
        }

    if state == "layer_3":
        l3 = session.get("layer_3") or {}
        return {
            "layer": "layer_3",
            "synthesis_text": l3.get("rendered_synthesis") or "",
            "is_refusal": bool(l3.get("refusal_flag")),
        }

    if state == "refused":
        l3 = session.get("layer_3") or {}
        return {
            "layer": "refused",
            "synthesis_text": None,
            "is_refusal": True,
            "refusal_rendering": l3.get("refusal_rendering") or l3.get("rendered_synthesis") or "",
            "refusal_reason": l3.get("refusal_reason"),
        }

    return {"layer": state, "question_text": None}


def _serialise(session: Dict[str, Any]) -> Dict[str, Any]:
    """Public response shape — strips Mongo internals."""
    s = dict(session)
    s.pop("_id", None)
    # Stringify datetimes for response.
    for k in ("created_at", "updated_at", "completed_at"):
        if isinstance(s.get(k), datetime):
            s[k] = s[k].isoformat()
    return s


# ─────────────────────────────────────────────────────────────────────
# Endpoints.
# ─────────────────────────────────────────────────────────────────────
@router.post("/sessions")
async def create_session(
    body: CreateSessionIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    account = ctx["account"]
    context_id = ctx["context"]["id"]
    sid = "sol-" + uuid.uuid4().hex
    now = _utc_now()
    row = {
        "session_id": sid,
        "user_id": account["id"],
        "account_id": account["id"],
        "context_id": context_id,
        "sub_module": body.sub_module,
        "status": "active",
        "layer_state": "entry",
        "initial_framing": None,
        "layer_0": None,
        "layer_1": None,
        "layer_2": None,
        "layer_3": None,
        "layer_4": None,
        "synisense_audit_ids": [],
        "orchestration_audit_log": [],
        "schema_version": 3,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    await _coll().insert_one(dict(row))
    row.pop("_id", None)
    return _serialise(row)


@router.get("/sessions")
async def list_sessions(
    status: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Strict context+account scoping."""
    account = ctx["account"]
    context_id = ctx["context"]["id"]
    q: Dict[str, Any] = {"account_id": account["id"], "context_id": context_id}
    if status:
        q["status"] = status
    rows = await _coll().find(q, {"_id": 0}).sort("updated_at", -1).to_list(length=limit)
    for r in rows:
        for k in ("created_at", "updated_at", "completed_at"):
            if isinstance(r.get(k), datetime):
                r[k] = r[k].isoformat()
    return {"items": rows, "count": len(rows)}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    account = ctx["account"]
    context_id = ctx["context"]["id"]
    row = await _get_session(context_id, session_id, account["id"])
    payload = _serialise(row)
    payload["next_question"] = _next_question_payload(row)
    return payload


@router.post("/sessions/{session_id}/framing")
async def submit_framing(
    session_id: str,
    body: SubmitFramingIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Submit initial framing → kicks off Layer 0 (silent FAR) → Layer 1."""
    account = ctx["account"]
    context_id = ctx["context"]["id"]
    session = await _get_session(context_id, session_id, account["id"])
    if session["layer_state"] != "framing" and session["layer_state"] != "entry":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot submit framing from layer_state={session['layer_state']}.",
        )

    # Move to framing state if still at entry.
    if session["layer_state"] == "entry":
        await _coll().update_one(
            {"session_id": session_id},
            {"$set": {"layer_state": "framing", "initial_framing": body.framing_text}},
        )
    else:
        await _coll().update_one(
            {"session_id": session_id},
            {"$set": {"initial_framing": body.framing_text}},
        )

    # Layer 0 — situation class + frame audit (silent).
    sc_out = await classify_situation(
        framing_text=body.framing_text,
        tenant_id=account["id"],
        user_id=account["id"],
    )
    far_out = await run_frame_audit(
        sub_module=session["sub_module"],
        framing_text=body.framing_text,
        tenant_id=account["id"],
        user_id=account["id"],
        situation_class=sc_out.situation_class,
    )

    audit_ids = []
    if sc_out.audit_id:
        audit_ids.append(sc_out.audit_id)
    if far_out.audit_id:
        audit_ids.append(far_out.audit_id)
    orch_entries = list(sc_out.orchestration_entries) + list(far_out.orchestration_entries)

    layer_0_record = {
        "verdict": far_out.verdict,
        "dimensions": [d.model_dump() for d in far_out.dimensions],
        "routing_decision": far_out.routing_decision,
        "situation_class": sc_out.situation_class,
        "situation_class_confidence": sc_out.confidence,
        "carry_forward_caveats": far_out.carry_forward_caveats,
    }

    # Advance: framing → layer_0 → layer_1 (Layer 0 is silent).
    await _coll().update_one(
        {"session_id": session_id},
        {
            "$set": {
                "layer_0": layer_0_record,
                "layer_1": {"questions_count": 0, "answers": [], "candidate_set": [], "question_ids_asked": []},
                "layer_state": "layer_1",
                "updated_at": _utc_now(),
            }
        },
    )
    await _push_audit(session_id, audit_ids, orch_entries)

    refreshed = await _get_session(context_id, session_id, account["id"])
    payload = _serialise(refreshed)
    payload["next_question"] = _next_question_payload(refreshed)
    payload["acknowledgement"] = render_acknowledgement(
        sub_module=session["sub_module"], framing_text=body.framing_text,
    )
    return payload


@router.post("/sessions/{session_id}/answer")
async def submit_answer(
    session_id: str,
    body: SubmitAnswerIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Advance the state machine by one answer."""
    account = ctx["account"]
    context_id = ctx["context"]["id"]
    session = await _get_session(context_id, session_id, account["id"])
    state = session.get("layer_state")
    if state in TERMINAL_STATES:
        raise HTTPException(status_code=409, detail=f"Session is {state}; no further answers.")
    if state not in {"layer_1", "layer_2", "layer_4"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot submit an answer at layer_state={state}.",
        )

    answer_record = {
        "id": "ans-" + uuid.uuid4().hex,
        "text": body.answer_text,
        "submitted_at": _utc_now().isoformat(),
    }

    if state == "layer_1":
        layer_1 = session.get("layer_1") or {}
        answers = list(layer_1.get("answers") or []) + [answer_record]
        questions_count = int(layer_1.get("questions_count") or 0) + 1
        await _coll().update_one(
            {"session_id": session_id},
            {"$set": {
                "layer_1.answers": answers,
                "layer_1.questions_count": questions_count,
                "updated_at": _utc_now(),
            }},
        )

        # When 3 answers collected: run candidate generation, transition to layer_2.
        if questions_count >= 3:
            far_routing = (session.get("layer_0") or {}).get("routing_decision", {})
            sc = (session.get("layer_0") or {}).get("situation_class", "other_strategic")
            cg = await generate_candidates(
                framing_text=session.get("initial_framing") or "",
                sub_module=session["sub_module"],
                situation_class=sc,
                far_routing=far_routing,
                tenant_id=account["id"],
                user_id=account["id"],
                layer_1_answers=answers,
            )
            audit_ids = [cg.audit_id] if cg.audit_id else []
            orch_entries = list(cg.orchestration_entries)

            await _coll().update_one(
                {"session_id": session_id},
                {"$set": {
                    "layer_1.candidate_set": [c.model_dump() for c in cg.candidates],
                    "layer_2": {
                        "questions_count": 0,
                        "answers": [],
                        "question_ids_asked": [],
                        "triangulation_result": {},
                        "detected_tensions": [],
                        "refined_candidates": [],
                    },
                    "layer_state": "layer_2",
                    "updated_at": _utc_now(),
                }},
            )
            await _push_audit(session_id, audit_ids, orch_entries)

    elif state == "layer_2":
        layer_2 = session.get("layer_2") or {}
        answers = list(layer_2.get("answers") or []) + [answer_record]
        questions_count = int(layer_2.get("questions_count") or 0) + 1
        await _coll().update_one(
            {"session_id": session_id},
            {"$set": {
                "layer_2.answers": answers,
                "layer_2.questions_count": questions_count,
                "updated_at": _utc_now(),
            }},
        )

        # When 3 answers collected: run triangulation + tension, then move to layer_3.
        if questions_count >= 3:
            narrative = "\n\n".join(
                a.get("text", "") for a in (session.get("layer_1") or {}).get("answers", []) + answers
            )
            tri = await run_triangulation(
                narrative_text=narrative,
                evidence_chunks=[],         # Phase D — no document retrieval yet (Phase E)
                prior_signals=[],
                tenant_id=account["id"],
                user_id=account["id"],
            )
            ten = await detect_tensions(
                narrative_text=narrative,
                evidence_chunks=[],
                tenant_id=account["id"],
                user_id=account["id"],
            )
            audit_ids = list(tri.audit_ids) + ([ten.audit_id] if ten.audit_id else [])
            orch_entries = list(tri.orchestration_entries) + list(ten.orchestration_entries)

            existing_candidates = (session.get("layer_1") or {}).get("candidate_set", [])
            refined = refine_candidates(
                existing=list(existing_candidates),
                layer_2_signal={
                    "supporting_candidate_ids": [],
                    "contradicting_candidate_ids": [],
                },
            )

            await _coll().update_one(
                {"session_id": session_id},
                {"$set": {
                    "layer_2.triangulation_result": {
                        "overall_consistency": tri.overall_consistency,
                        "divergences": [d.model_dump() for d in tri.divergences],
                        "extracted_claims": tri.extracted_claims,
                    },
                    "layer_2.detected_tensions": [t.model_dump() for t in ten.tensions],
                    "layer_2.refined_candidates": refined,
                    "layer_state": "layer_3",
                    "updated_at": _utc_now(),
                }},
            )
            await _push_audit(session_id, audit_ids, orch_entries)

            # ─── Layer 3 — synthesis OR refusal ───
            await _run_layer_3(session_id, context_id, account["id"])

    elif state == "layer_4":
        layer_4 = session.get("layer_4") or {"answers": []}
        answers = list(layer_4.get("answers") or []) + [answer_record]
        update: Dict[str, Any] = {
            "layer_4.answers": answers,
            "updated_at": _utc_now(),
        }
        if len(answers) >= 3:
            update["layer_state"] = "done"
            update["status"] = "completed"
            update["completed_at"] = _utc_now()
        await _coll().update_one({"session_id": session_id}, {"$set": update})

    refreshed = await _get_session(context_id, session_id, account["id"])
    payload = _serialise(refreshed)
    payload["next_question"] = _next_question_payload(refreshed)
    return payload


async def _run_layer_3(session_id: str, context_id: str, account_id: str) -> None:
    """Run probability weighting + refusal check + voice synthesis."""
    session = await _coll().find_one(
        {"session_id": session_id, "context_id": context_id, "account_id": account_id},
        {"_id": 0},
    )
    if not session:
        return
    far_dict = session.get("layer_0") or {}
    far_situation_class = far_dict.get("situation_class", "other_strategic")
    sc_conf = float(far_dict.get("situation_class_confidence", 0.0))
    refined = (session.get("layer_2") or {}).get("refined_candidates") or []
    tri_dict = (session.get("layer_2") or {}).get("triangulation_result") or {}
    layer_1_answers = (session.get("layer_1") or {}).get("answers") or []
    layer_2_answers = (session.get("layer_2") or {}).get("answers") or []

    # Reconstruct Pydantic-shaped inputs for the refusal evaluator.
    from services.solva.reasoning.frame_audit_engine import FrameAuditOutput, FARDimension
    from services.solva.reasoning.triangulation_engine import TriangulationOutput, Divergence
    from services.solva.reasoning.refusal_logic import compute_layer_2_resolved

    far_obj = FrameAuditOutput(
        verdict=far_dict.get("verdict", "sufficient"),
        dimensions=[FARDimension(**d) for d in far_dict.get("dimensions", [])],
        routing_decision=far_dict.get("routing_decision", {}),
        carry_forward_caveats=far_dict.get("carry_forward_caveats", []),
    )
    tri_obj = TriangulationOutput(
        overall_consistency=float(tri_dict.get("overall_consistency", 0.5)),
        divergences=[Divergence(**d) for d in tri_dict.get("divergences", [])],
        extracted_claims=tri_dict.get("extracted_claims", []),
    )

    # Compute resolved-missing-dimensions from actual answer content
    # (Phase D fix bundle 2026-05-16 — was hardcoded True, which made
    # Rule 3 of refusal_logic never fire in the live pipeline).
    layer_2_resolved = compute_layer_2_resolved(
        layer_1_answers=layer_1_answers,
        layer_2_answers=layer_2_answers,
    )

    decision = evaluate_refusal(
        far=far_obj,
        triangulation=tri_obj,
        candidates=refined,
        situation_class=far_situation_class,
        situation_class_confidence=sc_conf,
        layer_2_resolved_missing_dimensions=layer_2_resolved,
    )

    if decision.should_refuse:
        prose = render_refusal(
            sub_module=session["sub_module"],
            reason=decision.reason,  # type: ignore[arg-type]
            candidates_to_surface=decision.candidates_to_surface or refined,
        )
        await _coll().update_one(
            {"session_id": session_id},
            {"$set": {
                "layer_3": {
                    "scenarios": [],
                    "sensitivity_drivers": [],
                    "surfaced_tensions": [],
                    "evidence_trace": [],
                    "primary_diagnosis_prose": "",
                    "refusal_flag": True,
                    "refusal_reason": decision.reason.value if decision.reason else "refused",
                    "refusal_detail": decision.detail,
                    # Phase D fix bundle 2026-05-16 — refusal copy lands ONLY
                    # in `refusal_rendering`. `rendered_synthesis` is None
                    # because no synthesis was produced (brief §4.7 acceptance
                    # criterion). The AuditPanel timeline reads
                    # `synisense_audit_ids` not these fields, so no
                    # back-compat break.
                    "refusal_rendering": prose,
                    "rendered_synthesis": None,
                },
                "status": "refused",
                "layer_state": "refused",
                "completed_at": _utc_now(),
                "updated_at": _utc_now(),
            }},
        )
        return

    pw = await weight_scenarios(
        candidates=refined,
        triangulation_alignment=tri_obj.overall_consistency,
        sub_module=session["sub_module"],
        framing_text=session.get("initial_framing") or "",
        tenant_id=account_id,
        user_id=account_id,
    )
    surfaced = (session.get("layer_2") or {}).get("detected_tensions") or []
    rendered = render_synthesis(
        sub_module=session["sub_module"],
        scenarios=[s.model_dump() for s in pw.scenarios],
        sensitivity_drivers=[d.model_dump() for d in pw.sensitivity_drivers],
        surfaced_tensions=surfaced,
        # Phase D fix bundle 2026-05-16: carry_forward_caveats omitted.
        # The renderer ignores them; passing nothing makes intent explicit.
    )
    await _coll().update_one(
        {"session_id": session_id},
        {"$set": {
            "layer_3": {
                "scenarios": [s.model_dump() for s in pw.scenarios],
                "sensitivity_drivers": [d.model_dump() for d in pw.sensitivity_drivers],
                "surfaced_tensions": surfaced,
                "evidence_trace": [],
                "primary_diagnosis_prose": rendered,
                "refusal_flag": False,
                "rendered_synthesis": rendered,
            },
            "layer_4": {"answers": []},
            "layer_state": "layer_4",
            "updated_at": _utc_now(),
        }},
    )
    await _push_audit(session_id, list(pw.audit_ids), list(pw.orchestration_entries))


@router.post("/sessions/{session_id}/refuse")
async def refuse_session(
    session_id: str,
    body: RefuseIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Operator-driven refusal path. Sets status=refused without
    running the weighting engine."""
    account = ctx["account"]
    context_id = ctx["context"]["id"]
    session = await _get_session(context_id, session_id, account["id"])
    if session["status"] in ("refused", "completed", "abandoned"):
        raise HTTPException(status_code=409, detail=f"Session already {session['status']}.")
    candidates = (session.get("layer_1") or {}).get("candidate_set") or []
    prose = render_refusal(
        sub_module=session["sub_module"],
        reason=RefusalReason.INSUFFICIENT_EVIDENCE,
        candidates_to_surface=candidates,
    )
    await _coll().update_one(
        {"session_id": session_id},
        {"$set": {
            "status": "refused",
            "layer_state": "refused",
            "completed_at": _utc_now(),
            "updated_at": _utc_now(),
            "layer_3": {
                "scenarios": [],
                "sensitivity_drivers": [],
                "surfaced_tensions": [],
                "evidence_trace": [],
                "primary_diagnosis_prose": "",
                "refusal_flag": True,
                "refusal_reason": "operator_refusal",
                "operator_reason": body.operator_reason,
                "refusal_rendering": prose,
                "rendered_synthesis": None,
            },
        }},
    )
    refreshed = await _get_session(context_id, session_id, account["id"])
    return _serialise(refreshed)


# ─────────────────────────────────────────────────────────────────────
# Audit panel — timeline view (Bank-QA demo headline).
# ─────────────────────────────────────────────────────────────────────
from routers.chat_audit_panel import _friendly_purpose, _friendly_model_name  # noqa: E402


@router.get("/sessions/{session_id}/audit-panel/timeline")
async def audit_panel_timeline(
    session_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Compose a per-session privacy-provenance timeline.

    Reads the session's `synisense_audit_ids` array, fetches each
    `synisense_audit_log` row, and groups by purpose (layer label).
    Returns ONE step per audit row plus an aggregate footer.
    """
    account = ctx["account"]
    context_id = ctx["context"]["id"]
    session = await _get_session(context_id, session_id, account["id"])
    audit_ids: List[str] = session.get("synisense_audit_ids") or []
    if not audit_ids:
        return {
            "session_id": session_id,
            "steps": [],
            "aggregate": {
                "llm_calls": 0,
                "average_exposure_reduction": None,
                "average_dilution": None,
                "headline_prose": "No LLM calls have been routed through Synisense for this session yet.",
            },
        }

    rows = await db.synisense_audit_log.find(
        {"audit_id": {"$in": audit_ids}, "tenant_id": account["id"]},
        {"_id": 0},
    ).to_list(length=len(audit_ids) + 5)
    by_id = {r["audit_id"]: r for r in rows}

    # Preserve the order audit_ids were appended (chronological).
    steps: List[Dict[str, Any]] = []
    for idx, aid in enumerate(audit_ids):
        r = by_id.get(aid)
        if not r:
            continue
        steps.append({
            "step_index": idx + 1,
            "audit_id": aid,
            "purpose_raw": r.get("purpose"),
            "purpose_label": _friendly_purpose(r.get("purpose") or ""),
            "llm_provider": r.get("llm_provider"),
            "llm_model": _friendly_model_name(r.get("llm_model") or ""),
            "exposure_reduction": r.get("exposure_reduction_score"),
            "dilution": r.get("dilution_score"),
        })

    er_vals = [r.get("exposure_reduction_score") for r in rows if isinstance(r.get("exposure_reduction_score"), (int, float))]
    dl_vals = [r.get("dilution_score") for r in rows if isinstance(r.get("dilution_score"), (int, float))]
    er_avg = round(sum(er_vals) / len(er_vals), 1) if er_vals else None
    dl_avg = round(sum(dl_vals) / len(dl_vals), 1) if dl_vals else None

    headline = (
        f"Across this session: {len(rows)} governed LLM "
        + ("call" if len(rows) == 1 else "calls")
    )
    if er_avg is not None:
        headline += f", average exposure reduction {er_avg}%"
    if dl_avg is not None:
        headline += f", average dilution {dl_avg}%"
    headline += "."

    return {
        "session_id": session_id,
        "steps": steps,
        "aggregate": {
            "llm_calls": len(rows),
            "average_exposure_reduction": er_avg,
            "average_dilution": dl_avg,
            "headline_prose": headline,
        },
    }
