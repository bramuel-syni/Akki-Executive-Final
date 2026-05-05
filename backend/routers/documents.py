"""Documents: upload pipeline, thread, list/get/patch/archive/download, generate-meta."""
from __future__ import annotations

import io
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from llm_service import call_llm as llm_call_llm, parse_json_response
from documents_service import (
    ACCEPT_EXT, MAX_BYTES, save_to_storage, read_from_storage,
    delete_from_storage, extract_text, make_preview,
)
from services import clamav_service
from services.clamav_service import ClamAVUnreachable
from core import (
    db, now as _now, iso as _iso, write_audit, require_context_membership,
)

logger = logging.getLogger("akki.documents")

router = APIRouter(prefix="/api")

MAX_EXTRACT_CHARS_OUT = 40000


def sanitize_doc(d: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": d["id"],
        "context_id": d["context_id"],
        "name": d.get("name"),
        "description": d.get("description", ""),
        "original_filename": d.get("original_filename"),
        "mime_type": d.get("mime_type"),
        "size_bytes": d.get("size_bytes", 0),
        "status": d.get("status", "uploaded"),
        "preview": d.get("preview", ""),
        "extracted_chars": d.get("extracted_chars", 0),
        "data_trust": d.get("data_trust", "mixed"),
        "uploaded_by_email": d.get("uploaded_by_email"),
        "mentioned_account_ids": d.get("mentioned_account_ids", []),
        "related_doc_id": d.get("related_doc_id"),
        "relation_type": d.get("relation_type"),
        "error": d.get("error"),
        "created_at": d.get("created_at"),
        "doc_type": d.get("doc_type"),
        # Inbound email provenance (iter51) + trust tier (iter70)
        "source": d.get("source"),
        "inbound_from_email": d.get("inbound_from_email"),
        "inbound_from_name": d.get("inbound_from_name"),
        "inbound_subject": d.get("inbound_subject"),
        "inbound_trust_tier": d.get("inbound_trust_tier"),
        "inbound_trust_reason": d.get("inbound_trust_reason"),
        "inbound_reportee_id": d.get("inbound_reportee_id"),
        "inbound_reportee_name": d.get("inbound_reportee_name"),
        "inbound_reportee_title": d.get("inbound_reportee_title"),
        "inbound_queue_id": d.get("inbound_queue_id"),
        "inbound_promoted_by": d.get("inbound_promoted_by"),
        "inbound_promoted_at": d.get("inbound_promoted_at"),
        "inbound_promoted_note": d.get("inbound_promoted_note"),
    }


class DocumentTrustUpdate(BaseModel):
    data_trust: Optional[Literal["trusted", "mixed", "weak"]] = None
    related_doc_id: Optional[str] = Field(
        default=None,
        description="Link this document as a successor of an existing doc — "
                    "lets NEDs trace how a recurring report has evolved across "
                    "cycles. Pass `null` to unlink. Pass an empty string for "
                    "no change (use Optional[None] sentinel below).",
    )


class DocumentMetaGenerateIn(BaseModel):
    filename: Optional[str] = None
    preview_text: Optional[str] = Field(default=None, max_length=8_000)


