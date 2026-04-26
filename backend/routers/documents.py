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
    ACCEPT_EXT, MAX_BYTES, virus_scan_stub, save_to_storage, read_from_storage,
    delete_from_storage, extract_text, make_preview,
)
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
    }


class DocumentTrustUpdate(BaseModel):
    data_trust: Literal["trusted", "mixed", "weak"]


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

    clean, reason = virus_scan_stub(data, filename)
    if not clean:
        raise HTTPException(status_code=400, detail=f"Rejected by virus scan: {reason}")

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
    return out


@router.patch("/contexts/{context_id}/documents/{doc_id}")
async def update_document_trust(
    context_id: str, doc_id: str,
    body: DocumentTrustUpdate,
    ctx: Dict[str, Any] = Depends(require_context_membership()),
):
    res = await db.documents.update_one(
        {"id": doc_id, "context_id": context_id},
        {"$set": {"data_trust": body.data_trust, "updated_at": _iso(_now())}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    await write_audit(context_id, ctx["account"]["id"], "document.trust_updated", "document", doc_id,
                      {"data_trust": body.data_trust})
    d = await db.documents.find_one({"id": doc_id}, {"_id": 0, "storage_key": 0, "extracted_text": 0})
    return sanitize_doc(d)


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
    try:
        data = read_from_storage(d["storage_key"])
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Underlying file is no longer available")
    return StreamingResponse(
        io.BytesIO(data),
        media_type=d.get("mime_type", "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{d.get("original_filename", "download")}"'},
    )
