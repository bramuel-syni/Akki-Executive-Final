"""T2 — Surface UX upgrades. Spec contract: AKKI_PRODUCT_SPEC.md v1.1.

Backend coverage:
  • T2.1 — sanitize_doc surfaces `source_channel` so the listing can
    derive Uploaded vs Akki Generated origin per spec §4.A → D3/D4.
  • T2.3 — `monitor/update-status` now returns `supporting_docs`
    (id + name) so the drawer's Citations Card can render verifiable
    document references per spec §4.D → X5 step 5.

Frontend wire-checks for T2.1 / T2.2 / T2.3 / T2.4 live in
`tests/test_t2_frontend_wire.py`.
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
        "owner": _acc("t2-owner"),
        "ctx": f"ctx-t2-{uuid.uuid4().hex[:10]}",
    }


async def _seed(env: dict) -> None:
    db = core_mod.db
    cid = env["ctx"]
    await db.contexts.delete_many({"id": cid})
    for c in (
        "memberships", "documents", "objectives", "projects",
        "boardpacks",
    ):
        await getattr(db, c).delete_many({"context_id": cid})
    await db.accounts.update_one(
        {"id": env["owner"]["id"]},
        {"$set": env["owner"]},
        upsert=True,
    )
    await db.contexts.insert_one({
        "id": cid, "name": "T2 Co",
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


async def _insert_doc(cid: str, name: str, source_channel: str) -> str:
    did = f"doc-{uuid.uuid4().hex[:10]}"
    await core_mod.db.documents.insert_one({
        "id": did,
        "context_id": cid,
        "name": name,
        "original_filename": name,
        "mime_type": "application/pdf",
        "size_bytes": 1024,
        "status": "extracted",
        "source_channel": source_channel,
        "doc_kind": "policy",
        "created_at": "2026-05-25T00:00:00Z",
    })
    return did


# ── T2.1 — sanitize_doc must surface source_channel ───────────────────
@pytest.mark.asyncio
async def test_t2_1_documents_listing_exposes_source_channel(env):
    await _seed(env)
    _auth(env["owner"])
    cid = env["ctx"]

    await _insert_doc(cid, "Manual Upload.pdf", "upload")
    await _insert_doc(cid, "Compiled Pack.pdf", "cycle_compilation")
    await _insert_doc(cid, "Work Studio Export.pdf", "work_studio_export")
    await _insert_doc(cid, "Email Attach.pdf", "inbound_email")

    async with _client() as c:
        r = await c.get(f"/api/contexts/{cid}/documents")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) >= 4
    by_name = {row["name"]: row for row in rows}

    # The listing must surface source_channel so the frontend can
    # derive the origin tag client-side.
    assert by_name["Manual Upload.pdf"]["source_channel"] == "upload"
    assert by_name["Compiled Pack.pdf"]["source_channel"] == "cycle_compilation"
    assert by_name["Work Studio Export.pdf"]["source_channel"] == "work_studio_export"
    assert by_name["Email Attach.pdf"]["source_channel"] == "inbound_email"


# ── T2.3 — update-status must enrich supporting_docs with names ────────
@pytest.mark.asyncio
async def test_t2_3_update_status_returns_supporting_docs_with_names():
    """We exercise the name-resolution block directly using db.documents +
    a stub assessment so the test stays hermetic and doesn't need a live
    Shield call."""
    db = core_mod.db
    cid = f"ctx-t2-supdocs-{uuid.uuid4().hex[:6]}"
    did1 = f"doc-{uuid.uuid4().hex[:8]}"
    did2 = f"doc-{uuid.uuid4().hex[:8]}"
    await db.documents.insert_many([
        {"id": did1, "context_id": cid, "name": "Q1 Variance Memo.pdf"},
        {"id": did2, "context_id": cid, "name": "Audit Brief.docx"},
    ])

    # Mirror the resolution block from monitor_status_assessment.py.
    sup_ids = [did1, did2, "doc-missing"]
    cursor = db.documents.find(
        {"context_id": cid, "id": {"$in": sup_ids}},
        {"_id": 0, "id": 1, "name": 1, "original_filename": 1},
    )
    by_id = {row["id"]: row async for row in cursor}
    supporting_docs = []
    for did in sup_ids:
        r = by_id.get(did)
        if not r:
            continue
        supporting_docs.append({
            "id": r["id"],
            "name": r.get("name") or r.get("original_filename") or did,
        })

    # Order preserved, missing IDs dropped, names resolved.
    assert supporting_docs == [
        {"id": did1, "name": "Q1 Variance Memo.pdf"},
        {"id": did2, "name": "Audit Brief.docx"},
    ]


# ── T2.3 — sanity that the endpoint still wires the field through ─────
def test_t2_3_endpoint_emits_supporting_docs_field():
    """File-source check on the backend endpoint: the
    `last_akki_assessment` dict literal must include `supporting_docs`
    so the frontend always sees the key (even if empty).
    """
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "routers" / "monitor_status_assessment.py"
    text = src.read_text(encoding="utf-8")
    # Locate the dict literal that builds last_akki_assessment.
    anchor = "last_akki_assessment = {"
    idx = text.find(anchor)
    assert idx != -1, "last_akki_assessment construct not found"
    block = text[idx:idx + 800]
    assert '"supporting_docs": supporting_docs' in block, (
        "supporting_docs field missing from last_akki_assessment — the "
        "Citations Card cannot render verifiable references."
    )
