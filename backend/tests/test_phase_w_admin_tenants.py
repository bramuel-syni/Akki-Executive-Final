"""Phase W (2026-02 fork-resume) — Multi-tenant org list view.

Locks:
    1. /api/admin/tenants list + drill-down endpoints (superadmin-gated).
    2. Compartmentalization: NEVER returns doc bodies / chat / LLM content.
    3. Frontend page exists at /app/admin/tenants under SuperadminRoute.
    4. AdminIndex carries a tile for the new view.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


# ─────────────────────────────────────────────────────────────────
# A. Backend — router exists + endpoint shape
# ─────────────────────────────────────────────────────────────────


def test_phase_w_router_exists_with_correct_prefix():
    from routers import admin_tenants  # type: ignore
    assert admin_tenants.router.prefix == "/api/admin/tenants"


def test_phase_w_router_registered_in_server():
    src = (BACKEND / "server.py").read_text(encoding="utf-8")
    assert "from routers import admin_tenants as admin_tenants_router" in src
    assert "app.include_router(admin_tenants_router.router)" in src


def test_phase_w_router_does_not_leak_payload_fields():
    """The router must never project doc bodies, chat content, or
    LLM responses. Source-strict guard — scan non-comment lines."""
    src = (BACKEND / "routers" / "admin_tenants.py").read_text(encoding="utf-8")
    # Sensitive field markers (any one of these in a projection or
    # response would be a leak).
    forbidden = (
        "extracted_text",
        "doc_body",
        "chat_messages",
        "llm_response",
    )
    # Strip docstrings + line-comments before checking.
    lines = []
    in_doc = False
    for ln in src.splitlines():
        stripped = ln.strip()
        if stripped.startswith('"""') or stripped.startswith("'''"):
            # toggle docstring; ignore the line itself
            if stripped.count('"""') + stripped.count("'''") >= 2:
                # single-line docstring — ignore the line only
                continue
            in_doc = not in_doc
            continue
        if in_doc:
            continue
        if stripped.startswith("#"):
            continue
        # Strip inline comments.
        code = ln.split("#", 1)[0]
        lines.append(code)
    code_only = "\n".join(lines)
    for needle in forbidden:
        assert needle not in code_only, (
            f"admin_tenants.py code must not reference {needle!r} — "
            f"compartmentalization contract."
        )


@pytest.mark.asyncio
async def test_phase_w_list_requires_superadmin():
    from server import app  # type: ignore
    from core import get_current_account  # type: ignore

    async def _fake_user():
        return {"id": "u-x", "email": "x@example.com", "is_superadmin": False}

    app.dependency_overrides[get_current_account] = _fake_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            r = await client.get("/api/admin/tenants")
            assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_account, None)


@pytest.mark.asyncio
async def test_phase_w_list_returns_enriched_shape():
    """Seed a context + memberships + docs, list, verify enrichment."""
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    cid = f"phase-w-test-{uuid.uuid4().hex[:8]}"
    await db.contexts.insert_one({
        "id":   cid,
        "name": "Phase W Test Tenant",
        "type": "executive_personal",
        "owner_account_id": "acc-w",
        "status": "active",
        "created_at": "2026-02-01T00:00:00+00:00",
    })
    await db.memberships.insert_many([
        {"id": uuid.uuid4().hex, "context_id": cid, "account_id": "acc-a", "role": "executive", "created_at": "2026-02-01"},
        {"id": uuid.uuid4().hex, "context_id": cid, "account_id": "acc-b", "role": "reportee",  "created_at": "2026-02-02"},
    ])
    await db.documents.insert_many([
        {"id": uuid.uuid4().hex, "context_id": cid, "title": "doc 1", "updated_at": "2026-02-10"},
        {"id": uuid.uuid4().hex, "context_id": cid, "title": "doc 2", "updated_at": "2026-02-12"},
        {"id": uuid.uuid4().hex, "context_id": cid, "title": "doc 3", "updated_at": "2026-02-11"},
    ])

    async def _fake_admin():
        return {"id": "admin", "email": "admin@example.com", "is_superadmin": True}

    app.dependency_overrides[get_current_account] = _fake_admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            r = await client.get("/api/admin/tenants?q=Phase%20W%20Test")
            assert r.status_code == 200, r.text
            items = r.json()["items"]
            assert len(items) == 1
            it = items[0]
            assert it["id"] == cid
            assert it["name"] == "Phase W Test Tenant"
            assert it["member_count"] == 2
            assert it["doc_count"] == 3
            assert it["last_activity"] == "2026-02-12"

            # Drill-down endpoint.
            r2 = await client.get(f"/api/admin/tenants/{cid}")
            assert r2.status_code == 200, r2.text
            drill = r2.json()
            assert drill["id"] == cid
            assert drill["member_count"] == 2
            assert drill["doc_count"] == 3
            assert isinstance(drill.get("memberships"), list)
            assert len(drill["memberships"]) == 2
            # Membership rows must NOT carry payload-style fields.
            for m in drill["memberships"]:
                assert set(m.keys()) <= {"id", "context_id", "account_id", "role", "created_at"}

            # 404 on unknown.
            r3 = await client.get(f"/api/admin/tenants/{cid}-unknown")
            assert r3.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        await db.contexts.delete_one({"id": cid})
        await db.memberships.delete_many({"context_id": cid})
        await db.documents.delete_many({"context_id": cid})


# ─────────────────────────────────────────────────────────────────
# B. Frontend
# ─────────────────────────────────────────────────────────────────


def test_phase_w_frontend_page_exists_with_required_testids():
    p = REPO / "frontend" / "src" / "pages" / "admin" / "AdminTenants.jsx"
    assert p.exists()
    src = p.read_text(encoding="utf-8")
    for tid in (
        "admin-tenants-page",
        "tenants-table",
        "tenants-refresh-btn",
        "tenants-search-input",
        "tenants-type-filter",
        "tenant-drill-dialog",
    ):
        assert tid in src, f"AdminTenants.jsx must carry data-testid={tid!r}"


def test_phase_w_route_gated_by_superadmin():
    src = (REPO / "frontend" / "src" / "App.js").read_text(encoding="utf-8")
    assert 'lazy(() => import("@/pages/admin/AdminTenants"))' in src
    route_line = next(l for l in src.splitlines() if 'path="/app/admin/tenants"' in l)
    assert "<SuperadminRoute>" in route_line


def test_phase_w_admin_index_tile_present():
    src = (REPO / "frontend" / "src" / "pages" / "admin" / "AdminIndex.jsx").read_text(encoding="utf-8")
    assert "admin-tile-tenants" in src
    assert "/app/admin/tenants" in src
