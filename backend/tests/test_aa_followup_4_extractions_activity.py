"""AA.followup.4 (2026-02 fork-resume) — Extraction Activity superadmin view.

Locks the read-only listing of recent LLM-extraction runs at
`/api/admin/extractions` + the frontend page at `/app/admin/extractions`.
"""
from __future__ import annotations

import asyncio
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


# ─────────────────────────────────────────────────────────────────
# A. Backend — router registration + auth gate + payload shape
# ─────────────────────────────────────────────────────────────────


def test_aa_f4_router_module_exists_and_exposes_router():
    from routers import admin_extractions  # type: ignore
    assert hasattr(admin_extractions, "router")
    # Prefix matches the spec.
    assert admin_extractions.router.prefix == "/api/admin/extractions"


def test_aa_f4_router_registered_in_server():
    src = (BACKEND / "server.py").read_text(encoding="utf-8")
    assert "from routers import admin_extractions as admin_extractions_router" in src
    assert "app.include_router(admin_extractions_router.router)" in src


def test_aa_f4_validation_outcome_helper_classifies_correctly():
    from routers.admin_extractions import _outcome  # type: ignore
    # All passed.
    assert _outcome(count=3, failures=0) == "all_passed"
    # Partial.
    assert _outcome(count=3, failures=2) == "partial"
    # All failed.
    assert _outcome(count=0, failures=2) == "all_failed"
    # Empty run treated as clean.
    assert _outcome(count=0, failures=0) == "all_passed"


@pytest.mark.asyncio
async def test_aa_f4_endpoint_requires_superadmin():
    """Non-superadmin must get 403."""
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    async def _fake_user():
        return {"id": "u-fake", "email": "fake@example.com", "is_superadmin": False}

    app.dependency_overrides[get_current_account] = _fake_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/admin/extractions")
            assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_account, None)


@pytest.mark.asyncio
async def test_aa_f4_endpoint_returns_locked_shape_with_joins():
    """Seed 2 extractions_log rows + matching docs + tasks, hit
    endpoint, verify shape + join enrichment."""
    from server import app  # type: ignore
    from core import db, get_current_account  # type: ignore

    cid = f"aa-f4-test-cid-{uuid.uuid4().hex[:8]}"
    doc1 = f"aa-f4-doc-{uuid.uuid4().hex[:8]}"
    doc2 = f"aa-f4-doc-{uuid.uuid4().hex[:8]}"
    iso = datetime.now(timezone.utc).isoformat()

    # Seed.
    await db.documents.insert_many([
        {"id": doc1, "title": "Q1 Strategy Pack", "category": "Strategy"},
        {"id": doc2, "title": "Audit Notes", "category": "Audit"},
    ])
    await db.extractions_log.insert_many([
        {
            "id": uuid.uuid4().hex,
            "document_id": doc1,
            "context_id":  cid,
            "kind":        "tasks",
            "count":       5,
            "failures":    1,
            "model":       "claude-sonnet-4-5",
            "created_at":  iso,
        },
        {
            "id": uuid.uuid4().hex,
            "document_id": doc2,
            "context_id":  cid,
            "kind":        "goals",
            "count":       3,
            "failures":    0,
            "model":       "claude-sonnet-4-5",
            "created_at":  iso,
        },
    ])
    # 2 live tasks attributed to doc1.
    await db.tasks_initiatives.insert_many([
        {"id": uuid.uuid4().hex, "context_id": cid, "source_document_id": doc1,
         "title": "Task A", "status": "not_started"},
        {"id": uuid.uuid4().hex, "context_id": cid, "source_document_id": doc1,
         "title": "Task B", "status": "not_started"},
    ])

    async def _fake_admin():
        return {"id": "admin-fake", "email": "admin@example.com", "is_superadmin": True}

    app.dependency_overrides[get_current_account] = _fake_admin
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/admin/extractions?limit=50")
            assert r.status_code == 200, r.text
            payload = r.json()
            assert "total" in payload and "items" in payload
            # Both seeded rows should show up.
            our_items = [it for it in payload["items"]
                         if it.get("context_id") == cid]
            assert len(our_items) == 2
            # Shape per item.
            for it in our_items:
                assert set(it.keys()) >= {
                    "id", "document_id", "document_title", "document_category",
                    "context_id", "kind", "model", "count", "failures",
                    "tasks_persisted", "validation_outcome", "created_at",
                }
            # Doc-title join worked.
            titles = {it["document_title"] for it in our_items}
            assert "Q1 Strategy Pack" in titles
            assert "Audit Notes" in titles
            # Per-doc task count join.
            doc1_row = next(it for it in our_items if it["document_id"] == doc1)
            assert doc1_row["tasks_persisted"] == 2
            assert doc1_row["validation_outcome"] == "partial"
            # Filter by kind=goals returns only doc2.
            r2 = await client.get("/api/admin/extractions?kind=goals&limit=50")
            assert r2.status_code == 200
            goals_only = [it for it in r2.json()["items"]
                          if it.get("context_id") == cid]
            assert len(goals_only) == 1
            assert goals_only[0]["document_id"] == doc2
            # Bad kind returns 400.
            r3 = await client.get("/api/admin/extractions?kind=invalid")
            assert r3.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_account, None)
        # Cleanup.
        await db.documents.delete_many({"id": {"$in": [doc1, doc2]}})
        await db.extractions_log.delete_many({"context_id": cid})
        await db.tasks_initiatives.delete_many({"context_id": cid})


# ─────────────────────────────────────────────────────────────────
# B. Frontend — page exists, route registered, gated by SuperadminRoute
# ─────────────────────────────────────────────────────────────────


def test_aa_f4_frontend_page_file_exists():
    p = REPO / "frontend" / "src" / "pages" / "admin" / "ExtractionsActivity.jsx"
    assert p.exists(), "ExtractionsActivity.jsx must exist"
    src = p.read_text(encoding="utf-8")
    assert 'data-testid="admin-extractions-page"' in src
    assert 'data-testid="extractions-table"' in src
    assert 'data-testid="extractions-refresh-btn"' in src
    assert 'data-testid="extractions-filter-strip"' in src


def test_aa_f4_route_registered_with_superadmin_gate():
    src = (REPO / "frontend" / "src" / "App.js").read_text(encoding="utf-8")
    # Lazy import.
    assert 'lazy(() => import("@/pages/admin/ExtractionsActivity"))' in src
    # Route must be wrapped by SuperadminRoute.
    assert 'path="/app/admin/extractions"' in src
    # Locate the route line.
    line = next(l for l in src.splitlines() if 'path="/app/admin/extractions"' in l)
    assert "<SuperadminRoute>" in line, (
        "Extraction Activity route must be wrapped in <SuperadminRoute>"
    )


def test_aa_f4_admin_index_tile_present():
    src = (REPO / "frontend" / "src" / "pages" / "admin" / "AdminIndex.jsx").read_text(encoding="utf-8")
    assert "admin-tile-extractions" in src
    assert "/app/admin/extractions" in src
