"""Iter-19 — Polish / Committee scope / Blog admin (in-process rewrite).

Hardening Step 4 (2026-05-25). Replaces the archived
`test_iter19_polish_committee_medium.py` E2E shell. Same invariants,
in-process httpx ASGI pattern.

Anti-source-string-assertion discipline (closeout §5.8): every test
asserts a CONTROL-FLOW CHAIN — request → response → Mongo → RBAC
gate — not a literal source match.

Coverage:
  Committee scope (T3.3 G8 adjacent surface):
    s19.A — GET /cycle/committees returns a list (empty OR seeded).
    s19.B — POST /checklists/generate accepts an optional
            `committee_id` body field without 422 (scope guard).
            The endpoint requires `cycle_name` + `deadline_date`
            independently — `committee_id` is the field whose
            shape we pin.

  Polish endpoint RBAC (T3.3 G8 adjacent surface):
    s19.C — POST /reports/{rid}/polish returns 404 for unknown rid
            (RBAC integrity — caller is a context member but the
            report doesn't exist).

  Blog admin gating:
    s19.D — `GET /api/blog/admin/posts/{slug}` requires superadmin
            (403 for non-superadmin).
    s19.E — Superadmin caller against an unknown slug → 404
            (gate is auth-FIRST → resolve-SECOND).
    s19.F — `GET /api/blog/subscribers` (admin-gated) requires
            superadmin (403 for non-superadmin).
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from server import app


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


async def _register(c, prefix: str, role: str = "executive"):
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"
    r = await c.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "Password123!@#",
            "name": f"{prefix.title()} Tester",
            "role": role,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    return body["access_token"], body["account"], body["contexts"][0]["id"]


async def _make_superadmin(account_id: str) -> None:
    await core_mod.db.accounts.update_one(
        {"id": account_id}, {"$set": {"is_superadmin": True}},
    )


# ── s19.A — committee scope GET returns a list ─────────────────────
@pytest.mark.asyncio
async def test_s19_a_committee_scope_get_returns_list():
    """Anchor chain: a context-member GET on /cycle/committees →
    200 + the response body carries a list (the `committees` key)."""
    async with _client() as c:
        token, _, ctx_id = await _register(c, "s19-a")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.get(
            f"/api/contexts/{ctx_id}/cycle/committees", headers=h,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        committees = body.get("committees") if isinstance(body, dict) else body
        assert isinstance(committees, list), f"expected a list, got: {body!r}"


@pytest.mark.asyncio
async def test_s19_b_checklists_generate_accepts_committee_id_field():
    """Anchor chain: POST /checklists/generate with a body that
    carries a `committee_id` field MUST NOT 422 with a complaint
    about the committee_id field itself. The endpoint may return
    200 / 404 / 400 depending on cycle state, but the body
    schema MUST accept committee_id as a scope hint without
    Pydantic rejection.

    The endpoint additionally requires `cycle_name` +
    `deadline_date` — those are unrelated to the T3.3 G8 scope
    contract we're pinning, so we provide them as plumbing.
    Pass criterion: response is NOT a 422 mentioning
    `committee_id`."""
    async with _client() as c:
        token, _, ctx_id = await _register(c, "s19-b")
        h = {"Authorization": f"Bearer {token}"}
        body_with_committee = {
            "cycle_name": "Q2 board cycle",
            "deadline_date": "2026-07-01",
            "committee_id": "synthetic-test-cid",
        }
        r = await c.post(
            f"/api/contexts/{ctx_id}/checklists/generate",
            json=body_with_committee,
            headers=h,
        )
        if r.status_code == 422:
            err_text = r.text.lower()
            assert "committee_id" not in err_text, (
                f"422 mentions `committee_id` — T3.3 G8 contract "
                f"regression. Response: {r.text}"
            )


# ── s19.C — polish endpoint 404 on unknown report id ───────────────
@pytest.mark.asyncio
async def test_s19_c_polish_unknown_report_returns_404():
    """Anchor chain: context-member POST /reports/{rid}/polish with
    an unknown rid → 404 (RBAC integrity: lookup happens AFTER
    membership check, so it's NOT a 403).

    Pins that the polish endpoint's RBAC ordering is correct: a
    valid-context but invalid-report request returns the precise
    failure code, not a silent 200 or a 403 leakage."""
    async with _client() as c:
        token, _, ctx_id = await _register(c, "s19-c")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.post(
            f"/api/contexts/{ctx_id}/reports/00000000-nonexistent/polish",
            json={},
            headers=h,
        )
        assert r.status_code == 404, (
            f"Polish endpoint should 404 on unknown report id; "
            f"got {r.status_code} {r.text!r}"
        )


# ── s19.D — blog admin GET slug requires superadmin ────────────────
@pytest.mark.asyncio
async def test_s19_d_blog_admin_get_slug_requires_superadmin():
    """Anchor chain: register a regular user (no superadmin flag)
    → GET /api/blog/admin/posts/anything → 403 (NOT 404, NOT
    silent 200). Auth gate fires BEFORE slug resolution."""
    async with _client() as c:
        token, _, _ = await _register(c, "s19-d")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.get("/api/blog/admin/posts/test-slug", headers=h)
        assert r.status_code == 403, (
            f"Blog admin should be superadmin-only; got "
            f"{r.status_code} {r.text!r}"
        )


# ── s19.E — superadmin gets 404 on unknown slug ────────────────────
@pytest.mark.asyncio
async def test_s19_e_blog_admin_superadmin_unknown_slug_returns_404():
    """Anchor chain: promote a user to superadmin → GET
    /api/blog/admin/posts/<random-slug> → 404 (NOT 403). Proves
    the gate is auth-FIRST → resolve-SECOND."""
    async with _client() as c:
        token, account, _ = await _register(c, "s19-e")
        await _make_superadmin(account["id"])
        h = {"Authorization": f"Bearer {token}"}
        r = await c.get(
            f"/api/blog/admin/posts/{uuid.uuid4().hex[:12]}",
            headers=h,
        )
        assert r.status_code == 404, (
            f"Superadmin on unknown slug should 404, got "
            f"{r.status_code} {r.text!r}"
        )


# ── s19.F — blog admin subscribers list is superadmin-gated ────────
@pytest.mark.asyncio
async def test_s19_f_blog_admin_list_requires_superadmin():
    """Anchor chain: regular user → GET /api/blog/subscribers →
    403. Pairs with s19.D to lock the broader admin namespace
    behind the gate. `/blog/subscribers` is the only LIST-style
    admin endpoint on the blog router; `/admin/posts/{slug}` is
    item-level and covered by s19.D / s19.E."""
    async with _client() as c:
        token, _, _ = await _register(c, "s19-f")
        h = {"Authorization": f"Bearer {token}"}
        r = await c.get("/api/blog/subscribers", headers=h)
        assert r.status_code == 403, r.text
