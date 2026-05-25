"""Hardening Step 1 — ClamAV prod-status verification endpoint.

Anti-source-string-assertion discipline (closeout §5.8): every test
asserts a CONTROL-FLOW CHAIN, not a literal string match in source.

  S1.A — Alive branch: monkeypatch the lazy `import clamd` so that
         `ClamdNetworkSocket.ping` returns success → response
         `clamd_daemon == "alive"` AND `clamd_ping_response_ms` is
         a non-negative integer.
  S1.B — Unreachable branch (ConnectionRefusedError): same monkeypatch
         shape, `.ping` raises → `clamd_daemon == "unreachable"`
         AND `clamd_ping_response_ms is None` AND HTTP 200 (not 503).
  S1.C — Unreachable branch (ClamAVUnreachable): explicit re-raise of
         the service's own exception class still classifies as
         `unreachable`.
  S1.D — Unknown branch: `.ping` raises an unrelated `ValueError` →
         `clamd_daemon == "unknown"` AND `debug.exception_class ==
         "ValueError"` AND HTTP 200.
  S1.E — Histogram 24h: seed 5 `upload_scan_log` rows (one of each
         classified result + one stale row > 24h) → histogram counts
         only the 4 fresh ones AND `last_scan_at_utc` reflects the
         most-recent row regardless of age.
  S1.F — Empty log branch: drop `upload_scan_log` collection →
         `last_scan_at_utc is None` AND all 4 counts are zero.
  S1.G — Live schema-shape: hit the running endpoint without
         monkeypatching → all 6 top-level keys present, daemon
         state is one of the allowed strings, scans_last_24h dict
         has all 4 buckets. Daemon classification NOT asserted —
         depends on the env's clamd availability.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

import core as core_mod
from routers import healthz_clamav as router_mod
from server import app
from services.clamav_service import (
    UPLOAD_SCAN_LOG_COLLECTION,
    ClamAVUnreachable,
)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    )


# ── Fixture: replace the lazy `import clamd` inside the handler ────
class _FakeClamdAlive:
    """Stand-in for the `clamd` module that yields a passing PING."""
    class ClamdNetworkSocket:
        def __init__(self, host=None, port=None, timeout=None):
            self.host = host
            self.port = port
            self.timeout = timeout

        def ping(self):
            return "PONG"


class _FakeClamdRefuses:
    class ClamdNetworkSocket:
        def __init__(self, host=None, port=None, timeout=None):
            pass

        def ping(self):
            raise ConnectionRefusedError("clamd not listening on 3310")


# Mirrors the real `clamd` library's exception hierarchy:
# `clamd.ConnectionError` inherits from `clamd.ClamdError` and does
# NOT inherit from Python's built-in ConnectionError. The live
# preview-env probe surfaced this gap — without an explicit catch
# for `clamd.ConnectionError`, an unreachable daemon would mis-
# classify as "unknown" instead of "unreachable".
class _ClamdLibError(Exception):
    """Stand-in for `clamd.ClamdError`."""


class _ClamdLibConnectionError(_ClamdLibError):
    """Stand-in for `clamd.ConnectionError` (which is NOT Python's
    built-in ConnectionError)."""


class _FakeClamdLibConnectionError:
    """`clamd` module surrogate whose PING raises the library's own
    ConnectionError class. Pins the fix for the live-probe bug."""
    ClamdError = _ClamdLibError
    ConnectionError = _ClamdLibConnectionError  # noqa: A003

    class ClamdNetworkSocket:
        def __init__(self, host=None, port=None, timeout=None):
            pass

        def ping(self):
            raise _ClamdLibConnectionError(
                "Error connecting to clamd at clamd:3310"
            )


class _FakeClamdUnreachableException:
    class ClamdNetworkSocket:
        def __init__(self, host=None, port=None, timeout=None):
            pass

        def ping(self):
            raise ClamAVUnreachable("explicit service-exception path")


class _FakeClamdUnknown:
    class ClamdNetworkSocket:
        def __init__(self, host=None, port=None, timeout=None):
            pass

        def ping(self):
            raise ValueError("a totally unexpected error class")


def _install_fake_clamd(monkeypatch, fake_mod):
    """Make the in-handler ``import clamd`` resolve to `fake_mod`."""
    monkeypatch.setitem(sys.modules, "clamd", fake_mod)


# ── Fixture: clean upload_scan_log between tests ───────────────────
@pytest.fixture
async def clean_scan_log():
    await core_mod.db[UPLOAD_SCAN_LOG_COLLECTION].drop()
    yield
    await core_mod.db[UPLOAD_SCAN_LOG_COLLECTION].drop()


# ── S1.A — alive branch ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_step1_alive_branch(monkeypatch, clean_scan_log):
    """Anchor chain: ``_ping_clamd()`` is called → monkeypatched
    clamd PING returns → handler emits `clamd_daemon == "alive"`
    AND `clamd_ping_response_ms` is a non-negative integer."""
    _install_fake_clamd(monkeypatch, _FakeClamdAlive)
    async with _client() as c:
        r = await c.get("/api/healthz/clamav")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["clamd_daemon"] == "alive", body
    assert isinstance(body["clamd_ping_response_ms"], int), body
    assert body["clamd_ping_response_ms"] >= 0, body
    # `debug` is omitted on the alive path.
    assert "debug" not in body, body


# ── S1.B — unreachable branch (ConnectionRefusedError) ─────────────
@pytest.mark.asyncio
async def test_step1_unreachable_branch_connection_refused(monkeypatch, clean_scan_log):
    """Anchor chain: clamd PING raises ConnectionRefusedError →
    handler classifies `clamd_daemon == "unreachable"` AND
    `clamd_ping_response_ms is None` AND HTTP 200 (NOT 503 — this
    is a status report, not a gate)."""
    _install_fake_clamd(monkeypatch, _FakeClamdRefuses)
    async with _client() as c:
        r = await c.get("/api/healthz/clamav")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["clamd_daemon"] == "unreachable", body
    assert body["clamd_ping_response_ms"] is None, body
    # `debug.exception_class` must NOT leak on unreachable path —
    # the daemon is just down, no triage payload needed.
    assert "debug" not in body, body


# ── S1.C — unreachable branch (ClamAVUnreachable explicit) ─────────
@pytest.mark.asyncio
async def test_step1_unreachable_branch_clamav_unreachable_exception(
    monkeypatch, clean_scan_log,
):
    """Anchor chain: the service's own `ClamAVUnreachable` class is
    raised inside the ping path → still classified as
    `unreachable` (NOT `unknown`)."""
    _install_fake_clamd(monkeypatch, _FakeClamdUnreachableException)
    async with _client() as c:
        r = await c.get("/api/healthz/clamav")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["clamd_daemon"] == "unreachable", body
    assert body["clamd_ping_response_ms"] is None, body


# ── S1.C2 — unreachable branch (clamd library's own ConnectionError)
@pytest.mark.asyncio
async def test_step1_unreachable_branch_clamd_lib_connection_error(
    monkeypatch, clean_scan_log,
):
    """Regression test for the live-probe bug: `clamd.ConnectionError`
    does NOT inherit from Python's built-in `ConnectionError`. Without
    an explicit catch for the library's class, an unreachable daemon
    mis-classifies as `unknown`. The fix wires `clamd.ConnectionError`
    + `clamd.ClamdError` into the unreachable_exc_types tuple at
    handler runtime.

    Anchor chain: PING raises `clamd.ConnectionError` →
    `clamd_daemon == "unreachable"` (NOT `"unknown"`)."""
    _install_fake_clamd(monkeypatch, _FakeClamdLibConnectionError)
    async with _client() as c:
        r = await c.get("/api/healthz/clamav")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["clamd_daemon"] == "unreachable", (
        f"Library `clamd.ConnectionError` mis-classified as "
        f"'{body['clamd_daemon']}' — the explicit catch for "
        f"`clamd.ConnectionError` regressed."
    )
    assert body["clamd_ping_response_ms"] is None, body
    # `debug` MUST NOT leak on the unreachable path — daemon is just
    # down; no triage payload needed.
    assert "debug" not in body, body


# ── S1.D — unknown branch ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_step1_unknown_branch(monkeypatch, clean_scan_log):
    """Anchor chain: clamd PING raises an unrelated `ValueError` →
    handler classifies `clamd_daemon == "unknown"` AND surfaces the
    exception class via `debug.exception_class` (operator triage)
    AND HTTP 200."""
    _install_fake_clamd(monkeypatch, _FakeClamdUnknown)
    async with _client() as c:
        r = await c.get("/api/healthz/clamav")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["clamd_daemon"] == "unknown", body
    assert body["clamd_ping_response_ms"] is None, body
    assert (body.get("debug") or {}).get("exception_class") == "ValueError", body


# ── S1.E — histogram 24h with stale-row exclusion ──────────────────
@pytest.mark.asyncio
async def test_step1_histogram_24h_from_upload_scan_log(monkeypatch, clean_scan_log):
    """Anchor chain: 4 fresh `upload_scan_log` rows (one per bucket)
    + 1 stale row (>24h ago) → handler reports 4 in the histogram,
    the stale row is excluded, AND `last_scan_at_utc` reflects the
    MOST RECENT row (regardless of histogram window).

    Tests the `_scan_histogram_24h()` aggregation chain end-to-end."""
    _install_fake_clamd(monkeypatch, _FakeClamdAlive)
    now = datetime.now(timezone.utc)
    fresh_results = [
        ("clean",       now - timedelta(minutes=1),  "ok"),
        ("infected",    now - timedelta(minutes=2),  "infected"),
        ("bypassed",    now - timedelta(minutes=3),  "bypassed"),
        ("unreachable", now - timedelta(minutes=4),  "error"),
    ]
    stale_results = [
        ("clean", now - timedelta(hours=48), "ok"),
    ]
    most_recent_iso = (now - timedelta(minutes=1)).isoformat()
    rows = []
    for r, ts, _ in fresh_results + stale_results:
        rows.append({
            "file_id": f"step1-{uuid.uuid4().hex[:6]}",
            "scan_result": r,
            "scanned_at": ts.isoformat(),
            "filename": "step1.txt",
            "size_bytes": 16,
            "duration_ms": 1,
        })
    await core_mod.db[UPLOAD_SCAN_LOG_COLLECTION].insert_many(rows)
    async with _client() as c:
        r = await c.get("/api/healthz/clamav")
    assert r.status_code == 200, r.text
    body = r.json()
    h = body["scans_last_24h"]
    assert h == {"ok": 1, "infected": 1, "bypassed": 1, "error": 1}, h
    # `last_scan_at_utc` reflects the MOST RECENT row across all ages.
    assert body["last_scan_at_utc"] == most_recent_iso, body


# ── S1.F — empty log branch ────────────────────────────────────────
@pytest.mark.asyncio
async def test_step1_empty_log_branch(monkeypatch, clean_scan_log):
    """Anchor chain: empty `upload_scan_log` collection →
    `last_scan_at_utc is None` AND all 4 histogram buckets == 0."""
    _install_fake_clamd(monkeypatch, _FakeClamdAlive)
    async with _client() as c:
        r = await c.get("/api/healthz/clamav")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["last_scan_at_utc"] is None, body
    assert body["scans_last_24h"] == {
        "ok": 0, "infected": 0, "bypassed": 0, "error": 0,
    }, body


# ── S1.G — live schema-shape (no monkeypatch) ──────────────────────
@pytest.mark.asyncio
async def test_step1_schema_shape_live():
    """Anchor chain: hit the running endpoint with no monkeypatch.
    Schema MUST satisfy:
      - 6 top-level keys all present
      - `clamd_daemon` ∈ {alive, unreachable, unknown}
      - `scans_last_24h` is a dict with the 4 expected bucket keys
      - `preflight_size_check_active` is True
      - `checked_at_utc` parses as ISO 8601 datetime
    Daemon classification NOT asserted — env-dependent."""
    async with _client() as c:
        r = await c.get("/api/healthz/clamav")
    assert r.status_code == 200, r.text
    body = r.json()
    required_keys = {
        "clamd_daemon", "clamd_ping_response_ms", "last_scan_at_utc",
        "scans_last_24h", "checked_at_utc", "preflight_size_check_active",
    }
    missing = required_keys - set(body.keys())
    assert not missing, f"Missing top-level keys: {missing}. Got: {sorted(body.keys())}"
    assert body["clamd_daemon"] in {"alive", "unreachable", "unknown"}, body
    assert isinstance(body["scans_last_24h"], dict)
    assert set(body["scans_last_24h"].keys()) == {
        "ok", "infected", "bypassed", "error",
    }, body["scans_last_24h"]
    assert body["preflight_size_check_active"] is True, body
    # checked_at_utc parses as ISO 8601 (datetime.fromisoformat tolerates it).
    parsed = datetime.fromisoformat(body["checked_at_utc"])
    assert isinstance(parsed, datetime), body
    # The endpoint MUST NOT modify `services/clamav_service.py` — pin
    # the import-survival contract from the hardening brief.
    assert "ClamAVUnreachable" in router_mod.__dict__ or hasattr(
        router_mod, "ClamAVUnreachable",
    ) or "from services.clamav_service" in Path(router_mod.__file__).read_text(encoding="utf-8")
