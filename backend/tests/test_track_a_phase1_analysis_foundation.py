"""Track A Phase 1 — Analysis Foundation lockdown (v2 — post-tester R3 fix).

Rail R4 (≤10 tests per phase). Rail R3 (journey-completion, not
surface-render) — every export test below seeds via the NEW
`/upload-multi` endpoint and downloads through the existing
`/api/workbook/analyses/{aid}/report.{ext}` URLs. The previous
v1 of this file seeded via the legacy `/upload` shortcut and
therefore never exercised the multi-file → export journey; the
tester caught the gap at R3. This v2 closes it.

Test inventory (9, ≤10):
 1. Multi-file upload → 1 `ana-*` Analysis row with 2 source refs
 2. 250MB boundary → 413 on overflow
 3. PPTX builder byte-identical (legacy `wba-*` regression guard)
 4. Multi-file (`ana-*`) → .xlsx download is a real workbook
 5. Multi-file (`ana-*`) → .docx download is a real document
 6. Multi-file (`ana-*`) → .pptx download is a real presentation
 7. Session-close purges blob, retains Analysis row
 8. Cross-tenant guard (legacy + new + new exports + v2 read)
 9. OpenAPI spec lists the new endpoints

(Tests 10 — Solva v1 byte-identical guard 4/4 and voice-lint —
are delegated to the existing tree per the phase contract.)
"""
from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from typing import Any, Dict

import pytest
from httpx import AsyncClient, ASGITransport
from openpyxl import load_workbook

import server  # noqa: F401 — imports the FastAPI app
from server import app
from services.workbook_analyzer import (
    WorkbookAnalysis,
    build_pptx_report,
    parse_workbook,
)
from tests.fixtures.workbook_sample import build_sample_csv, build_sample_xlsx


# ─── Shared helpers ─────────────────────────────────────────────


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
    assert token, f"login returned no token: {body}"
    r = await client.get("/api/csrf")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": r.json()["csrf_token"],
    }


