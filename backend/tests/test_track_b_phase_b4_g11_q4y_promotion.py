"""Track B Phase B4 G11 (2026-06-04) — Doc-extracted question →
Q4Y promotion lockdown.

Covers ONLY the promotion-helper contract + the two call-site
invariants. Does NOT re-test Q4Y CRUD / G13 drawer / G14 CTAs —
those are owned by `test_track_b_phase3_questions_completion.py`.

R4 ceiling: ≤10 functions. This file owns 4 (well under cap).

  1. `test_promote_questions_writes_to_cycle_questions_with_provenance`
     Feed `(doc, open_questions=[Q1, Q2])` → two `cycle_questions`
     rows land with stable id, `source_doc_id`, `assignee_account_id`,
     `cycle_id=""` sentinel, `asker_role` derived, history with
     `kind=raised_from_doc`, `promoted_from="document_intelligence"`.

  2. `test_promote_questions_is_idempotent_and_closes_orphans`
     Two-sub-path test:
       (a) Same input twice → still exactly 2 rows (stable-id upsert).
       (b) Re-promote with shorter input (1 question) → idx=0 row
           updates in place; idx=1 row flips to `status="closed"`
           with history `kind=closed, note="superseded_by_reextraction"`.
           Row is NOT deleted (audit preserved).

  3. `test_promote_questions_no_op_on_empty_list_when_no_prior_rows`
     `open_questions=[]` AND no prior rows → returns `[]`, writes
     nothing. (If prior rows exist, see test 2 for close-out
     behaviour.)

  4. `test_companyhome_attention_card_count_reflects_doc_extracted_questions`
     Integration — promote via the helper directly, then call the
     CompanyHome attention-card endpoint with the doc owner's
     creds. Assert `attention.questions.count >= 2`. Also asserts
     the no-double-fire invariant: calling the promoter twice
     does NOT double the count (stable-id upsert guarantee).
"""
from __future__ import annotations

import uuid
from typing import Any, Dict

import pytest
from httpx import AsyncClient, ASGITransport

import server  # noqa: F401
from server import app
from core import db
from services.documents.intelligence_service import (
    promote_intelligence_questions_to_q4y,
)


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


async def _provision_context_for_admin() -> Dict[str, Any]:
    """Direct DB writes so the tests are independent of the
    full upload/onboarding flow. Returns the context id + the
    admin account id."""
    admin = await db.accounts.find_one(
        {"email": "admin@akki.ai"}, {"_id": 0, "id": 1},
    )
    assert admin and admin.get("id"), (
        "admin@akki.ai must exist — see /app/memory/test_credentials.md"
    )
    cid = f"ctx-tap4-{uuid.uuid4().hex[:8]}"
    await db.contexts.insert_one({
        "id":               cid,
        "name":             "TAP4 G11 test ctx",
        "owner_account_id": admin["id"],
        "type":             "company",
        "created_at":       "2026-06-04T06:00:00Z",
    })
    # `require_context_membership` (core.py:258) requires the
    # membership row to carry `status="active"` — see the
    # convention in `test_q4y_p0_c3_mark_answered._seed_account_ctx`.
    await db.memberships.update_one(
        {"account_id": admin["id"], "context_id": cid},
        {"$set": {
            "id":         uuid.uuid4().hex,
            "account_id": admin["id"],
            "context_id": cid,
            "role":       "founder",
            "sub_role":   "ceo",
            "status":     "active",
            "created_at": "2026-06-04T06:00:00Z",
        }},
        upsert=True,
    )
    return {"context_id": cid, "account_id": admin["id"]}


def _doc_stub(doc_id: str, account_id: str) -> Dict[str, Any]:
    return {
        "id":          doc_id,
        "account_id":  account_id,
        "name":        "Strategic Plan FY26.pdf",
    }


async def _cleanup(doc_id: str, context_id: str) -> None:
    await db.cycle_questions.delete_many(
        {"id": {"$regex": f"^q4y:from_intel:{doc_id}:"}},
    )
    await db.contexts.delete_many({"id": context_id})
    await db.memberships.delete_many({"context_id": context_id})


# ── 1. Writes with full provenance ───────────────────────────────


