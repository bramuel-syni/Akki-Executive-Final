"""
routers/compilations.py — Patch 2B.2 Compilation Wizard backend.

Endpoints (all under /api/contexts/{cid}/work-studio/compilations):
  • POST   — create a compilation from the wizard Step 4 confirm.
  • GET    — list compilations for the active context.
  • GET /{id} — detail.

Collection: `compilations`
  {
    id, context_id, title, artefact_type, template_key,
    source_ids[], contributor_ids[], cadence_kind, cadence_payload,
    formats[], status, created_at, created_by, last_compiled_at?,
    agent_cycle_log: [],
  }

Indexes: (context_id, status, created_at DESC), (context_id, artefact_type)
— installed on startup in server.py.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from core import db, iso as _iso, now as _now, require_context_membership


router = APIRouter(prefix="/api")


# Constrain the wizard inputs to the locked product decisions.
_ARTEFACT_TYPES = ("board_pack", "minutes", "committee_pack", "deck", "report", "briefing")
_CADENCE_KINDS = ("one_off", "recurring", "scheduled")
_RECURRING_INTERVALS = ("weekly", "fortnightly", "monthly", "quarterly")
_FORMATS = ("docx", "pptx", "pdf")


class CadencePayload(BaseModel):
    """Free-form bag — the shape varies by `kind`:
    • one_off    — payload is empty.
    • recurring  — {"interval": "weekly|fortnightly|monthly|quarterly"}
    • scheduled  — {"scheduled_at": "<ISO date>"}
    """
    interval: Optional[str] = None
    scheduled_at: Optional[str] = None


class CompilationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    artefact_type: str
    template_key: str = Field(default="standard", min_length=1, max_length=80)
    source_ids: List[str] = Field(default_factory=list)
    contributor_ids: List[str] = Field(default_factory=list)
    cadence_kind: str
    cadence_payload: CadencePayload = Field(default_factory=CadencePayload)
    formats: List[str] = Field(default_factory=list)

    @field_validator("artefact_type")
    @classmethod
    def _v_artefact(cls, v):
        if v not in _ARTEFACT_TYPES:
            raise ValueError(f"artefact_type must be one of {_ARTEFACT_TYPES}")
        return v

    @field_validator("cadence_kind")
    @classmethod
    def _v_cadence(cls, v):
        if v not in _CADENCE_KINDS:
            raise ValueError(f"cadence_kind must be one of {_CADENCE_KINDS}")
        return v

    @field_validator("formats")
    @classmethod
    def _v_formats(cls, v):
        # Patch 9+ correction — `formats` is OPTIONAL (default `[]`). When
        # present, every entry must be one of docx/pptx/pdf. An empty
        # list is valid — the wizard still produces a record; format
        # selection can land later via update.
        lower = [f.lower() for f in (v or [])]
        for f in lower:
            if f not in _FORMATS:
                raise ValueError(f"unknown format {f!r}; allowed: {_FORMATS}")
        return lower


def _sanitize(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Strip Mongo internals; rec must already exclude `_id`."""
    rec = dict(rec)
    rec.pop("_id", None)
    return rec


@router.post("/contexts/{context_id}/work-studio/compilations")
async def create_compilation(
    context_id: str,
    body: CompilationCreate,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    now = _now()
    rec: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "context_id": context_id,
        "title": body.title.strip(),
        "artefact_type": body.artefact_type,
        "template_key": body.template_key,
        "source_ids": list(body.source_ids),
        "contributor_ids": list(body.contributor_ids),
        "cadence_kind": body.cadence_kind,
        "cadence_payload": body.cadence_payload.model_dump(exclude_none=True),
        "formats": body.formats,
        "status": "queued",
        "created_at": _iso(now),
        "created_by": ctx["account"]["id"],
        "agent_cycle_log": [
            {
                "ts": _iso(now),
                "actor_id": ctx["account"]["id"],
                "kind": "created",
                "note": "Wizard confirm — commissioned to Agent Cycle.",
            },
        ],
    }
    await db.compilations.insert_one(rec.copy())
    return _sanitize(rec)


