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

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the entire test session.

    Without this override, pytest-asyncio creates a per-function loop and
    Motor's client latches onto a loop that closes between tests.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
