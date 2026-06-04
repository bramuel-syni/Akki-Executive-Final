"""Track B Phase B5 G7 (2026-06-04) — Document share "Field
required" false positive lockdown.

Two tests covering the schema swap + storage shape contract:

  1. test_share_document_accepts_recipient_emails_list
     POST `{recipient_emails: ["a@x.com","b@y.com"], message: "hi"}`
     → 200. Reads `document_shares` and asserts the row carries
     `recipient_emails: [...]` array AND `shared_with_email:
     "a@x.com"` (BC fallback). Engagement read returns the array.

  2. test_share_document_rejects_malformed_payloads
     Three sub-paths (all 422):
       (a) `{recipient_emails: []}` → min_length violation
       (b) `{to_email: "a@x.com"}` → legacy singular shape; required
           field `recipient_emails` missing
       (c) `{recipients: ["a@x.com"]}` → legacy plural FE shape; the
           field name changed, post-G7 BE must reject it explicitly

R4 ≤10 honoured: file owns 2 (well under cap).
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
    assert admin and admin.get("id"), (
        "admin@akki.ai must exist — see /app/memory/test_credentials.md"
    )
    cid = f"ctx-tap5-g7-{uuid.uuid4().hex[:8]}"
    doc_id = f"doc-tap5-g7-{uuid.uuid4().hex[:8]}"
    await db.contexts.insert_one({
        "id":               cid,
        "name":             "TAP5 G7 test ctx",
        "owner_account_id": admin["id"],
        "type":             "company",
        "created_at":       "2026-06-04T08:00:00Z",
    })
    await db.memberships.update_one(
        {"account_id": admin["id"], "context_id": cid},
        {"$set": {
            "id":         uuid.uuid4().hex,
            "account_id": admin["id"],
            "context_id": cid,
            "role":       "founder",
            "sub_role":   "ceo",
            "status":     "active",
            "created_at": "2026-06-04T08:00:00Z",
        }},
        upsert=True,
    )
    await db.documents.insert_one({
        "id":             doc_id,
        "context_id":     cid,
        "account_id":     admin["id"],
        "uploaded_by":    admin["id"],
        "name":           "TAP5 G7 test doc",
        "status":         "ready",
        "category":       "report",
        "created_at":     "2026-06-04T08:00:00Z",
    })
    return {"context_id": cid, "doc_id": doc_id, "account_id": admin["id"]}


async def _cleanup(seed: Dict[str, Any]) -> None:
    await db.document_shares.delete_many({"doc_id": seed["doc_id"]})
    await db.documents.delete_many({"id": seed["doc_id"]})
    await db.contexts.delete_many({"id": seed["context_id"]})
    await db.memberships.delete_many({"context_id": seed["context_id"]})


# ── 1. Happy path — schema swap + storage + engagement read shape ──


@pytest.mark.asyncio
async def test_share_document_accepts_recipient_emails_list(transport):
    seed = await _seed_doc_and_ctx()
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
            r = await ac.post(
                f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}/share",
                json={
                    "recipient_emails": ["alice@example.com", "bob@example.com"],
                    "message": "Per QA review",
                },
                headers=h,
            )
            # G7 pins: no more 422 "Field required" — the FE-canonical
            # payload shape now lands on the BE schema.
            assert r.status_code == 200, (
                f"share POST must accept recipient_emails list; got "
                f"{r.status_code} {r.text}"
            )
            body = r.json()
            assert "id" in body or "ok" in body  # response shape is permissive

            # Storage: BOTH `recipient_emails` (array, canonical) and
            # `shared_with_email` (singular, BC).
            row = await db.document_shares.find_one(
                {"doc_id": seed["doc_id"]}, {"_id": 0},
            )
            assert row is not None
            assert row.get("recipient_emails") == [
                "alice@example.com", "bob@example.com",
            ]
            assert row.get("shared_with_email") == "alice@example.com"
            assert row.get("message") == "Per QA review"

            # Engagement read: returns `recipient_emails` as an array
            # (FE renders `s.recipient_emails || []`).
            er = await ac.get(
                f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}/engagement",
                headers=h,
            )
            assert er.status_code == 200, er.text
            shares = er.json().get("shares") or []
            assert len(shares) == 1
            assert shares[0].get("recipient_emails") == [
                "alice@example.com", "bob@example.com",
            ]
            # BC fallback still surfaces.
            assert shares[0].get("shared_with_email") == "alice@example.com"
    finally:
        await _cleanup(seed)


# ── 2. Malformed payloads — three sub-paths all 422 ──


@pytest.mark.asyncio
async def test_share_document_rejects_malformed_payloads(transport):
    seed = await _seed_doc_and_ctx()
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
            base = f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}/share"

            # (a) Empty list — min_length=1 violation.
            ra = await ac.post(base, json={"recipient_emails": []}, headers=h)
            assert ra.status_code == 422, ra.text
            assert "recipient_emails" in ra.text

            # (b) Legacy singular shape — required field missing.
            rb = await ac.post(base, json={"to_email": "a@x.com"}, headers=h)
            assert rb.status_code == 422, rb.text
            detail_b = rb.json().get("detail") or []
            locs_b = [tuple(d.get("loc") or ()) for d in detail_b]
            assert any("recipient_emails" in str(loc) for loc in locs_b), (
                f"422 must point at the required `recipient_emails` field; "
                f"got locs={locs_b!r}"
            )

            # (c) Legacy plural FE shape (`recipients`) — explicitly
            # rejected post-G7 so the FE rename is enforced server-side.
            rc = await ac.post(
                base, json={"recipients": ["a@x.com"]}, headers=h,
            )
            assert rc.status_code == 422, rc.text
            detail_c = rc.json().get("detail") or []
            locs_c = [tuple(d.get("loc") or ()) for d in detail_c]
            assert any("recipient_emails" in str(loc) for loc in locs_c), (
                f"422 on legacy `recipients` payload must point at the "
                f"missing required `recipient_emails`; got locs={locs_c!r}"
            )
    finally:
        await _cleanup(seed)
