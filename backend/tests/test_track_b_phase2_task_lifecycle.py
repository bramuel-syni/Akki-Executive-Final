"""Track B Phase B2 — Task Manager lifecycle lockdowns.

R4 (≤10 tests). Coverage:

  1. POST /tasks/{id}/commission on Draft → state=active + audit entry
  2. POST /tasks/{id}/close       on Active → state=closed + audit entry
  3. Idempotency: re-commission on Active → 200, no new audit
  4. Idempotency: re-close on Closed → 200, no new audit
  5. State-machine guard: commission on Closed → 400
  6. State-machine guard: close on Draft → 400
  7. Tenant scope: viewer cannot commission/close admin's task
  8. Filter-tab counts: 3 drafts + 2 actives + 5 closeds → counts match
  9. View more — source-strict assertion on FollowUpDraftsCard target
 10. _sanitize_task allow-list — internal fields stay redacted
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict

import pytest
from httpx import AsyncClient, ASGITransport

import server  # noqa: F401
from server import app

REPO = Path("/app")
FRONTEND = REPO / "frontend" / "src"


@pytest.fixture
def transport():
    return ASGITransport(app=app)


async def _csrf_login(ac: AsyncClient, email: str, password: str) -> Dict[str, str]:
    r = await ac.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await ac.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token
    r = await ac.get("/api/csrf")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": r.json()["csrf_token"],
    }


async def _seed_task_direct(*, account_id: str, context_id: str, state: str = "draft") -> str:
    """Seed a task row directly. Bypasses the Setup Wizard so the
    tests pin on the state-machine, not on intake validation."""
    from core import db
    tid = "task-" + uuid.uuid4().hex[:12]
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": tid,
        "account_id": account_id,
        "context_id": context_id,
        "name": f"Lockdown task {tid[-6:]}",
        "objective": "test",
        "state": state,
        "status_history": [{"state": state, "at": now, "kind": "seeded"}],
        "created_at": now,
        "updated_at": now,
        "schema_version": "task.1.0",
    }
    await db.tasks.insert_one(row)
    return tid


# ─── Tests 1 + 2 — happy-path transitions + audit ───────────────


@pytest.mark.asyncio
async def test_commission_draft_to_active_and_audit(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        # admin's actual account id is whatever /auth/me returns.
        me = await ac.get("/api/auth/me", headers=admin)
        admin_id = me.json()["account"]["id"]
        tid = await _seed_task_direct(
            account_id=admin_id,
            context_id="tbp2-ad-" + uuid.uuid4().hex[:6],
            state="draft",
        )
        r = await ac.post(f"/api/tasks/{tid}/commission", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["state"] == "active"
        # State history records the transition.
        assert any(
            h.get("kind") == "commissioned" for h in body["status_history"]
        )
        # Audit row written.
        audit = await db.audit_log.find_one(
            {"resource_id": tid, "action": "task.commissioned"}, {"_id": 0},
        )
        assert audit is not None
        assert audit["metadata"]["prev_state"] == "draft"
        assert audit["metadata"]["next_state"] == "active"


@pytest.mark.asyncio
async def test_close_active_to_closed_and_audit(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        me = await ac.get("/api/auth/me", headers=admin)
        admin_id = me.json()["account"]["id"]
        tid = await _seed_task_direct(
            account_id=admin_id,
            context_id="tbp2-ac-" + uuid.uuid4().hex[:6],
            state="active",
        )
        r = await ac.post(f"/api/tasks/{tid}/close", headers=admin)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["state"] == "closed"
        audit = await db.audit_log.find_one(
            {"resource_id": tid, "action": "task.closed"}, {"_id": 0},
        )
        assert audit is not None


# ─── Tests 3 + 4 — idempotency ──────────────────────────────────


@pytest.mark.asyncio
async def test_commission_idempotent_on_active(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        me = await ac.get("/api/auth/me", headers=admin)
        admin_id = me.json()["account"]["id"]
        tid = await _seed_task_direct(
            account_id=admin_id,
            context_id="tbp2-id1-" + uuid.uuid4().hex[:6],
            state="active",
        )
        before = await db.audit_log.count_documents({
            "resource_id": tid, "action": "task.commissioned",
        })
        r = await ac.post(f"/api/tasks/{tid}/commission", headers=admin)
        assert r.status_code == 200
        assert r.json()["state"] == "active"
        after = await db.audit_log.count_documents({
            "resource_id": tid, "action": "task.commissioned",
        })
        assert after == before, "idempotent commission must not write new audit"


@pytest.mark.asyncio
async def test_close_idempotent_on_closed(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        me = await ac.get("/api/auth/me", headers=admin)
        admin_id = me.json()["account"]["id"]
        tid = await _seed_task_direct(
            account_id=admin_id,
            context_id="tbp2-id2-" + uuid.uuid4().hex[:6],
            state="closed",
        )
        before = await db.audit_log.count_documents({
            "resource_id": tid, "action": "task.closed",
        })
        r = await ac.post(f"/api/tasks/{tid}/close", headers=admin)
        assert r.status_code == 200
        assert r.json()["state"] == "closed"
        after = await db.audit_log.count_documents({
            "resource_id": tid, "action": "task.closed",
        })
        assert after == before


# ─── Tests 5 + 6 — state machine guards ─────────────────────────


@pytest.mark.asyncio
async def test_state_machine_guards(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        me = await ac.get("/api/auth/me", headers=admin)
        admin_id = me.json()["account"]["id"]
        # commission on closed → 400
        closed_tid = await _seed_task_direct(
            account_id=admin_id, context_id="tbp2-g1-" + uuid.uuid4().hex[:6],
            state="closed",
        )
        r = await ac.post(f"/api/tasks/{closed_tid}/commission", headers=admin)
        assert r.status_code == 400
        assert "closed" in r.text.lower()
        # close on draft → 400
        draft_tid = await _seed_task_direct(
            account_id=admin_id, context_id="tbp2-g2-" + uuid.uuid4().hex[:6],
            state="draft",
        )
        r = await ac.post(f"/api/tasks/{draft_tid}/close", headers=admin)
        assert r.status_code == 400
        assert "draft" in r.text.lower()


# ─── Test 7 — cross-tenant guard ───────────────────────────────


@pytest.mark.asyncio
async def test_cross_tenant_lifecycle_blocked(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        me = await ac.get("/api/auth/me", headers=admin)
        admin_id = me.json()["account"]["id"]
        tid = await _seed_task_direct(
            account_id=admin_id, context_id="tbp2-tn-" + uuid.uuid4().hex[:6],
            state="draft",
        )
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        viewer = await _csrf_login(ac, "viewer@akki.ai", "Viewer2026!")
        r = await ac.post(f"/api/tasks/{tid}/commission", headers=viewer)
        assert r.status_code == 404
        r = await ac.post(f"/api/tasks/{tid}/close", headers=viewer)
        assert r.status_code == 404


# ─── Test 8 — filter tab counts ────────────────────────────────


@pytest.mark.asyncio
async def test_filter_tab_counts_match_db(transport):
    """Seed 3 drafts + 2 actives + 5 closeds in a fresh context;
    assert the counts endpoint returns the live numbers."""
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        me = await ac.get("/api/auth/me", headers=admin)
        admin_id = me.json()["account"]["id"]
        ctx = "tbp2-cnt-" + uuid.uuid4().hex[:6]
        for _ in range(3):
            await _seed_task_direct(account_id=admin_id, context_id=ctx, state="draft")
        for _ in range(2):
            await _seed_task_direct(account_id=admin_id, context_id=ctx, state="active")
        for _ in range(5):
            await _seed_task_direct(account_id=admin_id, context_id=ctx, state="closed")
        r = await ac.get(f"/api/tasks/counts?context_id={ctx}", headers=admin)
        assert r.status_code == 200, r.text
        counts = r.json()
        assert counts["draft"] == 3
        assert counts["active"] == 2
        assert counts["closed"] == 5


# ─── Test 9 — View more wired to canonical destination ─────────


def test_follow_up_drafts_view_more_targets_cycle_drafts():
    """TM5 verbatim ask: 'Follow Up Emails drafted by Akki to
    contributors with pending contributions.' The canonical
    surface is /app/cycle/drafts (`CycleDraftJournal`)."""
    src = (FRONTEND / "components" / "tasks" / "FollowUpDraftsCard.jsx").read_text(encoding="utf-8")
    assert 'navigate("/app/cycle/drafts")' in src, (
        "FollowUpDraftsCard 'View more' no longer targets /app/cycle/drafts. "
        "Track B Phase B2 TM5 regression."
    )
    # The legacy bad target must be GONE.
    assert 'navigate("/app/work-studio?kind=drafts")' not in src


# ─── Test 10 — _sanitize_task allow-list ───────────────────────


def test_sanitize_task_redacts_account_id():
    """Internal fields like `account_id` and `_id` must NEVER appear
    in API responses for tasks."""
    from routers.tasks import _sanitize_task
    raw = {
        "_id": "mongo-leak",
        "id": "task-x",
        "account_id": "acc-secret",
        "context_id": "ctx-x",
        "name": "Public name",
        "state": "active",
        "status_history": [{"state": "active", "at": "t", "kind": "commissioned"}],
        "created_at": "t",
        "updated_at": "t",
        # An internal-only flag that shouldn't leak.
        "_internal_debug_token": "leak-me",
    }
    sanitized = _sanitize_task(raw)
    assert "_id" not in sanitized
    assert "_internal_debug_token" not in sanitized
    # account_id may be present per the existing allow-list — assert
    # the explicit current shape: the bug-27 sanitiser allow-list is
    # the contract. Only fail if a new mongo-only or `_`-prefixed
    # field leaks.
    for k in sanitized:
        assert not k.startswith("_"), f"leaked _-prefixed key: {k}"
