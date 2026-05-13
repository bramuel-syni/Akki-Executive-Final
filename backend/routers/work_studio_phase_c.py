"""
Phase C.1 — Work Studio export endpoints.

  POST /api/work_studio/exports
  GET  /api/work_studio/exports/{export_id}/download
  GET  /api/work_studio/picker

Note: this is the new C.1 endpoint group. The pre-existing Phase 13
work-studio export router (`/api/contexts/{cid}/work-studio/export/...`)
is unchanged and continues to serve the old block-composer pipeline.
"""
from __future__ import annotations
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Response
from pydantic import BaseModel, Field

from core import db, get_current_account
from work_studio import (
    PICKER,
    DEPTHS, FIDELITIES, FORMATS,
    FORMAT_DOCX, FORMAT_PPTX, FORMAT_PDF,
    build_brief_from_solva,
    render_docx, render_pptx, render_pdf,
    # Phase C.2 — persistence + revision_id resolution.
    ensure_brief_persisted, get_brief, get_revision, get_active_revision,
    dict_to_brief,
)

router = APIRouter(prefix="/api/work_studio")

CONTENT_TYPES = {
    FORMAT_DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FORMAT_PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    FORMAT_PDF:  "application/pdf",
}
EXTENSIONS = {FORMAT_DOCX: "docx", FORMAT_PPTX: "pptx", FORMAT_PDF: "pdf"}


class ExportRequest(BaseModel):
    source_id: str
    source_type: str = Field(
        ...,
        pattern="^(solva_session|cycle_compilation|chat_artefact|work_studio_brief)$",
    )
    format: str = Field(..., pattern="^(docx|pptx|pdf)$")
    depth: str = Field(..., pattern="^(executive_brief|board_summary|deep_dive)$")
    fidelity: str = Field(..., pattern="^(low|high)$")
    company_label: str = Field("Akki", max_length=80)
    document_type: str = Field("Board Briefing", max_length=80)
    programme: Optional[str] = Field(None, max_length=80)
    # Phase C.2 — pin a specific revision for re-export. When omitted,
    # `work_studio_brief` source uses the active revision; the other
    # source_types build a fresh Brief and persist revision_0.
    revision_id: Optional[str] = Field(None, max_length=64)


@router.get("/picker")
async def get_picker():
    """Return the depth/fidelity/format options each with a one-line
    FT-toned insight string. The Work Studio UI renders this directly."""
    return PICKER


