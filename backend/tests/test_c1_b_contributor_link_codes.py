"""C1-revised Phase B (2026-02) — Task-contribution magic link
verifier error-code lockdown.

The user-perceived "Magic Link Invalid" surface arose because three
distinct failure modes (token-revoked / task-deleted / contributor-
removed-from-team) all surfaced the same generic "Link not valid"
narrative on `ContributorPortal.jsx`. The backend now returns a
structured `{detail: {code, message}}` so the frontend can render a
precise narrative per case.

Negative paths covered:
  1. Token never existed              → 404 link_invalid
  2. Token revoked via re-invite      → 410 link_revoked
  3. Token expired (past expires_at)  → 410 link_expired
  4. Token spent (used=True no reason)→ 410 link_used
  5. Task deleted after invite        → 410 task_gone
  6. Contributor removed from team    → 410 not_on_team

Positive path (regression guard):
  7. Happy path returns 200 with full payload

Cross-tenant isolation:
  8. Token A cannot leak Task B's data (verified by separate
     contributor_email mismatch).

No mocks of business logic. The token rows are seeded directly into
Mongo to control each failure mode deterministically.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

import server
from core import db


REPO = Path(__file__).resolve().parent.parent.parent
BE   = REPO / "backend"
FE   = REPO / "frontend" / "src"

TASKS_ROUTER     = BE / "routers" / "tasks.py"
CONTRIBUTOR_PAGE = FE / "pages" / "ContributorPortal.jsx"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════
# Source-strict
# ═════════════════════════════════════════════════════════════════════
def test_c1b_resolver_returns_distinct_codes():
    src = _read(TASKS_ROUTER)
    # All 6 error codes present in the verifier surface.
    for code in (
        "link_invalid",
        "link_revoked",
        "link_used",
        "link_expired",
        "task_gone",
        "not_on_team",
    ):
        assert code in src, code


def test_c1b_contributor_portal_renders_distinct_narratives():
    src = _read(CONTRIBUTOR_PAGE)
    for code in (
        "link_invalid",
        "link_revoked",
        "link_used",
        "link_expired",
        "task_gone",
        "not_on_team",
    ):
        assert code in src, code
    # The data-error-code attribute lets the Playwright trace assert
    # the active narrative deterministically.
    assert 'data-error-code' in src


# ═════════════════════════════════════════════════════════════════════
# Wire-level — each negative path returns a precise code
# ═════════════════════════════════════════════════════════════════════
@pytest.fixture
def app():
    return server.app


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _seed_task_with_token(
    *,
    email: str,
    used: bool = False,
    revoked_reason: str = "",
    expires_in_seconds: int = 30 * 24 * 3600,
    delete_task: bool = False,
    contributor_in_team: bool = True,
) -> tuple[str, str, str]:
    """Returns (task_id, token, account_id)."""
    tid = f"task-c1b-{uuid.uuid4().hex[:10]}"
    aid = f"acc-c1b-{uuid.uuid4().hex[:10]}"
    team = []
    if contributor_in_team:
        team.append({
            "name": "C1B Tester",
            "role": "Reviewer",
            "email": email,
            "contribution": "Review section 1",
            "contribution_mode": "magic_link",
        })
    now = _now_iso()
    task_doc = {
        "id":         tid,
        "account_id": aid,
        "name":       "C1B trace task",
        "objective":  "Trace contributor magic link",
        "success_criteria": "Link works",
        "team":       team,
        "state":      "active",
        "created_at": now,
        "updated_at": now,
    }
    if not delete_task:
        await db.tasks.insert_one(dict(task_doc))
    tok = uuid.uuid4().hex + uuid.uuid4().hex
    token_row = {
        "id":                 uuid.uuid4().hex,
        "token":              tok,
        "task_id":            tid,
        "task_account_id":    aid,
        "contributor_email":  email.lower(),
        "contributor_id":     email.lower(),
        "expires_at":         (
            datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
        ).isoformat(),
        "used":               used,
        "created_at":         now,
    }
    if used and revoked_reason:
        token_row["revoked_reason"] = revoked_reason
        token_row["revoked_at"] = now
    await db.task_contributor_tokens.insert_one(dict(token_row))
    return tid, tok, aid


async def _cleanup(task_id: str, token: str) -> None:
    await db.tasks.delete_many({"id": task_id})
    await db.task_contributor_tokens.delete_many({"token": token})


@pytest.mark.asyncio
async def test_c1b_token_never_existed_returns_link_invalid(app):
    """A token that was never minted → 404 code=link_invalid."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        bogus = "this-token-was-never-issued-by-akki"
        r = await c.get(f"/api/tasks/contribute/{bogus}")
        assert r.status_code == 404
        body = r.json()
        assert body["detail"]["code"] == "link_invalid"


