"""Track A Phase 2 — Analyze Journal listing + drawer + notes lockdowns.

R4 (≤10 tests). Per-phase coverage (no overlap with Phase 1 file):

  1. GET /v2/analyses listing returns only the current account's rows
  2. POST upload-multi with objective string persists it on the entity
  3. Drawer mount-data load: GET /v2/analyses/{aid} returns full entity
  4. Notes auto-save flow: POST → GET → note present in `notes[]`
  5. Notes idempotency-ish: 2 sequential POSTs → 2 entries (no dedup)
  6. Export tab regression: all 3 formats still 200 on `ana-*` ids
  7. Cross-tenant: viewer cannot list/read/note admin's analysis
  8. Backward-compat: source-strict check that `/app/work-studio/analyze`
     redirects to `/app/analyze` in App.js
  9. Source-strict: AnalyzeDrawer has the three required tabs

(Test 10 — Solva v1 byte-identical guard + voice-lint — delegated to
the existing tree.)
"""
from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict

import pytest
from httpx import AsyncClient, ASGITransport

import server  # noqa: F401
from server import app
from tests.fixtures.workbook_sample import build_sample_csv

REPO = Path("/app")
FRONTEND = REPO / "frontend" / "src"


@pytest.fixture
def transport():
    return ASGITransport(app=app)


async def _csrf_login(client: AsyncClient, email: str, password: str) -> Dict[str, str]:
    r = await client.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token
    r = await client.get("/api/csrf")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": r.json()["csrf_token"],
    }


async def _seed_multi(client: AsyncClient, headers: Dict[str, str], *,
                      ctx: str, objective: str = "") -> str:
    fd = [
        ("files", ("a.csv", build_sample_csv(), "text/csv")),
        ("files", ("b.csv", build_sample_csv(), "text/csv")),
    ]
    data = {"context_id": ctx}
    if objective:
        data["objective"] = objective
    r = await client.post(
        "/api/workbook/upload-multi", files=fd, data=data, headers=headers,
    )
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    assert aid.startswith("ana-")
    return aid


# ─── Test 1 — listing tenant-scoped ─────────────────────────────