@pytest.mark.asyncio
async def test_promote_questions_writes_to_cycle_questions_with_provenance():
    seed = await _provision_context_for_admin()
    doc_id = f"doc-tap4-{uuid.uuid4().hex[:8]}"
    doc = _doc_stub(doc_id, seed["account_id"])
    try:
        ids = await promote_intelligence_questions_to_q4y(
            db,
            doc=doc,
            context_id=seed["context_id"],
            account_id=seed["account_id"],
            open_questions=[
                "What's our churn assumption for FY26?",
                "Is the EU market entry milestone still tied to Q3?",
            ],
        )
        assert ids == [
            f"q4y:from_intel:{doc_id}:0",
            f"q4y:from_intel:{doc_id}:1",
        ], f"unexpected ids returned: {ids!r}"

        rows = await db.cycle_questions.find(
            {"id": {"$in": ids}}, {"_id": 0},
        ).to_list(None)
        assert len(rows) == 2

        # Sort by stable id for deterministic assertions.
        rows.sort(key=lambda r: r["id"])

        # Row 0 — full provenance contract.
        r0 = rows[0]
        assert r0["context_id"]          == seed["context_id"]
        assert r0["cycle_id"]            == ""  # sentinel
        assert r0["text"]                == "What's our churn assumption for FY26?"
        assert r0["source_doc_id"]       == doc_id
        assert r0["asked_by_account_id"] == seed["account_id"]
        assert r0["assignee_account_id"] == seed["account_id"]
        assert r0["status"]              == "open"
        assert r0["promoted_from"]       == "document_intelligence"
        assert r0["asker_role"] in {"board", "ceo", "team"}

        # History — initial `raised_from_doc` entry.
        hist = r0.get("history") or []
        assert len(hist) >= 1
        assert hist[0]["kind"] == "raised_from_doc"
        assert "Surfaced from document" in hist[0]["note"]

        # Row 1 — sanity (same shape, different text + idx).
        assert rows[1]["text"] == "Is the EU market entry milestone still tied to Q3?"
        assert rows[1]["source_doc_id"] == doc_id
    finally:
        await _cleanup(doc_id, seed["context_id"])


# ── 2. Idempotent + orphan close-out ────────────────────────────


@pytest.mark.asyncio
async def test_promote_questions_is_idempotent_and_closes_orphans():
    seed = await _provision_context_for_admin()
    doc_id = f"doc-tap4-{uuid.uuid4().hex[:8]}"
    doc = _doc_stub(doc_id, seed["account_id"])
    try:
        # First pass — 2 questions land.
        first = await promote_intelligence_questions_to_q4y(
            db, doc=doc, context_id=seed["context_id"],
            account_id=seed["account_id"],
            open_questions=["Q1?", "Q2?"],
        )
        assert len(first) == 2

        # ─ Sub-path (a) — same input twice, no dupes ─────────────
        second = await promote_intelligence_questions_to_q4y(
            db, doc=doc, context_id=seed["context_id"],
            account_id=seed["account_id"],
            open_questions=["Q1?", "Q2?"],
        )
        assert second == first
        all_rows = await db.cycle_questions.find(
            {"id": {"$regex": f"^q4y:from_intel:{doc_id}:"}},
            {"_id": 0, "id": 1, "status": 1},
        ).to_list(None)
        assert len(all_rows) == 2, (
            f"idempotent re-run must not create dupes; got {len(all_rows)} rows"
        )
        assert all(r["status"] == "open" for r in all_rows)

        # ─ Sub-path (b) — shrink to 1 question; idx=1 closes ─────
        third = await promote_intelligence_questions_to_q4y(
            db, doc=doc, context_id=seed["context_id"],
            account_id=seed["account_id"],
            open_questions=["Q1 only — re-extraction shrank"],
        )
        assert third == [f"q4y:from_intel:{doc_id}:0"]

        rows = await db.cycle_questions.find(
            {"id": {"$regex": f"^q4y:from_intel:{doc_id}:"}},
            {"_id": 0, "id": 1, "status": 1, "text": 1, "history": 1},
        ).to_list(None)
        rows.sort(key=lambda r: r["id"])
        # Two rows must still exist (NOT deleted — audit preserved).
        assert len(rows) == 2, (
            f"orphan row must be preserved for audit; got {len(rows)} rows"
        )
        # idx=0: re-extracted text, status still open.
        assert rows[0]["status"] == "open"
        assert rows[0]["text"]   == "Q1 only — re-extraction shrank"
        # idx=1: orphan — flipped to closed with reason.
        assert rows[1]["status"] == "closed", (
            f"orphan idx=1 must be status=closed; got {rows[1]['status']!r}"
        )
        last_hist = (rows[1].get("history") or [])[-1]
        assert last_hist.get("kind")   == "closed"
        assert last_hist.get("note")   == "superseded_by_reextraction"

        # ─ Sub-path (c) — orphan close-out is idempotent ─────────
        # Re-running with the same shrunk input must NOT append a
        # second 'closed' history entry on the already-closed row.
        fourth = await promote_intelligence_questions_to_q4y(
            db, doc=doc, context_id=seed["context_id"],
            account_id=seed["account_id"],
            open_questions=["Q1 only — re-extraction shrank"],
        )
        assert fourth == third
        row_idx1 = await db.cycle_questions.find_one(
            {"id": f"q4y:from_intel:{doc_id}:1"}, {"_id": 0, "history": 1},
        )
        closed_entries = [
            h for h in (row_idx1.get("history") or [])
            if h.get("kind") == "closed"
            and h.get("note") == "superseded_by_reextraction"
        ]
        assert len(closed_entries) == 1, (
            f"close-out must be idempotent; got {len(closed_entries)} 'closed' entries"
        )
    finally:
        await _cleanup(doc_id, seed["context_id"])


