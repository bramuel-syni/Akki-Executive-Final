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
