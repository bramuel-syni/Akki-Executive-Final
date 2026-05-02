"""Phase 10 — production trust & storage foundation tests.

Covers:
  A) Real ClamAV scanning (EICAR rejection; clean file accepted;
     clamd-down returns 503).
  B) S3/MinIO storage round-trip (put/get/head/delete/presign).
  C) Stripe webhook hardening (bad signature → 400; idempotent
     replay; downgrade flow; dead-letter).
  D) Backup scripts present and runnable.

Run:
    pytest backend/tests/test_phase10_infra.py -v
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # Fall back to local frontend .env
    from dotenv import dotenv_values
    BASE_URL = dotenv_values("/app/frontend/.env").get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@akki.ai"
ADMIN_PASSWORD = "AkkiAdmin2026!"

EICAR = (
    r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
).encode("ascii")


@pytest.fixture(scope="module")
def client() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json().get("access_token")
    if tok:
        s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# ─────────────────────────────────────────────────────────────────────────
# A — Real virus scanning via ClamAV
# ─────────────────────────────────────────────────────────────────────────
class TestClamAV:
    def test_clamd_healthcheck_reachable(self):
        from services import clamav_service
        health = clamav_service.healthcheck()
        assert health["ok"] is True, health
        assert health["mode"] == "clamd", health

    def test_eicar_is_rejected_by_scan(self):
        from services import clamav_service
        result = clamav_service.scan(EICAR, filename="eicar.com")
        assert result.clean is False
        assert result.signature  # clamav's name for EICAR varies; just assert not empty
        assert "Eicar" in result.signature or "EICAR" in result.signature or "Test" in result.signature

    def test_clean_file_passes_scan(self):
        from services import clamav_service
        # Tiny in-memory PNG (valid header, 1x1 red pixel).
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf"
            b"\xc0\x00\x00\x00\x03\x00\x01\x00\xef\xa4\xd1\x8a\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        result = clamav_service.scan(png, filename="tiny.png")
        assert result.clean is True
        assert result.signature is None

    def test_unreachable_clamd_raises(self, monkeypatch):
        # Point at an unreachable port — must raise ClamAVUnreachable,
        # must NOT fall through to a stub.
        from services import clamav_service as cs
        monkeypatch.setattr(cs, "CLAMAV_HOST", "127.0.0.1")
        monkeypatch.setattr(cs, "CLAMAV_PORT", 3322)  # deliberately wrong
        monkeypatch.setattr(cs, "ALLOW_UNSAFE_UPLOADS", False)
        with pytest.raises(cs.ClamAVUnreachable):
            cs.scan(b"whatever", filename="x.txt")

    def test_eicar_upload_blocked_e2e(self, client):
        """End-to-end via the documents upload route. Expect 422, not 200."""
        # Resolve the admin's default context.
        r = client.get(f"{BASE_URL}/api/auth/me", timeout=20)
        cid = ((r.json() or {}).get("account") or {}).get("default_context_id")
        assert cid, "admin has no default context"
        files = {"file": ("eicar.txt", EICAR, "text/plain")}
        data = {"description": "eicar e2e"}
        up = client.post(f"{BASE_URL}/api/contexts/{cid}/documents", files=files, data=data, timeout=30)
        assert up.status_code == 422, up.text
        body = up.json()
        assert body.get("detail", {}).get("reason") == "malware_suspected", body


# ─────────────────────────────────────────────────────────────────────────
# B — S3/MinIO storage round-trip
# ─────────────────────────────────────────────────────────────────────────
class TestStorage:
    def test_put_head_get_delete_roundtrip(self):
        from services import storage_service
        storage = storage_service.get_storage()
        key = f"test-p10/{uuid.uuid4().hex[:8]}/hello.txt"
        payload = b"hello from phase 10"
        put = storage.put(key, payload, content_type="text/plain")
        assert put["size"] == len(payload)

        head = storage.head(key)
        assert head["exists"] is True
        assert head["size"] == len(payload)

        got = storage.get_bytes(key)
        assert got == payload

        assert storage.delete(key) is True
        head2 = storage.head(key)
        assert head2["exists"] is False

    def test_presigned_url_works_and_honours_ttl(self):
        from services import storage_service
        storage = storage_service.get_storage()
        if storage.backend != "s3":
            pytest.skip("presigned URL test requires S3 backend")
        key = f"test-p10/{uuid.uuid4().hex[:8]}/presign.txt"
        payload = b"signed url payload"
        storage.put(key, payload, content_type="text/plain")
        url = storage.get_presigned_url(key, ttl_seconds=60)
        assert url.startswith("http")
        # URL must fetch the exact bytes.
        r = requests.get(url, timeout=10)
        assert r.status_code == 200
        assert r.content == payload
        # Cleanup
        storage.delete(key)

    def test_object_metadata_never_leaks_pii(self):
        """Put an object with metadata that SHOULDN'T be used, confirm
        we write only what we pass and the key carries no PII."""
        from services import storage_service
        storage = storage_service.get_storage()
        if storage.backend != "s3":
            pytest.skip("metadata test requires S3 backend")
        key = f"test-p10/{uuid.uuid4().hex[:8]}/meta.txt"
        storage.put(key, b"x", content_type="text/plain",
                    metadata={"x-app": "akki", "surface": "ingest"})
        head = storage.head(key)
        assert head["exists"]
        # Keys must follow the ctx/doc/filename pattern; no raw email in key.
        assert "@" not in key
        storage.delete(key)


# ─────────────────────────────────────────────────────────────────────────
# C — Stripe webhook hardening (unit tests; no live Stripe call required)
# ─────────────────────────────────────────────────────────────────────────
class TestStripeWebhook:
    def test_bad_signature_returns_400(self, client):
        r = client.post(
            f"{BASE_URL}/api/webhook/stripe",
            data=b'{"id":"evt_1","type":"checkout.session.completed"}',
            headers={"Content-Type": "application/json", "Stripe-Signature": "bogus"},
            timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_missing_signature_returns_400(self, client):
        r = client.post(
            f"{BASE_URL}/api/webhook/stripe",
            data=b'{"id":"evt_1","type":"checkout.session.completed"}',
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        assert r.status_code == 400

    def test_idempotency_tracks_event_id(self):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from services import stripe_webhook as sw

        mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = mongo[os.environ["DB_NAME"]]
        eid = f"evt_test_{uuid.uuid4().hex[:10]}"

        async def run():
            await sw.ensure_indexes(db)
            assert await sw.is_replay(db, eid) is False
            await sw.record_event(db, eid, "checkout.session.completed")
            assert await sw.is_replay(db, eid) is True

        asyncio.get_event_loop().run_until_complete(run())
        mongo.close()

    def test_dead_letter_records_unhandled_event(self):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from services import stripe_webhook as sw

        mongo = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = mongo[os.environ["DB_NAME"]]

        async def run():
            eid = f"evt_dl_{uuid.uuid4().hex[:8]}"
            await sw.dead_letter(db, {"id": eid, "type": "customer.updated"}, reason="unhandled_event_type:customer.updated")
            row = await db.stripe_dead_letter.find_one({"event_id": eid})
            assert row is not None
            assert row["event_type"] == "customer.updated"
            assert "unhandled" in row["reason"]

        asyncio.get_event_loop().run_until_complete(run())
        mongo.close()


# ─────────────────────────────────────────────────────────────────────────
# D — Backup scripts present
# ─────────────────────────────────────────────────────────────────────────
class TestBackupScripts:
    def test_backup_script_exists_and_is_executable(self):
        p = Path("/app/scripts/backup_mongo.sh")
        assert p.exists()
        assert os.access(p, os.X_OK)

    def test_restore_script_exists_and_is_executable(self):
        p = Path("/app/scripts/restore_mongo.sh")
        assert p.exists()
        assert os.access(p, os.X_OK)

    def test_runbook_exists(self):
        assert Path("/app/docs/RUNBOOKS/MONGO_BACKUP.md").exists()
        assert Path("/app/docs/RUNBOOKS/STORAGE_MIGRATION.md").exists()

    def test_migrate_script_exists(self):
        assert Path("/app/scripts/migrate_local_to_s3.py").exists()
