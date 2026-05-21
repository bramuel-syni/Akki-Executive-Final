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

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core import db, require_context_membership

from documents_service import (
    ACCEPT_EXT, MAX_BYTES, extract_text, make_preview, save_to_storage,
)
from services import clamav_service
from services.clamav_service import ClamAVUnreachable
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
from services.solva.guardrails import (
    run_guardrail_ladder,
    GuardrailOutcome,
)
# QA-2026-05-20 SV-03 (auto-title) — single Shield-gateway LLM call
# after the first substantive exchange. CI guard
# `test_no_direct_llm_calls_outside_shield` stays green because every
# auto-title invocation routes through `shield_invoke`.
from services.synisense.shield.client import invoke as shield_invoke


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
class SeedPayload(BaseModel):
    """Phase E.5 — handoff payload from Cycle / Work Studio / Document Journal.

    Pre-populates the framing text, attaches referenced docs/artefacts as
    Layer 0 evidence anchors (real grounding, not placeholders), and
    optionally suggests a sub_module. Source provenance lives on the
    session as `source_handoff` for traceability.
    """
    model_config = ConfigDict(extra="ignore")
    source: str = Field(min_length=1, max_length=40)
    source_id: str = Field(min_length=1, max_length=120)
    preview_text: str = Field(default="", max_length=4000)
    attached_references: List[str] = Field(default_factory=list, max_length=20)
    sub_module_hint: Optional[str] = Field(default=None, max_length=40)

    @field_validator("source")
    @classmethod
    def _check_source(cls, v: str) -> str:
        allowed = {"cycle", "work_studio_artefact", "document_journal"}
        if v not in allowed:
            raise ValueError(f"source must be one of {sorted(allowed)}")
        return v

    @field_validator("sub_module_hint")
    @classmethod
    def _check_sm_hint(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in SUB_MODULES:
            raise ValueError(f"sub_module_hint must be one of {SUB_MODULES}")
        return v


class CreateSessionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sub_module: str = Field(min_length=4, max_length=40)
    seed_payload: Optional[SeedPayload] = None

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
async def _guardrail_check_and_persist(
    *,
    session_id: str,
    context_id: str,
    account_id: str,
    input_text: str,
) -> Optional[Dict[str, Any]]:
    """Run the Phase E guardrail ladder. If outcome is BLOCKED_HARD,
    persist the block on the session (status=blocked_hard, layer_3.
    rendered_synthesis=None, refusal_rendering carries the templated
    response). If BLOCKED_SOFT, persist a soft annotation on the session
    BUT allow the caller to continue. Returns a response payload to
    send back to the user OR None when the call should proceed.

    Audit IDs from the classifiers are appended to the session.
    """
    decision = await run_guardrail_ladder(
        input_text=input_text or "",
        tenant_id=account_id,
        user_id=account_id,
    )
    if decision.audit_ids or decision.orchestration_entries:
        await _push_audit(session_id, decision.audit_ids, decision.orchestration_entries)

    if decision.outcome == GuardrailOutcome.OK:
        return None

    if decision.outcome == GuardrailOutcome.BLOCKED_HARD:
        await _coll().update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "blocked_hard",
                "layer_state": "refused",
                "guardrail_outcome": decision.outcome.value,
                "guardrail_primary_classifier": decision.primary_classifier,
                "guardrail_scores": [s.model_dump() for s in decision.scores],
                "completed_at": _utc_now(),
                "updated_at": _utc_now(),
                "layer_3": {
                    "scenarios": [],
                    "sensitivity_drivers": [],
                    "surfaced_tensions": [],
                    "evidence_trace": [],
                    "primary_diagnosis_prose": "",
                    "refusal_flag": True,
                    "refusal_reason": f"guardrail.{decision.primary_classifier}",
                    "refusal_rendering": decision.rendering,
                    "rendered_synthesis": None,
                },
            }},
        )
        refreshed = await _get_session(context_id, session_id, account_id)
        return _serialise(refreshed)

    # SOFT — annotate and proceed.
    await _coll().update_one(
        {"session_id": session_id},
        {"$set": {
            "guardrail_outcome": decision.outcome.value,
            "guardrail_primary_classifier": decision.primary_classifier,
            "guardrail_scores": [s.model_dump() for s in decision.scores],
            "updated_at": _utc_now(),
        }, "$push": {
            "soft_guardrail_notices": {
                "classifier": decision.primary_classifier,
                "rendering": decision.rendering,
                "at": _utc_now().isoformat(),
            },
        }},
    )
    return None


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
# QA-2026-05-20 SV-03 — auto-title generation.
#
# Spec (verbatim from Solva QA brief 20 May 2026):
#   "The title is generated after the first substantive exchange…
#    a key phrase extracted from the session content — for example,
#    the main question or problem being worked through."
#
# Locked decision: single Shield gateway LLM call per session
# (`solva.session.auto_title`). NO heuristic fallback path — if Shield
# fails, the row keeps `title=""` and the listing renders the framing
# excerpt instead. This keeps the CI guard
# `test_no_direct_llm_calls_outside_shield` green and avoids a second
# code path that would inevitably drift from the model's outputs.
#
# Hook point: `submit_framing` after Layer 0 (FAR + situation
# classification) completes. That's the first AI engagement with the
# user's input — a "substantive exchange" by the brief's definition.
# ─────────────────────────────────────────────────────────────────────
_AUTO_TITLE_MAX_CHARS = 80
_AUTO_TITLE_PROMPT_TEMPLATE = (
    "Generate a concise, board-appropriate session title (six to ten "
    "words, no quotes, no trailing punctuation) for a Solva strategic "
    "reasoning session whose framing is below. The title should "
    "surface the core decision, risk, or question — not paraphrase "
    "every detail. Reply with ONLY the title on a single line.\n\n"
    "Framing:\n{framing}"
)


