"""Phase 15.0 smoke — the Solva v2 feature flag gates every /api/solva/v2/*
endpoint. Accounts without `solva_v2_poc=true` get 403 on every call.

Uses the running supervisor-backend via `requests`, same pattern as
test_cycle_manager_actions_tab.py. A fresh Motor client per DB call handles
the asyncio-loop-per-test constraint.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

import pytest
import requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")

BACKEND = os.environ.get("AKKI_BACKEND_URL", "http://localhost:8001")


def _run_db(coro_factory):
    async def _runner():
        from motor.motor_asyncio import AsyncIOMotorClient
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        try:
            db = cli[os.environ["DB_NAME"]]
            return await coro_factory(db)
        finally:
            cli.close()
    return asyncio.run(_runner())


def _seed_account(email: str, *, password: str, poc_flag: bool) -> str:
    """Insert a fresh account. Returns account_id. Cleaned up via _cleanup."""
    from core import hash_password
    aid = str(uuid.uuid4())
    doc = {
        "id": aid,
        "email": email,
        "name": "Solva v2 Smoke",
        "declared_role": "ned",
        "password_hash": hash_password(password),
        "mfa_enabled": False,
        "is_superadmin": False,
        "plan": "free",
        "created_at": "2026-05-04T00:00:00Z",
    }
    if poc_flag:
        doc["solva_v2_poc"] = True
    _run_db(lambda db: db.accounts.insert_one(doc))
    return aid


def _seed_context_for(aid: str) -> str:
    """Seed a fresh active context + admin membership for the given account.
    Returns the context_id. Cleaned up via _cleanup_context."""
    cid = str(uuid.uuid4())
    mid = str(uuid.uuid4())
    _run_db(lambda db: db.contexts.insert_one({
        "id": cid, "name": "Solva v2 Smoke Ctx", "type": "executive_personal",
        "status": "active", "owner_account_id": aid, "created_at": "2026-05-13T00:00:00Z",
    }))
    _run_db(lambda db: db.memberships.insert_one({
        "id": mid, "context_id": cid, "account_id": aid, "status": "active",
        "role": "executive", "sub_role": "admin", "joined_at": "2026-05-13T00:00:00Z",
    }))
    return cid


def _cleanup(aid: str):
    _run_db(lambda db: db.accounts.delete_one({"id": aid}))
    _run_db(lambda db: db.solva_v2_sessions.delete_many({"account_id": aid}))
    _run_db(lambda db: db.memberships.delete_many({"account_id": aid}))
    _run_db(lambda db: db.contexts.delete_many({"owner_account_id": aid}))


def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{BACKEND}/api/auth/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    r.raise_for_status()
    token = r.json().get("access_token")
    assert token, "login did not return access_token"
    return token


def test_v2_endpoints_open_to_any_authed_account_post_cutover():
    """Phase 15.3.5 cutover — the `solva_v2_poc` flag was retired.
    Solva v2 is the single production surface and is open to every
    authenticated account. This test was previously
    `test_unflagged_account_cannot_access_any_v2_endpoint` and asserted
    a 403; post-cutover it asserts 200 (or domain-natural responses)
    with NO 403.

    Chunk 1 (2026-05-13, WS-R16) — `GET /sessions` now requires a
    `context_id` query parameter. We seed a context for the test
    account and pass it explicitly so the endpoint reaches its
    200-path. Calling without the param is asserted in
    `test_chunk1_solva_leak.py::test_list_sessions_requires_context_id`."""
    email = f"solva-v2-smoke-{uuid.uuid4().hex[:8]}@solva-v2-test.ai"
    password = "Smoke2026!"
    aid = _seed_account(email, password=password, poc_flag=False)
    cid = _seed_context_for(aid)
    try:
        token = _login(email, password)
        headers = {"Authorization": f"Bearer {token}"}
        # Read endpoints — must not 403 anymore.
        r = requests.get(
            f"{BACKEND}/api/solva/v2/sessions",
            params={"context_id": cid},
            headers=headers, timeout=10,
        )
        assert r.status_code == 200, f"GET /sessions: {r.status_code}: {r.text[:200]}"
        # 404 on a nonexistent session id is the expected domain answer
        # (NOT 403). Same for abandon on a nonexistent id.
        r = requests.get(
            f"{BACKEND}/api/solva/v2/sessions/nonexistent",
            headers=headers, timeout=10,
        )
        assert r.status_code == 404, f"GET /sessions/non: {r.status_code}"
        r = requests.post(
            f"{BACKEND}/api/solva/v2/sessions/nonexistent/abandon",
            headers=headers, timeout=10,
        )
        assert r.status_code == 404, f"POST /abandon/non: {r.status_code}"
    finally:
        _cleanup(aid)


def test_legacy_flag_field_still_writable_for_forensic_parity():
    """Phase 15.3.5 — the `solva_v2_poc` field is preserved on accounts
    for forensic/observability parity even though no code path reads it.
    Flipping it has no effect on access; assert this so future
    refactors don't regress to gated behaviour.

    Chunk 1 (2026-05-13, WS-R16) — `GET /sessions` now requires a
    `context_id`. Seeded a context for the test account so we exercise
    the success path."""
    email = f"solva-v2-flip-{uuid.uuid4().hex[:8]}@solva-v2-test.ai"
    password = "Flip2026!"
    aid = _seed_account(email, password=password, poc_flag=False)
    cid = _seed_context_for(aid)
    try:
        token = _login(email, password)
        headers = {"Authorization": f"Bearer {token}"}
        # Pre-flip: must already be 200 (no gate).
        r = requests.get(
            f"{BACKEND}/api/solva/v2/sessions",
            params={"context_id": cid},
            headers=headers, timeout=10,
        )
        assert r.status_code == 200, r.text
        # Flip on — still 200 (and field is writable).
        _run_db(lambda db: db.accounts.update_one(
            {"id": aid}, {"$set": {"solva_v2_poc": True}},
        ))
        r = requests.get(
            f"{BACKEND}/api/solva/v2/sessions",
            params={"context_id": cid},
            headers=headers, timeout=10,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert body["count"] == 0
    finally:
        _cleanup(aid)
