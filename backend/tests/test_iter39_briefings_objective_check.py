"""Iter39 backend tests:
- Briefings: list returns is_read/read_via/read_at; mark-read upserts.
- Objective-check: eligibility flips after backdating generated_at;
  works on both sandbox and seeded contexts.
"""
import os
import asyncio
import pytest
import requests
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

EMAIL = "bramuel@syni.ai"
PASSWORD = "TestBramuel2026!"
TULI_NED_CTX = "fb4df969-3f17-4279-bf78-f07bb9e29650"


def _login():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s, data


@pytest.fixture(scope="module")
def session():
    s, _ = _login()
    return s


@pytest.fixture(scope="module")
def account_id():
    _, data = _login()
    return data["account"]["id"]


# ----- Briefings -----
class TestBriefings:
    def test_list_briefings_has_read_fields(self, session):
        r = session.get(f"{API}/contexts/{TULI_NED_CTX}/briefings", timeout=20)
        assert r.status_code == 200, r.text
        rows = r.json()
        assert isinstance(rows, list) and len(rows) > 0, "Expected seeded briefings on Tuli ned"
        for row in rows:
            assert "is_read" in row
            assert "read_at" in row
            assert "read_via" in row
            assert isinstance(row["is_read"], bool)

    def test_clear_then_mark_read_manual(self, session, account_id):
        # Clear briefing_reads for this account on this ctx so we have a fresh slate.
        async def _clear():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            await db.briefing_reads.delete_many(
                {"context_id": TULI_NED_CTX, "account_id": account_id}
            )
            client.close()
        asyncio.run(_clear())

        rows = session.get(f"{API}/contexts/{TULI_NED_CTX}/briefings", timeout=20).json()
        assert all(r["is_read"] is False for r in rows), "After clear, all should be unread"
        bid = rows[0]["id"]

        # Mark read manual
        r = session.post(
            f"{API}/contexts/{TULI_NED_CTX}/briefings/{bid}/mark-read",
            json={"via": "manual"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["read_via"] == "manual"
        assert "read_at" in body

        # List again — that briefing should be is_read=true
        rows2 = session.get(f"{API}/contexts/{TULI_NED_CTX}/briefings", timeout=20).json()
        target = next((b for b in rows2 if b["id"] == bid), None)
        assert target is not None
        assert target["is_read"] is True
        assert target["read_via"] == "manual"

    def test_mark_read_scroll_idempotent(self, session):
        rows = session.get(f"{API}/contexts/{TULI_NED_CTX}/briefings", timeout=20).json()
        bid = rows[0]["id"]
        # Hit it twice with via=scroll — should remain ok and is_read=true
        for _ in range(2):
            r = session.post(
                f"{API}/contexts/{TULI_NED_CTX}/briefings/{bid}/mark-read",
                json={"via": "scroll"},
                timeout=20,
            )
            assert r.status_code == 200
            assert r.json()["read_via"] == "scroll"

        rows2 = session.get(f"{API}/contexts/{TULI_NED_CTX}/briefings", timeout=20).json()
        target = next(b for b in rows2 if b["id"] == bid)
        assert target["is_read"] is True
        assert target["read_via"] == "scroll"

    def test_mark_read_404_on_unknown(self, session):
        r = session.post(
            f"{API}/contexts/{TULI_NED_CTX}/briefings/nope-12345/mark-read",
            json={"via": "manual"},
            timeout=20,
        )
        assert r.status_code == 404


# ----- Objective check -----
class TestObjectiveCheck:
    def _create_seeded_ctx(self, session):
        """Create a fresh seeded sandbox context."""
        body = {
            "company_name": "TEST_iter39 Objective Check Co",
            "region": "east_africa",
            "sector": "financial_services",
            "objective": "TEST_iter39 objective check follow-up",
            "role": "executive",
        }
        r = session.post(f"{API}/sandbox/contexts/seeded", json=body, timeout=30)
        assert r.status_code in (200, 201), f"seeded create failed: {r.status_code} {r.text}"
        data = r.json()
        cid = data.get("context_id") or (data.get("context") or {}).get("id") or data.get("id")
        assert cid, f"No context id in seeded response: {data}"
        return cid

    def test_objective_check_lifecycle_seeded(self, session, account_id):
        cid = self._create_seeded_ctx(session)

        # Fresh: not eligible
        r = session.get(f"{API}/sandbox/contexts/{cid}/objective-check", timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("eligible") is False

        # Backdate generated_at >24h via mongo
        async def _backdate():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            old_iso = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat().replace("+00:00", "Z")
            ctx = await db.contexts.find_one({"id": cid}, {"_id": 0, "type": 1, "seeded_metadata": 1, "sandbox_metadata": 1})
            assert ctx, "ctx vanished"
            # Determine which branch to update — seeded contexts use seeded_metadata
            field = "seeded_metadata.generated_at"
            if ctx.get("type") == "sandbox":
                field = "sandbox_metadata.generated_at"
            # If branch doesn't exist, ensure objective is set on seeded_metadata
            update = {"$set": {field: old_iso}}
            # If neither metadata branch contains 'objective', stamp one for the test
            meta = ctx.get("seeded_metadata") or ctx.get("sandbox_metadata") or {}
            if not meta.get("objective"):
                prefix = "seeded_metadata" if ctx.get("type") != "sandbox" else "sandbox_metadata"
                update["$set"][f"{prefix}.objective"] = "TEST_iter39 objective check follow-up"
            await db.contexts.update_one({"id": cid}, update)
            client.close()
            return old_iso
        old_iso = asyncio.run(_backdate())

        # Now eligible
        r = session.get(f"{API}/sandbox/contexts/{cid}/objective-check", timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("eligible") is True, f"Expected eligible=true after backdating, got {body}"
        assert body.get("objective"), "Expected an objective string"
        assert body.get("generated_at")

        # Answer 'partial' with note
        r = session.post(
            f"{API}/sandbox/contexts/{cid}/objective-check",
            json={"answer": "partial", "note": "Mostly there but Q2 still pending"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        ans = r.json()
        assert ans["ok"] is True
        assert ans["answer"] == "partial"
        assert ans["note"] == "Mostly there but Q2 still pending"

        # Subsequent GET → eligible=false, answered=true
        r = session.get(f"{API}/sandbox/contexts/{cid}/objective-check", timeout=20)
        assert r.status_code == 200
        body2 = r.json()
        assert body2.get("eligible") is False
        assert body2.get("answered") is True
        assert body2.get("answer") == "partial"

        # Cleanup the test context
        async def _cleanup():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            await db.contexts.delete_one({"id": cid})
            client.close()
        asyncio.run(_cleanup())

    def test_objective_check_skip_dismisses(self, session):
        cid = self._create_seeded_ctx(session)
        # Backdate + ensure objective
        async def _backdate():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            old_iso = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat().replace("+00:00", "Z")
            await db.contexts.update_one(
                {"id": cid},
                {"$set": {
                    "seeded_metadata.generated_at": old_iso,
                    "seeded_metadata.objective": "TEST_iter39 skip test",
                }},
            )
            client.close()
        asyncio.run(_backdate())

        # Skip
        r = session.post(
            f"{API}/sandbox/contexts/{cid}/objective-check",
            json={"answer": "skip"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("dismissed") is True

        # Subsequent get is eligible=false
        r = session.get(f"{API}/sandbox/contexts/{cid}/objective-check", timeout=20)
        assert r.status_code == 200
        assert r.json().get("eligible") is False

        # Cleanup
        async def _cleanup():
            client = AsyncIOMotorClient(MONGO_URL)
            db = client[DB_NAME]
            await db.contexts.delete_one({"id": cid})
            client.close()
        asyncio.run(_cleanup())

    def test_objective_check_invalid_answer(self, session):
        cid = self._create_seeded_ctx(session)
        try:
            r = session.post(
                f"{API}/sandbox/contexts/{cid}/objective-check",
                json={"answer": "maybe"},
                timeout=20,
            )
            assert r.status_code in (400, 422), f"expected validation error, got {r.status_code}"
        finally:
            async def _cleanup():
                client = AsyncIOMotorClient(MONGO_URL)
                db = client[DB_NAME]
                await db.contexts.delete_one({"id": cid})
                client.close()
            asyncio.run(_cleanup())
