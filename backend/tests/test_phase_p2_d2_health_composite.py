"""Phase P2 D.2 — Composite health probe lockdown."""
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

from httpx import ASGITransport, AsyncClient  # noqa: E402
from server import app  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


async def _get(path: str, headers=None):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        return await ac.get(path, headers=headers)


def test_d2_composite_shape():
    r = _run(_get("/api/health/composite"))
    assert r.status_code == 200
    data = r.json()
    assert data["overall"] in {"ok", "warn", "fail"}
    probes = data["probes"]
    expected = {"mongo", "llm_key", "sendgrid", "oauth_google",
                "oauth_microsoft", "solva_engine"}
    assert expected.issubset(set(probes.keys()))
    for name, p in probes.items():
        assert p["state"] in {"ok", "warn", "fail"}, name
        assert isinstance(p["detail"], str)


def test_d2_overall_rolls_up_fail_if_any_fails():
    # State machine: fail > warn > ok
    from routers.health_composite import _overall
    assert _overall({"a": {"state": "ok"}, "b": {"state": "ok"}}) == "ok"
    assert _overall({"a": {"state": "ok"}, "b": {"state": "warn"}}) == "warn"
    assert _overall({"a": {"state": "warn"}, "b": {"state": "fail"}}) == "fail"


def test_d2_caches_for_30_seconds():
    r1 = _run(_get("/api/health/composite"))
    r2 = _run(_get("/api/health/composite"))
    # Identical checked_at means we hit the cache on r2.
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["checked_at"] == r2.json()["checked_at"]


def test_d2_no_auth_required():
    """Public route — must not require a token."""
    r = _run(_get("/api/health/composite", headers={"Authorization": ""}))
    assert r.status_code == 200
