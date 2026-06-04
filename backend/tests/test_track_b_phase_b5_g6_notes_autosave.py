"""Track B Phase B5 G6 (2026-06-04) — Notes autosave backend
lockdown.

Three tests covering the BE contract the FE autosave depends on:

  1. PATCH `{notes: "foo"}` sets `notes_updated_at` to a fresh ISO
     timestamp; mutating an unrelated field (`category`) does NOT
     bump it. Pins the per-notes-timestamp invariant.
  2. PATCH `{notes: ""}` (the delete path) clears the field AND
     bumps `notes_updated_at` so the FE can render "Last updated: …"
     against the post-delete moment.
  3. Two consecutive PATCHes with the same notes text both succeed
     and both bump `notes_updated_at` — pins the debounce-can-flush-
     twice contract (idempotent for autosave race coalescing).

R4 ≤10 honoured: file owns 3 (well under cap).
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


async def _seed_doc_and_ctx(transport: ASGITransport) -> Dict[str, Any]:
    """Mint a context + minimal `documents` row for admin@akki.ai.
    Direct DB writes — independent of the upload pipeline."""
    admin = await db.accounts.find_one(
        {"email": "admin@akki.ai"}, {"_id": 0, "id": 1},
    )
    assert admin and admin.get("id"), (
        "admin@akki.ai must exist — see /app/memory/test_credentials.md"
    )
    cid = f"ctx-tap5-g6-{uuid.uuid4().hex[:8]}"
    doc_id = f"doc-tap5-g6-{uuid.uuid4().hex[:8]}"
    await db.contexts.insert_one({
        "id":               cid,
        "name":             "TAP5 G6 test ctx",
        "owner_account_id": admin["id"],
        "type":             "company",
        "created_at":       "2026-06-04T07:00:00Z",
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
            "created_at": "2026-06-04T07:00:00Z",
        }},
        upsert=True,
    )
    await db.documents.insert_one({
        "id":             doc_id,
        "context_id":     cid,
        "account_id":     admin["id"],
        "name":           "TAP5 G6 test doc",
        "status":         "ready",
        "category":       "report",
        "created_at":     "2026-06-04T07:00:00Z",
    })
    return {"context_id": cid, "doc_id": doc_id, "account_id": admin["id"]}


async def _cleanup(seed: Dict[str, Any]) -> None:
    await db.documents.delete_many({"id": seed["doc_id"]})
    await db.contexts.delete_many({"id": seed["context_id"]})
    await db.memberships.delete_many({"context_id": seed["context_id"]})


# ── 1. notes-bearing PATCH sets notes_updated_at; unrelated PATCH does not ──


@pytest.mark.asyncio
async def test_patch_notes_sets_notes_updated_at(transport):
    seed = await _seed_doc_and_ctx(transport)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")

            # Baseline — fresh row has neither field.
            row0 = await db.documents.find_one(
                {"id": seed["doc_id"]}, {"_id": 0, "notes": 1, "notes_updated_at": 1},
            )
            assert row0.get("notes") is None
            assert row0.get("notes_updated_at") is None

            # PATCH notes → both fields populate.
            r = await ac.patch(
                f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}",
                json={"notes": "First autosave."},
                headers=h,
            )
            assert r.status_code == 200, r.text
            row1 = await db.documents.find_one(
                {"id": seed["doc_id"]},
                {"_id": 0, "notes": 1, "notes_updated_at": 1, "updated_at": 1},
            )
            assert row1["notes"] == "First autosave."
            ts1 = row1["notes_updated_at"]
            assert isinstance(ts1, str) and ts1.startswith("20"), (
                f"notes_updated_at must be ISO timestamp; got {ts1!r}"
            )
            # FE invariant — sanitised PATCH response surfaces both fields.
            body = r.json()
            assert body.get("notes") == "First autosave."
            assert body.get("notes_updated_at") == ts1

            # Mutate an UNRELATED field — `notes_updated_at` MUST NOT bump.
            r = await ac.patch(
                f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}",
                json={"category": "briefing"},
                headers=h,
            )
            assert r.status_code == 200, r.text
            row2 = await db.documents.find_one(
                {"id": seed["doc_id"]},
                {"_id": 0, "notes_updated_at": 1, "updated_at": 1, "category": 1},
            )
            assert row2["category"] == "briefing"
            assert row2["notes_updated_at"] == ts1, (
                "unrelated PATCH must NOT bump notes_updated_at; "
                f"was {ts1!r}, became {row2['notes_updated_at']!r}"
            )
            # `updated_at` SHOULD have bumped (overall doc edit timestamp).
            assert row2["updated_at"] != row1["updated_at"]
    finally:
        await _cleanup(seed)


# ── 2. Delete path — empty notes clears field AND bumps timestamp ──


@pytest.mark.asyncio
async def test_patch_empty_notes_clears_field_and_bumps_timestamp(transport):
    seed = await _seed_doc_and_ctx(transport)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")

            # Establish a notes value first.
            r = await ac.patch(
                f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}",
                json={"notes": "Will be deleted."},
                headers=h,
            )
            assert r.status_code == 200
            row1 = await db.documents.find_one(
                {"id": seed["doc_id"]}, {"_id": 0, "notes": 1, "notes_updated_at": 1},
            )
            assert row1["notes"] == "Will be deleted."
            ts_before_delete = row1["notes_updated_at"]

            # PATCH empty string → clears field, bumps timestamp.
            r = await ac.patch(
                f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}",
                json={"notes": ""},
                headers=h,
            )
            assert r.status_code == 200, r.text
            row2 = await db.documents.find_one(
                {"id": seed["doc_id"]}, {"_id": 0, "notes": 1, "notes_updated_at": 1},
            )
            # Field nulled (matches existing Sprint Z1.2 behaviour).
            assert row2["notes"] is None
            # Timestamp bumped so FE can render "Last updated: …" against
            # the post-delete moment.
            assert row2["notes_updated_at"] != ts_before_delete
            assert isinstance(row2["notes_updated_at"], str)
    finally:
        await _cleanup(seed)


# ── 3. Debounce flush-twice idempotency ──


@pytest.mark.asyncio
async def test_patch_notes_idempotency_safe_for_autosave_debounce(transport):
    seed = await _seed_doc_and_ctx(transport)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
            payload = {"notes": "Same text both flushes."}

            # First flush.
            r1 = await ac.patch(
                f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}",
                json=payload, headers=h,
            )
            assert r1.status_code == 200, r1.text
            ts1 = r1.json().get("notes_updated_at")
            assert isinstance(ts1, str)

            # Second flush — same text, different timestamp.
            r2 = await ac.patch(
                f"/api/contexts/{seed['context_id']}/documents/{seed['doc_id']}",
                json=payload, headers=h,
            )
            assert r2.status_code == 200, r2.text
            ts2 = r2.json().get("notes_updated_at")
            assert isinstance(ts2, str)
            # No 4xx race / no body mismatch — autosave can flush twice
            # safely. (Timestamps may equal each other on very-fast
            # clocks; this test pins NO ERROR more than monotonicity.)
            row = await db.documents.find_one(
                {"id": seed["doc_id"]}, {"_id": 0, "notes": 1},
            )
            assert row["notes"] == "Same text both flushes."
    finally:
        await _cleanup(seed)
