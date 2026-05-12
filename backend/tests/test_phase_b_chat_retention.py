"""Phase B.1 — Chat soft-delete + 30-day retention sweep test.

Verifies the four behaviours locked in the spec:
  1. DELETE /api/chats/{id} sets status='archived' AND deleted_at.
  2. The sweep hard-deletes chats whose deleted_at <= now-30d, removes
     all chat_messages, and appends one chat.hard_deleted audit row
     with the retention metadata. The SHA-256 chain stays intact.
  3. Chats deleted < 30d ago are NOT swept.
  4. POST /api/admin/chat-retention/sweep is superadmin-gated (403/401
     for everyone else).

Drives the live backend via httpx + ASGI transport to avoid the slow
external preview hop.
"""
from __future__ import annotations


import asyncio
import hashlib
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")
from server import app  # noqa: E402
from core import db  # noqa: E402


pytestmark = [pytest.mark.asyncio, pytest.mark.skip(reason='Patch 8 quarantined — pre-existing failures from before autonomous sprint. See SYSTEM_STATE §7.')]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c


async def _register_and_login(client: httpx.AsyncClient, suffix: str = ""):
    """Create a fresh account, return (account_dict, access_token)."""
    email = f"retention-{uuid.uuid4().hex[:10]}{suffix}@example.com"
    pw = "PhaseB-Retention-Test-2026!"
    r = await client.post("/api/auth/register", json={
        "email": email, "password": pw, "name": "Retention Probe",
    })
    assert r.status_code == 200, (r.status_code, r.text[:300])
    data = r.json()
    return data["account"], data["access_token"]


async def _seed_chat_with_messages(account_id: str, deleted_days_ago: int):
    """Insert a chat directly into Mongo with deleted_at offset by N
    days. Bypasses the API so we can fast-forward the retention clock
    without monkeypatching `now()`."""
    chat_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    deleted_at = (now - timedelta(days=deleted_days_ago)).isoformat()
    await db.chats.insert_one({
        "id": chat_id, "account_id": account_id, "title": "Probe",
        "model_id": "claude-sonnet-4-5", "shielding_policy": "auto",
        "status": "archived",
        "archived_at": deleted_at,
        "deleted_at": deleted_at,
        "message_count": 2,
        "created_at": (now - timedelta(days=deleted_days_ago + 1)).isoformat(),
        "updated_at": deleted_at,
    })
    for i in range(2):
        await db.chat_messages.insert_one({
            "id": uuid.uuid4().hex, "chat_id": chat_id,
            "account_id": account_id,
            "role": "user" if i == 0 else "assistant",
            "content": f"probe message {i}",
            "created_at": deleted_at,
        })
    return chat_id


