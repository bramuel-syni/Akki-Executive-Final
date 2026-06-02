"""Test-harness hooks (admin-gated) — admin_qa_hooks.py.

Locks down the two endpoints e1_tester depends on to traverse the
onboarding flow and verify TC4 Home Continue card.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import server  # noqa: F401
from server import app


@pytest_asyncio.fixture(scope="module")
async def transport():
    yield ASGITransport(app=app)


async def _seed_admin(db, *, email: str, is_superadmin: bool = True,
                       mfa_enabled: bool = True) -> str:
    from core import hash_password
    aid = "acct-qa-" + uuid.uuid4().hex[:10]
    await db.accounts.insert_one({
        "id": aid,
        "email": email,
        "email_lc": email.lower(),
        "name": "QA hooks tester",
        "password_hash": hash_password("Qa-hooks-2026!"),
        "declared_role": "user",
        "is_superadmin": is_superadmin,
        "mfa_enabled": mfa_enabled,
        "first_session": {
            "status": "completed",
            "current_step": "done",
            "intake": {"primary_context_name": "Pre-existing intake"},
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return aid


async def _csrf_login_as(client: AsyncClient, *, email: str,
                         password: str) -> Dict[str, str]:
    r = await client.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await client.post(
        "/api/auth/login", json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    r = await client.get("/api/csrf")
    return {"Authorization": f"Bearer {token}",
            "X-CSRF-Token": r.json()["csrf_token"]}


# ─────────────────────────────────────────────────────────────────
# Block 1 — first-session/reset
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_qa_first_session_reset_rejects_non_admin(transport):
    """403 for non-superadmin even when authenticated."""
    from core import db
    email = f"qa-block1-nonadmin-{uuid.uuid4().hex[:6]}@example.com"
    await _seed_admin(db, email=email, is_superadmin=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login_as(client, email=email, password="Qa-hooks-2026!")
        r = await client.post(
            "/api/admin/qa/first-session/reset", json={}, headers=hdrs,
        )
    assert r.status_code == 403, (r.status_code, r.text)


@pytest.mark.asyncio
async def test_qa_first_session_reset_for_self_lands_on_door(transport):
    """Calling reset with no body resets the CALLER. Idempotent."""
    from core import db
    email = f"qa-block1-self-{uuid.uuid4().hex[:6]}@example.com"
    aid = await _seed_admin(db, email=email)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login_as(client, email=email, password="Qa-hooks-2026!")
        r = await client.post(
            "/api/admin/qa/first-session/reset", json={}, headers=hdrs,
        )
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    assert body["account_id"] == aid
    fs = body["first_session"]
    assert fs["status"] == "in_progress"
    assert fs["current_step"] == "door"
    assert fs["door_taken"] is None
    # Intake preserved.
    assert (fs.get("intake") or {}).get("primary_context_name") == "Pre-existing intake"

    fresh = await db.accounts.find_one({"id": aid}, {"first_session": 1, "_id": 0})
    assert fresh["first_session"]["current_step"] == "door"


@pytest.mark.asyncio
async def test_qa_first_session_reset_for_other_via_email(transport):
    """Superadmin may reset another account by passing account_email."""
    from core import db
    admin_email = f"qa-block1-admin-{uuid.uuid4().hex[:6]}@example.com"
    target_email = f"qa-block1-target-{uuid.uuid4().hex[:6]}@example.com"
    await _seed_admin(db, email=admin_email)
    target_aid = await _seed_admin(db, email=target_email, is_superadmin=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login_as(client, email=admin_email, password="Qa-hooks-2026!")
        r = await client.post(
            "/api/admin/qa/first-session/reset",
            json={"account_email": target_email},
            headers=hdrs,
        )
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json()["account_id"] == target_aid

    # Target's state was actually written.
    fresh = await db.accounts.find_one({"id": target_aid}, {"first_session": 1, "_id": 0})
    assert fresh["first_session"]["current_step"] == "door"


# ─────────────────────────────────────────────────────────────────
# Block 2 — seed/recent-doc
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_qa_seed_recent_doc_creates_context_doc_and_view(transport):
    """First call seeds all three. Second call is idempotent (same IDs).

    Resulting deep_link must satisfy the Card 4 contract."""
    from core import db
    email = f"qa-block2-{uuid.uuid4().hex[:6]}@example.com"
    aid = await _seed_admin(db, email=email)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login_as(client, email=email, password="Qa-hooks-2026!")

        r1 = await client.post(
            "/api/admin/qa/seed/recent-doc", json={}, headers=hdrs,
        )
        assert r1.status_code == 200, (r1.status_code, r1.text)
        body1 = r1.json()
        assert body1["ok"] is True
        assert body1["created_context"] is True
        assert body1["created_document"] is True
        assert body1["deep_link"].startswith("/app/work-studio?doc_id=")
        assert f"context_id={body1['context_id']}" in body1["deep_link"]
        assert f"doc_id={body1['doc_id']}" in body1["deep_link"]

        # Idempotency — second call returns SAME ids and reports
        # `created_*: False`.
        r2 = await client.post(
            "/api/admin/qa/seed/recent-doc", json={}, headers=hdrs,
        )
        assert r2.status_code == 200, (r2.status_code, r2.text)
        body2 = r2.json()
        assert body2["context_id"] == body1["context_id"]
        assert body2["doc_id"] == body1["doc_id"]
        assert body2["created_context"] is False
        assert body2["created_document"] is False

    # DB side-effects landed.
    rv = await db.user_recent_views.find_one(
        {"account_id": aid, "artefact_id": body1["doc_id"]},
        {"_id": 0},
    )
    assert rv is not None
    assert rv["artefact_kind"] == "document"
    assert rv["context_id"] == body1["context_id"]
    assert rv["deep_link"] == body1["deep_link"]


@pytest.mark.asyncio
async def test_qa_seed_recent_doc_rejects_non_admin(transport):
    from core import db
    email = f"qa-block2-nonadmin-{uuid.uuid4().hex[:6]}@example.com"
    await _seed_admin(db, email=email, is_superadmin=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        hdrs = await _csrf_login_as(client, email=email, password="Qa-hooks-2026!")
        r = await client.post(
            "/api/admin/qa/seed/recent-doc", json={}, headers=hdrs,
        )
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────
# OpenAPI discoverability — tester depends on this.
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_qa_endpoints_visible_in_openapi(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = spec.get("paths", {})
    assert "/api/admin/qa/first-session/reset" in paths
    assert "/api/admin/qa/seed/recent-doc" in paths
    # Both should be POST + tagged admin-qa.
    for p in ("/api/admin/qa/first-session/reset",
              "/api/admin/qa/seed/recent-doc"):
        post_spec = paths[p].get("post")
        assert post_spec is not None
        assert "admin-qa" in (post_spec.get("tags") or [])
