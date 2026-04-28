"""Iter54 backend tests: /api/admin/llm/spend, race-safe deep quota, inbound virus rejection audit."""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASS = "AkkiAdmin2026!"
USER_EMAIL = "bramuel@syni.ai"
USER_PASS = "TestBramuel2026!"
POSTMARK_SECRET = "c04fdcf8-24c4-4e44-b19f-337f80607d6c"


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def user_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": USER_EMAIL, "password": USER_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def admin_client(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def user_client(user_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"})
    return s


# ---------- 1. /api/admin/llm/spend endpoint ----------
class TestLLMSpendEndpoint:
    def test_non_superadmin_forbidden(self, user_client):
        r = user_client.get(f"{BASE_URL}/api/admin/llm/spend?days=30")
        assert r.status_code == 403, r.text

    def test_unauthenticated_unauthorised(self):
        r = requests.get(f"{BASE_URL}/api/admin/llm/spend?days=30", timeout=20)
        assert r.status_code in (401, 403), r.text

    @pytest.mark.parametrize("days", [1, 7, 30, 90])
    def test_superadmin_window(self, admin_client, days):
        r = admin_client.get(f"{BASE_URL}/api/admin/llm/spend?days={days}")
        assert r.status_code == 200, r.text
        d = r.json()
        # required top-level keys
        for k in ("window_days", "today_utc", "totals", "by_surface",
                  "by_account_top", "by_day", "unit_cost_usd", "default_quotas"):
            assert k in d, f"missing {k}"
        assert d["window_days"] == days
        for tk in ("calls", "est_cost_usd", "active_accounts", "surfaces_used"):
            assert tk in d["totals"], f"totals.{tk} missing"
        assert isinstance(d["by_surface"], list)
        assert isinstance(d["by_account_top"], list)
        assert isinstance(d["by_day"], list)
        assert isinstance(d["unit_cost_usd"], (int, float))
        assert isinstance(d["default_quotas"], dict)
        for k in ("brief", "blog", "deck", "chat", "validate", "minutes"):
            assert k in d["default_quotas"]
        # total >= 0 and consistent
        assert d["totals"]["calls"] >= 0
        # est_cost = calls * unit
        expected = round(d["totals"]["calls"] * d["unit_cost_usd"], 2)
        assert abs(expected - d["totals"]["est_cost_usd"]) < 0.01

    def test_seeded_data_visible_30d(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/llm/spend?days=30")
        d = r.json()
        # Expect ~700 from seed (351 rows averaging ~2 calls each per memo)
        assert d["totals"]["calls"] > 100, f"seeded data not visible: calls={d['totals']['calls']}"
        assert d["totals"]["active_accounts"] >= 1
        assert len(d["by_surface"]) >= 1
        assert len(d["by_account_top"]) >= 1
        first_acc = d["by_account_top"][0]
        for k in ("account_id", "email", "name", "calls", "est_cost_usd", "top_surface"):
            assert k in first_acc


# ---------- 2. Race-safe deep quota ----------
class TestRaceSafeDeepQuota:
    """Exhaust llm_deep_usage[brief] to 10, then fire 5 parallel check_and_consume.
    Confirm count NEVER exceeds 10 (race-safe)."""

    def test_unique_index_exists(self):
        async def _check():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            try:
                idx = await db.llm_deep_usage.index_information()
                # Find a unique index over (account_id, surface, day_utc)
                found = False
                for name, spec in idx.items():
                    keys = [k for k, _ in spec.get("key", [])]
                    if set(keys) >= {"account_id", "surface", "day_utc"} and spec.get("unique"):
                        found = True
                        break
                assert found, f"unique index missing over (account_id, surface, day_utc); have: {idx}"
            finally:
                client.close()
        asyncio.run(_check())

    def test_at_cap_and_under_cap_combined(self):
        """Both race-safety scenarios in one event loop (motor client is module-level
        and its event-loop binding is fragile across multiple asyncio.run calls)."""
        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            from llm_tier_quota import check_and_consume
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            surface = "brief"

            # ---- Scenario A: count==cap (10) ----
            aid_a = f"TEST_iter54a_{uuid.uuid4()}"
            await db.llm_deep_usage.delete_many({"account_id": aid_a})
            await db.llm_deep_usage.insert_one({
                "account_id": aid_a, "surface": surface, "day_utc": day, "count": 10,
                "first_used_at": datetime.now(timezone.utc).isoformat(),
                "last_used_at": datetime.now(timezone.utc).isoformat(),
            })
            res_a = await asyncio.gather(*[check_and_consume(aid_a, surface) for _ in range(5)])
            row_a = await db.llm_deep_usage.find_one(
                {"account_id": aid_a, "surface": surface, "day_utc": day})
            assert row_a["count"] == 10, f"OVERAGE@cap: count={row_a['count']}"
            assert all(not r["allowed"] for r in res_a), f"some allowed at cap: {res_a}"
            await db.llm_deep_usage.delete_many({"account_id": aid_a})

            # ---- Scenario B: count=8, fire 5 parallel ----
            aid_b = f"TEST_iter54b_{uuid.uuid4()}"
            await db.llm_deep_usage.delete_many({"account_id": aid_b})
            await db.llm_deep_usage.insert_one({
                "account_id": aid_b, "surface": surface, "day_utc": day, "count": 8,
                "first_used_at": datetime.now(timezone.utc).isoformat(),
                "last_used_at": datetime.now(timezone.utc).isoformat(),
            })
            res_b = await asyncio.gather(*[check_and_consume(aid_b, surface) for _ in range(5)])
            row_b = await db.llm_deep_usage.find_one(
                {"account_id": aid_b, "surface": surface, "day_utc": day})
            allowed_b = sum(1 for r in res_b if r["allowed"])
            assert row_b["count"] <= 10, f"OVERAGE@under: count={row_b['count']}"
            assert allowed_b == 2, f"expected 2 allowed under cap, got {allowed_b}: {res_b}"
            assert row_b["count"] == 10, f"final count != 10: {row_b['count']}"
            await db.llm_deep_usage.delete_many({"account_id": aid_b})
            client.close()
        asyncio.run(_run())

    def _disabled_test_at_cap_no_overage(self):
        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            try:
                # use a synthetic account to avoid touching real data
                aid = f"TEST_iter54_{uuid.uuid4()}"
                surface = "brief"
                day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                await db.llm_deep_usage.delete_many({"account_id": aid})
                await db.llm_deep_usage.insert_one({
                    "account_id": aid, "surface": surface, "day_utc": day,
                    "count": 10,
                    "first_used_at": datetime.now(timezone.utc).isoformat(),
                    "last_used_at": datetime.now(timezone.utc).isoformat(),
                })

                from llm_tier_quota import check_and_consume
                results = await asyncio.gather(*[check_and_consume(aid, surface) for _ in range(5)])

                row = await db.llm_deep_usage.find_one({"account_id": aid, "surface": surface, "day_utc": day})
                assert row["count"] == 10, f"OVERAGE: count went to {row['count']}"
                assert all(not r["allowed"] for r in results), f"some allowed despite cap: {results}"

                await db.llm_deep_usage.delete_many({"account_id": aid})
            finally:
                client.close()
        asyncio.run(_run())

    def _disabled_test_under_cap_parallel_no_overcount(self):
        """Set count=8 (under cap=10), fire 5 parallel — exactly 2 should succeed,
        final count must be 10 (never 11+)."""
        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            try:
                aid = f"TEST_iter54b_{uuid.uuid4()}"
                surface = "brief"
                day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                await db.llm_deep_usage.delete_many({"account_id": aid})
                await db.llm_deep_usage.insert_one({
                    "account_id": aid, "surface": surface, "day_utc": day, "count": 8,
                    "first_used_at": datetime.now(timezone.utc).isoformat(),
                    "last_used_at": datetime.now(timezone.utc).isoformat(),
                })

                from llm_tier_quota import check_and_consume
                results = await asyncio.gather(*[check_and_consume(aid, surface) for _ in range(5)])

                row = await db.llm_deep_usage.find_one({"account_id": aid, "surface": surface, "day_utc": day})
                allowed = sum(1 for r in results if r["allowed"])
                # Must be exactly 2 allowed and count==10. Critical: never > 10.
                assert row["count"] <= 10, f"OVERAGE: count={row['count']}"
                assert allowed == 2, f"expected 2 allowed, got {allowed}: {results}"
                assert row["count"] == 10

                await db.llm_deep_usage.delete_many({"account_id": aid})
            finally:
                client.close()
        asyncio.run(_run())


# ---------- 3. Postmark inbound virus rejection audit ----------
class TestInboundVirusRejected:
    def test_eicar_attachment_rejected_and_audited(self):
        # Find Bramuel's account_token + a valid context inbound_token
        async def _setup():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            try:
                account = await db.accounts.find_one({"email": USER_EMAIL}, {"_id": 0})
                assert account, "bramuel account not found"
                token = account.get("inbound_token")
                if not token:
                    return None, None
                # find a context membership with inbound_token
                m = await db.memberships.find_one(
                    {"account_id": account["id"], "status": "active"},
                    {"_id": 0, "context_id": 1},
                    sort=[("created_at", 1)],
                )
                ctx = await db.contexts.find_one({"id": m["context_id"]}, {"_id": 0})
                return account, ctx
            finally:
                client.close()
        account, ctx = asyncio.run(_setup())
        if not account or not account.get("inbound_token"):
            pytest.skip("bramuel inbound_token not minted; skipping (run /api/inbound/address first)")

        import base64 as _b64
        eicar = r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        eicar_b64 = _b64.b64encode(eicar.encode("ascii")).decode("ascii")
        msg_id = f"<iter54-virus-{uuid.uuid4()}@test>"
        payload = {
            "MailboxHash": account["inbound_token"],
            "Subject": "Iter54 virus probe",
            "From": "attacker@example.com",
            "FromName": "Bad Actor",
            "MessageID": msg_id,
            "TextBody": "see attached",
            "Attachments": [{
                "Name": "evil.txt",
                "Content": eicar_b64,
                "ContentType": "text/plain",
                "ContentLength": len(eicar),
            }],
        }
        url = f"{BASE_URL}/api/inbound/postmark?secret={POSTMARK_SECRET}"
        r = requests.post(url, json=payload, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is False, body
        assert body.get("error") == "virus_scan", body

        # Verify audit row exists
        async def _check_audit():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            try:
                row = await db.audit_log.find_one(
                    {"action": "inbound_email.rejected", "resource_id": msg_id},
                    {"_id": 0},
                )
                return row
            finally:
                client.close()
        audit = asyncio.run(_check_audit())
        assert audit is not None, "no audit_log row written for inbound_email.rejected"
        assert audit.get("action") == "inbound_email.rejected"
        meta = audit.get("metadata") or audit.get("meta") or audit.get("details") or {}
        # accept metadata under any of these keys
        assert any(
            (audit.get(f) or {}).get("reason") == "virus_scan"
            for f in ("metadata", "meta", "details")
        ) or meta.get("reason") == "virus_scan", f"reason!=virus_scan in audit: {audit}"
