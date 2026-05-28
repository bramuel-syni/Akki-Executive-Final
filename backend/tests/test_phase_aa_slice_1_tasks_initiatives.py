"""
Phase AA-slice-1 (2026-05-27) — `tasks_initiatives` data model +
CRUD CI guards.

Lock surface:

  Schema (Pydantic) —
    * `TICategory` enum: 6 values reused from goals.
    * `TIOwnerRole` enum: 9 canonical roles + null nullable.
    * `TIStatus` enum: 5 values (Phase AA spec).
    * `TIExtractedBy` enum: "llm" | "manual".
    * `TaskInitiativeIn` validates title length, body length,
      score bounds.

  Indexes —
    * (id) unique.
    * (context_id, parent_objective_id).
    * (context_id, owner_role).
    * (context_id, status).
    * (context_id, source_document_id).
    * (context_id, status_active, updated_at) for soft-delete-aware
      hot path.

  CRUD runtime —
    * POST creates a row with `extracted_by="manual"` + `origin`
      stamping.
    * GET single returns the row, 404 when missing or soft-deleted.
    * GET list returns paginated rows, accepts filters.
    * PATCH applies partial updates + refreshes `updated_at` +
      `last_reassessed_at`.
    * DELETE flips `status_active` to False (soft-delete); the
      next GET returns 404.

  FK validation —
    * `parent_objective_id` pointing at a non-existent goal → 400.
    * `source_document_id` pointing at a non-existent doc → 400.
    * Both null are allowed.

  Audit —
    * `tasks_initiative.create` / `.patch` / `.delete` audit rows
      written on each CRUD.

  Multi-context isolation —
    * Row in context A is invisible to a GET against context B.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport


# ─────────────────────────────────────────────────────────────────
# Source-strict schema locks
# ─────────────────────────────────────────────────────────────────


def test_aa1_router_module_imports_clean() -> None:
    from routers import tasks_initiatives as r
    assert hasattr(r, "router")
    assert hasattr(r, "ensure_indexes")


def test_aa1_category_enum_locked_to_goals_enum() -> None:
    """Lock the 6-value Category enum to match `goals` exactly."""
    from routers.tasks_initiatives import TICategory  # type: ignore
    from typing import get_args
    assert set(get_args(TICategory)) == {
        "revenue", "customer", "product", "people", "operations", "compliance",
    }


def test_aa1_owner_role_enum_locked() -> None:
    """Lock the canonical 9-token owner-role enum + null nullability
    (the field is `Optional[TIOwnerRole]` on the schemas).
    """
    from routers.tasks_initiatives import TIOwnerRole
    from typing import get_args
    assert set(get_args(TIOwnerRole)) == {
        "CEO", "CFO", "COO", "CRO", "CTO", "CHRO", "CMO", "CIO", "OTHER",
    }


def test_aa1_status_enum_locked() -> None:
    """Lock the 5-value Status enum (Phase AA spec — `not_started`
    replaces the `abandoned` token from the goals model)."""
    from routers.tasks_initiatives import TIStatus
    from typing import get_args
    assert set(get_args(TIStatus)) == {
        "on_track", "at_risk", "off_track", "achieved", "not_started",
    }


def test_aa1_extracted_by_enum_locked() -> None:
    from routers.tasks_initiatives import TIExtractedBy
    from typing import get_args
    assert set(get_args(TIExtractedBy)) == {"llm", "manual"}


def test_aa1_schema_in_validates_title_length() -> None:
    from routers.tasks_initiatives import TaskInitiativeIn

    # Too short → ValidationError.
    with pytest.raises(Exception):
        TaskInitiativeIn(title="a")
    # Too long → ValidationError.
    with pytest.raises(Exception):
        TaskInitiativeIn(title="x" * 181)
    # Just right.
    ok = TaskInitiativeIn(title="Migrate ERP")
    assert ok.title == "Migrate ERP"
    # Defaults locked.
    assert ok.category == "operations"
    assert ok.status == "not_started"
    assert ok.performance_score == 0
    assert ok.probability_score == 0


def test_aa1_schema_in_validates_score_bounds() -> None:
    from routers.tasks_initiatives import TaskInitiativeIn

    with pytest.raises(Exception):
        TaskInitiativeIn(title="ok", performance_score=101)
    with pytest.raises(Exception):
        TaskInitiativeIn(title="ok", probability_score=-1)


def test_aa1_schema_in_validates_body_length() -> None:
    from routers.tasks_initiatives import TaskInitiativeIn

    with pytest.raises(Exception):
        TaskInitiativeIn(title="ok", body="x" * 4001)
    ok = TaskInitiativeIn(title="ok", body="x" * 4000)
    assert ok.body is not None


# ─────────────────────────────────────────────────────────────────
# Indexes lock (ensure_indexes is idempotent)
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_aa1_ensure_indexes_creates_all_expected_keys() -> None:
    from core import db
    from routers.tasks_initiatives import ensure_indexes

    # Indexes are built at startup; re-running here is idempotent.
    await ensure_indexes()
    info = await db.tasks_initiatives.index_information()
    # The compound keys we care about — assert each expected key list
    # appears in at least one index definition.
    expected = (
        [("id", 1)],
        [("context_id", 1), ("parent_objective_id", 1)],
        [("context_id", 1), ("owner_role", 1)],
        [("context_id", 1), ("status", 1)],
        [("context_id", 1), ("source_document_id", 1)],
        [("context_id", 1), ("status_active", 1), ("updated_at", -1)],
    )
    have = [tuple(v["key"]) for v in info.values()]
    for spec in expected:
        assert tuple(spec) in have, (
            f"Missing index {spec!r}. Have: {have!r}"
        )


# ─────────────────────────────────────────────────────────────────
# Runtime CRUD — uses the same in-process AsyncClient pattern the
# Phase R suite uses.
# ─────────────────────────────────────────────────────────────────


@pytest.fixture
async def member_actor():
    """Seed a context + a member account inside it; tear down on exit."""
    from core import db, hash_password

    uid = f"aa1-user-{uuid.uuid4().hex[:8]}"
    email = f"aa1-user-{uuid.uuid4().hex[:6]}@example.com"
    pw = "AA1!Phase-User"
    cid = f"aa1-ctx-{uuid.uuid4().hex[:8]}"
    other_cid = f"aa1-ctx-other-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    await db.accounts.insert_one({
        "id": uid, "email": email, "password_hash": hash_password(pw),
        "name": "AA1 Member", "tier": "executive",
        "declared_role": "executive", "mfa_enrolled": False,
        "is_superadmin": False, "created_at": now_iso,
    })
    await db.contexts.insert_one({
        "id": cid, "name": "AA1 Test Context",
        "owner_account_id": uid, "created_at": now_iso,
    })
    await db.contexts.insert_one({
        "id": other_cid, "name": "AA1 Other Context",
        "owner_account_id": uid, "created_at": now_iso,
    })
    await db.memberships.insert_one({
        "context_id": cid, "account_id": uid, "status": "active",
        "role": "executive", "created_at": now_iso,
    })
    await db.memberships.insert_one({
        "context_id": other_cid, "account_id": uid, "status": "active",
        "role": "executive", "created_at": now_iso,
    })

    yield {"uid": uid, "email": email, "password": pw,
           "cid": cid, "other_cid": other_cid}

    await db.accounts.delete_one({"id": uid})
    await db.contexts.delete_many({"id": {"$in": [cid, other_cid]}})
    await db.memberships.delete_many({"account_id": uid})
    await db.tasks_initiatives.delete_many({"context_id": {"$in": [cid, other_cid]}})
    await db.audit_log.delete_many({"account_id": uid})


async def _login_token(client, email: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_aa1_post_create_minimum_payload(member_actor) -> None:
    """POST with just title creates a row with sane defaults +
    `extracted_by="manual"`."""
    from server import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login_token(c, member_actor["email"], member_actor["password"])
        r = await c.post(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives",
            headers={"Authorization": f"Bearer {tok}"},
            json={"title": "Migrate ERP by Q4"},
        )
        assert r.status_code == 200, r.text
        row = r.json()
        assert row["title"] == "Migrate ERP by Q4"
        assert row["category"] == "operations"
        assert row["status"] == "not_started"
        assert row["performance_score"] == 0
        assert row["probability_score"] == 0
        assert row["owner_role"] is None
        assert row["parent_objective_id"] is None
        assert row["source_document_id"] is None
        assert row["extracted_by"] == "manual"
        assert row["status_active"] is True
        assert row["created_at"]
        assert row["updated_at"]
        assert row["last_reassessed_at"]
        assert "_id" not in row


@pytest.mark.asyncio
async def test_aa1_post_create_rejects_invalid_parent_objective(member_actor) -> None:
    from server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login_token(c, member_actor["email"], member_actor["password"])
        r = await c.post(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "title": "Bogus parent",
                "parent_objective_id": "ghost-goal-id-zzz",
            },
        )
        assert r.status_code == 400, r.text
        assert "parent_objective_id" in r.text


@pytest.mark.asyncio
async def test_aa1_post_create_rejects_invalid_source_doc(member_actor) -> None:
    from server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login_token(c, member_actor["email"], member_actor["password"])
        r = await c.post(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "title": "Bogus source",
                "source_document_id": "ghost-doc-id-zzz",
            },
        )
        assert r.status_code == 400, r.text
        assert "source_document_id" in r.text


@pytest.mark.asyncio
async def test_aa1_post_create_accepts_real_parent_and_source(member_actor) -> None:
    """Valid `parent_objective_id` + `source_document_id` persist."""
    from core import db
    from server import app

    cid = member_actor["cid"]
    # Seed a goal row + a doc row inside this context so the FK checks pass.
    goal_id = f"aa1-goal-{uuid.uuid4().hex[:8]}"
    doc_id = f"aa1-doc-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.strategic_goals.insert_one({
        "id": goal_id, "context_id": cid, "title": "Q4 ERP",
        "department": "ceo", "category": "operations",
        "status": "on_track", "created_at": now_iso, "updated_at": now_iso,
    })
    await db.documents.insert_one({
        "id": doc_id, "context_id": cid, "name": "Q4 ERP plan",
        "origin": "upload", "category": "report", "status": "extracted",
        "created_at": now_iso, "updated_at": now_iso,
    })
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            tok = await _login_token(c, member_actor["email"], member_actor["password"])
            r = await c.post(
                f"/api/contexts/{cid}/tasks-initiatives",
                headers={"Authorization": f"Bearer {tok}"},
                json={
                    "title":               "Hire ERP integrator",
                    "category":            "operations",
                    "owner_role":          "COO",
                    "parent_objective_id": goal_id,
                    "source_document_id":  doc_id,
                    "status":              "on_track",
                    "performance_score":   45,
                    "probability_score":   60,
                    "body":                "Scope, RFP, shortlist by 2026-Q3.",
                },
            )
            assert r.status_code == 200, r.text
            row = r.json()
            assert row["parent_objective_id"] == goal_id
            assert row["source_document_id"] == doc_id
            assert row["owner_role"] == "COO"
            assert row["performance_score"] == 45
            assert row["probability_score"] == 60
            assert row["body"] == "Scope, RFP, shortlist by 2026-Q3."
    finally:
        await db.strategic_goals.delete_one({"id": goal_id})
        await db.documents.delete_one({"id": doc_id})


@pytest.mark.asyncio
async def test_aa1_get_list_and_filters(member_actor) -> None:
    """Seed 3 rows + a 4th in the OTHER context. List in the first
    context returns exactly 3 (no leakage)."""
    from server import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login_token(c, member_actor["email"], member_actor["password"])
        headers = {"Authorization": f"Bearer {tok}"}

        for i in range(3):
            r = await c.post(
                f"/api/contexts/{member_actor['cid']}/tasks-initiatives",
                headers=headers,
                json={
                    "title": f"AA1 list row {i}",
                    "owner_role": "CEO" if i < 2 else "CFO",
                    "status": "at_risk" if i == 1 else "on_track",
                },
            )
            assert r.status_code == 200, r.text
        # Leakage probe — same title pattern in the OTHER context.
        r2 = await c.post(
            f"/api/contexts/{member_actor['other_cid']}/tasks-initiatives",
            headers=headers,
            json={"title": "AA1 list row OTHER"},
        )
        assert r2.status_code == 200, r2.text

        # All rows in the primary context.
        lst = await c.get(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives",
            headers=headers,
        )
        assert lst.status_code == 200, lst.text
        body = lst.json()
        assert body["total"] == 3
        assert {r["title"] for r in body["rows"]} == {
            "AA1 list row 0", "AA1 list row 1", "AA1 list row 2",
        }

        # Owner=CEO filter → 2 rows.
        ceo_only = await c.get(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives?owner=CEO",
            headers=headers,
        )
        assert ceo_only.json()["total"] == 2

        # Status=at_risk filter → 1 row.
        ar = await c.get(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives?status=at_risk",
            headers=headers,
        )
        assert ar.json()["total"] == 1

        # Unknown status → 422.
        bad = await c.get(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives?status=bogus",
            headers=headers,
        )
        assert bad.status_code == 422


@pytest.mark.asyncio
async def test_aa1_get_list_pagination(member_actor) -> None:
    """page_size + page semantics. 7 rows; pages of 3 → total=7, 3 pages."""
    from server import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login_token(c, member_actor["email"], member_actor["password"])
        headers = {"Authorization": f"Bearer {tok}"}
        for i in range(7):
            r = await c.post(
                f"/api/contexts/{member_actor['cid']}/tasks-initiatives",
                headers=headers,
                json={"title": f"AA1 pager {i:02d}"},
            )
            assert r.status_code == 200, r.text

        p1 = await c.get(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives?page=1&page_size=3",
            headers=headers,
        )
        assert p1.status_code == 200, p1.text
        p1j = p1.json()
        assert p1j["total"] == 7
        assert len(p1j["rows"]) == 3

        p3 = await c.get(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives?page=3&page_size=3",
            headers=headers,
        )
        p3j = p3.json()
        assert len(p3j["rows"]) == 1  # tail page


@pytest.mark.asyncio
async def test_aa1_patch_partial_update(member_actor) -> None:
    from server import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login_token(c, member_actor["email"], member_actor["password"])
        headers = {"Authorization": f"Bearer {tok}"}
        create = await c.post(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives",
            headers=headers,
            json={"title": "Patch me", "status": "not_started"},
        )
        rid = create.json()["id"]
        orig_updated_at = create.json()["updated_at"]

        # Small delay so updated_at can actually advance one second.
        import asyncio as _aio
        await _aio.sleep(1.05)

        patched = await c.patch(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives/{rid}",
            headers=headers,
            json={"status": "at_risk", "performance_score": 33},
        )
        assert patched.status_code == 200, patched.text
        row = patched.json()
        assert row["status"] == "at_risk"
        assert row["performance_score"] == 33
        assert row["title"] == "Patch me"  # untouched
        assert row["updated_at"] > orig_updated_at


@pytest.mark.asyncio
async def test_aa1_delete_soft_deletes_and_404s_on_reget(member_actor) -> None:
    from server import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login_token(c, member_actor["email"], member_actor["password"])
        headers = {"Authorization": f"Bearer {tok}"}
        create = await c.post(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives",
            headers=headers,
            json={"title": "Delete me"},
        )
        rid = create.json()["id"]
        d = await c.delete(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives/{rid}",
            headers=headers,
        )
        assert d.status_code == 200, d.text
        assert d.json()["ok"] is True

        # Re-GET → 404.
        g = await c.get(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives/{rid}",
            headers=headers,
        )
        assert g.status_code == 404


@pytest.mark.asyncio
async def test_aa1_get_single_404_when_missing(member_actor) -> None:
    from server import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login_token(c, member_actor["email"], member_actor["password"])
        r = await c.get(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives/ghost-{uuid.uuid4().hex[:6]}",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_aa1_audit_rows_written(member_actor) -> None:
    """Create + patch + delete each emit an audit_log row scoped to
    the actor + context."""
    from core import db
    from server import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        tok = await _login_token(c, member_actor["email"], member_actor["password"])
        headers = {"Authorization": f"Bearer {tok}"}
        cr = await c.post(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives",
            headers=headers, json={"title": "Audited row"},
        )
        rid = cr.json()["id"]
        await c.patch(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives/{rid}",
            headers=headers, json={"status": "at_risk"},
        )
        await c.delete(
            f"/api/contexts/{member_actor['cid']}/tasks-initiatives/{rid}",
            headers=headers,
        )

    actions = await db.audit_log.find(
        {
            "account_id": member_actor["uid"],
            "action": {"$in": [
                "tasks_initiative.create",
                "tasks_initiative.patch",
                "tasks_initiative.delete",
            ]},
        },
        {"_id": 0, "action": 1},
    ).to_list(50)
    actions_set = {a["action"] for a in actions}
    assert actions_set == {
        "tasks_initiative.create",
        "tasks_initiative.patch",
        "tasks_initiative.delete",
    }