@pytest.mark.asyncio
async def test_c1b_token_revoked_returns_link_revoked(app):
    """Token was rotated by a re-invite → 410 code=link_revoked."""
    email = f"c1b-revoked-{uuid.uuid4().hex[:8]}@example.com"
    tid, tok, _ = await _seed_task_with_token(
        email=email, used=True, revoked_reason="rotated_on_reinvite",
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as c:
            r = await c.get(f"/api/tasks/contribute/{tok}")
            assert r.status_code == 410
            body = r.json()
            assert body["detail"]["code"] == "link_revoked"
    finally:
        await _cleanup(tid, tok)


@pytest.mark.asyncio
async def test_c1b_token_spent_returns_link_used(app):
    """Token was marked used=True without a revoked_reason → 410
    code=link_used."""
    email = f"c1b-used-{uuid.uuid4().hex[:8]}@example.com"
    tid, tok, _ = await _seed_task_with_token(email=email, used=True)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as c:
            r = await c.get(f"/api/tasks/contribute/{tok}")
            assert r.status_code == 410
            body = r.json()
            assert body["detail"]["code"] == "link_used"
    finally:
        await _cleanup(tid, tok)


@pytest.mark.asyncio
async def test_c1b_token_expired_returns_link_expired(app):
    """Token past expires_at → 410 code=link_expired."""
    email = f"c1b-expired-{uuid.uuid4().hex[:8]}@example.com"
    tid, tok, _ = await _seed_task_with_token(
        email=email, expires_in_seconds=-100,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as c:
            r = await c.get(f"/api/tasks/contribute/{tok}")
            assert r.status_code == 410
            body = r.json()
            assert body["detail"]["code"] == "link_expired"
    finally:
        await _cleanup(tid, tok)


@pytest.mark.asyncio
async def test_c1b_task_gone_returns_task_gone(app):
    """Token is valid but the referenced task was deleted → 410
    code=task_gone (previously surfaced as a misleading 404 'Task not
    found' which the FE rendered as catch-all "Invalid link")."""
    email = f"c1b-task-gone-{uuid.uuid4().hex[:8]}@example.com"
    tid, tok, _ = await _seed_task_with_token(email=email, delete_task=True)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as c:
            r = await c.get(f"/api/tasks/contribute/{tok}")
            assert r.status_code == 410
            body = r.json()
            assert body["detail"]["code"] == "task_gone"
    finally:
        await _cleanup(tid, tok)


@pytest.mark.asyncio
async def test_c1b_not_on_team_returns_not_on_team(app):
    """Token valid + task exists but contributor was removed from team
    → 410 code=not_on_team."""
    email = f"c1b-orphan-{uuid.uuid4().hex[:8]}@example.com"
    tid, tok, _ = await _seed_task_with_token(
        email=email, contributor_in_team=False,
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as c:
            r = await c.get(f"/api/tasks/contribute/{tok}")
            assert r.status_code == 410
            body = r.json()
            assert body["detail"]["code"] == "not_on_team"
    finally:
        await _cleanup(tid, tok)


@pytest.mark.asyncio
async def test_c1b_happy_path_returns_200(app):
    """Regression guard — clicking a valid, unused, unexpired token on
    a live task with the contributor on team must STILL return 200
    with the contribution payload. Phase B is an error-clarity
    refactor; the happy path must not change."""
    email = f"c1b-happy-{uuid.uuid4().hex[:8]}@example.com"
    tid, tok, aid = await _seed_task_with_token(email=email)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as c:
            r = await c.get(f"/api/tasks/contribute/{tok}")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["task"]["id"] == tid
            assert body["task"]["name"] == "C1B trace task"
            assert body["contributor_email"] == email.lower()
            assert body["contribution"] == "Review section 1"
            assert body["your_status"] == "not_started"
            assert body["expires_at"]
    finally:
        await _cleanup(tid, tok)


@pytest.mark.asyncio
async def test_c1b_cross_tenant_isolation_via_email_mismatch(app):
    """A token row that points at a task whose team contains a
    DIFFERENT contributor email returns 410 not_on_team, not the
    other contributor's data. This is the cross-tenant isolation
    guard — a token that survives a task edit must not leak the new
    contributor's contribution string back to the old email holder.

    # negative-leak: this assertion must remain green to lock in
    # tenant scoping at the contributor token level.
    """
    email_orig = f"c1b-orig-{uuid.uuid4().hex[:8]}@example.com"
    # Seed a task whose team contains a DIFFERENT contributor.
    tid = f"task-c1b-{uuid.uuid4().hex[:10]}"
    aid = f"acc-c1b-{uuid.uuid4().hex[:10]}"
    other_email = f"c1b-other-{uuid.uuid4().hex[:8]}@example.com"
    now = _now_iso()
    await db.tasks.insert_one({
        "id":         tid,
        "account_id": aid,
        "name":       "Cross-tenant trace",
        "objective":  "X",
        "success_criteria": "X",
        "team": [{
            "name": "Other Person",
            "role": "Lead",
            "email": other_email,
            "contribution": "Other person's secret contribution string",
            "contribution_mode": "magic_link",
        }],
        "state":      "active",
        "created_at": now,
        "updated_at": now,
    })
    # Token row points at the task but carries the original email.
    tok = uuid.uuid4().hex + uuid.uuid4().hex
    await db.task_contributor_tokens.insert_one({
        "id":                 uuid.uuid4().hex,
        "token":              tok,
        "task_id":            tid,
        "task_account_id":    aid,
        "contributor_email":  email_orig.lower(),
        "contributor_id":     email_orig.lower(),
        "expires_at":         (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "used":               False,
        "created_at":         now,
    })
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as c:
            r = await c.get(f"/api/tasks/contribute/{tok}")
            # Must be 410 not_on_team — must NOT be 200 with the other
            # person's contribution data leaked back.
            assert r.status_code == 410
            assert r.json()["detail"]["code"] == "not_on_team"
            assert "secret contribution string" not in r.text
    finally:
        await _cleanup(tid, tok)