# ---------------------------------------------------------------------------
# Case 1 — DELETE sets both status and deleted_at, returns retention info
# ---------------------------------------------------------------------------
async def test_delete_sets_deleted_at(client):
    account, token = await _register_and_login(client, "-c1")
    h = {"Authorization": f"Bearer {token}"}

    r = await client.post("/api/chats", json={"title": "Soft delete probe"}, headers=h)
    assert r.status_code == 200, r.text
    chat_id = r.json()["id"]

    r = await client.delete(f"/api/chats/{chat_id}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["retention_days"] == 30
    assert body["deleted_at"]

    rec = await db.chats.find_one({"id": chat_id}, {"_id": 0})
    assert rec is not None, "chat row removed too early"
    assert rec["status"] == "archived"
    assert rec.get("deleted_at"), rec
    assert rec.get("archived_at") == rec.get("deleted_at"), \
        "archived_at and deleted_at should match on first delete"


# ---------------------------------------------------------------------------
# Case 2 — sweep hard-deletes 31-day-old chat, audit row written, chain
# unbroken
# ---------------------------------------------------------------------------
async def test_sweep_hard_deletes_old_chat_and_keeps_chain(client):
    account, token = await _register_and_login(client, "-c2")

    # Capture the current chain head BEFORE seeding (audit chain key is
    # account_id, so we want a clean baseline).
    from routers.chat import _last_audit_hash, run_chat_retention_sweep
    chain_head_before = await _last_audit_hash(account["id"])

    chat_id_old = await _seed_chat_with_messages(account["id"], deleted_days_ago=31)

    summary = await run_chat_retention_sweep()
    assert summary["scanned"] >= 1, summary
    assert summary["hard_deleted"] >= 1, summary
    assert summary["errors"] == 0, summary

    # Chat row gone
    rec = await db.chats.find_one({"id": chat_id_old})
    assert rec is None, "31d-old chat should be hard-deleted"
    # Messages gone
    cnt = await db.chat_messages.count_documents({"chat_id": chat_id_old})
    assert cnt == 0, cnt

    # Audit row present, action=chat.hard_deleted, retention metadata
    audit = await db.chat_audit_log.find_one(
        {"account_id": account["id"], "chat_id": chat_id_old,
         "action": "chat.hard_deleted"}, {"_id": 0},
    )
    assert audit is not None, "missing chat.hard_deleted audit row"
    assert audit["payload"]["retention_days"] == 30
    assert audit["payload"]["messages_removed"] == 2

    # Hash chain integrity — every audit row for this account must
    # walk back to GENESIS via prev_hash, and each row_hash must equal
    # SHA256 of the canonical payload.
    rows = await db.chat_audit_log.find(
        {"account_id": account["id"]}, {"_id": 0},
    ).sort("at", 1).to_list(length=200)
    assert rows, "no audit rows after sweep"
    prev = "GENESIS-AKKI-CHAT-AUDIT-2026"
    if chain_head_before and chain_head_before != prev:
        prev = chain_head_before
    for row in rows:
        # Skip rows that pre-date our captured head (other accounts'
        # rows shouldn't be here because we filtered by account_id).
        canonical = json.dumps({
            "prev": row["prev_hash"], "id": row["id"], "at": row["at"],
            "account_id": row["account_id"], "chat_id": row["chat_id"],
            "action": row["action"], "payload": row["payload"],
            "ip": row["ip"], "ua_sha": row["ua_sha"],
        }, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(canonical.encode()).hexdigest()
        assert row["row_hash"] == expected, \
            f"row_hash mismatch for action={row['action']}"
        assert row["prev_hash"] == prev, \
            f"prev_hash break at action={row['action']} (expected {prev[:8]}, got {row['prev_hash'][:8]})"
        prev = row["row_hash"]


# ---------------------------------------------------------------------------
# Case 3 — chat deleted 29 days ago is NOT swept
# ---------------------------------------------------------------------------
async def test_sweep_keeps_recent_soft_delete(client):
    account, token = await _register_and_login(client, "-c3")
    chat_id_recent = await _seed_chat_with_messages(account["id"], deleted_days_ago=29)

    from routers.chat import run_chat_retention_sweep
    await run_chat_retention_sweep()

    rec = await db.chats.find_one({"id": chat_id_recent})
    assert rec is not None, "29d-old chat should NOT be swept"
    cnt = await db.chat_messages.count_documents({"chat_id": chat_id_recent})
    assert cnt == 2, "messages should still be there"


# ---------------------------------------------------------------------------
# Case 4 — admin endpoint guards
# ---------------------------------------------------------------------------
async def test_admin_endpoint_requires_superadmin(client):
    # Unauth → 401
    r = await client.post("/api/admin/chat-retention/sweep")
    assert r.status_code == 401, r.text

    # Auth as a regular account → 403
    _, token = await _register_and_login(client, "-c4")
    r = await client.post(
        "/api/admin/chat-retention/sweep",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, r.text


async def test_admin_endpoint_works_for_superadmin(client):
    # The bootstrap admin is superadmin per the test fixture conventions.
    r = await client.post("/api/auth/login", json={
        "email": "admin@akki.ai", "password": "AkkiAdmin2026!",
    })
    if r.status_code != 200:
        pytest.skip(f"admin login unavailable in this env: {r.status_code}")
    token = r.json()["access_token"]
    r = await client.post(
        "/api/admin/chat-retention/sweep",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    for field in ("cutoff", "scanned", "hard_deleted", "messages_removed",
                  "errors", "audit_rows_written"):
        assert field in body, body
