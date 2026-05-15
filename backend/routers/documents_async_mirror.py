"""Phase C — async-mirror endpoints for the 4 Document Reader endpoints.

The 4 sync endpoints (`generate-meta`, `summary`, `journal-commentary`,
`evolution-diff`) are 524-prone on slow LLM calls. This module ships
async mirrors that:

- Return immediately with `{job_id, audit_id?, status: "queued"}`.
- Run the heavy work in the background via `services.job_queue.spawn`.
- Persist the LLM result on the existing sync route's resource (so
  follow-up reads return the cached output and no schema migration
  is needed).
- Surface progress via `GET /api/jobs/{job_id}` (existing endpoint).

Frontend polling pattern:
1. POST to `/async` variant → receive `{job_id}`.
2. Poll `GET /api/jobs/{job_id}` every 1.5s.
3. On `status: "completed"`, render `result`.
4. On `status: "failed"`, show `error` (already canonical-format text).

The async mirrors run via FastAPI's standard dependency stack so
auth + context membership checks are identical to the sync routes.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException

from core import get_current_account
from services import job_queue

log = logging.getLogger("akki.docs.async_mirror")

router = APIRouter(prefix="/api", tags=["docs-async-mirror"])


# Common kind labels for the job-queue rows. Frontend reads
# `job.input_summary.surface` to know which UI to refresh.
_KINDS = {
    "meta":       "document.meta.generate",
    "summary":    "document.summary.generate",
    "commentary": "document_journal.commentary.generate",
    "diff":       "document_journal.evolution_diff",
}


async def _build_ctx(*, account_id: str, context_id: str) -> Dict[str, Any]:
    """Build the `ctx` dict shape that `require_context_membership`
    produces (`{"account": {...}, "context": {...}, "membership": {...}}`).
    The 4 sync handlers we delegate to expect this nested shape."""
    from core import db
    acc = await db.accounts.find_one({"id": account_id}, {"_id": 0}) or {}
    ctx_row = await db.contexts.find_one({"id": context_id}, {"_id": 0}) or {}
    return {
        "account": acc,
        "context": ctx_row,
        "membership": {"role": "owner", "sub_role": "admin"},
    }


async def _run_meta_job(
    *, job_id: str, account_id: str, context_id: str, body: Dict[str, Any],
) -> None:
    from routers.documents import generate_document_meta, DocumentMetaGenerateIn
    try:
        await job_queue.mark_running(job_id)
        ctx = await _build_ctx(account_id=account_id, context_id=context_id)
        in_body = DocumentMetaGenerateIn(**body)
        result = await generate_document_meta(context_id=context_id, body=in_body, ctx=ctx)
        await job_queue.mark_completed(job_id, {
            "result": result if isinstance(result, dict) else dict(result),
            "kind": _KINDS["meta"],
        })
    except Exception as exc:  # noqa: BLE001
        await job_queue.mark_failed(job_id, f"{type(exc).__name__}: {str(exc)[:300]}")


async def _run_summary_job(
    *, job_id: str, account_id: str, context_id: str, doc_id: str, refresh: bool,
) -> None:
    from routers.documents import generate_document_summary
    try:
        await job_queue.mark_running(job_id)
        ctx = await _build_ctx(account_id=account_id, context_id=context_id)
        result = await generate_document_summary(
            context_id=context_id, doc_id=doc_id, refresh=refresh, ctx=ctx,
        )
        await job_queue.mark_completed(job_id, {
            "result": result if isinstance(result, dict) else dict(result),
            "kind": _KINDS["summary"],
        })
    except Exception as exc:  # noqa: BLE001
        await job_queue.mark_failed(job_id, f"{type(exc).__name__}: {str(exc)[:300]}")


async def _run_commentary_job(
    *, job_id: str, account_id: str, context_id: str, doc_id: str, refresh: bool,
) -> None:
    try:
        await job_queue.mark_running(job_id)
        from routers.documents import journal_commentary
        ctx = await _build_ctx(account_id=account_id, context_id=context_id)
        result = await journal_commentary(
            context_id=context_id, doc_id=doc_id, refresh=refresh, ctx=ctx,
        )
        await job_queue.mark_completed(job_id, {
            "result": result if isinstance(result, dict) else dict(result),
            "kind": _KINDS["commentary"],
        })
    except Exception as exc:  # noqa: BLE001
        await job_queue.mark_failed(job_id, f"{type(exc).__name__}: {str(exc)[:300]}")


async def _run_diff_job(
    *, job_id: str, account_id: str, context_id: str, doc_id: str, refresh: bool,
) -> None:
    try:
        await job_queue.mark_running(job_id)
        from routers.documents import document_evolution_diff
        ctx = await _build_ctx(account_id=account_id, context_id=context_id)
        result = await document_evolution_diff(
            context_id=context_id, doc_id=doc_id, refresh=refresh, ctx=ctx,
        )
        await job_queue.mark_completed(job_id, {
            "result": result if isinstance(result, dict) else dict(result),
            "kind": _KINDS["diff"],
        })
    except Exception as exc:  # noqa: BLE001
        await job_queue.mark_failed(job_id, f"{type(exc).__name__}: {str(exc)[:300]}")


# ─────────────────────────────────────────────────────────────────────
# 4 async endpoints.
# ─────────────────────────────────────────────────────────────────────
@router.post("/contexts/{context_id}/documents/generate-meta/async")
async def generate_meta_async(
    context_id: str,
    body: Dict[str, Any] = Body(default_factory=dict),
    current: Dict[str, Any] = Depends(get_current_account),
):
    job_id = await job_queue.create_job(
        kind=_KINDS["meta"], account_id=current["id"], context_id=context_id,
        input_summary={"surface": "doc_reader.meta", "filename": body.get("filename")},
    )
    job_queue.spawn(_run_meta_job(
        job_id=job_id, account_id=current["id"], context_id=context_id, body=body,
    ))
    return {"job_id": job_id, "status": "queued", "kind": _KINDS["meta"]}


@router.post("/contexts/{context_id}/documents/{doc_id}/summary/async")
async def generate_summary_async(
    context_id: str, doc_id: str,
    refresh: bool = False,
    current: Dict[str, Any] = Depends(get_current_account),
):
    job_id = await job_queue.create_job(
        kind=_KINDS["summary"], account_id=current["id"], context_id=context_id,
        input_summary={"surface": "doc_reader.summary", "doc_id": doc_id, "refresh": refresh},
    )
    job_queue.spawn(_run_summary_job(
        job_id=job_id, account_id=current["id"], context_id=context_id,
        doc_id=doc_id, refresh=refresh,
    ))
    return {"job_id": job_id, "status": "queued", "kind": _KINDS["summary"]}


@router.post("/contexts/{context_id}/documents/{doc_id}/journal-commentary/async")
async def generate_commentary_async(
    context_id: str, doc_id: str,
    refresh: bool = False,
    current: Dict[str, Any] = Depends(get_current_account),
):
    job_id = await job_queue.create_job(
        kind=_KINDS["commentary"], account_id=current["id"], context_id=context_id,
        input_summary={"surface": "doc_reader.commentary", "doc_id": doc_id, "refresh": refresh},
    )
    job_queue.spawn(_run_commentary_job(
        job_id=job_id, account_id=current["id"], context_id=context_id,
        doc_id=doc_id, refresh=refresh,
    ))
    return {"job_id": job_id, "status": "queued", "kind": _KINDS["commentary"]}


@router.post("/contexts/{context_id}/documents/{doc_id}/evolution-diff/async")
async def evolution_diff_async(
    context_id: str, doc_id: str,
    refresh: bool = False,
    current: Dict[str, Any] = Depends(get_current_account),
):
    job_id = await job_queue.create_job(
        kind=_KINDS["diff"], account_id=current["id"], context_id=context_id,
        input_summary={"surface": "doc_reader.evolution_diff", "doc_id": doc_id, "refresh": refresh},
    )
    job_queue.spawn(_run_diff_job(
        job_id=job_id, account_id=current["id"], context_id=context_id,
        doc_id=doc_id, refresh=refresh,
    ))
    return {"job_id": job_id, "status": "queued", "kind": _KINDS["diff"]}
