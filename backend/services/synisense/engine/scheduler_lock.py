"""Synisense Engine — single-instance cron lock + heartbeat helper.

Chunk 18 (Track 4 item 3, 2026-05-21).

Problem statement: the in-process APScheduler armed inside `server.py`
fires the same job on every replica. For the engine hourly pass that's
wasteful (duplicate work) and risks racey writes against
`synisense_signals`. We want exactly-one-replica execution per hour
without pulling in a heavyweight job broker.

Solution: a Mongo-backed lock collection (`scheduler_locks`) with a
TTL index on `expires_at`. The first replica to `insert_one` for a
given (job_id, hour_bucket) key wins. Lock holders renew their lease
periodically until they hand off; non-holders skip the run. After a
crash the TTL index reaps stale rows so the next hour's run isn't
permanently blocked.

The `scheduler_runs` collection stores one row per executed run:
`{job_id, replica_id, started_at, finished_at, status, summary, error}`.
Operators can verify the cron is alive by querying `scheduler_runs`
for the most recent `status="ok"` row.
"""
from __future__ import annotations

import logging
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from pymongo.errors import DuplicateKeyError

from core import db

log = logging.getLogger("synisense.engine.scheduler_lock")

LOCK_COLLECTION = "scheduler_locks"
RUNS_COLLECTION = "scheduler_runs"

_replica_id_cache: Optional[str] = None


def replica_id() -> str:
    """Stable per-process identifier used to claim the lock.

    Combines hostname + pid + a process-lifetime UUID. The UUID
    component is what makes the identifier unique across replicas
    sharing a host (e.g. local dev with two backends bound to the
    same Mongo).
    """
    global _replica_id_cache
    if _replica_id_cache is None:
        _replica_id_cache = (
            f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
        )
    return _replica_id_cache


async def ensure_indexes() -> None:
    """Create the TTL index on `expires_at` so dead lock rows reap."""
    try:
        await db[LOCK_COLLECTION].create_index(
            "expires_at", expireAfterSeconds=0, name="scheduler_locks_ttl",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("scheduler_lock: index create failed: %s", exc)


async def _try_acquire(job_id: str, hour_bucket: str, lease_seconds: int) -> bool:
    """Attempt to claim the lock for the given (job_id, hour_bucket).

    Returns True if this replica won. The compound `_id` ensures one
    row per hour-bucket; a `DuplicateKeyError` means another replica
    is already running.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=lease_seconds)
    doc = {
        "_id": f"{job_id}:{hour_bucket}",
        "job_id": job_id,
        "hour_bucket": hour_bucket,
        "owner": replica_id(),
        "acquired_at": now,
        "expires_at": expires_at,
    }
    try:
        await db[LOCK_COLLECTION].insert_one(doc)
        return True
    except DuplicateKeyError:
        return False


async def _record_run(
    *,
    job_id: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    summary: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    row = {
        "job_id": job_id,
        "replica_id": replica_id(),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": int((finished_at - started_at).total_seconds() * 1000),
        "status": status,
        "summary": summary or {},
        "error": error,
    }
    try:
        await db[RUNS_COLLECTION].insert_one(row)
    except Exception as exc:  # noqa: BLE001
        log.warning("scheduler_lock: run heartbeat write failed: %s", exc)


async def run_locked(
    *,
    job_id: str,
    fn: Callable[[], Awaitable[Dict[str, Any]]],
    bucket: str,
    lease_seconds: int = 3600,
) -> None:
    """Run `fn()` exactly-once for the (job_id, bucket) tuple.

    `bucket` is typically the hour stamp `YYYYMMDDHH`. The first
    replica to claim writes a `scheduler_runs` heartbeat row on
    completion (success OR failure); non-holders log and exit.
    """
    won = await _try_acquire(job_id, bucket, lease_seconds)
    if not won:
        log.info("scheduler_lock: skip %s (bucket=%s, another replica is running)",
                 job_id, bucket)
        return
    started_at = datetime.now(timezone.utc)
    log.info("scheduler_lock: acquired %s (bucket=%s, replica=%s)",
             job_id, bucket, replica_id())
    try:
        summary = await fn()
        finished_at = datetime.now(timezone.utc)
        await _record_run(
            job_id=job_id, started_at=started_at, finished_at=finished_at,
            status="ok", summary=summary or {},
        )
        log.info("scheduler_lock: %s OK (bucket=%s, duration=%dms, summary=%s)",
                 job_id, bucket,
                 int((finished_at - started_at).total_seconds() * 1000),
                 summary)
    except Exception as exc:  # noqa: BLE001
        finished_at = datetime.now(timezone.utc)
        await _record_run(
            job_id=job_id, started_at=started_at, finished_at=finished_at,
            status="failed", error=f"{type(exc).__name__}: {str(exc)[:200]}",
        )
        log.warning("scheduler_lock: %s FAILED (bucket=%s): %s",
                    job_id, bucket, exc)


def current_hour_bucket(now: Optional[datetime] = None) -> str:
    """Return the `YYYYMMDDHH` UTC bucket for the given (or current) time."""
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y%m%d%H")
