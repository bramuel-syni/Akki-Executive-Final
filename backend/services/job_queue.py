"""Async job queue (Chunk 2, 2026-05-13).

A thin helper around `db.async_jobs` for the three QA-blocking
long-running endpoints (DJ-R03 brief, DJ-R05 signals, CM-R04 cycle
compilation). Each of those used to run its LLM/IO synchronously and
blew through the gateway's ~100s timeout (524 / 502 at the edge).

The helper deliberately mirrors the shape already in use by
`work_studio_export.py` (its own `db.work_studio_exports` collection
follows the same lifecycle) — small, single-collection, no Celery /
Redis dependency. We use `asyncio.create_task` rather than FastAPI's
`BackgroundTasks` because the latter is awaited inside Starlette's
TestClient / ASGITransport, defeating the whole point of the dispatch
in test environments. `create_task` is also semantically better for
production: it releases the gateway connection the instant the 202
is sent, instead of waiting for the response cycle to complete.

Lifecycle::

    queued ──▶ running ──▶ completed
                       └─▶ failed

Idempotency
-----------
`create_job`, `mark_*`, and `get_job` are all idempotent at the row
level. Re-calling `mark_completed` is a no-op if the row already
terminated. Re-calling `mark_failed` overwrites the error message
(useful for the worker_crash wrapper pattern).

Authorisation
-------------
Jobs are scoped per-(account, context). `get_job` requires the caller
to be the row's account_id — different users cannot poll each other's
jobs. The polling endpoint in `routers/async_jobs.py` enforces this.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional, Set

from core import db, iso, now

logger = logging.getLogger("akki.job_queue")

TERMINAL = ("completed", "failed", "cancelled")

# Strong references to in-flight worker tasks. Without this, Python may
# garbage-collect the task before it completes if no other reference
# holds it — see https://docs.python.org/3/library/asyncio-task.html#creating-tasks
# ("Important — Save a reference to the result of this function").
_IN_FLIGHT: Set[asyncio.Task] = set()


def spawn(coro: Awaitable[Any]) -> asyncio.Task:
    """Fire-and-forget scheduling that keeps a strong reference."""
    task = asyncio.create_task(coro)
    _IN_FLIGHT.add(task)
    task.add_done_callback(_IN_FLIGHT.discard)
    return task


async def create_job(
    *,
    kind: str,
    account_id: str,
    context_id: str,
    input_summary: Optional[Dict[str, Any]] = None,
) -> str:
    """Insert a queued job row and return its id.

    `kind` is a short string identifying the job class (e.g.
    `briefing.create`, `signals.generate`, `cycle.draft_compilation`).
    `input_summary` is optional human-readable metadata the polling
    endpoint can echo back so the UI can show "Generating Brief…".
    """
    job_id = str(uuid.uuid4())
    await db.async_jobs.insert_one({
        "id": job_id,
        "kind": kind,
        "account_id": account_id,
        "context_id": context_id,
        "status": "queued",
        "input_summary": input_summary or {},
        "result": None,
        "error": None,
        "created_at": iso(now()),
        "started_at": None,
        "completed_at": None,
    })
    return job_id


async def mark_running(job_id: str) -> None:
    await db.async_jobs.update_one(
        {"id": job_id},
        {"$set": {"status": "running", "started_at": iso(now())}},
    )


async def mark_completed(job_id: str, result: Dict[str, Any]) -> None:
    """Terminal-state safe: if the row already terminated, we no-op."""
    await db.async_jobs.update_one(
        {"id": job_id, "status": {"$nin": list(TERMINAL)}},
        {"$set": {
            "status": "completed",
            "result": result,
            "completed_at": iso(now()),
        }},
    )


async def mark_failed(job_id: str, error: str) -> None:
    """Worker-crash safe: overwrites any prior error string but
    refuses to undo a `completed` state."""
    await db.async_jobs.update_one(
        {"id": job_id, "status": {"$ne": "completed"}},
        {"$set": {
            "status": "failed",
            "error": error[:1500],
            "completed_at": iso(now()),
        }},
    )


async def get_job(job_id: str, *, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Look up a job row. When `account_id` is passed, the row is
    only returned if it belongs to that caller — otherwise the
    polling endpoint returns 404 (same response shape as "doesn't
    exist", so we don't leak existence of foreign jobs)."""
    q: Dict[str, Any] = {"id": job_id}
    if account_id is not None:
        q["account_id"] = account_id
    return await db.async_jobs.find_one(q, {"_id": 0})


async def is_terminal(job_id: str) -> bool:
    row = await db.async_jobs.find_one({"id": job_id}, {"_id": 0, "status": 1})
    return bool(row and row.get("status") in TERMINAL)