@router.post("/contexts/{context_id}/documents/generate-meta")
async def generate_document_meta(
    context_id: str, body: DocumentMetaGenerateIn,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Given a filename and optional preview text, ask the LLM to propose a
    short display name and ≤300-char description. Used by the upload modal."""
    if not body.filename and not body.preview_text:
        raise HTTPException(status_code=400, detail="Send filename or preview_text.")
    sample = (body.preview_text or "")[:4000]
    prompt = (
        "Propose a short display name and a description for a board-pack "
        "document. Stay neutral, specific, no hype. Return JSON ONLY:\n"
        '{"display_name": "<=60 chars title-case declarative name", '
        '"description": "<=300 chars single-paragraph description"}\n\n'
        f"Filename: {body.filename or '(unknown)'}\n\n"
        f"First ~4KB of extracted text:\n{sample or '(no text extracted)'}"
    )
    out = await llm_call_llm(
        module="document.meta",
        user_query=prompt,
        context_object=None,
        session_context={"session_id": f"docmeta-{context_id}"},
        data_trust={"overall": "unrated"},
        response_format="json",
    )
    parsed = parse_json_response(out.get("response", ""))
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail=f"LLM returned no meta. Mode={out.get('mode')}.")
    return {
        "display_name": (parsed.get("display_name") or "")[:60].strip(),
        "description": (parsed.get("description") or "")[:300].strip(),
        "mode": out.get("mode"),
        "shielding_masked": out.get("shielding", {}).get("identifiers_masked", 0),
        "shielding": out.get("shielding", {}),
    }


@router.post("/contexts/{context_id}/documents/{doc_id}/summary")
async def generate_document_summary(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    refresh: bool = False,
):
    """AKKI summary of a single document for the Document Journal.

    Returns:
        - tldr: 2-3 sentence executive summary
        - highlights: list of 4-7 important points the reader should know
        - questions: list of 2-3 questions the reader should bring back

    Cached on the document so opening it twice doesn't re-burn the LLM.
    Pass ?refresh=true to regenerate.
    """
    d = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id}, {"_id": 0},
    )
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")

    cached = d.get("akki_summary")
    if cached and not refresh:
        return cached

    text = (d.get("extracted_text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No extractable text on this document.")

    sample = text[:12000]
    prompt = (
        "Read the executive document below. Summarise it for a board "
        "member who has 60 seconds. Return JSON ONLY:\n"
        '{\n'
        '  "tldr": "<=2 sentences, what this document is and what it says>",\n'
        '  "highlights": [\n'
        '    "<the single most important point — a fact or a claim — phrased plainly>",\n'
        '    "<next>",\n'
        '    "<...4 to 7 total>"\n'
        '  ],\n'
        '  "questions": [\n'
        '    "<question the reader should walk into the room with>",\n'
        '    "<...2 to 3 total>"\n'
        '  ]\n'
        '}\n\n'
        f"Document name: {d.get('name')}\n\n"
        f"Document text (first ~12KB):\n{sample}"
    )
    out = await llm_call_llm(
        module="document.summary",
        user_query=prompt,
        context_object=None,
        session_context={"session_id": f"docsum-{doc_id}"},
        data_trust={"overall": d.get("data_trust", "unrated")},
        response_format="json",
    )
    parsed = parse_json_response(out.get("response", "")) or {}
    summary = {
        "tldr": (parsed.get("tldr") or "").strip(),
        "highlights": [str(h).strip() for h in (parsed.get("highlights") or []) if str(h).strip()][:7],
        "questions": [str(q).strip() for q in (parsed.get("questions") or []) if str(q).strip()][:3],
        "mode": out.get("mode"),
        "generated_at": _iso(_now()),
    }
    await db.documents.update_one(
        {"id": doc_id, "context_id": context_id},
        {"$set": {"akki_summary": summary, "updated_at": _iso(_now())}},
    )
    return summary


@router.post("/contexts/{context_id}/documents")
async def upload_document(
    context_id: str,
    file: UploadFile = File(...),
    display_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    data_trust: Optional[str] = Form(None),
    mentioned_account_ids: Optional[str] = Form(None),  # comma-sep
    related_doc_id: Optional[str] = Form(None),
    relation_type: Optional[str] = Form(None),  # update | follow_up | additional_context | correction
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    filename = file.filename or "unnamed"
    ext = Path(filename).suffix.lower()
    if ext not in ACCEPT_EXT:
        raise HTTPException(status_code=415, detail=f"Unsupported file type {ext}. Accepted: {', '.join(sorted(ACCEPT_EXT))}")

    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large. Max {MAX_BYTES // 1024 // 1024}MB.")

    # Real virus scanning (Phase 10). clamd unreachable → 503 + audit.
    # Signature match → 422 + audit. Neither branch persists the file.
    try:
        scan_result = clamav_service.scan(data, filename)
    except ClamAVUnreachable as e:
        await write_audit(
            context_id, ctx["account"]["id"],
            "upload.virus_scan.unreachable",
            "document", None,
            {"filename_hash": __import__("hashlib").sha256((filename or "").encode()).hexdigest()[:16],
             "error": str(e)[:200]},
        )
        raise HTTPException(
            status_code=503,
            detail={"error": "scanner_unavailable", "reason": "virus scanner offline"},
        )
    if not scan_result.clean:
        await write_audit(
            context_id, ctx["account"]["id"],
            "upload.virus_scan.blocked",
            "document", None,
            {
                "filename_hash": __import__("hashlib").sha256((filename or "").encode()).hexdigest()[:16],
                "signature": scan_result.signature,
                "size_bytes": len(data),
                "scan_ms": scan_result.scan_ms,
            },
        )
        raise HTTPException(
            status_code=422,
            detail={"error": "blocked", "reason": "malware_suspected", "signature": scan_result.signature},
        )

    if related_doc_id:
        if relation_type not in ("update", "follow_up", "additional_context", "correction"):
            raise HTTPException(status_code=400, detail="Invalid relation_type. Expected: update | follow_up | additional_context | correction")
        related = await db.documents.find_one(
            {"id": related_doc_id, "context_id": context_id, "status": {"$ne": "archived"}},
            {"_id": 0, "id": 1},
        )
        if not related:
            raise HTTPException(status_code=404, detail="related_doc_id not found in this context")

    mention_ids: List[str] = []
    if mentioned_account_ids:
        requested = [m.strip() for m in mentioned_account_ids.split(",") if m.strip()]
        if requested:
            valid = await db.memberships.find(
                {"context_id": context_id, "account_id": {"$in": requested}, "status": "active"},
                {"_id": 0, "account_id": 1},
            ).to_list(100)
            mention_ids = [v["account_id"] for v in valid]

    doc_id = str(uuid.uuid4())
    storage_key = save_to_storage(context_id, doc_id, filename, data)
    text, err = extract_text(data, filename, file.content_type or "")
    preview = make_preview(text)

    created_at = _iso(_now())
    trust = data_trust if data_trust in ("trusted", "mixed", "weak") else "mixed"
    doc = {
        "id": doc_id,
        "context_id": context_id,
        "name": (display_name or Path(filename).stem).strip() or "Untitled",
        "description": (description or "")[:300].strip(),
        "original_filename": filename,
        "mime_type": file.content_type or "application/octet-stream",
        "size_bytes": len(data),
        "storage_key": storage_key,
        "status": "extracted" if text and not err else ("failed" if err else "empty"),
        "extracted_text": text,
        "extracted_chars": len(text),
        "preview": preview,
        "data_trust": trust,
        "uploaded_by": ctx["account"]["id"],
        "uploaded_by_email": ctx["account"]["email"],
        "mentioned_account_ids": mention_ids,
        "related_doc_id": related_doc_id or None,
        "relation_type": relation_type if related_doc_id else None,
        "error": err,
        "created_at": created_at,
        "updated_at": created_at,
    }
    await db.documents.insert_one(doc)
    doc.pop("_id", None)

    for account_id in mention_ids:
        if account_id == ctx["account"]["id"]:
            continue
        await db.mentions.insert_one({
            "id": str(uuid.uuid4()),
            "context_id": context_id,
            "target_account_id": account_id,
            "source_account_id": ctx["account"]["id"],
            "source_name": ctx["account"].get("name") or ctx["account"].get("email", ""),
            "artefact_type": "document",
            "artefact_id": doc_id,
            "comment_id": None,
            "preview": f"Tagged you on: {doc['name']}",
            "created_at": created_at,
            "read": False,
        })

    await write_audit(
        context_id, ctx["account"]["id"], "document.uploaded", "document", doc_id,
        {"name": doc["name"], "size_bytes": doc["size_bytes"], "status": doc["status"],
         "related_doc_id": related_doc_id, "relation_type": doc["relation_type"],
         "mentions": len(mention_ids)},
    )
    return sanitize_doc(doc)


@router.get("/contexts/{context_id}/documents/{doc_id}/thread")
async def document_thread(
    doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Return the thread of linked documents for this doc — ancestors (the
    chain of related_doc_id pointers back to the origin) plus descendants
    (anything that points TO this doc)."""
    context_id = ctx["context"]["id"]
    ancestors: List[Dict[str, Any]] = []
    current_id: Optional[str] = doc_id
    seen: set = set()
    for _ in range(20):  # safety cap against loops
        if not current_id or current_id in seen:
            break
        seen.add(current_id)
        d = await db.documents.find_one(
            {"id": current_id, "context_id": context_id}, {"_id": 0},
        )
        if not d:
            break
        ancestors.insert(0, sanitize_doc(d))
        current_id = d.get("related_doc_id")

    ancestor_ids = [a["id"] for a in ancestors]
    descendants = await db.documents.find(
        {
            "context_id": context_id,
            "related_doc_id": {"$in": ancestor_ids},
            "id": {"$nin": ancestor_ids},
            "status": {"$ne": "archived"},
        },
        {"_id": 0},
    ).sort("created_at", 1).to_list(100)
    return {
        "ancestors": ancestors,
        "descendants": [sanitize_doc(d) for d in descendants],
    }


@router.get("/contexts/{context_id}/documents")
async def list_documents(
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    limit: int = 100,
    committee_id: Optional[str] = None,
):
    q: Dict[str, Any] = {"context_id": ctx["context"]["id"], "status": {"$ne": "archived"}}
    if committee_id:
        q["committee_id"] = committee_id
    docs = await db.documents.find(
        q, {"_id": 0, "extracted_text": 0, "storage_key": 0},
    ).sort("created_at", -1).to_list(min(limit, 500))
    return [sanitize_doc(d) for d in docs]


@router.get("/contexts/{context_id}/documents/{doc_id}")
async def get_document_detail(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    d = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id}, {"_id": 0, "storage_key": 0}
    )
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    out = sanitize_doc(d)
    out["extracted_text"] = d.get("extracted_text", "")[:MAX_EXTRACT_CHARS_OUT]
    if d.get("akki_summary"):
        out["akki_summary"] = d["akki_summary"]
    # Phase L.4: surface the Synisense + sensitivity-scorer artefacts on
    # the detail endpoint so the document page can render them and the
    # Strategic-Pack ingestion can be verified end-to-end.
    for k in (
        "body_redacted", "synisense_version",
        "sensitivity_score", "sensitivity_band", "sensitivity_label",
        "sensitivity_reasons", "doc_kind",
        # Phase M.2: surface the journal-specific fields too.
        "source_channel", "journal_commentary",
        "journal_commentary_generated_at", "journal_commentary_synisense_version",
    ):
        if k in d:
            out[k] = d[k]
    return out


