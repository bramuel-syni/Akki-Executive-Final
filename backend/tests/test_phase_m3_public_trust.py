"""Sprint M.3 (2026-02 fork-resume v3 dispatch 18) — Public /trust
page with velocity tile + architectural commitments lockdown.

Coverage:
  * Public endpoint exists, no auth required, 30d-only, 5-min cache.
  * Velocity-aggregate math reuses the same path as the authenticated
    ZZ.4 endpoint (single source of truth — `_velocity_aggregate`).
  * Three-state copy locked verbatim in PublicVelocityTile.
  * Architectural commitments locked verbatim in Trust.jsx.
  * Existing Trust v7 pillars untouched (anchor IDs + pillar count).
  * Voice-lint clean.
"""
from __future__ import annotations
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

REPO = Path(__file__).resolve().parent.parent.parent
OBS_PY = REPO / "backend" / "routers" / "observability.py"
TRUST_JSX = REPO / "frontend" / "src" / "website" / "pages" / "Trust.jsx"
TILE_JSX = REPO / "frontend" / "src" / "website" / "components" / "PublicVelocityTile.jsx"
SERVER_PY = REPO / "backend" / "server.py"


def _r(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ── Backend: public router source-strict locks ────────────────────────


def test_m3_public_router_registered_in_server():
    src = _r(SERVER_PY)
    assert "observability_router.public_router" in src


def test_m3_public_router_endpoint_present():
    src = _r(OBS_PY)
    assert '@public_router.get("/reasoning_velocity")' in src
    assert 'prefix="/api/public/observability"' in src
    assert 'pattern="^30d$"' in src
    assert "PUBLIC_CACHE_TTL_SECONDS = 300" in src


def test_m3_shared_aggregate_helper_present():
    """The authenticated ZZ.4 route and the M.3 public mirror share
    `_velocity_aggregate` — single source of truth for the math."""
    src = _r(OBS_PY)
    assert "async def _velocity_aggregate(" in src
    # Both routes must call it.
    assert src.count("_velocity_aggregate(") >= 3  # def + 2 callsites


# ── Frontend: PublicVelocityTile three-state copy verbatim ────────────


THREE_STATE_COPY = {
    "quiet": (
        "Solva is in a quiet patch. Reasoning velocity is reported "
        "when sessions have completed."
    ),
    "warming": (
        "Solva is warming up. Velocity reports once five sessions "
        "have completed in the window."
    ),
    # numeric uses interpolation; assert the literal template fragments.
    "numeric_template_avg": (
        "Akki delivers a fully-cited 16-slide diagnosis in ${avgS}s "
        "on average. p95 ${p95S}s."
    ),
}


def test_m3_velocity_tile_quiet_state_verbatim():
    src = _r(TILE_JSX)
    assert THREE_STATE_COPY["quiet"] in src


def test_m3_velocity_tile_warming_state_verbatim():
    src = _r(TILE_JSX)
    assert THREE_STATE_COPY["warming"] in src


def test_m3_velocity_tile_numeric_state_template():
    src = _r(TILE_JSX)
    # Both interpolated forms (template literal in source).
    assert THREE_STATE_COPY["numeric_template_avg"] in src


def test_m3_velocity_tile_uses_akki_in_public_copy():
    """Public copy uses 'Akki' not 'Solva' for the numeric state
    (per design lock — prospects may not know the internal name)."""
    src = _r(TILE_JSX)
    assert "Akki delivers a fully-cited 16-slide diagnosis" in src
    # Sanity: the internal ZZ.4 surface uses 'Solva' instead.
    tc_jsx = (REPO / "frontend" / "src" / "pages" / "TrustCenter.jsx").read_text(encoding="utf-8")
    assert "Solva delivers a fully-cited 16-slide diagnosis" in tc_jsx


def test_m3_velocity_tile_threshold_lock_five():
    src = _r(TILE_JSX)
    assert "sessions < 5" in src


def test_m3_velocity_tile_testids_present():
    src = _r(TILE_JSX)
    for tid in [
        'data-testid="trust-public-velocity"',
        'data-testid={`trust-public-velocity-${testidSuffix}`}',
    ]:
        assert tid in src


# ── Trust.jsx: existing pillars untouched + commitments locked ────────


def test_m3_existing_v7_pillars_untouched():
    src = _r(TRUST_JSX)
    # All four pillar map iteration markers present unchanged.
    assert "TRUST.pillars.map((pillar, i) =>" in src
    assert "data-testid={`trust-pillar-${pillar.anchor}`}" in src
    # Hero block unchanged.
    assert 'testId="trust-page"' in src


def test_m3_three_commitments_locked_verbatim():
    src = _r(TRUST_JSX)
    for line in [
        '"Akki refuses to train on your data."',
        '"Akki refuses to send raw personal identifiers to model providers."',
        '"Akki refuses to claim what it cannot source."',
    ]:
        assert line in src
    # Section header copy.
    assert 'kicker">ARCHITECTURAL COMMITMENTS' in src
    assert "What Akki will never do." in src


def test_m3_trust_page_imports_velocity_tile():
    src = _r(TRUST_JSX)
    assert 'import PublicVelocityTile from "../components/PublicVelocityTile"' in src
    assert "<PublicVelocityTile />" in src


# ── Voice-lint clean ──────────────────────────────────────────────────


def test_m3_voice_lint_clean():
    import sys
    sys.path.insert(0, str(REPO / "scripts"))
    from lint_voice import scan, DEFAULT_TARGETS
    hits = scan(DEFAULT_TARGETS)
    rendered = [(str(p.relative_to(REPO)), ln, w) for p, ln, w, _ in hits]
    assert not hits, f"voice-lint must remain clean post-M.3; got: {rendered}"


# ── Backend e2e: public endpoint contract ─────────────────────────────


@pytest.fixture
def app():
    import importlib, server
    importlib.reload(server)
    return server.app


@pytest.mark.asyncio
async def test_m3_public_endpoint_no_auth_required(app):
    """Public mirror must not require any Authorization header."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/public/observability/reasoning_velocity?window=30d")
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ["window", "session_count", "slide_count",
                    "avg_ms_per_slide", "p50_ms", "p95_ms",
                    "slowest_slide_kind", "fastest_slide_kind"]:
            assert key in body
        assert body["window"] == "30d"


@pytest.mark.asyncio
async def test_m3_public_endpoint_rejects_non_30d_window(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/public/observability/reasoning_velocity?window=7d")
        assert r.status_code == 422
        r = await c.get("/api/public/observability/reasoning_velocity?window=foo")
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_m3_public_endpoint_cache_hit(app):
    """Second call within TTL returns the cached payload (verified by
    confirming the underlying aggregate result is identical even when
    we'd expect timing-derived numbers to drift)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r1 = await c.get("/api/public/observability/reasoning_velocity?window=30d")
        r2 = await c.get("/api/public/observability/reasoning_velocity?window=30d")
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json() == r2.json()
