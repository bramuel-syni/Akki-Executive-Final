"""Phase E Sub-tasks F + G + H — admin migration + Solva→Work Studio
artefact creation + chat privacy-report PDF.

  F. `POST /api/admin/solva/legacy/soft-archive` — soft-deletes orphan
     legacy sessions (no `context_id`) by setting `archived_at`. The
     existing list endpoints already exclude `archived_at` rows.
     Companion `POST /api/admin/solva/legacy/restore` reverses it.

  G. `POST /api/contexts/{cid}/work-studio/artefacts/from-solva` —
     creates a Work Studio brief artefact pre-populated with a Phase D
     Solva session's synthesis. Adds `source_solva_session_id` to the
     artefact for traceability.

  H. `GET /api/chats/{cid}/privacy-report.pdf` — generates a styled PDF
     of every Trust Receipt + audit entry for the chat. Uses reportlab
     (already in requirements). Streamed back as application/pdf.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from core import db, get_current_account, require_context_membership
from routers.chat_audit_panel import _friendly_purpose, _friendly_model_name


# ─────────────────────────────────────────────────────────────────────
# Sub-task F — admin migration.
# ─────────────────────────────────────────────────────────────────────
admin_router = APIRouter(prefix="/api/admin/solva", tags=["admin-solva-migration"])


async def _require_superadmin(
    current: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not current.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin only.")
    return current


@admin_router.post("/legacy/soft-archive")
async def soft_archive_orphans(
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """Soft-delete legacy `solva_sessions` rows that have no
    `context_id` AND are not already archived. Reversible via
    `/legacy/restore?session_id=...`. Adds an `archived_at` timestamp
    and `archived_by_admin_id` for audit.
    """
    now = datetime.now(timezone.utc)
    admin_id = _admin.get("id") or _admin.get("account_id") or "superadmin"
    res = await db.solva_sessions.update_many(
        {
            "$or": [{"context_id": {"$exists": False}}, {"context_id": None}, {"context_id": ""}],
            "archived_at": {"$exists": False},
        },
        {"$set": {
            "archived_at": now,
            "archived_by_admin_id": admin_id,
            "archived_reason": "phase_e_legacy_migration",
        }},
    )
    return {
        "matched": res.matched_count,
        "modified": res.modified_count,
        "archived_at": now.isoformat(),
    }


@admin_router.post("/legacy/restore")
async def restore_one(
    session_id: str = Body(..., embed=True),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    res = await db.solva_sessions.update_one(
        {"id": session_id, "archived_at": {"$exists": True}},
        {"$unset": {"archived_at": "", "archived_by_admin_id": "", "archived_reason": ""}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found or not archived.")
    return {"session_id": session_id, "restored": True}


@admin_router.get("/legacy/orphan-count")
async def orphan_count(
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    pending = await db.solva_sessions.count_documents({
        "$or": [{"context_id": {"$exists": False}}, {"context_id": None}, {"context_id": ""}],
        "archived_at": {"$exists": False},
    })
    archived = await db.solva_sessions.count_documents({"archived_at": {"$exists": True}})
    return {"pending_orphans": pending, "archived_orphans": archived}


# ─────────────────────────────────────────────────────────────────────
# Sub-task G — Work Studio artefact from Solva session.
# ─────────────────────────────────────────────────────────────────────
solva_export_router = APIRouter(
    prefix="/api/contexts/{context_id}/work-studio",
    tags=["work-studio-from-solva"],
)


class ArtefactFromSolvaIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_id: str = Field(min_length=1, max_length=120)


@solva_export_router.post("/artefacts/from-solva")
async def create_artefact_from_solva(
    body: ArtefactFromSolvaIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
) -> Dict[str, Any]:
    """Create a Work Studio brief artefact pre-populated with a Phase D
    Solva session's synthesis. Strict scoping: session must belong to
    the active context AND the requesting account."""
    account = ctx["account"]
    context_id = ctx["context"]["id"]
    session = await db.solva_phase_d_sessions.find_one(
        {"session_id": body.session_id, "context_id": context_id, "account_id": account["id"]},
        {"_id": 0},
    )
    if not session:
        raise HTTPException(status_code=404, detail="Solva session not found.")
    if session["status"] not in ("completed", "refused"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot export an artefact for a Solva session that is {session['status']}.",
        )
    l3 = session.get("layer_3") or {}
    synthesis_text = l3.get("rendered_synthesis") or l3.get("refusal_rendering") or ""

    artefact_id = "art-" + uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    artefact = {
        "id": artefact_id,
        "type": "brief",
        "title": f"Solva diagnosis — {session.get('sub_module', 'session')}",
        "body_md": (
            f"# Diagnosis from Solva session\n\n"
            f"_Source: Solva session `{body.session_id}` "
            f"({session.get('sub_module')})_\n\n"
            f"{synthesis_text}\n"
        ),
        "context_id": context_id,
        "account_id": account["id"],
        "source_solva_session_id": body.session_id,
        "source_solva_audit_ids": list(session.get("synisense_audit_ids") or []),
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    await db.work_studio_artefacts.insert_one(dict(artefact))
    artefact.pop("_id", None)
    for k in ("created_at", "updated_at"):
        if isinstance(artefact.get(k), datetime):
            artefact[k] = artefact[k].isoformat()
    return artefact


# ─────────────────────────────────────────────────────────────────────
# Sub-task H — chat privacy-report PDF.
# ─────────────────────────────────────────────────────────────────────
chat_pdf_router = APIRouter(prefix="/api/chats", tags=["chat-privacy-report"])


def _build_pdf_bytes(*, chat: Dict[str, Any], audits: list, tenant: Dict[str, Any]) -> bytes:
    """Compose the privacy report PDF using reportlab. Falls back to a
    plain-text PDF wrapper if reportlab is unavailable in the env."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
        )
        from reportlab.lib import colors
    except ImportError:
        # Plain-text fallback wrapped as a minimal PDF (so the
        # endpoint never 500s if reportlab is missing).
        text = (
            "Privacy Report (fallback)\n\n"
            f"Chat: {chat.get('id')}\n"
            f"Tenant: {tenant.get('name') or tenant.get('id')}\n"
            f"Audit entries: {len(audits)}\n\n"
        )
        for a in audits[:50]:
            text += (
                f"- {a.get('audit_id')} | purpose={a.get('purpose')} "
                f"| exposure_reduction={a.get('exposure_reduction_score')}% "
                f"| dilution={a.get('dilution_score')}%\n"
            )
        # Return a minimal PDF stream.
        return _plain_text_pdf(text)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title=f"Privacy Report — Chat {chat.get('id', '')}")
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        "body", parent=styles["BodyText"], fontSize=10, leading=14,
    )
    story = []
    story.append(Paragraph("Privacy Report", styles["Title"]))
    story.append(Paragraph(
        f"Chat ID: <b>{chat.get('id', '')}</b><br/>"
        f"Tenant: <b>{tenant.get('name') or tenant.get('id', '')}</b><br/>"
        f"Generated: {datetime.now(timezone.utc).isoformat()}<br/>"
        f"LLM calls included: <b>{len(audits)}</b>",
        body_style,
    ))
    story.append(Spacer(1, 16))

    if not audits:
        story.append(Paragraph(
            "No governed LLM calls have been routed through Synisense for this chat.",
            body_style,
        ))
    for idx, a in enumerate(audits, 1):
        story.append(Paragraph(
            f"<b>Step {idx}/{len(audits)}</b> — "
            f"{_friendly_purpose(a.get('purpose') or '')}",
            styles["Heading4"],
        ))
        rows = [
            ["Audit ID", a.get("audit_id") or "—"],
            ["Purpose", _friendly_purpose(a.get("purpose") or "—")],
            ["Provider · Model",
             f"{a.get('llm_provider') or '—'} · {_friendly_model_name(a.get('llm_model') or '')}"],
            ["Exposure reduction", f"{a.get('exposure_reduction_score', '—')}%"],
            ["Dilution", f"{a.get('dilution_score', '—')}%"],
            ["Outcome", a.get("outcome") or "success"],
            ["Trust receipt", (a.get("trust_receipt_id") or "—")[:30]],
        ]
        tbl = Table(rows, colWidths=[140, 360])
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 10))
    doc.build(story)
    return buf.getvalue()