# ═════════════════════════════════════════════════════════════════════════
#  Phase M.2 — Document Journal endpoints
#
#  The Document Journal is the per-context chronological listing of every
#  document the context has ever received (upload / inbound email /
#  share / sandbox). The listing is mostly handled by the existing
#  GET /api/contexts/{cid}/documents — these endpoints add the two
#  pieces the Journal UX needs that the existing surface does not:
#
#    • A row-projection that joins source_channel + cached commentary
#      flags so the listing can render markers without N+1 round trips.
#    • An on-demand commentary generator (Akki dry FT-voice take on
#      one specific document; cached on the row).
# ═════════════════════════════════════════════════════════════════════════


@router.get("/contexts/{context_id}/document-journal")
async def get_document_journal(
    context_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Listing projection for the Document Journal surface.

    Returns docs newest-first with the marker fields the UI renders
    inline (sensitivity, data_trust, source_channel, has_commentary).
    """
    cursor = db.documents.find(
        {"context_id": context_id},
        {
            "_id": 0,
            "id": 1, "name": 1, "title": 1, "doc_kind": 1, "doc_type": 1,
            "data_trust": 1, "sensitivity_band": 1, "sensitivity_score": 1,
            "source_channel": 1, "source": 1, "status": 1,
            "size_bytes": 1, "preview": 1,
            "created_at": 1, "updated_at": 1,
            "journal_commentary": 1, "journal_commentary_generated_at": 1,
        },
    ).sort("created_at", -1)
    rows = await cursor.to_list(500)
    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "title": r.get("name") or r.get("title") or "(untitled)",
            "doc_kind": r.get("doc_kind"),
            "doc_type": r.get("doc_type"),
            "data_trust": r.get("data_trust") or "trusted",
            "sensitivity_band": r.get("sensitivity_band") or "internal",
            "sensitivity_score": r.get("sensitivity_score"),
            "source_channel": r.get("source_channel") or "upload",
            "source": r.get("source"),
            "status": r.get("status") or "ready",
            "size_bytes": r.get("size_bytes"),
            "preview": (r.get("preview") or "")[:240],
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "has_commentary": bool(r.get("journal_commentary")),
            "commentary_generated_at": r.get("journal_commentary_generated_at"),
        })
    return {"items": items, "count": len(items)}


@router.post("/contexts/{context_id}/documents/{doc_id}/journal-commentary")
async def journal_commentary(
    context_id: str, doc_id: str,
    refresh: bool = False,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Generate (or return cached) Akki commentary on a single document.

    ~400 word target, FT-voice, dry, specific. Cached on the row;
    subsequent calls return cached unless `?refresh=true`.

    Phase 1 (2026-05-05): the generation logic lives in
    `document_commentary_service.generate_journal_commentary` so the
    backfill script (`scripts/backfill_journal_commentary.py`) calls
    the exact same function. The pre-Phase-1 surface mis-label
    (`synisense_pipeline.run(... surface="briefing")`) is fixed in
    that shared service and surfaced here through the same import.
    """
    d = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id}, {"_id": 0},
    )
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")

    from document_commentary_service import (
        generate_journal_commentary, CommentaryGenerationError,
    )
    try:
        out = await generate_journal_commentary(
            doc=d,
            account_id=ctx["account"]["id"],
            refresh=refresh,
            record_audit=True,
        )
    except CommentaryGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    if out["status"] == "skipped":
        # Map the generic skip reasons onto the HTTP responses the live
        # endpoint historically used so existing UI code doesn't have
        # to learn a new contract.
        reason = out["reason"]
        if reason == "no_extracted_text":
            raise HTTPException(
                status_code=422,
                detail="Document has no extracted text — cannot generate commentary.",
            )
        if reason.startswith("sensitivity_band="):
            raise HTTPException(
                status_code=403,
                detail="Document is restricted; commentary cannot be generated.",
            )
        if reason.startswith("doc_status="):
            raise HTTPException(
                status_code=422,
                detail=f"Document not ready for commentary ({reason}).",
            )
        # Anything else — surface as 422 with the literal reason.
        raise HTTPException(status_code=422, detail=f"skipped:{reason}")

    return {
        "doc_id": doc_id,
        "commentary": out["commentary"],
        "commentary_redacted": out["redacted"],
        "synisense_version": out["synisense_version"],
        "generated_at": out["generated_at"],
        "cached": out["status"] == "cached",
    }