@router.get("/contexts/{context_id}/work-studio/compilations")
async def list_compilations(
    context_id: str,
    status: Optional[str] = None,
    artefact_type: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    q: Dict[str, Any] = {"context_id": context_id}
    if status:
        q["status"] = status
    if artefact_type:
        if artefact_type not in _ARTEFACT_TYPES:
            raise HTTPException(status_code=400, detail="Unknown artefact_type.")
        q["artefact_type"] = artefact_type
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 50)))
    total = await db.compilations.count_documents(q)
    cursor = (
        db.compilations
        .find(q, {"_id": 0})
        .sort("created_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [_sanitize(r) async for r in cursor]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/contexts/{context_id}/work-studio/compilations/{compilation_id}")
async def get_compilation(
    context_id: str,
    compilation_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    rec = await db.compilations.find_one(
        {"id": compilation_id, "context_id": context_id},
        {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Compilation not found.")
    return _sanitize(rec)


# ─────────────────────────────────────────────────────────────────────
# Track A Phase 5 (2026-06-04) — /start endpoint
#
# Bridges the wizard's intent-log row (this collection) to the real
# executor at `routers.work_studio_export._run_export`. Previously the
# wizard POSTed `/compilations`, saw a 200, closed, and nothing else
# ever happened — the `status="queued"` row sat untouched forever
# because there is no worker reading this collection. Phase 5 wires
# the wizard's "Commission Agent Cycle" submit through to the real
# `_run_export` path which already materialises a `work_studio_exports`
# row, runs the LLM, renders the file, and flips `lifecycle_state` to
# `in_review` on completion.
#
# Idempotency (Tightening 3): if a prior `/start` call already minted
# an `export_id` for this compilation_id, the second call returns the
# existing one without spawning a duplicate `_run_export`. This is
# essential because the wizard's "Commission" button is a common
# double-click target.
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/work-studio/compilations/{compilation_id}/start")
async def start_compilation(
    context_id: str,
    compilation_id: str,
    background: __import__("fastapi").BackgroundTasks,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    rec = await db.compilations.find_one(
        {"id": compilation_id, "context_id": context_id},
        {"_id": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Compilation not found.")

    # Tightening 3 — idempotency on double-clicks. If we already minted
    # an export_id for this compilation, return it as-is.
    existing_export_id = rec.get("export_id")
    if existing_export_id:
        existing_row = await db.work_studio_exports.find_one(
            {"id": existing_export_id, "context_id": context_id},
            {"_id": 0},
        )
        if existing_row:
            return {
                "export_id":      existing_export_id,
                "status":         existing_row.get("status", "running"),
                "compilation_id": compilation_id,
                "idempotent":     True,
            }

    # Lazy-import to avoid a circular reference (work_studio_export →
    # compilations via _run_export → work_studio_overlay → compilations
    # for the `intent_log` listing — keeping the import here breaks the
    # cycle).
    from routers.work_studio_export import _run_export, ExportRequestIn
    import uuid as _uuid
    import logging as _logging
    logger = _logging.getLogger("akki.compilations")

    export_id = str(_uuid.uuid4())
    artefact_type = rec.get("artefact_type", "report")
    formats = rec.get("formats") or []
    output_format = formats[0] if formats else "docx"
    title = rec.get("title", "")
    source_ids = rec.get("source_ids") or []
    contributor_ids = rec.get("contributor_ids") or []
    created_at = _iso(_now())

    # Seed the work_studio_exports row directly — same shape as the
    # `/export/{kind}` insert at routers/work_studio_export.py:1433
    # but with Phase 5 additive fields populated from the compilation
    # record (source_count = len(source_ids), contributor_count =
    # len(contributor_ids) ∪ self).
    row = {
        "id": export_id,
        "context_id": context_id,
        "account_id": ctx["account"]["id"],
        "kind": artefact_type,
        "output_format": output_format,
        "status": "running",
        "description_chars": len(title),
        "objective_chars": 0,
        "scope_chars": 0,
        "created_at": created_at,
        "completed_at": None,
        "file_name": None,
        "file_path": None,
        "sha256": None,
        "sensitivity_band": None,
        "error": None,
        "refusal_text": None,
        "chat_audit_id": None,
        "compilation_id": compilation_id,
        # Phase 5 additive fields.
        "source_count": len(source_ids),
        "contributor_count": max(1, len(set(contributor_ids) | {ctx["account"]["id"]})),
        "akki_generated": True,
    }
    await db.work_studio_exports.insert_one(row)
    await db.compilations.update_one(
        {"id": compilation_id},
        {"$set": {
            "export_id": export_id,
            "status": "running",
            "last_compiled_at": created_at,
        }},
    )

    # Build a minimal ExportRequestIn body. The wizard's title flows
    # to `description`; objective/scope default to a short placeholder
    # to satisfy the existing model's min_length=1 invariants.
    body = ExportRequestIn(
        description=title or f"{artefact_type} compile",
        objective=f"Compile {artefact_type} from the bound sources.",
        scope=f"Scope: {artefact_type} for this cycle.",
        output_format=output_format,
    )

    async def _runner():
        try:
            await _run_export(
                export_id=export_id, account_id=ctx["account"]["id"],
                context_id=context_id, kind=artefact_type,
                output_format=output_format, body=body,
            )
        except Exception as exc:  # noqa: BLE001
            # Swallow contract: a crashed compile must not 500 the
            # /start response that already returned 200. We log with
            # exc_info=True and persist the failure on the
            # work_studio_exports row so the FE polling sees `status=
            # "failed"` (Phase 4 iter-2 discipline).
            logger.warning(
                "[compilation.start] _run_export crashed for compile=%s export=%s: %s",
                compilation_id, export_id, exc, exc_info=True,
            )
            err_class = type(exc).__name__
            err_msg = str(exc).replace("\n", " ").strip()[:300] or "(no message)"
            await db.work_studio_exports.update_one(
                {"id": export_id},
                {"$set": {
                    "status": "failed",
                    "error": f"{err_class}: {err_msg}",
                    "completed_at": _iso(_now()),
                }},
            )

    background.add_task(_runner)

    return {
        "export_id":      export_id,
        "status":         "running",
        "compilation_id": compilation_id,
        "idempotent":     False,
    }


# ─────────────────────────────────────────────────────────────────────
# (legacy — kept above)
# ─────────────────────────────────────────────────────────────────────