@router.post("/exports")
async def create_export(
    body: ExportRequest,
    account=Depends(get_current_account),
    x_active_context: Optional[str] = Header(None, alias="X-Active-Context"),
):
    # 1) Resolve the source -------------------------------------------------
    # Phase C.2 — when source_type=work_studio_brief the source_id IS a
    # brief_id. Resolve to the requested revision (or the active one).
    # The depth/fidelity carried on the request override the snapshot's
    # defaults so the same revision can be re-exported at multiple
    # depth/fidelity settings without forking a new revision.
    brief = None
    resolved_brief_id: Optional[str] = None
    resolved_revision_id: Optional[str] = None

    if body.source_type == "work_studio_brief":
        parent = await get_brief(db, body.source_id, account["id"])
        if not parent:
            raise HTTPException(status_code=404, detail="brief_not_found")
        rev_id = body.revision_id or parent["active_revision_id"]
        rev = await get_revision(
            db, brief_id=body.source_id, revision_id=rev_id,
            account_id=account["id"],
        )
        if not rev:
            raise HTTPException(status_code=404, detail="revision_not_found")
        snapshot = dict(rev.get("snapshot") or {})
        if not snapshot:
            raise HTTPException(
                status_code=409,
                detail={"code": "revision_empty",
                        "message": "Revision has no snapshot."},
            )
        # Allow per-export depth/fidelity override on the revision.
        snapshot["depth"] = body.depth
        snapshot["fidelity"] = body.fidelity
        # Cosmetic envelope overrides (cover labels) — do NOT mutate the
        # persisted revision; only the rendered binary picks them up.
        if body.company_label:
            snapshot["company_label"] = body.company_label
        if body.document_type:
            snapshot["document_type"] = body.document_type
        if body.programme is not None:
            snapshot["programme"] = body.programme
        brief = dict_to_brief(snapshot)
        resolved_brief_id = body.source_id
        resolved_revision_id = rev_id

    elif body.source_type == "cycle_compilation":
        # Phase D.1 — wired. The `source_id` for cycle_compilation is the
        # cycle's agenda_id. Look up the persisted brief; if not present,
        # tell the caller to compile first.
        from work_studio.persistence import compute_brief_id
        bid = compute_brief_id(
            account_id=account["id"],
            source_type="cycle_compilation",
            source_id=body.source_id,
        )
        parent = await get_brief(db, bid, account["id"])
        if not parent:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "cycle_not_compiled",
                    "message": ("This cycle has not been compiled yet. "
                                "Run POST /api/contexts/{cid}/cycle/draft-compilation "
                                "first; that produces the brief."),
                },
            )
        rev_id = body.revision_id or parent["active_revision_id"]
        rev = await get_revision(
            db, brief_id=bid, revision_id=rev_id, account_id=account["id"],
        )
        if not rev:
            raise HTTPException(status_code=404, detail="revision_not_found")
        snapshot = dict(rev.get("snapshot") or {})
        snapshot["depth"] = body.depth
        snapshot["fidelity"] = body.fidelity
        if body.company_label:
            snapshot["company_label"] = body.company_label
        if body.document_type:
            snapshot["document_type"] = body.document_type
        if body.programme is not None:
            snapshot["programme"] = body.programme
        brief = dict_to_brief(snapshot)
        resolved_brief_id = bid
        resolved_revision_id = rev_id
    elif body.source_type == "chat_artefact":
        chat = await db.chats.find_one({"id": body.source_id, "account_id": account["id"]})
        if not chat:
            raise HTTPException(status_code=404, detail="chat_not_found")
        msgs = await db.chat_messages.find({"chat_id": body.source_id})\
            .sort("created_at", 1).to_list(2000)
        # Reduce the chat down to a Solva-shaped envelope so the existing
        # builder works without a parallel code path.
        full = "\n\n".join((m.get("content") or "").strip()
                           for m in msgs if m.get("role") == "assistant")
        chat_title = (chat.get("title") or "").strip()
        synthetic = {
            "id": chat["id"],
            "submodule": "seek_clarity",
            "intent": chat_title or "Chat artefact",
            "synthesis": {
                "body": full,
                "claims": [], "recommendations": [],
                "validation": {"verdict": "informational",
                               "confidence": 0,
                               "validator_provider": "—",
                               "validator_model": "—"},
            },
        }
        brief = build_brief_from_solva(
            synthetic, company_label=body.company_label,
            document_type=body.document_type, programme=body.programme,
            depth=body.depth, fidelity=body.fidelity,
            # Chunk 6 (2026-05-13, WS-R19): chat title becomes the
            # brief title verbatim; no submodule prefix, 200-char cap.
            title_override=chat_title or None,
        )
    else:  # solva_session
        session = await db.solva_v2_sessions.find_one(
            {"id": body.source_id, "account_id": account["id"]})
        if not session:
            raise HTTPException(status_code=404, detail="solva_session_not_found")
        if not (session.get("synthesis") or {}).get("body"):
            raise HTTPException(
                status_code=409,
                detail={"code": "synthesis_not_ready",
                        "message": "This Solva session has not yet produced a synthesis. "
                                   "Run it through to the synthesis layer before exporting."},
            )
        brief = build_brief_from_solva(
            session, company_label=body.company_label,
            document_type=body.document_type, programme=body.programme,
            depth=body.depth, fidelity=body.fidelity,
        )

    # 1b) Phase C.2 — persist the brief on first export of any source
    # OTHER than work_studio_brief (where it's already persisted). The
    # brief_id is deterministic, so a second call is a no-op.
    if body.source_type != "work_studio_brief" and brief is not None:
        parent = await ensure_brief_persisted(
            db, brief=brief, account_id=account["id"],
            context_id=x_active_context,
            source_type=body.source_type, source_id=body.source_id,
        )
        resolved_brief_id = parent["id"]
        resolved_revision_id = parent["active_revision_id"]

    # 2) Render -------------------------------------------------------------
    if body.format == FORMAT_DOCX:
        binary = render_docx(brief)
    elif body.format == FORMAT_PPTX:
        binary = render_pptx(brief)
    else:  # FORMAT_PDF
        binary = render_pdf(brief)

    sha = hashlib.sha256(binary).hexdigest()
    export_id = str(uuid.uuid4())
    filename = (
        f"{body.company_label.replace(' ', '_')}_"
        f"{body.document_type.replace(' ', '_')}_"
        f"{body.depth}_{body.fidelity}.{EXTENSIONS[body.format]}"
    )

    # 3) Persist ------------------------------------------------------------
    await db.work_studio_phase_c_exports.insert_one({
        "id": export_id,
        "account_id": account["id"],
        "context_id": x_active_context,
        "source_id": body.source_id,
        "source_type": body.source_type,
        "format": body.format,
        "depth": body.depth,
        "fidelity": body.fidelity,
        "company_label": body.company_label,
        "document_type": body.document_type,
        "programme": body.programme,
        "brief_id": resolved_brief_id,
        "revision_id": resolved_revision_id,
        "filename": filename,
        "size_bytes": len(binary),
        "sha256": sha,
        "binary": binary,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "export_id": export_id,
        "download_url": f"/api/work_studio/exports/{export_id}/download",
        "format": body.format,
        "depth": body.depth,
        "fidelity": body.fidelity,
        "filename": filename,
        "size_bytes": len(binary),
        "sha256": sha,
        "brief_id": resolved_brief_id,
        "revision_id": resolved_revision_id,
    }


@router.get("/exports/{export_id}/download")
async def download_export(
    export_id: str,
    account=Depends(get_current_account),
):
    rec = await db.work_studio_phase_c_exports.find_one(
        {"id": export_id, "account_id": account["id"]})
    if not rec:
        raise HTTPException(status_code=404, detail="export_not_found")
    return Response(
        content=rec["binary"],
        media_type=CONTENT_TYPES.get(rec["format"], "application/octet-stream"),
        headers={
            "Content-Disposition": f'attachment; filename="{rec["filename"]}"',
            "X-Akki-Export-Sha256": rec["sha256"],
        },
    )


@router.get("/exports/{export_id}")
async def get_export_meta(
    export_id: str,
    account=Depends(get_current_account),
):
    rec = await db.work_studio_phase_c_exports.find_one(
        {"id": export_id, "account_id": account["id"]},
        {"_id": 0, "binary": 0},
    )
    if not rec:
        raise HTTPException(status_code=404, detail="export_not_found")
    return rec
