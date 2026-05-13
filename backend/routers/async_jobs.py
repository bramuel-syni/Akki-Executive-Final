"""Async job polling endpoint (Chunk 2, 2026-05-13).

`GET /api/jobs/{job_id}` — single endpoint the frontend polls while
a long-running task is in flight.

Authorisation
-------------
The polling endpoint scopes by `account_id`: callers can only see
their own jobs. A 404 is returned when (a) the job_id doesn't exist
OR (b) the job exists but belongs to a different account — we don't
leak existence-vs-not-existence across the privacy boundary.

Response shape (always)::

    {
      "id":             "<job uuid>",
      "kind":           "<short job class id>",
      "status":         "queued" | "running" | "completed" | "failed",
      "input_summary":  {…},          # echo of what the caller submitted
      "result":         {…} | null,   # populated when status=completed
      "error":          "string" | null,  # populated when status=failed
      "created_at":     iso8601,
      "started_at":     iso8601 | null,
      "completed_at":   iso8601 | null,
    }

The frontend should poll every 2–3s with exponential backoff once
the wait exceeds ~30s. Cancellation is not implemented in this chunk
(documented in the diagnosis doc as an intentional limitation —
adding it requires Mongo CAS on every model call which is heavier
than the QA bar requires).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core import get_current_account
from services.job_queue import get_job

logger = logging.getLogger("akki.async_jobs")

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/jobs/{job_id}")
async def poll_job(
    job_id: str,
    account: Dict[str, Any] = Depends(get_current_account),
):
    row = await get_job(job_id, account_id=account["id"])
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return row
