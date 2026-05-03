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


def _cleanup(aid: str):
    _run_db(lambda db: db.accounts.delete_one({"id": aid}))
    _run_db(lambda db: db.solva_v2_sessions.delete_many({"account_id": aid}))


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


def test_unflagged_account_cannot_access_any_v2_endpoint():
    email = f"solva-v2-smoke-{uuid.uuid4().hex[:8]}@solva-v2-test.ai"
    password = "Smoke2026!"
    aid = _seed_account(email, password=password, poc_flag=False)
    try:
        token = _login(email, password)
        headers = {"Authorization": f"Bearer {token}"}
        endpoints = [
            ("GET", "/api/solva/v2/sessions", None),
            ("POST", "/api/solva/v2/sessions", {
                "cluster_id": "revenue_underperformance",
                "intent": "x" * 40,
                "submodule": "seek_clarity",
            }),
            ("GET", "/api/solva/v2/sessions/nonexistent", None),
            ("GET", "/api/solva/v2/sessions/nonexistent/reasoning-log", None),
            ("POST", "/api/solva/v2/sessions/nonexistent/abandon", None),
            ("POST", "/api/solva/v2/sessions/nonexistent/turn", {"user_text": "x" * 10}),
        ]
        for method, path, body in endpoints:
            fn = requests.get if method == "GET" else requests.post
            r = fn(f"{BACKEND}{path}", json=body, headers=headers, timeout=10)
            assert r.status_code == 403, (
                f"{method} {path} returned {r.status_code} expected 403.\nBody: {r.text[:200]}"
            )
            assert "POC is not enabled" in r.text, r.text[:200]
    finally:
        _cleanup(aid)


def test_flipping_flag_unlocks_endpoints():
    email = f"solva-v2-flip-{uuid.uuid4().hex[:8]}@solva-v2-test.ai"
    password = "Flip2026!"
    aid = _seed_account(email, password=password, poc_flag=False)
    try:
        token = _login(email, password)
        headers = {"Authorization": f"Bearer {token}"}
        r = requests.get(f"{BACKEND}/api/solva/v2/sessions", headers=headers, timeout=10)
        assert r.status_code == 403
        # Flip on
        _run_db(lambda db: db.accounts.update_one(
            {"id": aid}, {"$set": {"solva_v2_poc": True}},
        ))
        r = requests.get(f"{BACKEND}/api/solva/v2/sessions", headers=headers, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert body["count"] == 0
    finally:
        _cleanup(aid)
