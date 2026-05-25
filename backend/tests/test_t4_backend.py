"""T4 — Work Studio compiled document.

Backend coverage:
  • T4.1 / G6 — `/work-studio/documents/{aid}/render?format={docx|pdf|pptx}`
    streams a non-empty binary in each of the three formats with the
    correct Content-Type, Content-Disposition, and X-AKKI-Sensitivity-
    Band headers. Unknown format → 422. Missing artefact → 404.
    Artefact with no `structured_content` → 409.

T4.2 (G7) and T4.5 (G10) failure-path toast wording are file-source
asserted in `tests/test_t4_frontend_wire.py` because the toast strings
are emitted client-side from the LLM-error catch handlers (browser-use
cannot force the LLM to fail; testing those strings server-side would
require mocking the entire Shield pipeline).
"""
from __future__ import annotations

import os
import sys
import uuid

import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from server import app


_DOCX_MAGIC = b"PK\x03\x04"
_PPTX_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF-"


def _acc(prefix: str) -> dict:
    uid = uuid.uuid4().hex[:10]
    return {
        "id": f"{prefix}-{uid}",
        "email": f"{prefix}-{uid}@example.com",
        "display_name": prefix.title(),
        "name": prefix.title(),
    }


@pytest.fixture(scope="module")
def env() -> dict:
    return {
        "owner": _acc("t4-owner"),
        "ctx": f"ctx-t4-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env: dict) -> None:
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    for c in ("memberships", "work_studio_exports"):
        await getattr(db, c).delete_many({"context_id": cid})
    await db.accounts.update_one(
        {"id": env["owner"]["id"]},
        {"$set": env["owner"]},
        upsert=True,
    )
    await db.contexts.insert_one({
        "id": cid, "name": "T4 Co",
        "owner_account_id": env["owner"]["id"],
        "type": "executive_enterprise",
    })
    await db.memberships.update_one(
        {"context_id": cid, "account_id": env["owner"]["id"]},
        {"$set": {
            "context_id": cid,
            "account_id": env["owner"]["id"],
            "role": "executive", "sub_role": "admin", "status": "active",
        }},
        upsert=True,
    )


def _auth(account: dict) -> None:
    async def _o():
        return account
    app.dependency_overrides[core_mod.get_current_account] = _o


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


async def _insert_compiled_artefact(cid: str, kind: str = "board_pack") -> str:
    aid = str(uuid.uuid4())
    await core_mod.db.work_studio_exports.insert_one({
        "id": aid,
        "context_id": cid,
        "account_id": f"acc-{uuid.uuid4().hex[:8]}",
        "kind": kind,
        "title": "Q2 2026 Board Pack",
        "status": "complete",
        "lifecycle_state": "in_review",
        "output_format": "docx",
        "source_document_ids": [],
        "structured_content": {
            "sections": [
                {
                    "heading": "Executive Summary",
                    "paragraphs": [
                        "Revenue grew 6.2% QoQ, driven by enterprise expansion.",
                        "Operating margin held at 18.4% despite headcount investment.",
                    ],
                },
                {
                    "heading": "Risks",
                    "paragraphs": [
                        "Pipeline coverage remains light for Q4; FX exposure widened.",
                    ],
                },
            ],
        },
        "sensitivity_band": "CONFIDENTIAL",
        "created_at": "2026-05-25T00:00:00Z",
        "updated_at": "2026-05-25T00:00:00Z",
    })
    return aid


# ── T4.1 / G6 — Render endpoint, three formats ────────────────────────
@pytest.mark.parametrize("fmt,magic,media", [
    ("docx", _DOCX_MAGIC, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("pptx", _PPTX_MAGIC, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ("pdf",  _PDF_MAGIC,  "application/pdf"),
])
@pytest.mark.asyncio
async def test_t4_1_g6_render_returns_nonempty_binary_with_correct_headers(env, fmt, magic, media):
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    aid = await _insert_compiled_artefact(cid)
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{cid}/work-studio/documents/{aid}/render",
            params={"format": fmt},
        )
    assert r.status_code == 200, r.text
    # Non-empty binary.
    body = r.content
    assert len(body) > 200, f"format {fmt} produced suspiciously small payload ({len(body)} bytes)"
    # Magic bytes confirm the format actually rendered (not a JSON error masquerading as 200).
    assert body.startswith(magic), f"format {fmt} did not start with expected magic"
    # Content-Type matches.
    assert media in (r.headers.get("content-type") or "")
    # Content-Disposition exposes a filename containing the format extension.
    cd = r.headers.get("content-disposition") or ""
    assert ".{}".format(fmt) in cd.lower(), cd
    # Sensitivity band leaks through to download response (Shield invariant).
    assert r.headers.get("x-akki-sensitivity-band") == "CONFIDENTIAL"


@pytest.mark.asyncio
async def test_t4_1_g6_render_rejects_unknown_format(env):
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    aid = await _insert_compiled_artefact(cid)
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{cid}/work-studio/documents/{aid}/render",
            params={"format": "rtf"},
        )
    assert r.status_code == 422, r.text
    body = r.json()
    # G6 message identifies the accepted set.
    detail = body.get("detail", "")
    assert "docx" in detail and "pdf" in detail and "pptx" in detail, detail


@pytest.mark.asyncio
async def test_t4_1_g6_render_404_for_missing_artefact(env):
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{cid}/work-studio/documents/aid-does-not-exist/render",
            params={"format": "docx"},
        )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_t4_1_g6_render_409_when_no_structured_content(env):
    """Fresh Draft created via T3.1 D5 has no `structured_content` yet
    until the user runs a compile. The render endpoint must surface 409
    so the frontend can show a clean "not compiled yet" toast rather
    than an opaque 500."""
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    aid = str(uuid.uuid4())
    await core_mod.db.work_studio_exports.insert_one({
        "id": aid,
        "context_id": cid,
        "account_id": f"acc-{uuid.uuid4().hex[:8]}",
        "kind": "board_pack",
        "title": "Empty Draft",
        "status": "draft",
        "structured_content": None,  # no compile yet
        "source_document_ids": [],
        "created_at": "2026-05-25T00:00:00Z",
    })
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{cid}/work-studio/documents/{aid}/render",
            params={"format": "pdf"},
        )
    assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_t4_1_g6_render_writes_audit_row(env):
    """Each download writes a `work_studio.compiled_document.rendered`
    audit row so the Trust Center surfaces a forensic trail of who
    downloaded what + in which format."""
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    aid = await _insert_compiled_artefact(cid)
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{cid}/work-studio/documents/{aid}/render",
            params={"format": "docx"},
        )
    assert r.status_code == 200
    # Audit row landed.
    row = await core_mod.db.audit_log.find_one(
        {
            "context_id": cid,
            "action": "work_studio.compiled_document.rendered",
            "resource_id": aid,
        },
        sort=[("created_at", -1)],
    )
    assert row is not None
    assert row.get("metadata", {}).get("format") == "docx"
    assert isinstance(row.get("metadata", {}).get("size_bytes"), int)