async def _seed_multi_analysis(
    client: AsyncClient, headers: Dict[str, str], *, context_suffix: str,
) -> str:
    """Seed via the NEW `/upload-multi` endpoint and return the
    `ana-*` analysis id. NO legacy fallback."""
    r = await client.post(
        "/api/workbook/upload-multi",
        files=[
            ("files", ("first.csv", build_sample_csv(), "text/csv")),
            ("files", ("second.xlsx", build_sample_xlsx(),
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
        ],
        data={"context_id": f"tracka-p1-{context_suffix}-" + uuid.uuid4().hex[:6]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    assert aid.startswith("ana-"), f"unexpected id prefix: {aid}"
    return aid


# ─── Test 1 — Multi-file upload ─────────────────────────────────


@pytest.mark.asyncio
async def test_multi_file_upload_creates_one_analysis_with_two_source_refs(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        ctx = "ctx-mfu-" + uuid.uuid4().hex[:6]
        r = await client.post(
            "/api/workbook/upload-multi",
            files=[
                ("files", ("first.csv", build_sample_csv(), "text/csv")),
                ("files", ("second.csv", build_sample_csv(), "text/csv")),
            ],
            data={"context_id": ctx},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["sources"]) == 2
        assert {s["filename"] for s in body["sources"]} == {"first.csv", "second.csv"}
        assert body["status"] == "draft"
        assert body["id"].startswith("ana-")
        row = await db.analyses.find_one({"id": body["id"]}, {"_id": 0})
        assert row is not None
        assert row["context_id"] == ctx
        assert len(row["sources"]) == 2
        assert await db.analysis_blobs.count_documents({"analysis_id": body["id"]}) == 2


# ─── Test 2 — 250MB boundary ────────────────────────────────────


@pytest.mark.asyncio
async def test_250mb_boundary_rejects_overflow(transport):
    from routers import workbook_analysis as wba_router
    assert wba_router.MAX_BYTES == 250 * 1024 * 1024
    real_max = wba_router.MAX_BYTES
    try:
        wba_router.MAX_BYTES = 1024
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
            payload = b"x," * 600 + b"\n"
            r = await client.post(
                "/api/workbook/upload",
                files={"file": ("big.csv", payload, "text/csv")},
                headers=headers,
            )
            assert r.status_code == 413, r.text
            assert "too_large_250mb" in r.text
    finally:
        wba_router.MAX_BYTES = real_max


# ─── Test 3 — PPTX builder byte-identical (legacy schema) ───────


def test_pptx_builder_byte_identical_on_same_input():
    """Direct legacy-schema regression guard. The builder MUST
    produce a structurally-identical deck across re-invocations.
    python-pptx embeds a build timestamp; the test asserts on the
    slide + notes XML content rather than raw bytes."""
    sheets, _ = parse_workbook(blob=build_sample_xlsx(), file_format="xlsx")
    analysis = WorkbookAnalysis(
        id="wba-regression",
        account_id="acct-x",
        document_id="wba-regression",
        filename="sample.xlsx",
        file_format="xlsx",
        file_size_bytes=4096,
        status="ready",
        sheets=sheets,
    )

    def _content(blob: bytes) -> bytes:
        with zipfile.ZipFile(io.BytesIO(blob), "r") as z:
            interesting = sorted(
                n for n in z.namelist()
                if (n.startswith("ppt/slides/slide") and n.endswith(".xml"))
                or (n.startswith("ppt/notesSlides/notesSlide") and n.endswith(".xml"))
            )
            return b"\n".join(z.read(n) for n in interesting)

    a = build_pptx_report(analysis)
    b = build_pptx_report(analysis)
    assert hashlib.sha256(_content(a)).hexdigest() == hashlib.sha256(_content(b)).hexdigest()


# ─── Test 4 — Multi-file → .xlsx end-to-end ─────────────────────


@pytest.mark.asyncio
async def test_multi_file_xlsx_export_end_to_end(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi_analysis(client, headers, context_suffix="xlsx")
        r = await client.get(f"/api/workbook/analyses/{aid}/report.xlsx", headers=headers)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert r.content[:4] == b"PK\x03\x04"
        assert len(r.content) > 2000
        # Multi-file Analysis carries the title as its filename
        # surrogate — adapter sets `filename` from `title`. Title
        # for a 2-file upload is "first.csv + 1 more". Just
        # assert the Content-Disposition + `_analysis.xlsx`.
        assert "_analysis.xlsx" in r.headers.get("content-disposition", "")
        wb = load_workbook(io.BytesIO(r.content), read_only=True, data_only=True)
        # The Summary sheet's analysis_id row must carry our aid.
        rows = list(wb["Summary"].iter_rows(min_row=1, max_row=14, values_only=True))
        aid_row = next(row for row in rows if row[0] == "analysis_id")
        assert aid_row[1] == aid


# ─── Test 5 — Multi-file → .docx end-to-end ─────────────────────


@pytest.mark.asyncio
async def test_multi_file_docx_export_end_to_end(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi_analysis(client, headers, context_suffix="docx")
        r = await client.get(f"/api/workbook/analyses/{aid}/report.docx", headers=headers)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert r.content[:4] == b"PK\x03\x04"
        assert len(r.content) > 2000
        assert "_analysis.docx" in r.headers.get("content-disposition", "")
        with zipfile.ZipFile(io.BytesIO(r.content), "r") as z:
            assert "word/document.xml" in z.namelist()
            body_xml = z.read("word/document.xml")
            assert b"Workbook Analysis" in body_xml


# ─── Test 6 — Multi-file → .pptx end-to-end (R3 blocker fix) ────


@pytest.mark.asyncio
async def test_multi_file_pptx_export_end_to_end(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        aid = await _seed_multi_analysis(client, headers, context_suffix="pptx")
        r = await client.get(f"/api/workbook/analyses/{aid}/report.pptx", headers=headers)
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
        assert r.content[:4] == b"PK\x03\x04"
        assert len(r.content) > 2000
        assert "_analysis.pptx" in r.headers.get("content-disposition", "")
        # The pptx file is a zip; a presentation always has at
        # least one slide XML at ppt/slides/slide1.xml.
        with zipfile.ZipFile(io.BytesIO(r.content), "r") as z:
            names = z.namelist()
            assert "ppt/slides/slide1.xml" in names


# ─── Test 7 — Session close ─────────────────────────────────────


@pytest.mark.asyncio
async def test_session_close_purges_blob_retains_analysis(transport):
    from core import db
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = await _csrf_login(client, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client.post(
            "/api/workbook/upload-multi",
            files=[("files", ("sc.csv", build_sample_csv(), "text/csv"))],
            data={"context_id": "tracka-p1-sc-" + uuid.uuid4().hex[:6]},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        assert await db.analysis_blobs.count_documents({"analysis_id": aid}) == 1
        r = await client.post(
            f"/api/workbook/v2/analyses/{aid}/session-close",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert await db.analysis_blobs.count_documents({"analysis_id": aid}) == 0
        retained = await db.analyses.find_one({"id": aid}, {"_id": 0})
        assert retained is not None
        assert all(s["blob_purged"] is True for s in retained["sources"])
        assert retained["status"] == "purged"
        assert any(rh["triggered_by"] == "session-close" for rh in retained["refresh_history"])
        assert body["id"] == aid


# ─── Test 8 — Tenant scope ──────────────────────────────────────


@pytest.mark.asyncio
async def test_tenant_scope_viewer_cannot_read_admin_analysis(transport):
    """Viewer must get 404 on admin's Analysis: read, .xlsx, .docx,
    .pptx, and the v2 read endpoint. Cross-direction: admin must
    not see viewer's new-entity Analysis."""
    async with AsyncClient(transport=transport, base_url="http://test") as client_admin:
        admin_headers = await _csrf_login(client_admin, "admin@akki.ai", "AkkiAdmin2026!")
        admin_aid = await _seed_multi_analysis(
            client_admin, admin_headers, context_suffix="tenant-admin",
        )

    async with AsyncClient(transport=transport, base_url="http://test") as client_viewer:
        viewer_headers = await _csrf_login(client_viewer, "viewer@akki.ai", "Viewer2026!")
        # All three export formats — 404.
        for ext in ("xlsx", "docx", "pptx"):
            r = await client_viewer.get(
                f"/api/workbook/analyses/{admin_aid}/report.{ext}",
                headers=viewer_headers,
            )
            assert r.status_code == 404, (
                f"tenant leak on report.{ext}: viewer got "
                f"{r.status_code}: {r.text[:200]}"
            )
        # v2 read — 404.
        r = await client_viewer.get(
            f"/api/workbook/v2/analyses/{admin_aid}", headers=viewer_headers,
        )
        assert r.status_code == 404

        # Viewer seeds their own; admin must not see it.
        viewer_aid = await _seed_multi_analysis(
            client_viewer, viewer_headers, context_suffix="tenant-viewer",
        )

    async with AsyncClient(transport=transport, base_url="http://test") as client_admin:
        admin_headers = await _csrf_login(client_admin, "admin@akki.ai", "AkkiAdmin2026!")
        r = await client_admin.get(
            f"/api/workbook/v2/analyses/{viewer_aid}", headers=admin_headers,
        )
        assert r.status_code == 404
        # And on exports too — admin's export for viewer's id 404s.
        r = await client_admin.get(
            f"/api/workbook/analyses/{viewer_aid}/report.xlsx",
            headers=admin_headers,
        )
        assert r.status_code == 404


# ─── Test 9 — OpenAPI spec lists the new endpoints ──────────────


@pytest.mark.asyncio
async def test_openapi_spec_includes_new_endpoints(transport):
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/openapi.json")
        if r.status_code == 404:
            r = await client.get("/openapi.json")
        assert r.status_code == 200, r.text
        paths = r.json().get("paths", {})
        assert "/api/workbook/analyses/{aid}/report.docx" in paths
        assert "/api/workbook/analyses/{aid}/report.xlsx" in paths
        assert "/api/workbook/upload-multi" in paths
        assert "/api/workbook/v2/analyses/{aid}" in paths
        assert "/api/workbook/v2/analyses/{aid}/session-close" in paths
        assert "/api/workbook/analyses/{aid}/report.pptx" in paths
        assert "get" in paths["/api/workbook/analyses/{aid}/report.docx"]
        assert "get" in paths["/api/workbook/analyses/{aid}/report.xlsx"]
        assert "post" in paths["/api/workbook/upload-multi"]
        assert "get" in paths["/api/workbook/v2/analyses/{aid}"]
        assert "post" in paths["/api/workbook/v2/analyses/{aid}/session-close"]
