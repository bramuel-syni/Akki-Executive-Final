"""T5 — Cycle Manager redesign.

Backend coverage:
  • C5 + G6 parity — the Cycle Page's Compile downloads hit the same
    `/work-studio/documents/{aid}/render?format=...` endpoint used by
    T4.1, returning non-empty binary for DOCX/PDF/PPTX with the
    correct Content-Type and X-AKKI-Sensitivity-Band header.

The G4 (C2) field validation and G5 (C3) email regex + dupe block are
client-side logic; their wire-checks live in `test_t5_frontend_wire.py`.
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
        "owner": _acc("t5-owner"),
        "ctx": f"ctx-t5-{uuid.uuid4().hex[:10]}",
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
        "id": cid, "name": "T5 Co",
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


_DOCX_MAGIC = b"PK\x03\x04"
_PPTX_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF-"


async def _insert_cycle_compilation(cid: str) -> str:
    """Insert a cycle compilation artefact in `work_studio_exports`
    matching the C5 Compile output shape (kind=cycle_board_pack)."""
    aid = str(uuid.uuid4())
    await core_mod.db.work_studio_exports.insert_one({
        "id": aid,
        "context_id": cid,
        "account_id": f"acc-{uuid.uuid4().hex[:8]}",
        "kind": "cycle_board_pack",
        "title": "Q3 2026 Cycle Compilation",
        "status": "complete",
        "lifecycle_state": "in_review",
        "output_format": "docx",
        "source_document_ids": [],
        "structured_content": {
            "sections": [
                {"heading": "Cycle Summary", "paragraphs": [
                    "Q3 reviewed with focus on margin protection.",
                    "Three contributions landed on the day.",
                ]},
                {"heading": "Decisions Needed", "paragraphs": [
                    "Re-baseline FY guidance; sign off audit timing.",
                ]},
            ],
        },
        "sensitivity_band": "CONFIDENTIAL",
        "created_at": "2026-05-25T00:00:00Z",
        "updated_at": "2026-05-25T00:00:00Z",
    })
    return aid


# ── T5.5 / C5 + G6 parity — Cycle compile downloads in DOCX/PDF/PPTX ──
@pytest.mark.parametrize("fmt,magic,media", [
    ("docx", _DOCX_MAGIC, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("pptx", _PPTX_MAGIC, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    ("pdf",  _PDF_MAGIC,  "application/pdf"),
])
@pytest.mark.asyncio
async def test_t5_5_c5_g6_cycle_compile_renders_in_all_three_formats(env, fmt, magic, media):
    """The C5 Compile downloads must work end-to-end for cycle compilations
    (kind=cycle_board_pack rows in work_studio_exports). This exercises
    the same T4.1 render endpoint that the Cycle Page's three buttons hit,
    proving G6 parity at the Cycle Page surface as well as the W3 surface.
    """
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    aid = await _insert_cycle_compilation(cid)
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{cid}/work-studio/documents/{aid}/render",
            params={"format": fmt},
        )
    assert r.status_code == 200, r.text
    body = r.content
    assert len(body) > 200, f"format {fmt} produced suspiciously small payload"
    assert body.startswith(magic), f"format {fmt} did not start with expected magic"
    assert media in (r.headers.get("content-type") or "")
    # Sensitivity band must leak through to cycle compile downloads
    # too — that's the Shield invariant.
    assert r.headers.get("x-akki-sensitivity-band") == "CONFIDENTIAL"


@pytest.mark.asyncio
async def test_t5_5_c5_g6_cycle_compile_audit_row_emitted(env):
    """Each Cycle Page download writes a `work_studio.compiled_document
    .rendered` audit row tagged with the kind=cycle_board_pack — so
    the Trust Center forensic trail covers Cycle compilations the same
    way it covers Work Studio compilations (G6 parity at the audit
    layer, not just the response layer).
    """
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]
    aid = await _insert_cycle_compilation(cid)
    async with _client() as c:
        r = await c.get(
            f"/api/contexts/{cid}/work-studio/documents/{aid}/render",
            params={"format": "pdf"},
        )
    assert r.status_code == 200
    row = await core_mod.db.audit_log.find_one(
        {
            "context_id": cid,
            "action": "work_studio.compiled_document.rendered",
            "resource_id": aid,
        },
        sort=[("created_at", -1)],
    )
    assert row is not None
    assert row.get("resource_type") == "work_studio_artefact.cycle_board_pack"
    assert row["metadata"]["format"] == "pdf"
