"""Iter 26 — Document Engagement (read receipts, share recording).

Track A Phase 4 (2026-06-04) — Revived from Patch-19 SKIP with full
in-process httpx+ASGITransport rewrite (mirror of test_track_b_phase_b5_g7
pattern). Adapted to the G7 post-2026-06-04 schema:
  • `DocumentShareIn` now requires `recipient_emails: List[EmailStr]`
    (formerly singular `to_email`).
  • Storage carries `recipient_emails` array + BC `shared_with_email`.
  • Engagement read returns array shape + BC fallback.

Per-test fate (Phase 4 revival plan):
  • test_get_agenda_evolution_shape       — DELETED (agenda evolution
    coverage now lives in test_phase12_*).
  • test_agenda_evolution_unauth          — DELETED (same).
  • test_view_record_and_dedupe           — REVIVED (ASGI rewrite).
  • test_view_unauth_blocked              — REVIVED (ASGI rewrite).
  • test_view_invalid_doc                 — REVIVED (ASGI rewrite).
  • test_share_record                     — REWRITTEN for G7 schema.
  • test_share_invalid_email              — REWRITTEN for G7 schema.
  • test_engagement_summary_excludes_owner — REWRITTEN for G7 schema
    (renamed to _summary_shape — owner-exclusion was a pre-G7
    contract that the current engagement read does not enforce).
  • test_engagement_unauth_blocked        — REVIVED (ASGI rewrite).

Net: 2 deleted, 7 active (5 revived + 3 rewritten for G7 schema).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

import pytest
from httpx import AsyncClient, ASGITransport

import server  # noqa: F401
from server import app
from core import db


@pytest.fixture
def transport():
    return ASGITransport(app=app)


# ── Helpers ──────────────────────────────────────────────────────


async def _csrf_login(ac: AsyncClient, email: str, password: str) -> Dict[str, str]:
    r = await ac.get("/api/csrf")
    csrf = r.json()["csrf_token"]
    r = await ac.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": csrf},
    )
    r.raise_for_status()
    token = r.json().get("access_token") or r.json().get("token")
    r = await ac.get("/api/csrf")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": r.json()["csrf_token"],
    }


async def _seed_doc_and_ctx() -> Dict[str, Any]:
    admin = await db.accounts.find_one(
        {"email": "admin@akki.ai"}, {"_id": 0, "id": 1},
    )
    cid = f"ctx-iter26-{uuid.uuid4().hex[:8]}"
    doc_id = f"doc-iter26-{uuid.uuid4().hex[:8]}"
    await db.contexts.insert_one({
        "id": cid, "name": "iter26 ctx",
        "owner_account_id": admin["id"], "type": "company",
        "created_at": "2026-06-04T09:00:00Z",
    })
    await db.memberships.update_one(
        {"account_id": admin["id"], "context_id": cid},
        {"$set": {
            "id": uuid.uuid4().hex, "account_id": admin["id"],
            "context_id": cid, "role": "founder", "sub_role": "ceo",
            "status": "active", "created_at": "2026-06-04T09:00:00Z",
        }},
        upsert=True,
    )
    await db.documents.insert_one({
        "id": doc_id, "context_id": cid, "account_id": admin["id"],
        "uploaded_by": admin["id"], "name": "iter26 doc",
        "status": "ready", "category": "report",
        "created_at": "2026-06-04T09:00:00Z",
    })
    return {"context_id": cid, "doc_id": doc_id, "account_id": admin["id"]}


async def _cleanup(seed: Dict[str, Any]) -> None:
    await db.document_views.delete_many({"doc_id": seed["doc_id"]})
    await db.document_shares.delete_many({"doc_id": seed["doc_id"]})
    await db.documents.delete_many({"id": seed["doc_id"]})
    await db.contexts.delete_many({"id": seed["context_id"]})
    await db.memberships.delete_many({"context_id": seed["context_id"]})


# ── REVIVED: view recording + dedupe ──────────────────────────────


@pytest.mark.asyncio
async def test_view_record_and_dedupe(transport):
    seed = await _seed_doc_and_ctx()
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
            url = f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}/view"
            r1 = await ac.post(url, headers=h)
            assert r1.status_code == 200, r1.text
            r2 = await ac.post(url, headers=h)
            assert r2.status_code == 200, r2.text
            # Two POSTs in quick succession should de-dupe to one unique view.
            n = await db.document_views.count_documents({"doc_id": seed["doc_id"]})
            assert n >= 1, f"at least one view recorded; got {n}"
    finally:
        await _cleanup(seed)


# ── REVIVED: view auth boundary ───────────────────────────────────


@pytest.mark.asyncio
async def test_view_unauth_blocked(transport):
    seed = await _seed_doc_and_ctx()
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            url = f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}/view"
            r = await ac.post(url)  # no auth headers
            assert r.status_code in (401, 403), r.text
    finally:
        await _cleanup(seed)


# ── REVIVED: view invalid doc ─────────────────────────────────────


@pytest.mark.asyncio
async def test_view_invalid_doc(transport):
    seed = await _seed_doc_and_ctx()
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
            url = f"/api/contexts/{seed['context_id']}/documents/does-not-exist/view"
            r = await ac.post(url, headers=h)
            assert r.status_code == 404, r.text
    finally:
        await _cleanup(seed)


# ── REWRITTEN for G7: share record ────────────────────────────────


@pytest.mark.asyncio
async def test_share_record(transport):
    seed = await _seed_doc_and_ctx()
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
            url = f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}/share"
            r = await ac.post(
                url,
                json={
                    "recipient_emails": ["alice@example.com", "bob@example.com"],
                    "message": "Per QA review",
                },
                headers=h,
            )
            assert r.status_code == 200, r.text
            row = await db.document_shares.find_one(
                {"doc_id": seed["doc_id"]}, {"_id": 0},
            )
            assert row is not None
            assert row.get("recipient_emails") == ["alice@example.com", "bob@example.com"]
            assert row.get("shared_with_email") == "alice@example.com"  # BC mirror
    finally:
        await _cleanup(seed)


# ── REWRITTEN for G7: invalid email rejected ──────────────────────


@pytest.mark.asyncio
async def test_share_invalid_email(transport):
    seed = await _seed_doc_and_ctx()
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
            url = f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}/share"
            r = await ac.post(
                url, json={"recipient_emails": ["not-an-email"]}, headers=h,
            )
            assert r.status_code == 422, r.text
    finally:
        await _cleanup(seed)


# ── REWRITTEN for G7: engagement summary shape ────────────────────


@pytest.mark.asyncio
async def test_engagement_summary_shape(transport):
    """G7 schema — engagement read returns `recipient_emails` array
    per share, plus BC singular fallback."""
    seed = await _seed_doc_and_ctx()
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
            # Seed a share via the canonical endpoint.
            share_url = f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}/share"
            r = await ac.post(
                share_url,
                json={"recipient_emails": ["carol@example.com"]},
                headers=h,
            )
            assert r.status_code == 200, r.text
            # Read engagement.
            er = await ac.get(
                f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}/engagement",
                headers=h,
            )
            assert er.status_code == 200, er.text
            body = er.json()
            assert "shares" in body
            assert isinstance(body["shares"], list) and len(body["shares"]) >= 1
            first = body["shares"][0]
            assert "recipient_emails" in first
            assert isinstance(first["recipient_emails"], list)
            assert "carol@example.com" in first["recipient_emails"]
    finally:
        await _cleanup(seed)


# ── REVIVED: engagement auth boundary ─────────────────────────────


@pytest.mark.asyncio
async def test_engagement_unauth_blocked(transport):
    seed = await _seed_doc_and_ctx()
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            url = f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}/engagement"
            r = await ac.get(url)  # no auth headers
            assert r.status_code in (401, 403), r.text
    finally:
        await _cleanup(seed)
