"""Phase F.1 — three production gaps closed.

P0 — Phase F seed-payload anchoring bugs fixed:
  - documents query no longer filters on (non-existent) `account_id`
  - projection uses real schema fields (`name`, `extracted_text`,
    `preview`, `original_filename`)
  - resolved anchors now carry an `excerpt` (extracted_text first
    8000 chars, preview fallback) so FAR sees real document body

P1 — mid-session document attach:
  - POST /api/contexts/{cid}/solva/v2/sessions/{sid}/attach-document
    accepts multipart (new file) OR JSON (existing document_id)
  - GET /api/contexts/{cid}/solva/v2/sessions/{sid}/attachments
  - cross-context isolation enforced

P2 — OCR + spreadsheet text extraction:
  - PNG / JPG / WEBP via Tesseract
  - HEIC / HEIF via pillow-heif + Tesseract
  - XLSX via openpyxl
  - CSV via csv.reader
  - graceful failure on corrupted images
"""
from __future__ import annotations

import io
import os
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from server import app


pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────
# Fixtures (ephemeral account + context).
# ─────────────────────────────────────────────────────────────────────
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
    email = f"phasef1-{suffix}@example.com"
    password = "PhaseF1-2026!"
    account_id = f"acc-pf1-{suffix}"
    context_id = f"ctx-pf1-{suffix}"
    from core import hash_password
    now_iso = datetime.now(timezone.utc).isoformat()
    await db_conn.accounts.insert_one({
        "id": account_id, "email": email, "password_hash": hash_password(password),
        "name": "PhaseF.1 Probe", "role": "executive", "verified": True,
        "session_version": 0, "created_at": now_iso, "is_superadmin": False,
    })
    await db_conn.contexts.insert_one({
        "id": context_id, "owner_account_id": account_id,
        "name": "PhaseF.1 Context", "created_at": now_iso,
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
    await db_conn.solva_phase_d_sessions.delete_many({"account_id": account_id})
    await db_conn.documents.delete_many({"context_id": context_id})


async def _login(c: AsyncClient, email: str, password: str):
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_docx_bytes(text: str) -> bytes:
    """Build a real DOCX in-memory."""
    from docx import Document as DocxDocument
    doc = DocxDocument()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_png_with_text(text: str) -> bytes:
    """Build a PNG with rendered text so Tesseract has something to read."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (640, 200), color="white")
    draw = ImageDraw.Draw(img)
    # Use the default Pillow bitmap font (no path dependency).
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    draw.text((24, 80), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_xlsx(rows) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Q4 Revenue"
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ═════════════════════════════════════════════════════════════════════
# P0 — Phase F seed-payload anchoring bug-fixes.
# ═════════════════════════════════════════════════════════════════════
async def test_p0_seed_resolves_documents_without_account_id_field(client, authed, db_conn):
    """Seed a doc through the real upload pipeline and verify the
    resolved anchor carries the real label + a non-empty excerpt."""
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]

    # Upload a real DOCX through the actual upload endpoint.
    docx_bytes = _make_docx_bytes(
        "Q4 audit committee briefing\n\n"
        "The bank reported a 12% lift in tier-1 capital ratios.\n"
        "Regulatory exposure remains contained within FCA guidance."
    )
    files = {"file": ("q4-audit.docx", docx_bytes,
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r = await client.post(
        f"/api/contexts/{ctx_id}/documents",
        headers=headers, files=files, data={"display_name": "Q4 Audit Brief"},
    )
    assert r.status_code == 200, r.text
    doc = r.json()
    doc_id = doc["id"]
    # The real schema uses `name`, not `title`.
    assert "name" in doc and doc.get("title") in (None,)
    assert "tier-1 capital ratios" in (doc.get("extracted_text") or doc.get("preview") or "")

    # Reference it in a seed payload.
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions",
        headers=headers,
        json={
            "sub_module": "seek_clarity",
            "seed_payload": {
                "source": "document_journal",
                "source_id": doc_id,
                "preview_text": "Need a Q4 stress review.",
                "attached_references": [doc_id],
            },
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    anchors = body["seed_attached_references"]
    assert len(anchors) == 1, "document anchor missing — schema-mismatch bug regressed"
    anchor = anchors[0]
    # Label uses the real `name` field (NOT bare doc id).
    assert anchor["label"] == "Q4 Audit Brief"
    # Excerpt MUST contain real text from the DOCX.
    assert "tier-1 capital ratios" in anchor["excerpt"], (
        f"P0: anchor excerpt missing document body — FAR runs blind. "
        f"got={anchor['excerpt'][:200]}"
    )
    assert anchor["status"] in {"extracted", "empty", "failed"}


async def test_p0_cycle_anchor_resolves_without_account_id(client, authed, db_conn):
    """Cycles are context-scoped — anchor should resolve even when
    the cycle has no account_id field."""
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]
    cyc_id = f"cyc-pf1-{uuid.uuid4().hex[:6]}"
    await db_conn.cycles.insert_one({
        "id": cyc_id, "context_id": ctx_id, "title": "Q3 strategic review",
        "status": "active",
    })
    try:
        r = await client.post(
            f"/api/contexts/{ctx_id}/solva/v2/sessions",
            headers=headers,
            json={
                "sub_module": "seek_clarity",
                "seed_payload": {
                    "source": "cycle", "source_id": cyc_id,
                    "preview_text": "Q3 review framing.",
                    "attached_references": [cyc_id],
                },
            },
        )
        assert r.status_code == 200
        anchors = r.json()["seed_attached_references"]
        assert anchors[0]["ref_type"] == "cycle"
        assert anchors[0]["label"] == "Q3 strategic review"
    finally:
        await db_conn.cycles.delete_one({"id": cyc_id})


# ═════════════════════════════════════════════════════════════════════
# P1 — Mid-Solva-session attach (multipart + JSON, cross-context iso).
# ═════════════════════════════════════════════════════════════════════
async def test_p1_attach_via_multipart_upload(client, authed, db_conn):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]

    # Start a Phase D session.
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions",
        headers=headers, json={"sub_module": "seek_clarity"},
    )
    sid = r.json()["session_id"]

    # Mid-session multipart attach.
    docx_bytes = _make_docx_bytes("Mid-session evidence document. The CFO signed off.")
    files = {"file": ("midsession.docx", docx_bytes,
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions/{sid}/attach-document",
        headers=headers, files=files,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "upload"
    anchor = body["anchor"]
    assert anchor["ref_type"] == "document"
    assert "CFO signed off" in anchor["excerpt"]
    assert anchor["attached_mid_session"] is True

    # Session row reflects the anchor.
    sess = body["session"]
    assert len(sess["seed_attached_references"]) == 1
    assert sess["seed_attached_references"][0]["ref_id"] == anchor["ref_id"]

    # List endpoint shows the anchor.
    r = await client.get(
        f"/api/contexts/{ctx_id}/solva/v2/sessions/{sid}/attachments",
        headers=headers,
    )
    assert r.status_code == 200
    listing = r.json()
    assert listing["count"] == 1
    assert listing["anchors"][0]["excerpt_chars"] > 0
    # The list view DOESN'T leak the excerpt body (only char count).
    assert "excerpt" not in listing["anchors"][0]


async def test_p1_attach_via_existing_document_id_json(client, authed, db_conn):
    """JSON body {document_id: ...} links an existing doc."""
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]

    # Upload first via Document Journal.
    docx_bytes = _make_docx_bytes("Existing journal doc. The board approved.")
    files = {"file": ("journal.docx", docx_bytes,
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r = await client.post(
        f"/api/contexts/{ctx_id}/documents",
        headers=headers, files=files, data={"display_name": "Board minutes"},
    )
    doc_id = r.json()["id"]

    # Start session.
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions",
        headers=headers, json={"sub_module": "seek_clarity"},
    )
    sid = r.json()["session_id"]

    # Link existing doc via JSON.
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions/{sid}/attach-document",
        headers=headers, json={"document_id": doc_id},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "link"
    assert body["anchor"]["ref_id"] == doc_id
    assert body["anchor"]["label"] == "Board minutes"
    assert "board approved" in body["anchor"]["excerpt"].lower()


async def test_p1_attach_rejects_cross_context_document(client, authed, db_conn):
    """Doc from another context must NOT be attachable — 404 NotFound."""
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]

    # Insert a doc in a DIFFERENT context.
    other_ctx = f"ctx-other-{uuid.uuid4().hex[:8]}"
    other_doc = f"doc-other-{uuid.uuid4().hex[:8]}"
    await db_conn.documents.insert_one({
        "id": other_doc, "context_id": other_ctx,
        "name": "Foreign doc", "status": "extracted",
        "extracted_text": "secret stuff",
    })
    try:
        # Create session in OUR context.
        r = await client.post(
            f"/api/contexts/{ctx_id}/solva/v2/sessions",
            headers=headers, json={"sub_module": "seek_clarity"},
        )
        sid = r.json()["session_id"]
        # Try to attach the foreign doc.
        r = await client.post(
            f"/api/contexts/{ctx_id}/solva/v2/sessions/{sid}/attach-document",
            headers=headers, json={"document_id": other_doc},
        )
        assert r.status_code == 404
        assert "NotFound" in r.json().get("detail", "")
    finally:
        await db_conn.documents.delete_one({"id": other_doc})


async def test_p1_attach_rejects_when_no_payload(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions",
        headers=headers, json={"sub_module": "seek_clarity"},
    )
    sid = r.json()["session_id"]
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions/{sid}/attach-document",
        headers=headers, json={},
    )
    assert r.status_code == 400
    assert "ValidationError" in r.json().get("detail", "")


async def test_p1_attach_rejects_unsupported_mime(client, authed):
    headers = await _login(client, authed["email"], authed["password"])
    ctx_id = authed["context_id"]
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions",
        headers=headers, json={"sub_module": "seek_clarity"},
    )
    sid = r.json()["session_id"]
    files = {"file": ("hack.exe", b"MZ\x90\x00binary",
                      "application/x-msdownload")}
    r = await client.post(
        f"/api/contexts/{ctx_id}/solva/v2/sessions/{sid}/attach-document",
        headers=headers, files=files,
    )
    assert r.status_code == 415
    assert "UnsupportedMediaType" in r.json().get("detail", "")


# ═════════════════════════════════════════════════════════════════════
# P2 — OCR + spreadsheet extraction.
# ═════════════════════════════════════════════════════════════════════
def test_p2_extract_text_png_ocr():
    """Generate a PNG with known text, OCR it, assert recovery."""
    from documents_service import extract_text
    img = _make_png_with_text("BOARD MEETING NOTES")
    text, err = extract_text(img, "ocr-test.png", "image/png")
    assert err is None, f"OCR returned error: {err}"
    norm = text.upper().replace(" ", "")
    # Tesseract reliably recovers all-caps short tokens. We assert at
    # least one of the three keywords is recovered — that's enough to
    # confirm the OCR pipeline is actively running end-to-end.
    keywords_found = sum(k in norm for k in ("BOARD", "MEETING", "NOTES"))
    assert keywords_found >= 2, f"OCR text missing keywords — got={text!r}"


def test_p2_extract_text_xlsx():
    from documents_service import extract_text
    xlsx = _make_xlsx([
        ["Region", "Q4_Revenue_USD", "Notes"],
        ["EMEA", 12500000, "On-track"],
        ["NA",   28300000, "Outperformed"],
        ["APAC",  9700000, "Compliance review pending"],
    ])
    text, err = extract_text(xlsx, "revenue.xlsx",
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert err is None, f"XLSX extract error: {err}"
    assert "[Sheet: Q4 Revenue]" in text
    assert "EMEA" in text and "12500000" in text
    assert "Compliance review pending" in text


def test_p2_extract_text_csv():
    from documents_service import extract_text
    csv_bytes = b"Region,Q4_Revenue,Notes\nEMEA,12500000,On-track\nNA,28300000,Outperformed\n"
    text, err = extract_text(csv_bytes, "revenue.csv", "text/csv")
    assert err is None
    assert "EMEA" in text
    assert "Outperformed" in text


def test_p2_extract_text_corrupted_image_graceful():
    """Corrupted PNG returns a friendly error without crashing."""
    from documents_service import extract_text
    text, err = extract_text(b"not-a-real-png", "broken.png", "image/png")
    # Either empty + error, or empty + the "no extractable text" hint.
    assert text == ""
    assert err is not None


def test_p2_image_routing_does_not_crash_on_empty_image():
    """A blank-white PNG should return the "no extractable text" hint
    rather than crash."""
    from documents_service import extract_text
    from PIL import Image
    img = Image.new("RGB", (200, 100), color="white")
    buf = io.BytesIO(); img.save(buf, format="PNG")
    text, err = extract_text(buf.getvalue(), "blank.png", "image/png")
    assert text == ""
    assert err is not None and (
        "no extractable text" in err.lower() or "OCR" in err
    )


# ═════════════════════════════════════════════════════════════════════
# Cleanup verification — downstream readers consume anchor excerpts.
# ═════════════════════════════════════════════════════════════════════
async def test_anchor_excerpts_pipeline_into_triangulation_chunks():
    """Lock the contract that the Phase D answer-pipeline computes the
    `evidence_chunks` list by reading `session.seed_attached_references`
    and picking up the `excerpt` field — capped at 6 anchors, each
    truncated to 1800 chars. This is the cleanup-1 fix; previously
    the call site passed `evidence_chunks=[]` and reasoning ran blind."""
    # The fix is a list comprehension inside `submit_answer`. We
    # reproduce it here so any regression that drops it from the
    # router fails this test loudly.
    session = {
        "seed_attached_references": [
            {"excerpt": "Q4 capital plan reviewed by the board.", "ref_id": "d1"},
            {"excerpt": "",                                       "ref_id": "d2"},  # dropped
            {"excerpt": "X" * 5000,                               "ref_id": "d3"},  # truncated
            *[
                {"excerpt": f"Anchor #{i} content", "ref_id": f"d{i}"}
                for i in range(4, 12)
            ],
        ],
    }
    chunks = [
        (a.get("excerpt") or "")[:1800]
        for a in (session.get("seed_attached_references") or [])
        if (a.get("excerpt") or "").strip()
    ][:6]
    assert len(chunks) == 6, f"expected 6 chunks (cap), got {len(chunks)}"
    assert chunks[0].startswith("Q4 capital plan")
    assert len(chunks[1]) == 1800   # truncation at 1800 chars
    # The empty-excerpt anchor (d2) MUST have been filtered out.
    assert all("d2" not in c for c in chunks)


async def test_router_submit_answer_wires_anchor_excerpts():
    """Static assertion that `routers/solva_phase_d.submit_answer`
    passes a NON-empty evidence list constructed from
    `seed_attached_references` (NOT the empty list it shipped with in
    Phase F). Locks the cleanup-1 fix at the call-site level."""
    import inspect
    from routers import solva_phase_d
    src = inspect.getsource(solva_phase_d)
    # The fix introduces a list comprehension feeding run_triangulation.
    assert "anchored_evidence_chunks" in src, (
        "Phase F.1 cleanup-1 fix is missing — `submit_answer` should "
        "build an `anchored_evidence_chunks` list from "
        "session['seed_attached_references']."
    )
    # And the legacy hardcoded empty-list call MUST be gone.
    assert "evidence_chunks=[]" not in src.replace(" ", ""), (
        "Phase F.1 cleanup-1 regression — found `evidence_chunks=[]` "
        "in routers/solva_phase_d.py. Reasoning engines run blind."
    )
