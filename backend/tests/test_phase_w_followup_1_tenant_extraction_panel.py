"""Phase W.followup.1 (2026-02 fork-resume) — Per-tenant extraction
activity panel in AdminTenants drilldown.

Locks:
    1. New backend endpoint GET /api/admin/tenants/{cid}/extractions
    2. /api/admin/extractions honours ?tenant_id= query param
    3. Frontend drill-dialog renders the extraction panel + outcome
       badges + "View all" deep-link including the tenant_id query param
    4. Empty state copy matches spec
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─────────────────────────────────────────────────────────────────
# A. Backend — new per-tenant endpoint + ?tenant_id= filter
# ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wf1_per_tenant_extraction_endpoint_shape():
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    cid = f"wf1-cid-{uuid.uuid4().hex[:8]}"
    other_cid = f"wf1-other-{uuid.uuid4().hex[:8]}"
    doc_id = f"wf1-doc-{uuid.uuid4().hex[:8]}"

    await db.contexts.insert_one({
        "id": cid, "name": "WF1 Test", "type": "executive_personal",
        "owner_account_id": "acc-wf1", "status": "active", "created_at": _iso(),
    })
    await db.documents.insert_one({
        "id": doc_id, "context_id": cid, "title": "WF1 doc", "category": "Strategy",
    })
    await db.extractions_log.insert_many([
        {"id": uuid.uuid4().hex, "document_id": doc_id, "context_id": cid,
         "kind": "tasks", "count": 4, "failures": 0, "model": "claude-sonnet-4-5",
         "created_at": _iso()},
        # Another tenant's row — must NOT appear.
        {"id": uuid.uuid4().hex, "document_id": "other-doc", "context_id": other_cid,
         "kind": "goals", "count": 1, "failures": 0, "model": "claude-sonnet-4-5",
         "created_at": _iso()},
    ])
    await db.tasks_initiatives.insert_one({
        "id": uuid.uuid4().hex, "context_id": cid, "source_document_id": doc_id,
        "title": "wf1 task", "status": "not_started",
    })

    async def _fake_admin():
        return {"id": "admin", "email": "a@e.com", "is_superadmin": True}

    app.dependency_overrides[get_current_account] = _fake_admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            # Per-tenant endpoint.
            r = await c.get(f"/api/admin/tenants/{cid}/extractions?limit=5")
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            it = data["items"][0]
            assert it["context_id"] == cid
            assert it["document_title"] == "WF1 doc"
            assert it["validation_outcome"] == "all_passed"
            assert it["tasks_persisted"] == 1
            assert it["kind"] == "tasks"

            # Global endpoint with ?tenant_id= filter — same row.
            r2 = await c.get(f"/api/admin/extractions?tenant_id={cid}")
            assert r2.status_code == 200, r2.text
            items2 = r2.json()["items"]
            assert all(i["context_id"] == cid for i in items2)
            assert len(items2) == 1

            # Per-tenant endpoint requires superadmin.
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        await db.contexts.delete_one({"id": cid})
        await db.documents.delete_one({"id": doc_id})
        await db.extractions_log.delete_many({"context_id": {"$in": [cid, other_cid]}})
        await db.tasks_initiatives.delete_many({"source_document_id": doc_id})


@pytest.mark.asyncio
async def test_wf1_per_tenant_endpoint_requires_superadmin():
    from server import app  # type: ignore
    from core import get_current_account  # type: ignore

    async def _fake_user():
        return {"id": "u", "email": "u@e.com", "is_superadmin": False}

    app.dependency_overrides[get_current_account] = _fake_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/api/admin/tenants/any-cid/extractions")
            assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_account, None)


@pytest.mark.asyncio
async def test_wf1_global_endpoint_tenant_id_filter_empty_other_tenant():
    """`?tenant_id=` to a tenant with no rows returns empty list, not 404."""
    from server import app  # type: ignore
    from core import get_current_account  # type: ignore

    async def _fake_admin():
        return {"id": "admin", "is_superadmin": True}

    app.dependency_overrides[get_current_account] = _fake_admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/api/admin/extractions?tenant_id=does-not-exist")
            assert r.status_code == 200
            assert r.json() == {"total": 0, "items": []}
    finally:
        app.dependency_overrides.pop(get_current_account, None)


# ─────────────────────────────────────────────────────────────────
# B. Frontend — drill panel + deep-link query param
# ─────────────────────────────────────────────────────────────────


def test_wf1_drill_panel_renders_in_admin_tenants_jsx():
    src = (REPO / "frontend" / "src" / "pages" / "admin" / "AdminTenants.jsx").read_text(encoding="utf-8")
    required = (
        "tenant-extraction-panel",
        "tenant-extraction-view-all-link",
        "tenant-extraction-empty",
        "tenant-extraction-table",
        "OutcomeBadge",          # component declared inline
        "/admin/tenants/${cid}/extractions",
    )
    for needle in required:
        assert needle in src, (
            f"AdminTenants.jsx must contain {needle!r} for the W.followup.1 panel"
        )
    # Deep-link must include tenant_id query param.
    assert "tenant_id=${drillCid}" in src or "tenant_id=${cid}" in src or "tenant_id=${tenantId}" in src or "?tenant_id=" in src, (
        "View-all link must deep-link to /app/admin/extractions?tenant_id=…"
    )
    # Empty-state copy per spec.
    assert "No extractions yet for this tenant." in src, (
        "Empty-state copy must read exactly 'No extractions yet for this tenant.'"
    )


def test_wf1_extractions_activity_honours_tenant_id_query_param():
    src = (REPO / "frontend" / "src" / "pages" / "admin" / "ExtractionsActivity.jsx").read_text(encoding="utf-8")
    assert "useSearchParams" in src, (
        "ExtractionsActivity.jsx must import useSearchParams from react-router-dom"
    )
    assert "tenant_id" in src, (
        "ExtractionsActivity.jsx must extract `tenant_id` from URL searchParams"
    )
    assert "extractions-tenant-scope-pill" in src, (
        "Tenant-scope pill must render when tenant_id is set"
    )
