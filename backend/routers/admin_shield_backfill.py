"""H4 — Admin endpoints for Shield v1.x back-fill.

Two endpoints:

  * ``POST /api/admin/shield/backfill`` — kick off an async back-fill
    job. Returns ``{job_id}`` immediately; processing happens in a
    background task. Body params:
      - ``batch_size`` (int, default 50)
      - ``sleep_ms`` (int, default 200)
      - ``dry_run`` (bool, default false)
      - ``limit`` (int, optional — for safe staged runs)

  * ``GET /api/admin/shield/backfill/status`` — last/current job
    summary.

  * ``GET /api/admin/shield/backfill/{job_id}/status`` — specific job.

Superadmin only. Read-only consumer of ``services.backfill_shield_v1``.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core import db, get_current_account
from services.backfill_shield_v1 import (
    DEFAULT_BATCH_SIZE, DEFAULT_SLEEP_MS, run_backfill,
)

router = APIRouter(prefix="/api/admin/shield", tags=["admin", "shield", "backfill"])


async def _require_superadmin(
    account: Dict[str, Any] = Depends(get_current_account),
) -> Dict[str, Any]:
    if not account.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Superadmin only.")
    return account


class BackfillRequest(BaseModel):
    batch_size: int = Field(DEFAULT_BATCH_SIZE, ge=1, le=500)
    sleep_ms: int = Field(DEFAULT_SLEEP_MS, ge=0, le=10000)
    dry_run: bool = False
    limit: Optional[int] = Field(None, ge=1, le=100000)


async def _start_job(req: BackfillRequest, job_id: str) -> None:
    """Coroutine driver — runs the back-fill and updates job status."""
    try:
        await run_backfill(
            batch_size=req.batch_size,
            sleep_ms=req.sleep_ms,
            dry_run=req.dry_run,
            limit=req.limit,
            job_id=job_id,
        )
    except Exception as exc:  # noqa: BLE001
        await db.backfill_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": f"{type(exc).__name__}: {str(exc)[:300]}",
            }},
            upsert=True,
        )


@router.post("/backfill")
async def kick_off_backfill(
    req: BackfillRequest,
    background: BackgroundTasks,
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """Kick off an async back-fill. Returns immediately with ``job_id``."""
    job_id = "bf-" + datetime.now(timezone.utc).strftime(
        "%Y%m%d-%H%M%S",
    ) + "-" + datetime.now(timezone.utc).strftime("%f")[:6]

    # Refuse to overlap with an already-running job.
    in_flight = await db.backfill_jobs.find_one(
        {"status": "running"}, {"_id": 0, "id": 1},
    )
    if in_flight:
        raise HTTPException(
            status_code=409,
            detail=f"Back-fill already running: {in_flight['id']}",
        )

    background.add_task(_start_job, req, job_id)
    return {
        "job_id": job_id,
        "status": "queued",
        "dry_run": req.dry_run,
        "batch_size": req.batch_size,
        "sleep_ms": req.sleep_ms,
        "limit": req.limit,
    }


@router.get("/backfill/status")
async def latest_status(
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """Latest back-fill summary (running or most-recent completed)."""
    job = await db.backfill_jobs.find_one(
        {}, {"_id": 0}, sort=[("started_at", -1)],
    )
    if not job:
        return {
            "running": False,
            "last_batch_id": None,
            "last_completed_at": None,
            "total_chats_scanned": 0,
            "total_chats_backfilled": 0,
            "total_audit_rows_written": 0,
            "chats_with_pre_v1_pii_detected": 0,
            "errors_count": 0,
            "estimated_remaining_seconds": 0,
        }

    pending = await db.chats.count_documents({
        "$or": [
            {"synisense_audit_ids": {"$exists": False}},
            {"synisense_audit_ids": {"$size": 0}},
        ],
        "backfill_metadata.partial": {"$ne": False},
    })

    # Naive ETA: assume same per-chat rate as the current job.
    rate_chats_per_s = 0.0
    if job.get("started_at") and job.get("total_chats_scanned"):
        try:
            started = datetime.fromisoformat(
                job["started_at"].replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            elapsed_s = max(1.0, (now - started).total_seconds())
            rate_chats_per_s = job["total_chats_scanned"] / elapsed_s
        except Exception:  # noqa: BLE001
            rate_chats_per_s = 0.0
    eta_s = int(pending / rate_chats_per_s) if rate_chats_per_s > 0 else 0

    return {
        "running": job.get("status") == "running",
        "last_batch_id": job.get("id"),
        "last_completed_at": job.get("completed_at"),
        "total_chats_scanned": job.get("total_chats_scanned", 0),
        "total_chats_backfilled": job.get("total_chats_backfilled", 0),
        "total_audit_rows_written": job.get("total_audit_rows_written", 0),
        "chats_with_pre_v1_pii_detected": job.get(
            "chats_with_pre_v1_pii_detected", 0,
        ),
        "errors_count": job.get("errors_count", 0),
        "estimated_remaining_seconds": eta_s,
        "pending_chats": pending,
    }


@router.get("/backfill/{job_id}/status")
async def job_status(
    job_id: str,
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """Per-job summary."""
    job = await db.backfill_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.get("/backfill/{job_id}/log")
async def job_log(
    job_id: str,
    limit: int = Query(200, ge=1, le=5000),
    status: Optional[str] = Query(
        None, pattern="^(completed|failed)$",
    ),
    _admin: Dict[str, Any] = Depends(_require_superadmin),
) -> Dict[str, Any]:
    """Per-chat back-fill log for a job."""
    match: Dict[str, Any] = {"batch_id": job_id}
    if status:
        match["status"] = status
    rows = await db.backfill_log.find(
        match, {"_id": 0},
    ).sort([("started_at", 1)]).limit(limit).to_list(length=limit)
    return {"job_id": job_id, "rows": rows, "count": len(rows)}