def _plain_text_pdf(text: str) -> bytes:
    """Tiny hand-rolled PDF for the no-reportlab fallback path. Single
    page, monospaced. Not pretty but valid PDF that opens cleanly."""
    body = text.replace("(", r"\(").replace(")", r"\)")
    stream = (
        "BT /F1 9 Tf 50 750 Td ("
        + body.replace("\n", ") Tj T* (")
        + ") Tj ET"
    )
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
        b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Courier>>endobj\n"
        b"5 0 obj<</Length " + str(len(stream)).encode() + b">>stream\n"
        + stream.encode("latin-1", errors="replace")
        + b"\nendstream endobj\n"
        b"xref\n0 6\n0000000000 65535 f\n"
        b"trailer<</Size 6/Root 1 0 R>>\nstartxref\n0\n%%EOF\n"
    )
    return pdf


@chat_pdf_router.get("/{chat_id}/privacy-report.pdf")
async def chat_privacy_report_pdf(
    chat_id: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    """Generate a privacy-report PDF for one chat. Streams as
    `application/pdf`. Strict scoping: the chat must belong to the
    requesting account."""
    chat = await db.chats.find_one(
        {"id": chat_id, "account_id": account["id"]},
        {"_id": 0},
    )
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found.")
    audit_ids = chat.get("synisense_audit_ids") or []
    audits = []
    if audit_ids:
        audits = await db.synisense_audit_log.find(
            {"audit_id": {"$in": audit_ids}, "tenant_id": account["id"]},
            {"_id": 0},
        ).to_list(length=len(audit_ids) + 10)
    tenant = {
        "id": account["id"],
        "name": account.get("name") or account.get("email") or account["id"],
    }
    pdf_bytes = _build_pdf_bytes(chat=chat, audits=audits, tenant=tenant)
    filename = f"privacy-report-{chat_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
