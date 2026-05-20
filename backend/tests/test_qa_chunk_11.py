"""Chunk 11 — 16-May Monitor-surface P1 + P2 batch (-045/-046/-048/-050/-051).

Backend regression coverage. Anchor: `/app/memory/qa_reports/QA_REPORT_16MAY2026.md`
sections QA-2026-05-16-045 / -046 / -048 / -050 / -051. Frontend-only display
behaviours (tabs + counts, context-bar dual-role label, switch-modal loading
state) are covered by render-smoke step 13 + ESLint; this file covers the
API-layer guarantees that the frontend reads from.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_conn():
    mclient = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = mclient[os.environ["DB_NAME"]]
    yield db
    mclient.close()


@pytest_asyncio.fixture
async def client():
    os.environ["SYNISENSE_LLM_MODE"] = "mock"
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.update(saved)


@pytest_asyncio.fixture
async def authed(db_conn):
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk11-{suffix}@example.com"
    password = "Chunk11-2026!"
    account_id = f"acc-c11-{suffix}"
    context_id = f"ctx-c11-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk11 Exec", "role": "executive", "declared_role": "executive",
        "verified": True, "session_version": 0, "created_at": now_iso,
        "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk11 Context", "created_at": now_iso,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "context_id": context_id, "account_id": account_id,
        "status": "active", "sub_role": "owner", "created_at": now_iso,
    })
    yield {"email": email, "password": password,
           "account_id": account_id, "context_id": context_id}
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.objectives.delete_many({"context_id": context_id})
    await db_conn.projects.delete_many({"context_id": context_id})
    await db_conn.strategic_goals.delete_many({"context_id": context_id})
    await db_conn.cycles.delete_many({"context_id": context_id})


@pytest_asyncio.fixture
async def authed_ned(db_conn):
    """Fixture for a NED-declared account (used for QA-048 RBAC test)."""
    suffix = uuid.uuid4().hex[:8]
    email = f"chunk11ned-{suffix}@example.com"
    password = "Chunk11-2026!"
    account_id = f"acc-c11n-{suffix}"
    context_id = f"ctx-c11n-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "Chunk11 NED", "role": "ned", "declared_role": "ned",
        "verified": True, "session_version": 0, "created_at": now_iso,
        "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "Chunk11 NED Context", "created_at": now_iso,
    })
    await db_conn.memberships.insert_one({
        "id": f"mem-{uuid.uuid4().hex[:8]}",
        "context_id": context_id, "account_id": account_id,
        "status": "active", "sub_role": "owner", "created_at": now_iso,
    })
    yield {"email": email, "password": password,
           "account_id": account_id, "context_id": context_id}
    await db_conn.accounts.delete_one({"id": account_id})
    await db_conn.contexts.delete_one({"id": context_id})
    await db_conn.memberships.delete_many({"account_id": account_id})
    await db_conn.strategic_goals.delete_many({"context_id": context_id})


async def _login(c, email, password):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body.get('access_token') or body.get('token')}"}


async def _seed_objective(db, context_id, rag_status, title=None):
    oid = f"obj-{uuid.uuid4().hex[:10]}"
    await db.objectives.insert_one({
        "id": oid,
        "context_id": context_id,
        "kind": "objective",
        "title": title or f"Test obj {rag_status}",
        "rag_status": rag_status,
        "score": {"green": 85, "amber": 55, "red": 30,
                  "achieved": 100, "not_started": 0}.get(rag_status, 50),
        "trend": "flat",
        "source": "manual",
        "source_refs": [],
        "owner": {"role": "CFO"},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return oid


# =====================================================================
# QA-045 — Monitor list returns status_counts per tab
# =====================================================================
async def test_qa045_status_counts_present_on_list_response(client, db_conn, authed):
    """The Monitor list endpoint MUST return a `status_counts` dict so
    the tab strip can show per-status badge counts. Pre-fix the
    frontend had `count: undefined` on every status tab."""
    # Seed one objective per RAG status.
    for rag in ["green", "amber", "red", "achieved", "not_started"]:
        await _seed_objective(db_conn, authed["context_id"], rag)
    # Plus an extra green.
    await _seed_objective(db_conn, authed["context_id"], "green", title="Bonus green")

    headers = await _login(client, authed["email"], authed["password"])
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/monitor/objective",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "status_counts" in body, body
    sc = body["status_counts"]
    assert sc["all"] == 6, sc
    assert sc["green"] == 2, sc
    assert sc["amber"] == 1, sc
    assert sc["red"] == 1, sc
    assert sc["achieved"] == 1, sc
    assert sc["not_started"] == 1, sc


async def test_qa045_status_counts_ignore_active_status_filter(client, db_conn, authed):
    """`status_counts` must reflect ALL items (modulo non-status
    filters like owner_role), NOT just the currently-filtered status.
    Otherwise switching tabs reshuffles the counts."""
    for rag in ["green", "amber", "achieved"]:
        await _seed_objective(db_conn, authed["context_id"], rag)

    headers = await _login(client, authed["email"], authed["password"])
    # Filter to status=amber — counts should STILL show green=1.
    r = await client.get(
        f"/api/contexts/{authed['context_id']}/monitor/objective?status=amber",
        headers=headers,
    )
    sc = r.json().get("status_counts") or {}
    assert sc["all"] == 3, sc
    assert sc["green"] == 1, sc
    assert sc["amber"] == 1, sc
    assert sc["achieved"] == 1, sc


# =====================================================================
# QA-046 — auto-suggest dedup
# =====================================================================
async def test_qa046_auto_suggest_objectives_dedups_after_accept(client, db_conn, authed):
    """A cycle that has already been promoted to an objective MUST NOT
    re-appear in `auto-suggest-objectives` on the next call."""
    headers = await _login(client, authed["email"], authed["password"])
    # Seed one active cycle.
    cycle_id = f"cyc-{uuid.uuid4().hex[:8]}"
    await db_conn.cycles.insert_one({
        "id": cycle_id, "context_id": authed["context_id"],
        "account_id": authed["account_id"], "status": "active",
        "title": "Reduce regulatory exposure", "readiness_pct": 70,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # Pre-accept: cycle surfaces.
    r1 = await client.get(
        f"/api/contexts/{authed['context_id']}/monitor/auto-suggest-objectives",
        headers=headers,
    )
    titles = [i["title"] for i in r1.json().get("items") or []]
    assert "Reduce regulatory exposure" in titles, titles

    # Accept the suggestion by minting an objective with the same source_refs.
    await db_conn.objectives.insert_one({
        "id": f"obj-{uuid.uuid4().hex[:8]}",
        "context_id": authed["context_id"], "kind": "objective",
        "title": "Reduce regulatory exposure", "rag_status": "amber",
        "score": 70, "trend": "flat", "source": "auto",
        "source_refs": [{"kind": "cycle", "id": cycle_id}],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    # Post-accept: suggestion should be filtered out.
    r2 = await client.get(
        f"/api/contexts/{authed['context_id']}/monitor/auto-suggest-objectives",
        headers=headers,
    )
    titles2 = [i["title"] for i in r2.json().get("items") or []]
    assert "Reduce regulatory exposure" not in titles2, titles2


async def test_qa046_auto_suggest_projects_dedups_after_accept(client, db_conn, authed):
    """Same dedup behaviour for projects."""
    headers = await _login(client, authed["email"], authed["password"])
    cycle_id = f"cyc-{uuid.uuid4().hex[:8]}"
    await db_conn.cycles.insert_one({
        "id": cycle_id, "context_id": authed["context_id"],
        "account_id": authed["account_id"], "status": "active",
        "title": "Refresh data analytics platform", "readiness_pct": 50,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    r1 = await client.get(
        f"/api/contexts/{authed['context_id']}/monitor/auto-suggest-projects",
        headers=headers,
    )
    assert any(i["title"] == "Refresh data analytics platform" for i in r1.json().get("items") or [])

    await db_conn.projects.insert_one({
        "id": f"prj-{uuid.uuid4().hex[:8]}",
        "context_id": authed["context_id"], "kind": "project",
        "title": "Refresh data analytics platform", "rag_status": "amber",
        "score": 50, "trend": "flat", "source": "auto",
        "source_refs": [{"kind": "cycle", "id": cycle_id}],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })

    r2 = await client.get(
        f"/api/contexts/{authed['context_id']}/monitor/auto-suggest-projects",
        headers=headers,
    )
    assert not any(i["title"] == "Refresh data analytics platform" for i in r2.json().get("items") or [])


# =====================================================================
# QA-048 — NED user cannot generate strategic goals
# =====================================================================
async def test_qa048_ned_user_rejected_on_strategic_goals_create(client, authed_ned):
    """NED accounts MUST get 403 on `POST /strategic-goals`."""
    headers = await _login(client, authed_ned["email"], authed_ned["password"])
    r = await client.post(
        f"/api/contexts/{authed_ned['context_id']}/strategic-goals",
        headers=headers,
        json={
            "department": "cfo", "title": "Some goal",
            "description": "x", "category": "revenue",
            "target_score": 80, "current_score": 50,
            "probability": 60,
        },
    )
    assert r.status_code == 403, r.text
    assert "Executive-only" in (r.json().get("detail") or "")


async def test_qa048_ned_user_rejected_on_strategic_goals_extract(client, authed_ned, db_conn):
    """NED accounts MUST get 403 on `POST /strategic-goals/extract`."""
    # Seed a doc in the NED's context (so the endpoint reaches the
    # RBAC guard, not a 404 on doc lookup).
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    await db_conn.documents.insert_one({
        "id": doc_id, "context_id": authed_ned["context_id"],
        "name": "strategy.pdf", "extracted_text": "fake",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    headers = await _login(client, authed_ned["email"], authed_ned["password"])
    r = await client.post(
        f"/api/contexts/{authed_ned['context_id']}/strategic-goals/extract",
        headers=headers,
        json={"doc_id": doc_id},
    )
    assert r.status_code == 403, r.text
    # Cleanup.
    await db_conn.documents.delete_one({"id": doc_id})


async def test_qa048_exec_user_can_still_create_strategic_goal(client, authed):
    """Defence-in-depth check — the RBAC guard MUST NOT block the
    Exec account that the feature is designed for."""
    headers = await _login(client, authed["email"], authed["password"])
    r = await client.post(
        f"/api/contexts/{authed['context_id']}/strategic-goals",
        headers=headers,
        json={
            "department": "cfo", "title": "Q3 capital uplift",
            "description": "increase CET1", "category": "revenue",
            "target_score": 80, "current_score": 50,
            "probability": 60,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json().get("title") == "Q3 capital uplift"
