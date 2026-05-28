"""Phase X (2026-02 fork-resume) — Self-service account deletion.

Locks:
    1. POST /api/me/delete-account — 30-day soft-delete contract
    2. POST /api/me/delete-account/cancel — restores active status
    3. POST /api/admin/users/process-deletions — hard-delete cascade
    4. Email-confirm guard, last-superadmin lockout, pending state
       still allows login (so user can cancel)
    5. Frontend Danger Zone in AccountSecurity.jsx
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────
# A. Module + grace window constant
# ─────────────────────────────────────────────────────────────────


def test_phase_x_module_constants_and_router_prefix():
    from routers import account_deletion as ad  # type: ignore
    assert ad.GRACE_DAYS == 30
    assert ad.router.prefix == "/api"


def test_phase_x_router_registered_in_server():
    src = (BACKEND / "server.py").read_text(encoding="utf-8")
    assert "from routers import account_deletion as account_deletion_router" in src
    assert "app.include_router(account_deletion_router.router)" in src


def test_phase_x_sanitize_account_surfaces_deletion_fields():
    """Phase X surfaces deletion timestamps via sanitize_account so
    the Danger Zone UI can render without an extra round-trip."""
    src = (BACKEND / "core.py").read_text(encoding="utf-8")
    assert "deletion_requested_at" in src
    assert "deletion_scheduled_for" in src


# ─────────────────────────────────────────────────────────────────
# B. Endpoint contracts (live with httpx ASGI transport)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_phase_x_request_deletion_requires_email_confirm():
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    acc_id = f"px-acc-{uuid.uuid4().hex[:8]}"
    await db.accounts.insert_one({
        "id": acc_id, "email": "phasex@example.com", "name": "PX User",
        "status": "active", "is_superadmin": False, "created_at": _iso_now(),
    })

    async def _fake_user():
        return await db.accounts.find_one({"id": acc_id}, {"_id": 0})

    app.dependency_overrides[get_current_account] = _fake_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            # Wrong email confirm → 400
            r = await client.post("/api/me/delete-account", json={"confirm": "wrong@example.com"})
            assert r.status_code == 400
            # Correct email → 200 with schedule
            r2 = await client.post("/api/me/delete-account", json={"confirm": "phasex@example.com"})
            assert r2.status_code == 200, r2.text
            data = r2.json()
            assert data["status"] == "pending_deletion"
            assert data["grace_days"] == 30
            assert "deletion_requested_at" in data
            assert "deletion_scheduled_for" in data
            # DB row reflects schedule.
            row = await db.accounts.find_one({"id": acc_id}, {"_id": 0})
            assert row["status"] == "pending_deletion"
            assert row.get("deletion_scheduled_for")

            # Idempotent — second call returns the SAME schedule.
            r3 = await client.post("/api/me/delete-account", json={"confirm": "phasex@example.com"})
            assert r3.status_code == 200
            assert r3.json()["deletion_scheduled_for"] == data["deletion_scheduled_for"]

            # Cancel → restores active.
            r4 = await client.post("/api/me/delete-account/cancel")
            assert r4.status_code == 200, r4.text
            row2 = await db.accounts.find_one({"id": acc_id}, {"_id": 0})
            assert row2["status"] == "active"
            assert row2.get("deletion_scheduled_for") is None

            # Cancel on a non-pending account → 400.
            r5 = await client.post("/api/me/delete-account/cancel")
            assert r5.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        await db.accounts.delete_one({"id": acc_id})


@pytest.mark.asyncio
async def test_phase_x_superadmin_cannot_self_delete():
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    acc_id = f"px-super-{uuid.uuid4().hex[:8]}"
    await db.accounts.insert_one({
        "id": acc_id, "email": "supex@example.com", "name": "Super X",
        "status": "active", "is_superadmin": True, "created_at": _iso_now(),
    })

    async def _fake_super():
        return await db.accounts.find_one({"id": acc_id}, {"_id": 0})

    app.dependency_overrides[get_current_account] = _fake_super
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            r = await client.post("/api/me/delete-account", json={"confirm": "supex@example.com"})
            assert r.status_code == 400
            assert "Superadmin" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        await db.accounts.delete_one({"id": acc_id})


@pytest.mark.asyncio
async def test_phase_x_process_deletions_cascades_to_owned_data():
    """Backdate scheduled_for to the past, run admin processor,
    verify cascade across memberships + owned contexts + docs +
    tasks_initiatives."""
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore
    from routers.account_deletion import _cascade_hard_delete  # type: ignore

    acc_id = f"px-cas-{uuid.uuid4().hex[:8]}"
    ctx_id = f"px-ctx-{uuid.uuid4().hex[:8]}"
    other_acc = f"px-other-{uuid.uuid4().hex[:8]}"

    # Set up: account owning a context + memberships + docs + tasks.
    yesterday_iso = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    await db.accounts.insert_many([
        {
            "id": acc_id, "email": "casc@example.com", "name": "Cas X",
            "status": "pending_deletion", "is_superadmin": False,
            "deletion_requested_at":  _iso_now(),
            "deletion_scheduled_for": yesterday_iso,
            "created_at": _iso_now(),
        },
        # Spectator account — must NOT be touched by the cascade.
        {
            "id": other_acc, "email": "spectator@example.com", "name": "Spectator",
            "status": "active", "is_superadmin": False, "created_at": _iso_now(),
        },
    ])
    await db.contexts.insert_one({
        "id": ctx_id, "name": "PX Owned Ctx", "type": "executive_personal",
        "owner_account_id": acc_id, "status": "active",
        "created_at": _iso_now(),
    })
    await db.memberships.insert_many([
        {"id": uuid.uuid4().hex, "context_id": ctx_id, "account_id": acc_id, "role": "executive"},
        {"id": uuid.uuid4().hex, "context_id": ctx_id, "account_id": other_acc, "role": "reportee"},
    ])
    await db.documents.insert_one({
        "id": uuid.uuid4().hex, "context_id": ctx_id, "title": "PX cascade doc",
    })
    await db.tasks_initiatives.insert_one({
        "id": uuid.uuid4().hex, "context_id": ctx_id, "title": "PX cascade task",
        "status": "not_started",
    })

    async def _fake_super():
        return {"id": "super", "email": "super@example.com", "is_superadmin": True}

    app.dependency_overrides[get_current_account] = _fake_super
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            r = await client.post("/api/admin/users/process-deletions")
            assert r.status_code == 200, r.text
            payload = r.json()
            assert payload["processed"] >= 1
            # Find the result for our account.
            our_result = next(
                (rr for rr in payload["results"] if rr["account_id"] == acc_id),
                None,
            )
            assert our_result is not None
            counts = our_result["counts"]
            assert counts["account"] == 1
            assert counts.get("owned_contexts", 0) == 1
            assert counts.get("documents_by_owned_ctx", 0) == 1
            assert counts.get("tasks_initiatives_by_owned_ctx", 0) == 1
            # Either route (account_id-based or owned_ctx-based) must
            # cascade memberships — combined total should be at least 2
            # (acc_id's membership + spectator's membership on owned ctx).
            total_mem_deleted = (
                counts.get("memberships", 0)
                + counts.get("memberships_by_owned_ctx", 0)
            )
            assert total_mem_deleted >= 2
            # DB state — account + context + memberships + docs gone.
            assert await db.accounts.find_one({"id": acc_id}) is None
            assert await db.contexts.find_one({"id": ctx_id}) is None
            assert await db.memberships.count_documents({"context_id": ctx_id}) == 0
            # Spectator account unscathed.
            assert await db.accounts.find_one({"id": other_acc}) is not None
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        await db.accounts.delete_many({"id": {"$in": [acc_id, other_acc]}})
        await db.contexts.delete_many({"id": ctx_id})
        await db.memberships.delete_many({"context_id": ctx_id})
        await db.documents.delete_many({"context_id": ctx_id})
        await db.tasks_initiatives.delete_many({"context_id": ctx_id})


@pytest.mark.asyncio
async def test_phase_x_process_deletions_skips_future_scheduled():
    """Don't hard-delete accounts whose grace window hasn't expired."""
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    acc_id = f"px-fut-{uuid.uuid4().hex[:8]}"
    future_iso = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
    await db.accounts.insert_one({
        "id": acc_id, "email": "future@example.com",
        "status": "pending_deletion",
        "deletion_requested_at": _iso_now(),
        "deletion_scheduled_for": future_iso,
        "created_at": _iso_now(),
    })

    async def _fake_super():
        return {"id": "super", "email": "super@example.com", "is_superadmin": True}

    app.dependency_overrides[get_current_account] = _fake_super
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            r = await client.post("/api/admin/users/process-deletions")
            assert r.status_code == 200
            # Our future-scheduled account must STILL exist.
            assert await db.accounts.find_one({"id": acc_id}) is not None
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        await db.accounts.delete_one({"id": acc_id})


@pytest.mark.asyncio
async def test_phase_x_process_deletions_requires_superadmin():
    from server import app  # type: ignore
    from core import get_current_account  # type: ignore

    async def _fake_user():
        return {"id": "u", "email": "u@example.com", "is_superadmin": False}

    app.dependency_overrides[get_current_account] = _fake_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            r = await client.post("/api/admin/users/process-deletions")
            assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_account, None)


# ─────────────────────────────────────────────────────────────────
# C. Frontend — Danger Zone in AccountSecurity
# ─────────────────────────────────────────────────────────────────


def test_phase_x_frontend_danger_zone_present():
    src = (REPO / "frontend" / "src" / "pages" / "AccountSecurity.jsx").read_text(encoding="utf-8")
    required_testids = (
        "account-danger-zone",
        "open-delete-account-btn",
        "delete-account-dialog",
        "delete-account-confirm-input",
        "delete-account-confirm-btn",
        "delete-account-cancel-btn",
        "cancel-account-deletion-btn",
    )
    for tid in required_testids:
        assert f'data-testid="{tid}"' in src, (
            f'AccountSecurity.jsx must carry data-testid="{tid}"'
        )
    assert '/me/delete-account' in src
    assert '/me/delete-account/cancel' in src