@router.patch("/contexts/{context_id}/documents/{doc_id}")
async def update_document_trust(
    context_id: str, doc_id: str,
    body: DocumentTrustUpdate,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Patch trust and/or evolution-chain link.

    The endpoint name predates the evolution-link feature (added iter34); the
    payload now carries either `data_trust`, `related_doc_id`, or both.
    Passing `related_doc_id=null` unlinks the document from any predecessor.
    """
    update: Dict[str, Any] = {"updated_at": _iso(_now())}
    if body.data_trust is not None:
        update["data_trust"] = body.data_trust
    if "related_doc_id" in body.model_fields_set:
        new_link = body.related_doc_id
        if new_link == doc_id:
            raise HTTPException(status_code=400, detail="A document cannot be its own predecessor.")
        if new_link:
            # Verify the predecessor exists in the same context AND that
            # linking won't introduce a cycle.
            parent = await db.documents.find_one(
                {"id": new_link, "context_id": context_id},
                {"_id": 0, "id": 1, "related_doc_id": 1},
            )
            if not parent:
                raise HTTPException(status_code=404, detail="Predecessor document not found in this company.")
            cur = parent
            for _ in range(20):
                if cur.get("related_doc_id") == doc_id:
                    raise HTTPException(status_code=400, detail="That link would create a cycle.")
                if not cur.get("related_doc_id"):
                    break
                cur = await db.documents.find_one(
                    {"id": cur["related_doc_id"], "context_id": context_id},
                    {"_id": 0, "id": 1, "related_doc_id": 1},
                ) or {}
        update["related_doc_id"] = new_link
    if len(update) == 1:  # only updated_at — nothing was sent
        raise HTTPException(status_code=400, detail="Send data_trust and/or related_doc_id.")
    res = await db.documents.update_one(
        {"id": doc_id, "context_id": context_id},
        {"$set": update},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    audit_changes = {k: v for k, v in update.items() if k != "updated_at"}
    await write_audit(
        context_id, ctx["account"]["id"], "document.updated", "document", doc_id,
        audit_changes,
    )
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0, "storage_key": 0, "extracted_text": 0})
    return sanitize_doc(d)


@router.post("/contexts/{context_id}/documents/{doc_id}/evolution-diff")
async def document_evolution_diff(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
    refresh: bool = False,
):
    """LLM-powered "what changed" between this doc and its immediate
    predecessor. Used by the NED Document Evolution panel to surface drift
    in recurring reports across cycles.

    Returns:
        {
          "previous_doc": {id, name, created_at} | null,
          "diff": {
            "what_changed": "<2-3 sentences: the headline of the drift>",
            "added_or_strengthened": ["<bullet>", ...],
            "weakened_or_removed":   ["<bullet>", ...],
            "questions_for_management": ["<bullet>", "<bullet>"]
          } | null
        }

    Cached on the doc record; pass ?refresh=true to regenerate.
    """
    d = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id}, {"_id": 0},
    )
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    parent_id = d.get("related_doc_id")
    if not parent_id:
        return {"previous_doc": None, "diff": None}
    parent = await db.documents.find_one(
        {"id": parent_id, "context_id": context_id}, {"_id": 0},
    )
    if not parent:
        return {"previous_doc": None, "diff": None}

    cached = d.get("evolution_diff")
    if cached and cached.get("previous_doc_id") == parent_id and not refresh:
        return {
            "previous_doc": {
                "id": parent["id"], "name": parent.get("name"),
                "created_at": parent.get("created_at"),
            },
            "diff": cached.get("diff"),
        }

    cur_text  = (d.get("extracted_text") or "").strip()[:8000]
    prev_text = (parent.get("extracted_text") or "").strip()[:8000]
    if not cur_text or not prev_text:
        raise HTTPException(
            status_code=400,
            detail="Both documents must have extractable text for a comparison.",
        )

    prompt = (
        "Compare two versions of a recurring executive report. Tell a NED, "
        "in plain English, how the second version has evolved from the first. "
        "Stay neutral. Surface drift, softening, and quiet omissions — these "
        "are the parts NEDs actually want flagged. Return JSON ONLY:\n"
        '{\n'
        '  "what_changed": "<2-3 sentences — the headline of the drift>",\n'
        '  "added_or_strengthened": [\n'
        '    "<plain-language bullet — claim/figure/promise that is new or now stronger>",\n'
        '    "<...3-5 bullets total>"\n'
        '  ],\n'
        '  "weakened_or_removed": [\n'
        '    "<bullet — claim/figure that is gone or now hedged>",\n'
        '    "<...3-5 bullets total>"\n'
        '  ],\n'
        '  "questions_for_management": [\n'
        '    "<question NED should put on the table>",\n'
        '    "<question 2>"\n'
        '  ]\n'
        '}\n\n'
        f"=== PREVIOUS VERSION ({parent.get('name')}, {parent.get('created_at')}) ===\n"
        f"{prev_text}\n\n"
        f"=== CURRENT VERSION ({d.get('name')}, {d.get('created_at')}) ===\n"
        f"{cur_text}"
    )
    out = await llm_call_llm(
        module="document.evolution_diff",
        user_query=prompt,
        context_object=None,
        session_context={"session_id": f"docevo-{doc_id}"},
        data_trust={"overall": d.get("data_trust", "unrated")},
        response_format="json",
    )
    parsed = parse_json_response(out.get("response", "")) or {}
    diff = {
        "what_changed": (parsed.get("what_changed") or "").strip(),
        "added_or_strengthened": [
            str(x).strip() for x in (parsed.get("added_or_strengthened") or [])
            if str(x).strip()
        ][:5],
        "weakened_or_removed": [
            str(x).strip() for x in (parsed.get("weakened_or_removed") or [])
            if str(x).strip()
        ][:5],
        "questions_for_management": [
            str(x).strip() for x in (parsed.get("questions_for_management") or [])
            if str(x).strip()
        ][:3],
        "mode": out.get("mode"),
        "generated_at": _iso(_now()),
    }
    await db.documents.update_one(
        {"id": doc_id, "context_id": context_id},
        {"$set": {
            "evolution_diff": {"previous_doc_id": parent_id, "diff": diff},
            "updated_at": _iso(_now()),
        }},
    )
    return {
        "previous_doc": {
            "id": parent["id"], "name": parent.get("name"),
            "created_at": parent.get("created_at"),
        },
        "diff": diff,
    }


@router.delete("/contexts/{context_id}/documents/{doc_id}")
async def archive_document(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    d = await db.documents.find_one({"id": doc_id, "context_id": context_id})
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    if d.get("uploaded_by") != ctx["account"]["id"] and ctx["membership"].get("sub_role") != "admin":
        raise HTTPException(status_code=403, detail="Only the uploader or a context admin can archive this document.")
    await db.documents.update_one(
        {"id": doc_id},
        {"$set": {"status": "archived", "archived_at": _iso(_now())}},
    )
    try:
        delete_from_storage(d.get("storage_key", ""))
    except Exception as e:
        logger.warning(f"delete_from_storage failed: {e}")
    await write_audit(context_id, ctx["account"]["id"], "document.archived", "document", doc_id, {})
    return {"ok": True}


@router.get("/contexts/{context_id}/documents/{doc_id}/download")
async def download_document(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    d = await db.documents.find_one({"id": doc_id, "context_id": context_id})
    if not d or d.get("status") == "archived":
        raise HTTPException(status_code=404, detail="Document not found")
    # Phase 10: S3 backend → 302 to a presigned URL. Local backend →
    # keep the streaming response for dev / tests (no presign target).
    from services import storage_service
    backend = storage_service.get_storage()
    if backend.backend == "s3":
        try:
            url = backend.get_presigned_url(
                d["storage_key"],
                ttl_seconds=300,
                response_content_disposition=f'attachment; filename="{d.get("original_filename", "download")}"',
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"presign failed: {e}")
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=url, status_code=302)
    try:
        data = read_from_storage(d["storage_key"])
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Underlying file is no longer available")
    return StreamingResponse(
        io.BytesIO(data),
        media_type=d.get("mime_type", "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{d.get("original_filename", "download")}"'},
    )


# ---------------------------------------------------------------------------
# Paragraph anchors (Reading Viewer · Phase 1, Advisory 2)
#
# Lazy-on-read endpoint + nightly cron sweep. Schema additions on `db.documents`:
#   - paragraphs: [{id, page, paragraph_number, text, char_start, char_end}]
#   - paragraphs_computed_at: iso str | null
#   - paragraphs_version: int (bumps if algorithm changes)
# Existing docs continue to work; anchors materialise on first read or on the
# nightly sweep, whichever comes first.
# ---------------------------------------------------------------------------
import os as _os
from fastapi import Header

from paragraph_anchors import compute_paragraphs, PARAGRAPH_ANCHOR_VERSION


async def _materialise_paragraphs(d: Dict[str, Any]) -> Dict[str, Any]:
    """Compute + persist paragraphs[] for a document. Idempotent.

    Phase 12.2 ITEM B — paragraphs are computed FIRST (anchor IDs are
    content hashes of the *original* text, so they stay stable across
    redaction). Synisense then runs per-paragraph in `shield_reversible`
    mode; we replace `paragraphs[i].text` with the redacted version and
    persist `shield_map_id` next to it so context members can reverse
    server-side via `/paragraphs/{pid}/original`. The TTL on the shield
    map (24h default) means originals reclaim themselves automatically.

    Returns the paragraph payload. Raises ValueError if the doc has no
    extracted_text yet (caller decides whether that's a 409 or a skip)."""
    text = (d.get("extracted_text") or "").strip()
    if not text:
        raise ValueError("Document has no extracted text yet.")
    payload = compute_paragraphs(d["id"], d["extracted_text"])

    # Run Synisense per paragraph. We do this AFTER the anchor compute
    # because anchor IDs are content hashes of the original — running
    # before would change every anchor ID on every reupload.
    redacted_paragraphs: List[Dict[str, Any]] = []
    syn_total_spans = 0
    syn_failed = False
    try:
        from services.synisense import run as syn_run
        for p in payload["paragraphs"]:
            try:
                out = await syn_run(
                    text=p.get("text") or "",
                    context_id=d.get("context_id") or "",
                    surface="ingest",
                    mode="shield_reversible",
                    account_id=None,
                )
                p_redacted = dict(p)
                p_redacted["text"] = out["redacted_text"]
                p_redacted["text_redacted"] = True
                if out.get("shield_map_id"):
                    p_redacted["shield_map_id"] = out["shield_map_id"]
                p_redacted["synisense_span_count"] = len(out.get("spans") or [])
                syn_total_spans += len(out.get("spans") or [])
                redacted_paragraphs.append(p_redacted)
            except Exception:  # noqa: BLE001 — degrade per-paragraph
                redacted_paragraphs.append(dict(p))
    except Exception:  # noqa: BLE001 — module-level degrade
        syn_failed = True
        redacted_paragraphs = list(payload["paragraphs"])

    update = {
        "paragraphs": redacted_paragraphs,
        "paragraphs_computed_at": payload["computed_at"],
        "paragraphs_version": payload["version"],
        "paragraphs_page_count": payload["page_count"],
        "synisense_version": 0 if syn_failed else 1,
        "synisense_paragraph_spans_total": syn_total_spans,
    }
    await db.documents.update_one({"id": d["id"]}, {"$set": update})
    payload["paragraphs"] = redacted_paragraphs
    payload["synisense_version"] = update["synisense_version"]
    payload["synisense_paragraph_spans_total"] = syn_total_spans
    return payload


@router.get("/contexts/{context_id}/documents/{doc_id}/paragraphs")
async def get_document_paragraphs(
    context_id: str, doc_id: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Return the paragraph anchors for this document. Lazy-computes on
    first read; subsequent reads return the cached array. The doc row is
    updated in-place with `paragraphs[]`, `paragraphs_computed_at`, and
    `paragraphs_version`.

    Response shape:
        {
          "doc_id": str,
          "paragraphs": [...],
          "page_count": int,
          "computed_at": str (iso),
          "version": int
        }
    """
    d = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id},
        {"_id": 0},
    )
    if not d or d.get("status") == "archived":
        raise HTTPException(status_code=404, detail="Document not found")

    cached = (
        d.get("paragraphs")
        and d.get("paragraphs_computed_at")
        and (d.get("paragraphs_version") or 0) >= PARAGRAPH_ANCHOR_VERSION
    )
    if cached:
        return {
            "doc_id": doc_id,
            "paragraphs": d["paragraphs"],
            "page_count": d.get("paragraphs_page_count", 1),
            "computed_at": d["paragraphs_computed_at"],
            "version": d["paragraphs_version"],
        }

    # Lazy compute.
    if not (d.get("extracted_text") or "").strip():
        raise HTTPException(
            status_code=409,
            detail="Document extraction is incomplete; paragraphs not yet computable.",
        )
    try:
        payload = await _materialise_paragraphs(d)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {
        "doc_id": doc_id,
        "paragraphs": payload["paragraphs"],
        "page_count": payload["page_count"],
        "computed_at": payload["computed_at"],
        "version": payload["version"],
    }


@router.get("/contexts/{context_id}/documents/{doc_id}/paragraphs/{pid}/original")
async def get_paragraph_original(
    context_id: str, doc_id: str, pid: str,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    """Phase 12.2 ITEM B — server-side shield_map reversal for a single
    paragraph. Members of the context can read the un-redacted original
    via this endpoint as long as the per-paragraph shield map hasn't
    expired (24h default TTL). Never returns the shield_map itself or
    any encrypted bytes — only the plain-text reversal. Per-request
    audit row written via `synisense.unshield`. After TTL expiry, the
    shield_map is gone and the endpoint returns 410.
    """
    d = await db.documents.find_one(
        {"id": doc_id, "context_id": context_id},
        {"_id": 0, "paragraphs": 1},
    )
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    paragraph = next(
        (p for p in (d.get("paragraphs") or []) if p.get("id") == pid), None,
    )
    if not paragraph:
        raise HTTPException(status_code=404, detail="Paragraph not found")
    smid = paragraph.get("shield_map_id")
    if not smid:
        # Paragraph had no redactions — original equals current text.
        return {"id": pid, "original_text": paragraph.get("text") or "",
                "had_redactions": False}
    # Reverse server-side. unshield writes its own audit row.
    from services.synisense import unshield
    mapping = await unshield(
        smid, surface="ingest", account_id=ctx["account"]["id"],
    )
    if not mapping:
        raise HTTPException(
            status_code=410,
            detail="Paragraph original is no longer available — shield map expired (24h TTL).",
        )
    # Apply the reverse mapping to reconstruct the original text from the
    # redacted text. Replacement tokens are deterministic so this is exact.
    text = paragraph.get("text") or ""
    for replacement, original in mapping.items():
        text = text.replace(replacement, original)
    return {
        "id": pid,
        "original_text": text,
        "had_redactions": True,
        "span_count": paragraph.get("synisense_span_count", 0),
    }


@router.post("/cron/paragraph-anchors-sweep")
async def cron_paragraph_anchors_sweep(
    x_cron_secret: Optional[str] = Header(default=None, alias="X-Cron-Secret"),
    limit: int = 100,
):
    """Nightly batch sweep — compute paragraphs[] for any docs that are
    missing them or have stale `paragraphs_version`. Designed for the
    APScheduler entry registered in server.py @ 03:00 UTC.

    Gated by `X-Cron-Secret` matching the `AKKI_CRON_SECRET` env var.
    Anonymous callers get 401; missing env var fails closed with 503.
    Per-doc timeout is enforced by an asyncio.wait_for at the caller."""
    expected = _os.environ.get("AKKI_CRON_SECRET")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Cron disabled — AKKI_CRON_SECRET not configured.",
        )
    if not x_cron_secret or x_cron_secret != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Cron-Secret header.")

    cap = max(1, min(limit, 500))
    # Pick docs where anchors are missing OR stale.
    cursor = db.documents.find(
        {
            "$or": [
                {"paragraphs_computed_at": {"$exists": False}},
                {"paragraphs_computed_at": None},
                {"paragraphs_version": {"$lt": PARAGRAPH_ANCHOR_VERSION}},
            ],
            "status": {"$ne": "archived"},
            "extracted_text": {"$exists": True, "$ne": ""},
        },
        {"_id": 0},
    ).limit(cap)

    swept = 0
    failed = 0
    skipped_no_text = 0

    import asyncio
    async for d in cursor:
        if not (d.get("extracted_text") or "").strip():
            skipped_no_text += 1
            continue
        try:
            await asyncio.wait_for(_materialise_paragraphs(d), timeout=30.0)
            swept += 1
            await write_audit(
                d.get("context_id", ""), "system", "paragraphs.batch_compute",
                "document", d["id"],
                {"version": PARAGRAPH_ANCHOR_VERSION, "outcome": "ok"},
            )
        except asyncio.TimeoutError:
            failed += 1
            logger.warning("paragraph-anchors-sweep: timeout for doc %s", d["id"])
            await write_audit(
                d.get("context_id", ""), "system", "paragraphs.batch_compute",
                "document", d["id"],
                {"version": PARAGRAPH_ANCHOR_VERSION, "outcome": "timeout"},
            )
        except Exception as e:  # noqa: BLE001
            failed += 1
            logger.warning("paragraph-anchors-sweep: failed for doc %s: %s", d["id"], e)
            await write_audit(
                d.get("context_id", ""), "system", "paragraphs.batch_compute",
                "document", d["id"],
                {"version": PARAGRAPH_ANCHOR_VERSION, "outcome": "error", "error": str(e)[:200]},
            )

    return {
        "swept": swept,
        "skipped_no_text": skipped_no_text,
        "failed": failed,
        "version": PARAGRAPH_ANCHOR_VERSION,
        "limit": cap,
    }