# ── 3. No-op on empty list ──────────────────────────────────────


@pytest.mark.asyncio
async def test_promote_questions_no_op_on_empty_list_when_no_prior_rows():
    seed = await _provision_context_for_admin()
    doc_id = f"doc-tap4-{uuid.uuid4().hex[:8]}"
    doc = _doc_stub(doc_id, seed["account_id"])
    try:
        result = await promote_intelligence_questions_to_q4y(
            db, doc=doc, context_id=seed["context_id"],
            account_id=seed["account_id"],
            open_questions=[],
        )
        assert result == []
        n = await db.cycle_questions.count_documents(
            {"id": {"$regex": f"^q4y:from_intel:{doc_id}:"}},
        )
        assert n == 0, f"no-op promoter must not write; got {n} rows"
    finally:
        await _cleanup(doc_id, seed["context_id"])


# ── 4. CompanyHome attention-card count integration ────────────


@pytest.mark.asyncio
async def test_companyhome_attention_card_count_reflects_doc_extracted_questions(transport):
    seed = await _provision_context_for_admin()
    doc_id = f"doc-tap4-{uuid.uuid4().hex[:8]}"
    doc = _doc_stub(doc_id, seed["account_id"])
    try:
        # Promote 3 questions.
        first = await promote_intelligence_questions_to_q4y(
            db, doc=doc, context_id=seed["context_id"],
            account_id=seed["account_id"],
            open_questions=["Q1?", "Q2?", "Q3?"],
        )
        assert len(first) == 3

        # No-double-fire invariant — promote the same 3 again
        # (simulates eager + lazy call sites both firing). Stable-id
        # upsert must keep the count at exactly 3.
        second = await promote_intelligence_questions_to_q4y(
            db, doc=doc, context_id=seed["context_id"],
            account_id=seed["account_id"],
            open_questions=["Q1?", "Q2?", "Q3?"],
        )
        assert second == first

        # Count via direct DB query (the helper's only job is to
        # make `cycle_questions` reflect the doc).
        open_count = await db.cycle_questions.count_documents({
            "context_id":          seed["context_id"],
            "assignee_account_id": seed["account_id"],
            "status":              {"$in": ["open", "pending"]},
        })
        assert open_count == 3, (
            f"after eager+lazy promotion the open-question count must "
            f"be 3 (no double-fire); got {open_count}"
        )

        # Integration via the home/insights API. We query the
        # authenticated route to prove the count surfaces end-to-end.
        # Route is `/api/contexts/{cid}/home/insights` (home.py:222).
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            admin_h = await _csrf_login(ac, "admin@akki.ai", "AkkiAdmin2026!")
            r = await ac.get(
                f"/api/contexts/{seed['context_id']}/home/insights",
                headers=admin_h,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            # Envelope shape from home.py:_insights_envelope:
            # {insights: {open_questions: {count: int, ...}, ...}}
            insights = body.get("insights") or {}
            oq = insights.get("open_questions") or {}
            assert oq.get("count") == 3, (
                f"Home insights open_questions.count must reflect "
                f"the 3 promoted rows; got {oq!r}"
            )
    finally:
        await _cleanup(doc_id, seed["context_id"])
