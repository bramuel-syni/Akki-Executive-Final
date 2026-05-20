"""Document Overlay endpoints (Chunk 8 — QA-2026-05-16-029…-036).

Endpoints (all under `/api/contexts/{context_id}/work-studio/documents/{aid}`):

  GET    /                            — overlay payload (QA-029, -030, -031)
  PATCH  /                            — update editable fields (title / structured_content) — QA-030 / -033
  POST   /save                        — create a version snapshot — QA-030 / -035
  POST   /move-to-review              — Draft → In Review (owner only) — Q1 trigger
  POST   /commit                      — Pre-commit snapshot + lifecycle commit + lock — QA-030 / -036
  POST   /create-new-version          — clone Committed → new Draft row — QA-030
  GET    /versions                    — list version snapshots — QA-035
  POST   /versions/{vid}/restore      — restore structured_content from snapshot — QA-035
  POST   /revise                      — AI Revision (Shield-routed, source-doc allowlist) — QA-034

All endpoints honour `context_id` scoping via require_context_membership.
The revise endpoint goes through `synisense.shield.client.invoke()`
exclusively — no direct LLM SDK calls.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from core import db, iso as _iso, now as _now, require_context_membership
from services.synisense.shield.client import invoke as shield_invoke
from services.work_studio_overlay import (
    can_transition,
    create_version_snapshot,
    list_versions,
    normalise_structured_content,
    overlay_payload,
    rag_band,
    validate_revision_inputs,
)

log = logging.getLogger("work_studio.overlay")

router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────────────────────────────
# GET — overlay payload
# ─────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/work-studio/documents/{artefact_id}")
async def get_document(
    context_id: str,
    artefact_id: str,
    ctx=Depends(require_context_membership()),
):
    row = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    payload = overlay_payload(row)
    # Computed overlay-only fields.
    intel = payload.get("intelligence_report")
    confidence = intel.get("confidence_pct") if isinstance(intel, dict) else None
    payload["confidence_band"] = rag_band(confidence)
    payload["is_owner"] = ctx["context"]["owner_account_id"] == ctx["account"]["id"]
    return payload


# ─────────────────────────────────────────────────────────────────────
# PATCH — editable fields (title + structured_content)
# ─────────────────────────────────────────────────────────────────────
class DocumentPatchIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=300)
    structured_content: Optional[Dict[str, Any]] = None


@router.patch("/contexts/{context_id}/work-studio/documents/{artefact_id}")
async def patch_document(
    context_id: str,
    artefact_id: str,
    payload: DocumentPatchIn,
    ctx=Depends(require_context_membership()),
):
    row = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    state = row.get("lifecycle_state") or "committed"
    if state == "committed":
        raise HTTPException(
            status_code=409,
            detail="This document is committed and read-only. Create a new version to make changes.",
        )
    updates: Dict[str, Any] = {"updated_at": _iso(_now())}
    if payload.title is not None:
        updates["document_title"] = payload.title.strip()
    if payload.structured_content is not None:
        updates["structured_content"] = normalise_structured_content(payload.structured_content)
    await db.work_studio_exports.update_one(
        {"id": artefact_id, "context_id": context_id},
        {"$set": updates},
    )
    refreshed = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    return overlay_payload(refreshed or row)


# ─────────────────────────────────────────────────────────────────────
# POST /save — create version snapshot
# ─────────────────────────────────────────────────────────────────────
class SaveIn(BaseModel):
    label: Optional[str] = Field(default=None, max_length=80)


@router.post("/contexts/{context_id}/work-studio/documents/{artefact_id}/save")
async def save_document(
    context_id: str,
    artefact_id: str,
    payload: SaveIn = Body(default=SaveIn()),
    ctx=Depends(require_context_membership()),
):
    row = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    if (row.get("lifecycle_state") or "committed") == "committed":
        raise HTTPException(
            status_code=409,
            detail="This document is committed and read-only.",
        )
    snap = await create_version_snapshot(
        db,
        artefact_id=artefact_id,
        context_id=context_id,
        account_id=ctx["account"]["id"],
        label=payload.label or "Auto-save",
        pre_commit=False,
    )
    return {"snapshot_id": snap["id"], "saved_at": snap["saved_at"]}


# ─────────────────────────────────────────────────────────────────────
# POST /move-to-review — Draft → In Review (owner only)
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/work-studio/documents/{artefact_id}/move-to-review")
async def move_to_review(
    context_id: str,
    artefact_id: str,
    ctx=Depends(require_context_membership()),
):
    row = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    is_owner = ctx["context"]["owner_account_id"] == ctx["account"]["id"]
    current = row.get("lifecycle_state") or "committed"
    ok, reason = can_transition(current, "in_review", is_owner=is_owner)
    if not ok:
        raise HTTPException(status_code=409, detail=reason)
    await db.work_studio_exports.update_one(
        {"id": artefact_id, "context_id": context_id},
        {"$set": {"lifecycle_state": "in_review", "updated_at": _iso(_now())}},
    )
    return {"id": artefact_id, "lifecycle_state": "in_review"}


# ─────────────────────────────────────────────────────────────────────
# POST /commit — Pre-commit snapshot + Committed lock
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/work-studio/documents/{artefact_id}/commit")
async def commit_document(
    context_id: str,
    artefact_id: str,
    ctx=Depends(require_context_membership()),
):
    row = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    current = row.get("lifecycle_state") or "committed"
    is_owner = ctx["context"]["owner_account_id"] == ctx["account"]["id"]
    ok, reason = can_transition(current, "committed", is_owner=is_owner)
    if not ok:
        raise HTTPException(status_code=409, detail=reason)
    # Pre-commit snapshot.
    snap = await create_version_snapshot(
        db,
        artefact_id=artefact_id,
        context_id=context_id,
        account_id=ctx["account"]["id"],
        label="Pre-commit",
        pre_commit=True,
    )
    await db.work_studio_exports.update_one(
        {"id": artefact_id, "context_id": context_id},
        {"$set": {
            "lifecycle_state": "committed",
            "committed_at": _iso(_now()),
            "committed_by": ctx["account"]["id"],
            "updated_at": _iso(_now()),
        }},
    )
    return {
        "id": artefact_id,
        "lifecycle_state": "committed",
        "pre_commit_snapshot_id": snap["id"],
    }


# ─────────────────────────────────────────────────────────────────────
# POST /create-new-version — clone Committed → new Draft row
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/work-studio/documents/{artefact_id}/create-new-version")
async def create_new_version(
    context_id: str,
    artefact_id: str,
    ctx=Depends(require_context_membership()),
):
    row = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    if (row.get("lifecycle_state") or "committed") != "committed":
        raise HTTPException(
            status_code=409,
            detail="Only committed documents can be cloned via Create New Version. Use the Draft itself.",
        )
    new_id = f"ws-{uuid.uuid4().hex[:12]}"
    base_title = (
        row.get("document_title") or row.get("name") or row.get("file_name") or "Untitled document"
    )
    clone = {
        **row,
        "id": new_id,
        "lifecycle_state": "draft",
        "legacy": False,
        "document_title": f"{base_title} (new version)",
        "created_at": _iso(_now()),
        "updated_at": _iso(_now()),
        "committed_at": None,
        "committed_by": None,
        "cloned_from_artefact_id": artefact_id,
        # Strip rendered binary references — caller must re-render
        # / re-export when committing. The structured_content stays
        # so the user has an editable starting point.
        "file_path": None,
        "file_sha256": None,
        "status": "draft",
    }
    await db.work_studio_exports.insert_one(dict(clone))
    refreshed = await db.work_studio_exports.find_one(
        {"id": new_id, "context_id": context_id}, {"_id": 0},
    )
    return overlay_payload(refreshed or clone)


# ─────────────────────────────────────────────────────────────────────
# GET /versions — list snapshots
# ─────────────────────────────────────────────────────────────────────
@router.get("/contexts/{context_id}/work-studio/documents/{artefact_id}/versions")
async def get_versions(
    context_id: str,
    artefact_id: str,
    ctx=Depends(require_context_membership()),
):
    rows = await list_versions(db, artefact_id=artefact_id, context_id=context_id)
    # Strip the full snapshot payload from the list response — the
    # preview / restore endpoints carry that. Keeps payloads small.
    return {
        "items": [
            {
                "id": r["id"],
                "saved_at": r["saved_at"],
                "saved_by": r["saved_by"],
                "label": r.get("label"),
                "pre_commit": bool(r.get("pre_commit", False)),
                "document_title_snapshot": r.get("document_title_snapshot"),
                "lifecycle_state_snapshot": r.get("lifecycle_state_snapshot"),
                "section_count": len(((r.get("structured_content_snapshot") or {}).get("sections") or [])),
            }
            for r in rows
        ],
    }


@router.get("/contexts/{context_id}/work-studio/documents/{artefact_id}/versions/{version_id}")
async def get_version_detail(
    context_id: str,
    artefact_id: str,
    version_id: str,
    ctx=Depends(require_context_membership()),
):
    row = await db.work_studio_artefact_versions.find_one(
        {"id": version_id, "artefact_id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Version not found")
    return row


@router.post("/contexts/{context_id}/work-studio/documents/{artefact_id}/versions/{version_id}/restore")
async def restore_version(
    context_id: str,
    artefact_id: str,
    version_id: str,
    ctx=Depends(require_context_membership()),
):
    artefact = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not artefact:
        raise HTTPException(status_code=404, detail="Document not found")
    if (artefact.get("lifecycle_state") or "committed") == "committed":
        raise HTTPException(
            status_code=409,
            detail="Cannot restore on a committed document. Use Create New Version first.",
        )
    snap = await db.work_studio_artefact_versions.find_one(
        {"id": version_id, "artefact_id": artefact_id, "context_id": context_id},
        {"_id": 0},
    )
    if not snap:
        raise HTTPException(status_code=404, detail="Version not found")
    # Take a safety snapshot of the CURRENT content before overwriting,
    # so the restore itself is reversible.
    await create_version_snapshot(
        db,
        artefact_id=artefact_id,
        context_id=context_id,
        account_id=ctx["account"]["id"],
        label="Auto-save (before restore)",
        pre_commit=False,
    )
    await db.work_studio_exports.update_one(
        {"id": artefact_id, "context_id": context_id},
        {"$set": {
            "structured_content": snap.get("structured_content_snapshot") or {"sections": []},
            "document_title": snap.get("document_title_snapshot") or artefact.get("document_title"),
            "updated_at": _iso(_now()),
        }},
    )
    refreshed = await db.work_studio_exports.find_one(
        {"id": artefact_id, "context_id": context_id}, {"_id": 0},
    )
    return overlay_payload(refreshed or artefact)


# ─────────────────────────────────────────────────────────────────────
# POST /revise — AI revision (Shield-routed, source-doc allowlist)
# ─────────────────────────────────────────────────────────────────────
class ReviseIn(BaseModel):
    instruction: str = Field(..., min_length=3, max_length=4000)
    scope: Literal["entire", "section", "pages"] = "entire"
    tone: Literal["formal", "concise", "detailed"] = "formal"
    section_index: Optional[int] = Field(default=None, ge=0, le=200)


@router.post("/contexts/{context_id}/work-studio/documents/{artefact_id}/revise")
async def revise_document(
    context_id: str,
    artefact_id: str,
    payload: ReviseIn,
    ctx=Depends(require_context_membership()),
):
    ok, err, row = await validate_revision_inputs(
        db,
        artefact_id=artefact_id,
        context_id=context_id,
        instruction=payload.instruction,
    )
    if not ok:
        raise HTTPException(status_code=err["status_code"], detail=err["detail"])

    allow = row.get("source_document_ids") or []
    # Fetch the source documents (extracted_text only) — these are
    # the ONLY context the Shield call sees. No broader context.
    source_docs = await db.documents.find(
        {"id": {"$in": allow}, "context_id": context_id},
        {"_id": 0, "id": 1, "name": 1, "extracted_text": 1},
    ).to_list(20)
    sources_block = "\n\n".join([
        f"[doc:{d['id']}] {d.get('name') or 'Untitled'}\n"
        f"{(d.get('extracted_text') or '')[:6000]}"
        for d in source_docs
    ]) or "[no extracted text available]"

    # Snapshot before revision so the user can always roll back.
    pre_revision_snap = await create_version_snapshot(
        db,
        artefact_id=artefact_id,
        context_id=context_id,
        account_id=ctx["account"]["id"],
        label="Auto-save (before AI revision)",
        pre_commit=False,
    )

    current_content = row.get("structured_content") or {"sections": []}
    prompt = _build_revision_prompt(
        instruction=payload.instruction,
        scope=payload.scope,
        tone=payload.tone,
        section_index=payload.section_index,
        current_content=current_content,
        sources_block=sources_block,
    )

    shield_result = await shield_invoke(
        purpose="work_studio.document.revise",
        content=prompt,
        tenant_id=ctx["account"]["id"],
        consumer_id="work_studio_overlay",
        user_id=ctx["account"]["id"],
        model_preference="analytical",
        internal_caller=True,
    )

    # Parse the LLM's structured response.
    diff = _parse_revision_response(shield_result.get("response") or "", current_content)

    return {
        "artefact_id": artefact_id,
        "scope": payload.scope,
        "tone": payload.tone,
        "diff": diff,
        "pre_revision_snapshot_id": pre_revision_snap["id"],
        "audit_id": shield_result.get("audit_id"),
    }


def _build_revision_prompt(
    *, instruction: str, scope: str, tone: str,
    section_index: Optional[int],
    current_content: Dict[str, Any],
    sources_block: str,
) -> str:
    sections = (current_content or {}).get("sections") or []
    current_render = "\n\n".join([
        f"## Section {i} — {s.get('heading', '')}\n" +
        "\n".join(s.get("paragraphs") or [])
        for i, s in enumerate(sections)
    ]) or "[empty document]"
    scope_line = (
        f"Scope: revise section index {section_index} only" if scope == "section" and section_index is not None
        else f"Scope: {scope}"
    )
    return (
        "You are revising a Work Studio document. You draw ONLY from the "
        "SOURCE DOCUMENTS below — never introduce external knowledge.\n\n"
        f"=== SOURCE DOCUMENTS ===\n{sources_block}\n\n"
        f"=== CURRENT DOCUMENT ===\n{current_render}\n\n"
        f"=== INSTRUCTION ===\n{instruction.strip()}\n{scope_line}\nTone: {tone}\n\n"
        "Return STRICT JSON only:\n"
        '{"sections":[{"heading":"<text>","paragraphs":["<para>","<para>"]}],'
        '"change_notes":["<one-line bullet describing each change>"]}\n'
        "Preserve sections that should not change. Do NOT add commentary "
        "outside the JSON."
    )


def _parse_revision_response(raw: str, current_content: Dict[str, Any]) -> Dict[str, Any]:
    """Parse the LLM revision response and emit a paragraph-level diff.

    Returns: {revised_sections: [...], change_notes: [...]}
    The frontend renders this as an accept/reject diff.
    """
    from llm_service import parse_json_response

    parsed = parse_json_response(raw) or {}
    revised_sections_raw = parsed.get("sections") if isinstance(parsed, dict) else None
    if not isinstance(revised_sections_raw, list):
        revised_sections_raw = []
    revised = normalise_structured_content({"sections": revised_sections_raw})
    change_notes = parsed.get("change_notes") if isinstance(parsed, dict) else []
    if not isinstance(change_notes, list):
        change_notes = []
    change_notes = [str(n)[:240] for n in change_notes if isinstance(n, (str, int, float))]

    # Best-effort paragraph-level diff (additions / deletions /
    # modifications) — section-aligned by index. Sections beyond the
    # original or revised length are treated as pure additions /
    # deletions.
    orig_sections = (current_content or {}).get("sections") or []
    rev_sections = revised.get("sections") or []
    section_diffs: List[Dict[str, Any]] = []
    for i in range(max(len(orig_sections), len(rev_sections))):
        o = orig_sections[i] if i < len(orig_sections) else None
        r = rev_sections[i] if i < len(rev_sections) else None
        if o and not r:
            section_diffs.append({
                "section_index": i,
                "heading": o.get("heading", ""),
                "change_type": "section_removed",
                "original_paragraphs": o.get("paragraphs") or [],
                "revised_paragraphs": [],
            })
        elif r and not o:
            section_diffs.append({
                "section_index": i,
                "heading": r.get("heading", ""),
                "change_type": "section_added",
                "original_paragraphs": [],
                "revised_paragraphs": r.get("paragraphs") or [],
            })
        else:
            orig_paras = o.get("paragraphs") or []
            rev_paras = r.get("paragraphs") or []
            if orig_paras == rev_paras and (o.get("heading") == r.get("heading")):
                section_diffs.append({
                    "section_index": i,
                    "heading": o.get("heading", ""),
                    "change_type": "unchanged",
                    "original_paragraphs": orig_paras,
                    "revised_paragraphs": rev_paras,
                })
            else:
                section_diffs.append({
                    "section_index": i,
                    "heading": r.get("heading") or o.get("heading", ""),
                    "change_type": "modified",
                    "original_paragraphs": orig_paras,
                    "revised_paragraphs": rev_paras,
                })
    return {
        "revised_content": revised,
        "section_diffs": section_diffs,
        "change_notes": change_notes,
    }
