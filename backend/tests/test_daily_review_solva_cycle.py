"""Phase 15.1 — Daily Review × Solva v2 cycle handoff regression test.

Pinned scope:
  - The bug this test guards against is `SOLVA_CYCLE_KIND` being undefined,
    which made every Daily-Review request 500 once a Solva v2 cycle handoff
    landed in the queue. The fix landed alongside this file in
    routers/daily_review.py.
  - The contract this test pins is:

      1.  GET  /api/me/review-queue                returns the seeded item
          with kind='solva_cycle_action'.
      2.  GET  /api/me/review-queue/counts         counts the seeded item
          in `total` and `by_kind.solva_cycle_action`.
      3.  POST /api/me/review-queue/items/solva_cycle_action/{id}/approve
            * returns 200,
            * inserts one row per question into db.questions,
            * flips solva_cycle_handoff_queue[id].status to 'approved',
            * flips solve_handoffs[review_queue_id=id].status to 'approved',
            * is idempotent (second call returns ok=True without re-writing).
      4.  Reject and edit paths each return 200 and produce the correct
          downstream effects.

The test seeds data directly into Mongo (faster + isolates this surface
from the v2 orchestrator). Real handoff creation is exercised by
test_solva_v2_integration.py.

Run:
    pytest /app/backend/tests/test_daily_review_solva_cycle.py -v
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import pytest
import requests
from dotenv import load_dotenv

# Read the same environment the running backend reads.
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"


# ---------------------------------------------------------------------------
# Mongo helpers — sync via pymongo so we don't fight the session-scoped
# event loop in conftest. This file is a sync test (requests + pymongo) so
# we never await anything; that keeps the surface decoupled from the v2
# integration test which is async.
# ---------------------------------------------------------------------------
def _mongo_client() -> Tuple[Any, str]:
    """Return (db, db_name). Reads MONGO_URL + DB_NAME from backend/.env if
    they're not already in the env, mirroring conftest's pattern in
    test_iter71_studio_blocks.py."""
    from pymongo import MongoClient

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME") or "akki_dev"
    if not mongo_url:
        with open("/app/backend/.env") as f:
            for line in f:
                if line.startswith("MONGO_URL="):
                    mongo_url = line.split("=", 1)[1].strip()
                elif line.startswith("DB_NAME="):
                    db_name = line.split("=", 1)[1].strip()
    assert mongo_url, "MONGO_URL is required for this test"
    return MongoClient(mongo_url)[db_name], db_name


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_queue_item(
    account_id: str,
    context_id: str,
    questions: List[Dict[str, Any]],
    *,
    session_id: str = None,
) -> Tuple[str, str]:
    """Seed one solva_cycle_handoff_queue row + one matching solve_handoffs
    row. Returns (queue_id, handoff_id)."""
    db, _ = _mongo_client()
    queue_id = str(uuid.uuid4())
    handoff_id = str(uuid.uuid4())
    sid = session_id or str(uuid.uuid4())
    db.solva_cycle_handoff_queue.insert_one({
        "id": queue_id,
        "kind": "solva_cycle_action",
        "account_id": account_id,
        "context_id": context_id,
        "session_id": sid,
        "cluster_id": "cluster.test",
        "cluster_label": "Test cluster · Phase 15.1 regression",
        "questions": questions,
        "status": "pending_review",
        "note": "",
        "audit_entry_count": 7,
        "created_at": _now_iso(),
        "reviewed_at": None,
    })
    db.solve_handoffs.insert_one({
        "id": handoff_id,
        "session_id": sid,
        "account_id": account_id,
        "target": "cycle",
        "status": "pending_review",
        "review_queue_id": queue_id,
        "created_at": _now_iso(),
    })
    return queue_id, handoff_id


def _cleanup_queue(queue_id: str) -> None:
    """Hard-delete what this test seeded — including any db.questions rows
    that approve created. Idempotent."""
    db, _ = _mongo_client()
    item = db.solva_cycle_handoff_queue.find_one({"id": queue_id}, {"inserted_question_ids": 1})
    if item:
        for qid in (item.get("inserted_question_ids") or []):
            db.questions.delete_one({"id": qid})
    db.solva_cycle_handoff_queue.delete_one({"id": queue_id})
    db.solve_handoffs.delete_many({"review_queue_id": queue_id})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client() -> requests.Session:
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def admin_account(client: requests.Session) -> Dict[str, Any]:
    r = client.get(f"{BASE_URL}/api/auth/me", timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    acc = body.get("account") or {}
    assert acc.get("id"), "no account on /auth/me"
    cid = acc.get("default_context_id")
    if not cid and body.get("contexts"):
        cid = body["contexts"][0]["id"]
    assert cid, "no default context for admin"
    return {"id": acc["id"], "context_id": cid, "email": acc.get("email")}


def _seed_questions() -> List[Dict[str, Any]]:
    return [
        {
            "id": str(uuid.uuid4()),
            "ordinal": 1,
            "text": "What does the comparable evidence say about board composition risk?",
            "category": "strategic",
            "source_tier": "comparable",
            "confidence_band": "Likely",
        },
        {
            "id": str(uuid.uuid4()),
            "ordinal": 2,
            "text": "Where in the corpus is the strongest signal on capital pressure?",
            "category": "strategic",
            "source_tier": "corpus",
            "confidence_band": "High-conviction",
        },
    ]


# ---------------------------------------------------------------------------
# Test 1 — kind constant is defined and the listing endpoint surfaces the item
# ---------------------------------------------------------------------------
def test_solva_cycle_kind_constant_defined():
    """Smoke test: import the router and assert the constant the bug took out."""
    from routers import daily_review as dr

    assert dr.SOLVA_CYCLE_KIND == "solva_cycle_action", (
        "SOLVA_CYCLE_KIND must equal 'solva_cycle_action' to keep "
        "routers/solva_v2.py and frontend kind dispatch in sync."
    )
    # Sanity: the four kind constants must all be distinct strings.
    kinds = {dr.INBOUND_KIND, dr.BRIEFING_KIND, dr.STUDIO_KIND, dr.SOLVA_CYCLE_KIND}
    assert len(kinds) == 4, f"kind constants collided: {kinds}"


def test_listing_endpoint_includes_solva_cycle_item(client, admin_account):
    questions = _seed_questions()
    queue_id, _ = _seed_queue_item(
        admin_account["id"], admin_account["context_id"], questions,
    )
    try:
        r = client.get(f"{BASE_URL}/api/me/review-queue", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body and isinstance(body["items"], list)
        # The listing returns the most-recent first; locate our seeded
        # item by id rather than positional indexing.
        ours = [
            it for it in body["items"]
            if it.get("id") == f"solva_cycle_action:{queue_id}"
        ]
        assert ours, (
            f"seeded queue item {queue_id} not surfaced in /api/me/review-queue. "
            f"Returned {len(body['items'])} items; total_pending={body.get('total_pending')}."
        )
        item = ours[0]
        assert item["kind"] == "solva_cycle_action"
        assert item["payload"]["question_count"] == len(questions)
        assert item["payload"]["session_id"]
        # total_pending must include the seeded item.
        assert body.get("total_pending", 0) >= 1
    finally:
        _cleanup_queue(queue_id)


# ---------------------------------------------------------------------------
# Test 2 — counts endpoint
# ---------------------------------------------------------------------------
def test_counts_endpoint_includes_solva_cycle_kind(client, admin_account):
    # Baseline counts before seeding.
    r0 = client.get(f"{BASE_URL}/api/me/review-queue/counts", timeout=20)
    assert r0.status_code == 200, r0.text
    base = r0.json()
    base_total = int(base.get("total") or 0)
    base_kind = int((base.get("by_kind") or {}).get("solva_cycle_action") or 0)

    queue_id, _ = _seed_queue_item(
        admin_account["id"], admin_account["context_id"], _seed_questions(),
    )
    try:
        r1 = client.get(f"{BASE_URL}/api/me/review-queue/counts", timeout=20)
        assert r1.status_code == 200, r1.text
        body = r1.json()
        # Schema: total + by_kind dict carrying all four kinds.
        assert "by_kind" in body
        bk = body["by_kind"]
        for k in ("inbound_doc", "briefing", "studio_artefact", "solva_cycle_action"):
            assert k in bk, f"by_kind missing kind '{k}': {bk}"
        # Counts moved by exactly one for the new kind, and total moved by
        # at least one (other kinds may legitimately have moved too if a
        # parallel test did something — bracket loosely).
        assert bk["solva_cycle_action"] == base_kind + 1
        assert int(body["total"]) >= base_total + 1
    finally:
        _cleanup_queue(queue_id)


# ---------------------------------------------------------------------------
# Test 3 — approve writes to db.questions, flips status, is idempotent
# ---------------------------------------------------------------------------
def test_approve_inserts_questions_and_is_idempotent(client, admin_account):
    questions = _seed_questions()
    queue_id, handoff_id = _seed_queue_item(
        admin_account["id"], admin_account["context_id"], questions,
    )
    db_handle, _ = _mongo_client()
    try:
        # First approve.
        r1 = client.post(
            f"{BASE_URL}/api/me/review-queue/items/solva_cycle_action/{queue_id}/approve",
            json={"note": "shipped to cycle"},
            timeout=30,
        )
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1.get("ok") is True
        assert body1.get("kind") == "solva_cycle_action"
        assert body1.get("idempotent") in (False, None)
        assert body1.get("questions_inserted") == len(questions)

        # Queue item flipped.
        item = db_handle.solva_cycle_handoff_queue.find_one({"id": queue_id})
        assert item["status"] == "approved", item.get("status")
        assert item.get("inserted_question_ids")
        assert len(item["inserted_question_ids"]) == len(questions)
        assert item.get("approve_note") == "shipped to cycle"

        # Each question landed in db.questions with the right shape.
        for inserted_qid in item["inserted_question_ids"]:
            q = db_handle.questions.find_one({"id": inserted_qid})
            assert q is not None, f"question {inserted_qid} not found in db.questions"
            assert q["context_id"] == admin_account["context_id"]
            assert q["text"], "empty question text"
            assert q["source"].startswith("AKKI Solva v2 ")
            assert q["source_session_id"] == item["session_id"]
            assert q["created_by"] == admin_account["id"]

        # solve_handoffs flipped.
        h = db_handle.solve_handoffs.find_one({"id": handoff_id})
        assert h["status"] == "approved", h.get("status")

        # Second approve must be idempotent — no extra questions inserted.
        r2 = client.post(
            f"{BASE_URL}/api/me/review-queue/items/solva_cycle_action/{queue_id}/approve",
            json={"note": "second call — should noop"},
            timeout=30,
        )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2.get("ok") is True
        assert body2.get("idempotent") is True
        assert body2.get("questions_inserted") == 0

        # Question count in db.questions did not grow.
        questions_count = db_handle.questions.count_documents({
            "id": {"$in": item["inserted_question_ids"]},
        })
        assert questions_count == len(questions), (
            f"idempotency broken — db.questions has {questions_count} of "
            f"{len(questions)} expected rows after second approve"
        )
    finally:
        _cleanup_queue(queue_id)


# ---------------------------------------------------------------------------
# Test 4 — reject path
# ---------------------------------------------------------------------------
def test_reject_marks_queue_rejected_and_does_not_insert_questions(client, admin_account):
    questions = _seed_questions()
    queue_id, handoff_id = _seed_queue_item(
        admin_account["id"], admin_account["context_id"], questions,
    )
    db_handle, _ = _mongo_client()
    try:
        r = client.post(
            f"{BASE_URL}/api/me/review-queue/items/solva_cycle_action/{queue_id}/reject",
            json={"reason": "synthesis too soft"},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("kind") == "solva_cycle_action"

        item = db_handle.solva_cycle_handoff_queue.find_one({"id": queue_id})
        assert item["status"] == "rejected", item.get("status")
        assert item.get("reject_reason") == "synthesis too soft"
        assert not item.get("inserted_question_ids"), (
            "reject must not have written into db.questions"
        )

        h = db_handle.solve_handoffs.find_one({"id": handoff_id})
        assert h["status"] == "rejected"

        # No db.questions rows should exist for these question ids.
        seeded_qids = [q["id"] for q in questions]
        leaked = db_handle.questions.count_documents({"id": {"$in": seeded_qids}})
        assert leaked == 0, (
            f"reject leaked {leaked} questions into db.questions — should be 0"
        )

        # Approve after reject must 409 (state-machine invariant).
        r2 = client.post(
            f"{BASE_URL}/api/me/review-queue/items/solva_cycle_action/{queue_id}/approve",
            json={},
            timeout=30,
        )
        assert r2.status_code == 409, (
            f"approve after reject should 409, got {r2.status_code} {r2.text}"
        )
    finally:
        _cleanup_queue(queue_id)


# ---------------------------------------------------------------------------
# Test 5 — edit path: GET-style returns current questions; PUT-style with
# replacement persists + auto-approves.
# ---------------------------------------------------------------------------
def test_edit_returns_current_questions_when_body_omits_them(client, admin_account):
    questions = _seed_questions()
    queue_id, _ = _seed_queue_item(
        admin_account["id"], admin_account["context_id"], questions,
    )
    try:
        r = client.post(
            f"{BASE_URL}/api/me/review-queue/items/solva_cycle_action/{queue_id}/edit",
            json={},  # no questions list — returns current
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        assert body.get("kind") == "solva_cycle_action"
        assert body.get("inline") is True
        current = body.get("current_questions") or []
        assert len(current) == len(questions)
        assert {q["text"] for q in current} == {q["text"] for q in questions}
    finally:
        _cleanup_queue(queue_id)


def test_edit_with_questions_payload_persists_and_approves(client, admin_account):
    queue_id, handoff_id = _seed_queue_item(
        admin_account["id"], admin_account["context_id"], _seed_questions(),
    )
    db_handle, _ = _mongo_client()
    try:
        edited = [
            {
                "id": str(uuid.uuid4()),
                "ordinal": 1,
                "text": "Edited: where does the corpus stress capital pressure?",
                "category": "strategic",
                "source_tier": "corpus",
                "confidence_band": "Likely",
            },
            # Empty / whitespace-only entries should be silently dropped.
            {"id": str(uuid.uuid4()), "ordinal": 2, "text": "   "},
            # Non-dict entries must not crash the handler.
            "garbage entry — should be skipped",
        ]
        r = client.post(
            f"{BASE_URL}/api/me/review-queue/items/solva_cycle_action/{queue_id}/edit",
            json={"questions": edited, "note": "edited and approved"},
            timeout=30,
        )
        # The handler edits-then-approves in one call. 200 expected; the
        # body should look like an approve response.
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is True
        # Only the one usable question should have been written.
        assert body.get("questions_inserted") == 1, body

        # Queue item flipped to approved with the edited questions persisted.
        item = db_handle.solva_cycle_handoff_queue.find_one({"id": queue_id})
        assert item["status"] == "approved"
        assert len(item["questions"]) == 1
        assert item["questions"][0]["text"].startswith("Edited: ")
        assert item.get("approve_note") == "edited and approved"

        # solve_handoffs row flipped too.
        h = db_handle.solve_handoffs.find_one({"id": handoff_id})
        assert h["status"] == "approved"

        # The single edited question landed in db.questions.
        edited_qids = item["inserted_question_ids"]
        assert len(edited_qids) == 1
        q = db_handle.questions.find_one({"id": edited_qids[0]})
        assert q is not None
        assert q["text"].startswith("Edited: ")
    finally:
        _cleanup_queue(queue_id)


def test_edit_rejects_empty_question_list(client, admin_account):
    queue_id, _ = _seed_queue_item(
        admin_account["id"], admin_account["context_id"], _seed_questions(),
    )
    try:
        r = client.post(
            f"{BASE_URL}/api/me/review-queue/items/solva_cycle_action/{queue_id}/edit",
            json={"questions": [
                {"text": ""},
                {"text": "   "},
                "still rubbish",
            ]},
            timeout=20,
        )
        # Brief contract: an edit that empties the list must 422, not
        # silently approve a question-less queue item.
        assert r.status_code == 422, r.text
    finally:
        _cleanup_queue(queue_id)
