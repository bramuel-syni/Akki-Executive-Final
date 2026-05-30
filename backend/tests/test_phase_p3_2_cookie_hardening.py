"""Phase P3.2 — Cookie hardening lockdown."""
from __future__ import annotations

import asyncio
import bcrypt
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from server import app  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_account(prefix: str, password: str) -> dict:
    import pymongo
    db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    email = f"{prefix}-{uuid.uuid4().hex[:6]}@p3-2.example.com"
    doc = {
        "id": uuid.uuid4().hex, "email": email, "email_lc": email.lower(),
        "status": "active", "is_superadmin": False,
        "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        "auth_provider": "password",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.accounts.insert_one(dict(doc))
    return doc


def test_p3_2_login_cookie_attributes():
    """Login Set-Cookie response carries HttpOnly + Secure + SameSite=Strict."""
    acc = _make_account("p3-2-cookie", "TestPass1234!")
    async def _do():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            r = await ac.post(
                "/api/auth/login",
                json={"email": acc["email"], "password": "TestPass1234!"},
            )
            assert r.status_code == 200, r.text
            cookies = r.headers.get_list("set-cookie")
            access_cookies = [c for c in cookies if c.startswith("access_token=")]
            refresh_cookies = [c for c in cookies if c.startswith("refresh_token=")]
            assert access_cookies, "access_token cookie absent"
            assert refresh_cookies, "refresh_token cookie absent"
            for c in access_cookies + refresh_cookies:
                lower = c.lower()
                assert "httponly" in lower, f"HttpOnly missing in {c}"
                assert "samesite=strict" in lower, f"SameSite=Strict missing in {c}"
                # Secure may be absent on http loopback if COOKIE_SECURE=0;
                # in this env it must be Secure.
                assert "secure" in lower, f"Secure missing in {c}"
                assert "path=/" in lower, f"Path=/ missing in {c}"
            return r
    _run(_do())


def test_p3_2_csrf_cookie_samesite_lax():
    """CSRF cookie uses SameSite=Lax (double-submit pattern needs it)."""
    async def _do():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
            r = await ac.get("/api/csrf")
            cookies = r.headers.get_list("set-cookie")
            csrf_cookies = [c for c in cookies if c.startswith("csrf_token=")]
            assert csrf_cookies, "csrf_token cookie absent"
            for c in csrf_cookies:
                lower = c.lower()
                assert "samesite=lax" in lower, f"SameSite=Lax missing in {c}"
                # HttpOnly must be ABSENT — JS needs to read it for double-submit.
                assert "httponly" not in lower, f"CSRF cookie must not be HttpOnly: {c}"
    _run(_do())
