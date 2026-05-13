"""Chunk 2 — Async job pattern regression tests (DJ-R03, DJ-R05, CM-R04).

The three long-running endpoints used to do their LLM/IO work
synchronously and timed out at the gateway (~100 s ceiling) — HTTP
524 for the brief / signals endpoints, HTTP 502 for the cycle
compilation endpoint. The Chunk 2 fix:

* Endpoint returns **202 + job_id** immediately (< 100 ms).
* Heavy work runs in `BackgroundTasks` and updates `db.async_jobs`.
* Frontend polls `GET /api/jobs/{job_id}` until terminal state.

These tests mock the heavy worker so they don't need a real LLM call
(no LLM = sub-second test runtime). The mocks simulate both the
happy path AND the long-running case (sleep 120 s) to prove the
endpoint never times out at the gateway regardless of how slow the
worker is.

Coverage
--------
* Async dispatch shape — 202 + job_id, even with a 120-s mock worker.
* Polling: 404 for unknown job_id, 200 for valid, 404 for someone
  else's job (privacy boundary).
* Failure path: worker raises → status=failed + error captured.
* Cancellation is intentionally out of scope this chunk —
  asserted in `test_cancellation_not_implemented_but_status_polls_safely`.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def db_conn():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest_asyncio.fixture
async def seeded(db_conn):
    """Seed an account + active membership + one extracted document so
    the pre-flight checks on the signals endpoint pass."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk2-async-{suffix}@example.com"
    password = "Chunk2Async2026!"
    account_id = f"acc-c2-{suffix}"
    context_id = f"ctx-c2-{suffix}"
    doc_id = f"doc-c2-{suffix}"
    now = _iso()

    from core import hash_password
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk2 Probe", "role": "executive", "created_at": now,
        "default_context_id": context_id, "session_version": 0, "verified": True,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "name": "Probe Ctx Chunk2", "type": "executive_personal",
        "status": "active", "owner_account_id": account_id, "created_at": now,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4()}", "context_id": context_id, "account_id": account_id,
        "status": "active", "role": "executive", "sub_role": "admin", "joined_at": now,
    })
    await db_conn.documents.insert_one({
        "id": doc_id, "context_id": context_id, "account_id": account_id,
        "name": "probe.pdf", "status": "extracted", "doc_kind": "policy",
        "created_at": now, "size_bytes": 100, "sensitivity_band": "internal",
        "text_extracted": "Sample extracted text for the chunk-2 probe document.",
        "preview": "Sample extracted text…",
    })
    yield {
        "email": email, "password": password,
        "account_id": account_id, "context_id": context_id, "doc_id": doc_id,
    }
    await db_conn.documents.delete_one({"id": doc_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.async_jobs.delete_many({"account_id": account_id})
    await db_conn.signals.delete_many({"context_id": context_id})


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


# ────────────────────────────────────────────────────────────────────
# 1. Dispatch shape — endpoint must return 202 + job_id, FAST.
# ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_signals_generate_returns_202_and_job_id_fast(client, seeded, monkeypatch):
    """The endpoint returns 202 + job_id in < 1 s, even when the
    underlying worker would take 120 s.

    We mock `_generate_signals_worker` to sleep 120 s — the test
    must STILL complete the request in milliseconds because the
    sleep happens in the BackgroundTasks worker, not inline. If
    this test ever exceeds 5 s the async refactor has regressed.
    """
    from routers import signals_ask

    async def _slow_worker(**kwargs):
        await asyncio.sleep(120)  # would 524 if it were inline
        return {"signals": [], "mode": "stub"}

    monkeypatch.setattr(signals_ask, "_generate_signals_worker", _slow_worker)

    token = await _login(client, seeded["email"], seeded["password"])
    start = asyncio.get_event_loop().time()
    r = await client.post(
        f"/api/contexts/{seeded['context_id']}/signals/generate",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    elapsed = asyncio.get_event_loop().time() - start
    assert r.status_code == 202, f"expected 202, got {r.status_code}: {r.text}"
    assert elapsed < 5.0, f"endpoint took {elapsed:.1f} s — async dispatch is broken"
    body = r.json()
    assert "job_id" in body and body["status"] == "queued"


# ────────────────────────────────────────────────────────────────────
# 2. Polling — happy path and privacy boundary.
# ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_job_polling_happy_path(client, seeded, monkeypatch, db_conn):
    """End-to-end: enqueue, poll until terminal, assert completed
    state carries the worker's `result` payload."""
    from routers import signals_ask

    async def _fast_worker(**kwargs):
        return {"signals": [{"id": "sig-1", "title": "ok"}], "mode": "stub"}

    monkeypatch.setattr(signals_ask, "_generate_signals_worker", _fast_worker)

    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.post(
        f"/api/contexts/{seeded['context_id']}/signals/generate",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = r.json()["job_id"]

    # Poll until terminal — generous bound so a busy test runner doesn't
    # flake. The worker is sub-second so this loops ~once or twice.
    terminal = None
    for _ in range(30):
        await asyncio.sleep(0.1)
        pr = await client.get(
            f"/api/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pr.status_code == 200, pr.text
        body = pr.json()
        if body["status"] in ("completed", "failed"):
            terminal = body
            break

    assert terminal is not None, "job never reached terminal state"
    assert terminal["status"] == "completed", f"job failed: {terminal.get('error')}"
    assert terminal["result"]["mode"] == "stub"


@pytest.mark.asyncio
async def test_job_polling_unknown_job_returns_404(client, seeded):
    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.get(
        f"/api/jobs/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_job_polling_foreign_job_returns_404(client, seeded, monkeypatch, db_conn):
    """A second user must NOT be able to poll someone else's job.
    The endpoint returns 404 (not 403) so foreign existence is not
    leaked."""
    from routers import signals_ask

    async def _fast_worker(**kwargs):
        return {"signals": [], "mode": "stub"}

    monkeypatch.setattr(signals_ask, "_generate_signals_worker", _fast_worker)

    # User A enqueues a job.
    token_a = await _login(client, seeded["email"], seeded["password"])
    r = await client.post(
        f"/api/contexts/{seeded['context_id']}/signals/generate",
        json={},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    job_id = r.json()["job_id"]

    # User B (fresh account, unrelated) tries to poll the same job.
    suffix = uuid.uuid4().hex[:8]
    email_b = f"chunk2-foreign-{suffix}@example.com"
    password_b = "Foreign2026!"
    aid_b = f"acc-f-{suffix}"
    from core import hash_password
    await db_conn.accounts.insert_one({
        "id": aid_b, "email": email_b, "password_hash": hash_password(password_b),
        "name": "Foreign", "role": "executive", "created_at": _iso(),
        "session_version": 0, "verified": True,
    })
    try:
        token_b = await _login(client, email_b, password_b)
        pr = await client.get(
            f"/api/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert pr.status_code == 404, (
            f"User B saw User A's job (status={pr.status_code}): privacy boundary leaked"
        )
    finally:
        await db_conn.accounts.delete_one({"id": aid_b})


# ────────────────────────────────────────────────────────────────────
# 3. Failure path — worker raises → terminal status=failed + error.
# ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_worker_exception_yields_failed_status(client, seeded, monkeypatch):
    from routers import signals_ask

    async def _exploding_worker(**kwargs):
        raise RuntimeError("LLM provider returned 503")

    monkeypatch.setattr(signals_ask, "_generate_signals_worker", _exploding_worker)

    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.post(
        f"/api/contexts/{seeded['context_id']}/signals/generate",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = r.json()["job_id"]

    terminal = None
    for _ in range(30):
        await asyncio.sleep(0.1)
        pr = await client.get(
            f"/api/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if pr.json()["status"] in ("completed", "failed"):
            terminal = pr.json()
            break

    assert terminal is not None
    assert terminal["status"] == "failed"
    assert "503" in (terminal.get("error") or ""), terminal


# ────────────────────────────────────────────────────────────────────
# 4. Cancellation — intentionally not implemented this chunk.
#    The polling endpoint must STILL be safe for a long-running job —
#    repeated polls do not corrupt the row.
# ────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_cancellation_not_implemented_but_status_polls_safely(client, seeded, monkeypatch):
    from routers import signals_ask

    async def _ten_iters_worker(**kwargs):
        # 10 short awaits to simulate work without blocking the loop.
        for _ in range(10):
            await asyncio.sleep(0.05)
        return {"signals": [], "mode": "stub"}

    monkeypatch.setattr(signals_ask, "_generate_signals_worker", _ten_iters_worker)

    token = await _login(client, seeded["email"], seeded["password"])
    r = await client.post(
        f"/api/contexts/{seeded['context_id']}/signals/generate",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = r.json()["job_id"]

    # Hammer the polling endpoint while the worker is running. None
    # of the polls should error and the final state must still be
    # `completed` (i.e. polling does not corrupt the row).
    last_status = None
    for _ in range(60):
        pr = await client.get(
            f"/api/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pr.status_code == 200, pr.text
        last_status = pr.json()["status"]
        if last_status in ("completed", "failed"):
            break
        await asyncio.sleep(0.05)

    assert last_status == "completed", f"final status={last_status}"
