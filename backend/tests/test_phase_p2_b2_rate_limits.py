"""Phase P2 B.2 — Rate-limit dependency lockdown.

Tests the rate-limit primitives directly — the bucket lookup, the
per-IP/per-user keying, and the 429 trip via the strategy — without
reloading the server module (which would reinit Motor against a
closed event loop and fight pytest-asyncio).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO / "backend" / ".env")


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_b2_limits_table_carries_expected_buckets():
    from services.rate_limit import LIMITS
    expected = {
        "auth_login", "auth_register", "auth_forgot", "auth_reset",
        "auth_pwchange", "cohort_apply", "public_tile", "solva",
    }
    assert expected.issubset(set(LIMITS.keys()))


def test_b2_rate_limit_keys_per_ip_when_anonymous():
    """Anonymous calls are bucketed by IP (x-forwarded-for first hop)."""
    from services.rate_limit import _client_key
    from fastapi import Request

    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"x-forwarded-for", b"203.0.113.42")],
        "client": ("10.0.0.1", 1234),
    }
    r = Request(scope)
    k = _client_key(r)
    assert k == "ip:203.0.113.42"


def test_b2_rate_limit_keys_per_user_when_jwt():
    """Authenticated calls are bucketed by the JWT sub."""
    import jwt as _jwt
    from core import JWT_SECRET, JWT_ALGO
    from services.rate_limit import _client_key
    from fastapi import Request

    tok = _jwt.encode({"sub": "user-abc"}, JWT_SECRET, algorithm=JWT_ALGO)
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [
            (b"authorization", f"Bearer {tok}".encode()),
            (b"x-forwarded-for", b"203.0.113.42"),
        ],
        "client": ("10.0.0.1", 1234),
    }
    r = Request(scope)
    k = _client_key(r)
    assert k == "user:user-abc"


def test_b2_strategy_trips_429_after_threshold():
    """Hitting the bucket > LIMIT in the window yields HTTPException 429."""
    from fastapi import HTTPException, Request
    from limits import parse
    from limits.storage import MemoryStorage
    from limits.strategies import MovingWindowRateLimiter

    storage = MemoryStorage()
    strategy = MovingWindowRateLimiter(storage)
    limit = parse("2/minute")
    bucket = "test_bucket"
    key = "ip:test-key"

    # First two hits succeed.
    assert strategy.hit(limit, bucket, key) is True
    assert strategy.hit(limit, bucket, key) is True
    # Third trips.
    assert strategy.hit(limit, bucket, key) is False


def test_b2_dependency_raises_429_when_bucket_exhausted(monkeypatch):
    """Drive the rate_limit() dependency directly and assert the
    HTTPException it raises carries the documented 429 shape."""
    import services.rate_limit as rl
    from fastapi import HTTPException, Request

    # Conftest sets RATE_LIMIT_DISABLED=1 globally to avoid IP-bucket
    # collisions between tests. Re-enable for this specific case.
    monkeypatch.setattr(rl, "DISABLED", False)

    # Replace the parsed limit for a unique bucket with a 1/minute cap.
    from limits import parse
    rl._parsed["__b2_test"] = parse("1/minute")
    rl.LIMITS["__b2_test"] = "1/minute"

    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"x-forwarded-for", b"203.0.113.99")],
        "client": ("10.0.0.1", 0),
    }
    req = Request(scope)

    dep = rl.rate_limit("__b2_test")
    # First call passes.
    _run(dep(req))
    # Second call must raise 429.
    with pytest.raises(HTTPException) as ei:
        _run(dep(req))
    exc = ei.value
    assert exc.status_code == 429
    assert exc.detail["code"] == "RATE_LIMIT_EXCEEDED"
    assert exc.detail["bucket"] == "__b2_test"
    assert "Retry-After" in exc.headers


def test_b2_dependency_noop_when_disabled(monkeypatch):
    """When RATE_LIMIT_DISABLED=1 the dependency must be a no-op."""
    import services.rate_limit as rl
    from fastapi import Request

    monkeypatch.setattr(rl, "DISABLED", True)

    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(b"x-forwarded-for", b"203.0.113.100")],
        "client": ("10.0.0.1", 0),
    }
    req = Request(scope)

    dep = rl.rate_limit("auth_login")
    # Even calling many times must never raise.
    for _ in range(50):
        _run(dep(req))
