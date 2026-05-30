"""Phase ZZ.4 (2026-02 fork-resume v2) — Reasoning velocity aggregate.

Source-strict + math validation tests.
"""
from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport

REPO = Path(__file__).resolve().parent.parent.parent
OBS_PY = REPO / "backend" / "routers" / "observability.py"
TC_JSX = REPO / "frontend" / "src" / "pages" / "TrustCenter.jsx"


# ── Source-strict layer ──────────────────────────────────────────────


def test_zz4_endpoint_source_present():
    src = OBS_PY.read_text(encoding="utf-8")
    assert '@router.get("/reasoning_velocity")' in src
    assert 'pattern="^(7d|30d)$"' in src
    # Locked deck size constant
    assert "LOCKED_SLIDE_COUNT = 16" in src


def test_zz4_response_shape_keys():
    src = OBS_PY.read_text(encoding="utf-8")
    for key in [
        "session_count", "slide_count",
        "avg_ms_per_slide", "p50_ms", "p95_ms",
        "slowest_slide_kind", "fastest_slide_kind",
    ]:
        assert f'"{key}"' in src, f"Missing response key {key!r}"


def test_zz4_frontend_tile_copy_verbatim():
    src = TC_JSX.read_text(encoding="utf-8")
    # Voice-clean copy locked verbatim.
    assert "Solva delivers a fully-cited 16-slide diagnosis in" in src
    assert "on average. p95" in src
    assert "Slowest layer:" in src
    assert "No completed Solva sessions in the last" in src
    # Tile testids locked.
    for tid in [
        'data-testid="tc-velocity-tile"',
        'data-testid="tc-velocity-copy"',
        'data-testid="tc-velocity-avg"',
        'data-testid="tc-velocity-p95"',
        'data-testid="tc-velocity-slowest"',
    ]:
        assert tid in src, f"Missing testid {tid}"


def test_zz4_frontend_no_banned_vocab():
    """ZZ.4 tile must not introduce marketing puffery."""
    src = TC_JSX.read_text(encoding="utf-8")
    for bad in ["empower", "seamless", "AI-powered", "AI-driven",
                "lightning-fast", "blazing"]:
        # Tile-copy region locked; full file scan is OK because the
        # ZZ.3 voice-lint test already excludes pre-existing banned
        # vocab elsewhere.
        assert bad.lower() not in src.lower(), f"Banned word {bad!r} found"


# ── Math validation ─────────────────────────────────────────────────


@pytest.fixture
def app():
    import importlib, server
    importlib.reload(server)
    return server.app


@pytest.mark.asyncio
async def test_zz4_math_p50_p95_slowest_fastest(app):
    """Seed 5 completed sessions with known durations + per-engine
    latencies and assert the aggregate math."""
    from core import db
    test_account_id = "zz4-test-acct"
    now = datetime.now(timezone.utc)
    # 5 sessions: durations 16s, 32s, 48s, 64s, 160s  → per-slide ms = 1000, 2000, 3000, 4000, 10000
    durations_s = [16, 32, 48, 64, 160]
    seeded = []
    try:
        for i, d in enumerate(durations_s):
            sid = f"zz4-sess-{i}"
            start = now - timedelta(minutes=i + 1, seconds=d)
            end = start + timedelta(seconds=d)
            await db.solva_v2_sessions.insert_one({
                "id": sid,
                "account_id": test_account_id,
                "status": "completed",
                "started_at": start.isoformat(),
                "completed_at": end.isoformat(),
                "reasoning_audit_log": [
                    {"engine": "frame_audit", "latency_ms": 500.0},
                    {"engine": "tension_detector", "latency_ms": 5000.0},
                    {"engine": "scenario_synth", "latency_ms": 2000.0},
                ],
            })
            seeded.append(sid)

        # Mock the auth dependency to return our test account.
        from core import get_current_account
        async def _fake_current():
            return {"id": test_account_id, "is_superadmin": False}
        app.dependency_overrides[get_current_account] = _fake_current

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/observability/reasoning_velocity?window=30d")
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["session_count"] == 5
            assert body["slide_count"] == 5 * 16
            # avg per-slide ms across 5 sessions:
            # (1000+2000+3000+4000+10000)/5 = 4000.0
            assert abs(body["avg_ms_per_slide"] - 4000.0) < 0.5
            # p50 of per-slide ms is 3000 (middle of sorted [1000,2000,3000,4000,10000]).
            # Endpoint returns p50_ms * 16 (session total). 3000 * 16 = 48000ms.
            assert abs(body["p50_ms"] - 48000.0) < 1.0
            # p95 = idx round(0.95 * 4) = 4 → 10000 per-slide; * 16 = 160000ms.
            assert abs(body["p95_ms"] - 160000.0) < 1.0
            # Slowest engine: tension_detector (5000ms median).
            assert body["slowest_slide_kind"]["kind"] == "tension_detector"
            assert abs(body["slowest_slide_kind"]["median_ms"] - 5000.0) < 0.5
            # Fastest engine: frame_audit (500ms median).
            assert body["fastest_slide_kind"]["kind"] == "frame_audit"
            assert abs(body["fastest_slide_kind"]["median_ms"] - 500.0) < 0.5
    finally:
        for sid in seeded:
            await db.solva_v2_sessions.delete_one({"id": sid})
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_zz4_empty_window_returns_zeros(app):
    """No completed sessions in window → zero counts, null kinds."""
    from core import get_current_account
    async def _fake_current():
        return {"id": "zz4-nonexistent-acct", "is_superadmin": False}
    app.dependency_overrides[get_current_account] = _fake_current
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/observability/reasoning_velocity?window=7d")
            assert r.status_code == 200
            body = r.json()
            assert body["session_count"] == 0
            assert body["slowest_slide_kind"] is None
            assert body["fastest_slide_kind"] is None
            assert body["avg_ms_per_slide"] == 0.0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_zz4_window_param_strict(app):
    """Invalid window → 422."""
    from core import get_current_account
    async def _fake_current():
        return {"id": "zz4-nonexistent-acct", "is_superadmin": False}
    app.dependency_overrides[get_current_account] = _fake_current
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/observability/reasoning_velocity?window=foo")
            assert r.status_code == 422
    finally:
        app.dependency_overrides.clear()


# ── Live e2e smoke ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zz4_endpoint_live_admin_smoke():
    import requests
    base = "https://akki-executive.preview.emergentagent.com"
    r = requests.post(f"{base}/api/auth/login",
                      json={"email": "admin@akki.ai", "password": "AkkiAdmin2026!"},
                      timeout=15)
    if r.status_code >= 400:
        pytest.skip(f"login: {r.status_code}")
    tok = r.json()["access_token"]
    rr = requests.get(f"{base}/api/observability/reasoning_velocity?window=30d",
                      headers={"Authorization": f"Bearer {tok}"}, timeout=20)
    assert rr.status_code == 200
    body = rr.json()
    for key in ["window", "session_count", "slide_count",
                "avg_ms_per_slide", "p50_ms", "p95_ms",
                "slowest_slide_kind", "fastest_slide_kind"]:
        assert key in body