async def _generate_session_auto_title(
    *,
    framing_text: str,
    tenant_id: str,
    user_id: str,
) -> Optional[str]:
    """Returns a Shield-generated title, or None on failure.

    Callers MUST treat None as "leave the row's title field empty" —
    no heuristic fallback. Logging is best-effort; we never raise.
    """
    framing = (framing_text or "").strip()
    if not framing:
        return None
    prompt = _AUTO_TITLE_PROMPT_TEMPLATE.format(framing=framing[:2000])
    try:
        result = await shield_invoke(
            purpose="solva.session.auto_title",
            content=prompt,
            tenant_id=tenant_id,
            consumer_id="solva.phase_d",
            user_id=user_id,
            model_preference="generative",
        )
    except Exception as exc:  # noqa: BLE001 — never blow up the answer flow
        logger.warning(
            "auto-title shield call failed: %s: %s",
            type(exc).__name__, str(exc)[:300],
        )
        return None
    raw = (result.get("response") or "").strip()
    if not raw:
        return None
    # Pick first non-empty line, strip surrounding quotes/asterisks.
    line = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
    line = line.strip("\"'`*“”‘’ ")
    # Drop any trailing punctuation the model might still emit.
    while line and line[-1] in ".!?:;,":
        line = line[:-1]
    if not line:
        return None
    return line[:_AUTO_TITLE_MAX_CHARS]


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

    # Phase E.5 — apply seed_payload: choose effective sub_module via
    # `sub_module_hint` (the explicit `body.sub_module` always wins
    # when both are set) and resolve attached references against the
    # caller's context so we never bind to data the user can't see.
    seed = body.seed_payload
    effective_sub_module = body.sub_module
    source_handoff: Optional[Dict[str, Any]] = None
    initial_framing: Optional[str] = None
    attached_resolved: List[Dict[str, Any]] = []

    if seed is not None:
        if seed.sub_module_hint and body.sub_module == "seek_clarity":
            # `seek_clarity` is the wizard default — accept the hint
            # when the caller didn't explicitly choose a different
            # sub_module. (Validator already locked the hint to a
            # known sub_module.)
            effective_sub_module = seed.sub_module_hint
        source_handoff = {
            "source":    seed.source,
            "source_id": seed.source_id,
            "source_url": _build_source_url(seed.source, seed.source_id, context_id),
        }
        if seed.preview_text:
            initial_framing = seed.preview_text[:4000]
        attached_resolved = await _resolve_seed_references(
            references=list(seed.attached_references or []),
            context_id=context_id,
            account_id=account["id"],
        )

    row = {
        "session_id": sid,
        "user_id": account["id"],
        "account_id": account["id"],
        "context_id": context_id,
        "sub_module": effective_sub_module,
        "status": "active",
        "layer_state": "framing" if initial_framing else "entry",
        "initial_framing": initial_framing,
        "layer_0": None,
        "layer_1": None,
        "layer_2": None,
        "layer_3": None,
        "layer_4": None,
        "synisense_audit_ids": [],
        "orchestration_audit_log": [],
        # Phase E.5 — seed-handoff provenance + Layer 0 evidence anchors.
        "source_handoff": source_handoff,
        "seed_attached_references": attached_resolved,
        "schema_version": 4 if seed is not None else 3,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    await _coll().insert_one(dict(row))
    row.pop("_id", None)
    return _serialise(row)


def _build_source_url(source: str, source_id: str, context_id: str) -> str:
    """Return the deep-link URL for the seed source — used by the
    Trust panel to back-link from Solva to its origin surface."""
    if source == "cycle":
        return f"/app/cycle/{source_id}"
    if source == "work_studio_artefact":
        return f"/app/work-studio/artefact/{source_id}"
    if source == "document_journal":
        return f"/app/workspace?doc={source_id}"
    return ""


async def _resolve_seed_references(
    *,
    references: List[str],
    context_id: str,
    account_id: str,
) -> List[Dict[str, Any]]:
    """Resolve each reference against the caller's context. References
    that don't exist OR are scoped to a different context are silently
    dropped (we never error on a stale reference, but we never bind
    Solva to data the user can't see).

    Phase F.1 bug-fix (2026-05-16):
      * The `documents` collection has no `account_id` field — strip
        it from the query. `context_id` already scopes correctly via
        the membership chain.
      * Projection switched to the real schema fields (`name`,
        `extracted_text`, `preview`, `original_filename`).
      * Each resolved anchor now carries an `excerpt` (extracted_text
        first 8000 chars, preview as fallback) so FAR sees real
        document body in Layer 0 instead of an opaque ID.

    `account_id` is still passed in (back-compat with callers) but
    only used for cycles + artefacts where tenant isolation is
    needed. Documents are context-scoped, not tenant-scoped.
    """
    _ = account_id  # see docstring — kept for caller back-compat
    resolved: List[Dict[str, Any]] = []
    for ref in references[:20]:
        # Try in order: documents → cycles → work_studio_artefacts.
        doc = await db.documents.find_one(
            {"id": ref, "context_id": context_id},
            {"_id": 0, "id": 1, "name": 1, "original_filename": 1,
             "extracted_text": 1, "preview": 1, "status": 1},
        )
        if doc:
            label = (
                doc.get("name")
                or doc.get("original_filename")
                or doc["id"]
            )
            excerpt = (
                (doc.get("extracted_text") or "")[:8000]
                or doc.get("preview")
                or ""
            )
            resolved.append({
                "ref_type": "document",
                "ref_id": doc["id"],
                "label": label,
                "excerpt": excerpt,
                "status": doc.get("status"),
            })
            continue
        cyc = await db.cycles.find_one(
            {"id": ref, "context_id": context_id},
            {"_id": 0, "id": 1, "title": 1},
        )
        if cyc:
            resolved.append({
                "ref_type": "cycle",
                "ref_id": cyc["id"],
                "label": cyc.get("title") or cyc["id"],
                "excerpt": "",
                "status": None,
            })
            continue
        art = await db.work_studio_artefacts.find_one(
            {"id": ref, "context_id": context_id},
            {"_id": 0, "id": 1, "title": 1, "summary": 1},
        )
        if art:
            resolved.append({
                "ref_type": "work_studio_artefact",
                "ref_id": art["id"],
                "label": art.get("title") or art["id"],
                "excerpt": (art.get("summary") or "")[:8000],
                "status": None,
            })
            continue
        # Unknown / stale ref — silently drop; never error.
    return resolved


# ─────────────────────────────────────────────────────────────────────
# Phase F.1 — mid-session document attach.
#   Accepts EITHER multipart/form-data with a new file OR
#   application/json with {document_id} for an existing doc. Appends
#   the resolved anchor to `session.seed_attached_references` and
#   audit-logs the attach event.
# ─────────────────────────────────────────────────────────────────────
def _is_terminal(layer_state: str) -> bool:
    return layer_state in TERMINAL_STATES


async def _attach_anchor_to_session(
    *, session_id: str, anchor: Dict[str, Any], event: Dict[str, Any],
) -> Dict[str, Any]:
    """Append the resolved anchor to seed_attached_references and
    push an orchestration_audit_log entry. Returns the updated row."""
    await _coll().update_one(
        {"session_id": session_id},
        {
            "$push": {
                "seed_attached_references": anchor,
                "orchestration_audit_log": event,
            },
            "$set": {"updated_at": _utc_now()},
        },
    )
    return await _coll().find_one({"session_id": session_id}, {"_id": 0})


@router.post("/sessions/{session_id}/attach-document")
async def attach_document(
    session_id: str,
    request: Request,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Mid-session document anchor.

    Two modes, dispatched by Content-Type:
      - multipart/form-data with `file=...` → upload pipeline runs
        (ClamAV → extract_text → storage save → documents row insert)
        and the resulting doc is anchored.
      - application/json with `{"document_id": "..."}` → link an
        existing doc by id (context-scoped) and anchor it.
    """
    account = ctx["account"]
    context_id = ctx["context"]["id"]

    # Session resolution + state gate.
    session = await _get_session(context_id, session_id, account["id"])
    if _is_terminal(session.get("layer_state") or ""):
        raise HTTPException(
            status_code=409,
            detail="ConflictError: session is closed; new attachments are not accepted.",
        )

    content_type = (request.headers.get("content-type") or "").lower()
    is_multipart = content_type.startswith("multipart/form-data")
    is_json = content_type.startswith("application/json")

    doc_row: Optional[Dict[str, Any]] = None
    mode: str

    if is_multipart:
        mode = "upload"
        form = await request.form()
        file = form.get("file")
        if file is None or not getattr(file, "filename", None):
            raise HTTPException(
                status_code=400,
                detail="ValidationError: multipart payload missing `file`.",
            )
        filename = file.filename or "unnamed"
        ext = Path(filename).suffix.lower()
        if ext not in ACCEPT_EXT:
            raise HTTPException(
                status_code=415,
                detail=(
                    f"UnsupportedMediaType: {ext}. "
                    f"Accepted: {', '.join(sorted(ACCEPT_EXT))}"
                ),
            )
        data = await file.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"PayloadTooLarge: max {MAX_BYTES // 1024 // 1024}MB.",
            )

        # Virus scan (Phase 10 path).
        try:
            scan_result = await clamav_service.scan(data, filename, file_id=session_id, user_id=ctx["account"]["id"])
        except ClamAVUnreachable as e:
            raise HTTPException(
                status_code=503,
                detail=f"ClamAVUnreachable: {str(e)[:200]}",
            )
        if not scan_result.clean:
            raise HTTPException(
                status_code=422,
                detail=f"VirusBlocked: signature={scan_result.signature}",
            )

        # Extract + store.
        doc_id = str(uuid.uuid4())
        storage_key = save_to_storage(context_id, doc_id, filename, data)
        text, err = extract_text(data, filename, file.content_type or "")
        preview = make_preview(text)
        created_at = _utc_now().isoformat()
        doc_row = {
            "id": doc_id,
            "context_id": context_id,
            "name": Path(filename).stem.strip() or "Untitled",
            "description": "",
            "original_filename": filename,
            "mime_type": file.content_type or "application/octet-stream",
            "size_bytes": len(data),
            "storage_key": storage_key,
            "status": "extracted" if text and not err else ("failed" if err else "empty"),
            "extracted_text": text,
            "extracted_chars": len(text),
            "preview": preview,
            "data_trust": "mixed",
            "uploaded_by": account["id"],
            "uploaded_by_email": account.get("email", ""),
            "doc_type": "solva_attachment",
            "source_channel": "solva_attach",
            "error": err,
            "created_at": created_at,
            "updated_at": created_at,
        }
        await db.documents.insert_one(dict(doc_row))
        doc_row.pop("_id", None)

    elif is_json:
        mode = "link"
        try:
            body = await request.json()
        except Exception as e:  # noqa: BLE001
            raise HTTPException(
                status_code=400,
                detail=f"ValidationError: malformed JSON body — {type(e).__name__}",
            )
        document_id = (body or {}).get("document_id")
        if not document_id:
            raise HTTPException(
                status_code=400,
                detail="ValidationError: provide `document_id` in the JSON body.",
            )
        existing = await db.documents.find_one(
            {"id": document_id, "context_id": context_id},
            {"_id": 0, "id": 1, "name": 1, "original_filename": 1,
             "extracted_text": 1, "preview": 1, "status": 1},
        )
        if not existing:
            raise HTTPException(
                status_code=404,
                detail="NotFound: document_id not present in this context.",
            )
        doc_row = existing
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "ValidationError: provide either multipart/form-data with `file`, "
                "or application/json with `document_id`."
            ),
        )

    anchor = {
        "ref_type": "document",
        "ref_id": doc_row["id"],
        "label": (
            doc_row.get("name")
            or doc_row.get("original_filename")
            or doc_row["id"]
        ),
        "excerpt": (
            (doc_row.get("extracted_text") or "")[:8000]
            or doc_row.get("preview")
            or ""
        ),
        "status": doc_row.get("status"),
        "attached_mid_session": True,
        "attached_at": _utc_now().isoformat(),
    }
    event = {
        "event": "attach_document",
        "mode": mode,  # upload | link
        "document_id": doc_row["id"],
        "layer_state": session.get("layer_state"),
        "at": _utc_now().isoformat(),
    }
    updated = await _attach_anchor_to_session(
        session_id=session_id, anchor=anchor, event=event,
    )
    return {
        "ok": True,
        "mode": mode,
        "anchor": anchor,
        "session": _serialise(updated),
    }


@router.get("/sessions/{session_id}/attachments")
async def list_session_attachments(
    session_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """List anchors currently bound to a session. Lightweight view —
    excludes the full `excerpt` field so the UI list stays small."""
    account = ctx["account"]
    context_id = ctx["context"]["id"]
    session = await _get_session(context_id, session_id, account["id"])
    anchors = list(session.get("seed_attached_references") or [])
    return {
        "session_id": session_id,
        "anchors": [
            {
                "ref_type": a.get("ref_type"),
                "ref_id": a.get("ref_id"),
                "label": a.get("label"),
                "status": a.get("status"),
                "excerpt_chars": len((a.get("excerpt") or "")),
                "attached_mid_session": a.get("attached_mid_session", False),
                "attached_at": a.get("attached_at"),
            }
            for a in anchors
        ],
        "count": len(anchors),
    }


_ = (hashlib, json)  # silence imports kept for future audit fingerprints


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


# QA-2026-05-20 SV-03 — inline title edit on the session list.
# Body shape kept deliberately narrow so future fields don't require
# breaking the wire contract.
class _UpdateSessionTitleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=_AUTO_TITLE_MAX_CHARS)


@router.patch("/sessions/{session_id}/title")
async def update_session_title(
    session_id: str,
    body: _UpdateSessionTitleIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Save a user-edited session title.

    Strict ownership: the underlying `_get_session` already enforces
    `account_id == ctx.account.id` AND `context_id == ctx.context.id`
    so cross-tenant overwrites are impossible. Stores `title_source =
    "user"` so a future re-run of `submit_framing` won't clobber the
    user's choice (see the idempotency guard there).
    """
    account = ctx["account"]
    context_id = ctx["context"]["id"]
    await _get_session(context_id, session_id, account["id"])
    new_title = body.title.strip()
    if not new_title:
        raise HTTPException(status_code=422, detail="Title cannot be empty after trimming.")
    await _coll().update_one(
        {"session_id": session_id, "account_id": account["id"],
         "context_id": context_id},
        {"$set": {"title": new_title, "title_source": "user",
                  "title_updated_at": _utc_now()}},
    )
    return {"session_id": session_id, "title": new_title, "title_source": "user"}


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

    # Phase E Sub-task B (2026-05-16) — guardrail ladder runs BEFORE
    # the FAR. Hard blocks return immediately; soft annotations are
    # logged but the engine continues.
    blocked = await _guardrail_check_and_persist(
        session_id=session_id,
        context_id=context_id,
        account_id=account["id"],
        input_text=body.framing_text,
    )
    if blocked is not None:
        return blocked

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

    # QA-2026-05-20 SV-03 — auto-title generation after the first
    # substantive exchange (framing + Layer 0 == one user→AI cycle).
    # Idempotent: only fires when the row doesn't already have a
    # non-empty title (re-running submit_framing won't clobber a
    # user-edited title).
    existing_title = (session.get("title") or "").strip()
    if not existing_title:
        new_title = await _generate_session_auto_title(
            framing_text=body.framing_text,
            tenant_id=account["id"],
            user_id=account["id"],
        )
        if new_title:
            await _coll().update_one(
                {"session_id": session_id},
                {"$set": {"title": new_title, "title_source": "auto",
                          "title_updated_at": _utc_now()}},
            )

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

    # Phase E Sub-task B (2026-05-16) — guardrail ladder runs BEFORE
    # the answer is recorded. Hard block returns immediately.
    blocked = await _guardrail_check_and_persist(
        session_id=session_id,
        context_id=context_id,
        account_id=account["id"],
        input_text=body.answer_text,
    )
    if blocked is not None:
        return blocked

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
            # Phase F.1 cleanup (2026-05-18) — feed `seed_attached_references`
            # excerpts into triangulation + tension detection so attached
            # documents actually reach the reasoning engines. Cap each
            # chunk at 1800 chars (Shield's per-call prompt budget); keep
            # the first 6 anchors so a busy session doesn't exceed the
            # prompt window.
            anchored_evidence_chunks = [
                (anchor.get("excerpt") or "")[:1800]
                for anchor in (session.get("seed_attached_references") or [])
                if (anchor.get("excerpt") or "").strip()
            ][:6]
            tri = await run_triangulation(
                narrative_text=narrative,
                evidence_chunks=anchored_evidence_chunks,
                prior_signals=[],
                tenant_id=account["id"],
                user_id=account["id"],
            )
            ten = await detect_tensions(
                narrative_text=narrative,
                evidence_chunks=anchored_evidence_chunks,
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

            # Phase E Sub-task C (2026-05-16) — tension auto-activation.
            from services.solva.reasoning.tension_detection import auto_activate as _auto_act
            ten_decision = _auto_act(
                candidates=refined,
                triangulation_result={
                    "overall_consistency": tri.overall_consistency,
                    "divergences": [d.model_dump() for d in tri.divergences],
                },
                detected_tensions=[t.model_dump() for t in ten.tensions],
                sub_module=session["sub_module"],
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
                    "layer_2.tension_activation": ten_decision,
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
    tension_activation = (session.get("layer_2") or {}).get("tension_activation") or None
    rendered = render_synthesis(
        sub_module=session["sub_module"],
        scenarios=[s.model_dump() for s in pw.scenarios],
        sensitivity_drivers=[d.model_dump() for d in pw.sensitivity_drivers],
        surfaced_tensions=surfaced,
        tension_activation=tension_activation,
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
