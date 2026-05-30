"""Pytest fixtures shared by Solva v2 tests (and any future async test).

Phase 15.0 hardening pass: pytest-asyncio 0.23 with `auto` mode creates a
fresh event loop per async test by default. Motor's AsyncIO client latches
onto whichever loop first awaits it; once that loop is closed, subsequent
tests in fresh loops break with `RuntimeError: Event loop is closed`.

The fix is a session-scoped event_loop fixture so every async test in this
process shares a single loop. This is the documented pattern for sharing
Motor across tests under pytest-asyncio. The `scope='session'` event_loop
override is deprecated-but-functional in 0.23 (a clean replacement
`asyncio_default_loop_scope` ships in 0.25 which we have not pinned).

Sync tests (e.g. test_cycle_manager_actions_tab.py) are unaffected: they
use `asyncio.run()` and create their own short-lived loops, ignoring this
fixture entirely.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest
from dotenv import load_dotenv

# Load backend env once for every collected test. Without this, any test
# whose imports reach `core.py` (which reads MONGO_URL at import time) fails
# at collection unless an earlier test file already called load_dotenv.
# Phase 15.1: services/solva_v2/__init__.py now re-exports the llm_adapter
# (which imports core), so the implicit-ordering hack the older tests relied
# on is no longer safe. Frontend env is loaded too because the
# request-driven smoke tests read REACT_APP_BACKEND_URL.
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

# Phase P3.1 (2026-02) — CSRF middleware bypass for test runs.
# Existing tests drive endpoints directly via TestClient / AsyncClient
# and don't mint a CSRF cookie. Honour the in-process bypass switch so
# the suite keeps passing while production traffic still enforces CSRF.
os.environ.setdefault("CSRF_TEST_BYPASS_HEADER", "1")
# Phase P3 — disable rate-limit during tests. The suite drives ~50+
# login calls in <60s; without this, the per-IP login bucket trips
# and downstream MFA / B.4 / B.6 tests cascade-fail. Production
# never sets this env.
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")
import httpx as _httpx  # noqa: E402
_orig_request = _httpx.AsyncClient.request
async def _patched_request(self, method, url, *args, **kwargs):
    headers = kwargs.get("headers") or {}
    headers = dict(headers)
    headers.setdefault("X-CSRF-Test-Bypass", "1")
    kwargs["headers"] = headers
    return await _orig_request(self, method, url, *args, **kwargs)
_httpx.AsyncClient.request = _patched_request

# Also patch the sync TestClient transport.
from starlette.testclient import TestClient as _StarletteTestClient  # noqa: E402
_orig_sync_request = _StarletteTestClient.request
def _patched_sync_request(self, method, url, **kwargs):
    headers = kwargs.get("headers") or {}
    headers = dict(headers)
    headers.setdefault("X-CSRF-Test-Bypass", "1")
    kwargs["headers"] = headers
    return _orig_sync_request(self, method, url, **kwargs)
_StarletteTestClient.request = _patched_sync_request

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the entire test session.

    Phase 15.1: bumped pytest-asyncio to >=0.25 in requirements.txt and set
    `asyncio_default_fixture_loop_scope = session` in pytest.ini so this
    override is no longer deprecated. Motor's module-singleton client
    needs a stable loop for the lifetime of the suite.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _isolate_dependency_overrides():
    """Snapshot + restore `app.dependency_overrides` per test.

    Phase C — Several legacy tests (test_cycle_feel_pass.py,
    test_cycle_assignment_handoff.py, test_cycles_v2.py, test_patch_*.py,
    etc.) set `app.dependency_overrides[get_current_account] = …` from
    inside the test body and never clean up. The pollution then bleeds
    into any test that runs *after* them, masking auth-gate assertions
    as 200 OK responses.

    This autouse fixture snapshots the override dict at test start and
    restores it at teardown, isolating each test without modifying the
    polluters. Tests that legitimately set overrides inside their own
    body keep working unchanged — only the cross-test leak is plugged.
    """
    # Import is local to avoid pulling FastAPI into collection-only runs.
    try:
        from server import app as _app  # type: ignore
    except Exception:
        # If `server` can't import here, the test will fail anyway with a
        # clearer error — don't mask import-level breakage.
        yield
        return
    snapshot = dict(_app.dependency_overrides)
    try:
        yield
    finally:
        _app.dependency_overrides.clear()
        _app.dependency_overrides.update(snapshot)

