"""Phase P3.3 — MFA enrolment, verification, lockout, recovery codes."""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bcrypt
import pyotp
import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from server import app  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_account(prefix: str, password: str = "TestPass1234!", is_superadmin: bool = False) -> dict:
    import pymongo
    db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    email = f"{prefix}-{uuid.uuid4().hex[:6]}@p3-3.example.com"
    doc = {
        "id": uuid.uuid4().hex, "email": email, "email_lc": email.lower(),
        "status": "active", "is_superadmin": is_superadmin,
        "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "auth_provider": "password",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.accounts.insert_one(dict(doc))
    return doc


def _login_token(email: str, password: str) -> str:
    async def _do():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            r = await ac.post("/api/auth/login", json={"email": email, "password": password})
            return r.json()["access_token"]
    return _run(_do())


def test_p3_3_enroll_start_returns_otpauth_and_qr():
    acc = _make_account("p3-3-enroll")
    tok = _login_token(acc["email"], "TestPass1234!")
    async def _do():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            r = await ac.post(
                "/api/auth/mfa/enroll/start",
                headers={"Authorization": f"Bearer {tok}"},
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["otpauth_url"].startswith("otpauth://totp/")
            assert data["qr_data_url"].startswith("data:image/png;base64,")
            assert len(data["secret"]) >= 16
            return data["secret"]
    secret = _run(_do())
    # Verify pending secret was persisted.
    import pymongo
    db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    fresh = db.accounts.find_one({"id": acc["id"]}, {"_id": 0})
    assert fresh["mfa_secret_pending"] == secret


def test_p3_3_enroll_confirm_returns_recovery_codes_once():
    acc = _make_account("p3-3-confirm")
    tok = _login_token(acc["email"], "TestPass1234!")
    async def _start():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            r = await ac.post("/api/auth/mfa/enroll/start",
                              headers={"Authorization": f"Bearer {tok}"})
            return r.json()["secret"]
    secret = _run(_start())
    code = pyotp.TOTP(secret).now()
    async def _confirm():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            r = await ac.post("/api/auth/mfa/enroll/confirm",
                              headers={"Authorization": f"Bearer {tok}"},
                              json={"code": code})
            return r
    r = _run(_confirm())
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["mfa_enabled"] is True
    assert len(data["recovery_codes"]) == 10
    for c in data["recovery_codes"]:
        # XXXX-XXXX-XXXX shape
        assert len(c) == 14 and c.count("-") == 2
    # Verify codes are stored as bcrypt hashes (not raw).
    import pymongo
    db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    fresh = db.accounts.find_one({"id": acc["id"]}, {"_id": 0})
    hashes = fresh["mfa_recovery_codes"]
    assert len(hashes) == 10
    for h in hashes:
        assert h.startswith("$2"), f"hash not bcrypt: {h}"
    # Pending secret cleared.
    assert fresh.get("mfa_secret_pending") is None


def test_p3_3_verify_with_recovery_code_burns_it():
    """A recovery code used once cannot be used twice."""
    acc = _make_account("p3-3-recovery")
    tok = _login_token(acc["email"], "TestPass1234!")
    async def _setup():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            r1 = await ac.post("/api/auth/mfa/enroll/start",
                               headers={"Authorization": f"Bearer {tok}"})
            secret = r1.json()["secret"]
            r2 = await ac.post("/api/auth/mfa/enroll/confirm",
                               headers={"Authorization": f"Bearer {tok}"},
                               json={"code": pyotp.TOTP(secret).now()})
            return r2.json()["recovery_codes"]
    codes = _run(_setup())
    one = codes[0]
    async def _use_once():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            r = await ac.post("/api/auth/mfa/verify",
                              headers={"Authorization": f"Bearer {tok}"},
                              json={"code": one})
            return r
    r = _run(_use_once())
    assert r.status_code == 200, r.text
    assert r.json()["mfa_verified"] is True
    # Use again — should now fail.
    r2 = _run(_use_once())
    assert r2.status_code == 401
    assert r2.json()["detail"]["code"] == "MFA_CODE_INVALID"


def test_p3_3_disable_requires_password():
    acc = _make_account("p3-3-disable")
    tok = _login_token(acc["email"], "TestPass1234!")
    async def _enrol():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            r1 = await ac.post("/api/auth/mfa/enroll/start",
                               headers={"Authorization": f"Bearer {tok}"})
            secret = r1.json()["secret"]
            await ac.post("/api/auth/mfa/enroll/confirm",
                          headers={"Authorization": f"Bearer {tok}"},
                          json={"code": pyotp.TOTP(secret).now()})
    _run(_enrol())
    async def _bad_pw():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            return await ac.post("/api/auth/mfa/disable",
                                 headers={"Authorization": f"Bearer {tok}"},
                                 json={"password": "WrongPass"})
    r = _run(_bad_pw())
    assert r.status_code == 401
    async def _good_pw():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            return await ac.post("/api/auth/mfa/disable",
                                 headers={"Authorization": f"Bearer {tok}"},
                                 json={"password": "TestPass1234!"})
    r2 = _run(_good_pw())
    assert r2.status_code == 200
    assert r2.json()["mfa_enabled"] is False


def test_p3_3_admin_force_enrol_blocks_non_enrolled_superadmin():
    """Phase P3.3 — non-enrolled superadmin (not on grace list) gets
    428 Precondition Required when hitting /api/admin/*."""
    acc = _make_account("p3-3-new-admin", is_superadmin=True)
    # Ensure this email is NOT on the grace list.
    grace = (os.environ.get("MFA_ADMIN_GRACE_EMAILS", "admin@akki.ai")).split(",")
    assert acc["email"].lower() not in [e.strip().lower() for e in grace]
    tok = _login_token(acc["email"], "TestPass1234!")
    async def _hit_admin():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            return await ac.get("/api/admin/users",
                                headers={"Authorization": f"Bearer {tok}"})
    r = _run(_hit_admin())
    assert r.status_code == 428
    assert r.json()["detail"]["code"] == "mfa_enrolment_required"


def test_p3_3_grace_admin_bypasses_force_enrol():
    """The seeded admin@akki.ai is grace-bypassed for this phase."""
    async def _do():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            r1 = await ac.post("/api/auth/login",
                               json={"email": "admin@akki.ai", "password": "AkkiAdmin2026!"})
            tok = r1.json()["access_token"]
            r2 = await ac.get("/api/admin/users",
                              headers={"Authorization": f"Bearer {tok}"})
            return r2
    r = _run(_do())
    assert r.status_code == 200, r.text