@pytest.mark.asyncio
async def test_v2_list_returns_only_tenant_rows(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_aid = await _seed_multi(
            ac, admin, ctx="tap2-list-" + uuid.uuid4().hex[:6],
        )

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        viewer = await _csrf_login(ac, "viewer@akki.ai", "Viewer2026!")
        viewer_aid = await _seed_multi(
            ac, viewer, ctx="tap2-list-v-" + uuid.uuid4().hex[:6],
        )
        r = await ac.get("/api/workbook/v2/analyses", headers=viewer)
        assert r.status_code == 200
        body = r.json()
        ids = {row["id"] for row in body}
        assert viewer_aid in ids
        assert admin_aid not in ids, "tenant leak — viewer saw admin's analysis"


# ─── Test 2 — objective string persists ─────────────────────────


@pytest.mark.asyncio
async def test_upload_multi_persists_objective_text(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(
            ac, admin,
            ctx="tap2-obj-" + uuid.uuid4().hex[:6],
            objective="Why did Q3 actuals miss the plan?",
        )
        r = await ac.get(f"/api/workbook/v2/analyses/{aid}", headers=admin)
        assert r.status_code == 200
        assert r.json()["objective"] == "Why did Q3 actuals miss the plan?"


# ─── Test 3 — drawer detail load ───────────────────────────────


@pytest.mark.asyncio
async def test_v2_detail_returns_full_entity(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap2-det-" + uuid.uuid4().hex[:6])
        r = await ac.get(f"/api/workbook/v2/analyses/{aid}", headers=admin)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == aid
        assert isinstance(body["sources"], list)
        assert isinstance(body["notes"], list)
        assert "refresh_history" in body
        assert "objective" in body


# ─── Test 4 — notes POST + verify on read ───────────────────────


@pytest.mark.asyncio
async def test_note_post_then_appears_on_read(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap2-note-" + uuid.uuid4().hex[:6])
        r = await ac.post(
            f"/api/workbook/v2/analyses/{aid}/notes",
            json={"body": "Outliers look like seasonal noise."},
            headers=admin,
        )
        assert r.status_code == 200, r.text
        note = r.json()
        assert note["body"] == "Outliers look like seasonal noise."
        r = await ac.get(f"/api/workbook/v2/analyses/{aid}", headers=admin)
        assert r.status_code == 200
        notes = r.json()["notes"]
        assert any(n["id"] == note["id"] for n in notes)


# ─── Test 5 — two notes both persist (no silent dedup) ──────────


@pytest.mark.asyncio
async def test_two_notes_both_persist(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap2-2note-" + uuid.uuid4().hex[:6])
        for body in ("first", "second"):
            r = await ac.post(
                f"/api/workbook/v2/analyses/{aid}/notes",
                json={"body": body}, headers=admin,
            )
            assert r.status_code == 200
        r = await ac.get(f"/api/workbook/v2/analyses/{aid}", headers=admin)
        bodies = [n["body"] for n in r.json()["notes"]]
        assert "first" in bodies
        assert "second" in bodies


# ─── Test 6 — export tab regression (Phase 1 still green) ───────


@pytest.mark.asyncio
async def test_export_endpoints_still_serve_ana_ids(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi(ac, admin, ctx="tap2-exp-" + uuid.uuid4().hex[:6])
        for ext, mime_prefix in (
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ):
            r = await ac.get(
                f"/api/workbook/analyses/{aid}/report.{ext}", headers=admin,
            )
            assert r.status_code == 200, f"{ext}: {r.text[:200]}"
            assert r.headers["content-type"].startswith(mime_prefix)
            assert r.content[:4] == b"PK\x03\x04"
        # Sanity — `.xlsx` zip-readable.
        r = await ac.get(f"/api/workbook/analyses/{aid}/report.xlsx", headers=admin)
        with zipfile.ZipFile(io.BytesIO(r.content), "r") as z:
            assert "xl/workbook.xml" in z.namelist()


# ─── Test 7 — cross-tenant guard on notes ────────────────────────


@pytest.mark.asyncio
async def test_cross_tenant_note_post_blocked(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        admin = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
        admin_aid = await _seed_multi(
            ac, admin, ctx="tap2-cross-" + uuid.uuid4().hex[:6],
        )
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        viewer = await _csrf_login(ac, "viewer@akki.ai", "Viewer2026!")
        r = await ac.post(
            f"/api/workbook/v2/analyses/{admin_aid}/notes",
            json={"body": "hi"}, headers=viewer,
        )
        assert r.status_code == 404
        r = await ac.patch(
            f"/api/workbook/v2/analyses/{admin_aid}/objective",
            json={"objective": "leak"}, headers=viewer,
        )
        assert r.status_code == 404
        r = await ac.get(f"/api/workbook/v2/analyses/{admin_aid}", headers=viewer)
        assert r.status_code == 404


# ─── Test 8 — backward-compat redirect mounted ──────────────────


def test_legacy_workstudio_analyze_redirects_to_analyze():
    src = (FRONTEND / "App.js").read_text(encoding="utf-8")
    # The legacy path must now be a <Navigate ... to="/app/analyze">.
    assert '<Route path="/app/work-studio/analyze" element={<Navigate to="/app/analyze" replace />} />' in src, (
        "App.js missing the backward-compat redirect from "
        "/app/work-studio/analyze → /app/analyze. Track A Phase 2 contract."
    )
    # And the new route exists.
    assert '<Route path="/app/analyze" element={<Gated><AnalyzeJournal /></Gated>} />' in src


# ─── Test 9 — drawer chrome has Bottom Line / Sources / Export ──


def test_analyze_drawer_renders_three_required_tabs():
    src = (FRONTEND / "components" / "analyze" / "AnalyzeDrawer.jsx").read_text(encoding="utf-8")
    assert 'data-testid="analyze-drawer-tab-bottom-line"' in src
    assert 'data-testid="analyze-drawer-tab-sources"' in src
    assert 'data-testid="analyze-drawer-tab-export"' in src
    # Export wires onClick to a function that builds a `/api/workbook/
    # analyses/${aid}/report.${ext}` URL. Both pieces must be present.
    assert "/api/workbook/analyses/" in src
    assert "report.${ext}" in src or "report.xlsx" in src
    # And each format button mounted with its own testid.
    for ext in ("xlsx", "docx", "pptx"):
        assert f'data-testid="analyze-drawer-export-{ext}"' in src, (
            f"AnalyzeDrawer missing export-{ext} button"
        )
