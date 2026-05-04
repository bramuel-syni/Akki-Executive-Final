"""Synisense surface allow-list — prefix-check tests (Phase 15.0 hardening).

The pipeline accepts any surface in the explicit allow-list OR any string of
the form `solve_v2.<segment>` where segment is non-empty lowercase a-z0-9_.
This pattern lets Phase 15.1 add per-engine sub-surfaces (e.g.
`solve_v2.triangulation`) without further Phase-12 edits.
"""
from __future__ import annotations

import os
import sys

import pytest
from dotenv import load_dotenv

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
load_dotenv("/app/backend/.env")

from services.synisense.pipeline import _is_valid_surface, _VALID_SURFACES  # noqa: E402


@pytest.mark.parametrize("surface", sorted(_VALID_SURFACES))
def test_explicit_allow_list_remains_valid(surface):
    assert _is_valid_surface(surface) is True


def test_solve_v2_bare_remains_valid():
    assert _is_valid_surface("solve_v2") is True


@pytest.mark.parametrize("surface", [
    "solve_v2.triangulation",
    "solve_v2.candidate_generation",
    "solve_v2.probability_weighting",
    "solve_v2.refusal",
    "solve_v2.a",
    "solve_v2.synth_v2",
    "solve_v2.engine_42",
])
def test_solve_v2_subsurfaces_are_valid(surface):
    assert _is_valid_surface(surface) is True


@pytest.mark.parametrize("bad", [
    "solve_v2.",                    # empty segment
    "solve_v2.Bad-Thing",           # capitals + hyphen
    "solve_v2.UPPER",               # capitals
    "solve_v2.with-hyphen",         # hyphen
    "solve_v2.has space",           # space
    "solve_v2.has.dot",             # nested dot
    "solve_v3.triangulation",       # not allow-listed prefix
    "solve.foo",                    # solve (v1) does NOT support sub-surfaces
    "chat.foo",                     # chat does NOT support sub-surfaces
    "",                             # empty
    "random_surface",               # not in allow-list at all
])
def test_invalid_surfaces_are_rejected(bad):
    assert _is_valid_surface(bad) is False


def test_real_pipeline_run_rejects_bad_subsurface(monkeypatch):
    """End-to-end: pipeline.run raises ValueError on a malformed sub-surface."""
    import asyncio
    from services.synisense.pipeline import run

    async def _runner():
        with pytest.raises(ValueError, match="invalid surface"):
            await run(
                text="hello world",
                context_id="ctx-test",
                surface="solve_v2.Bad-Thing",
                mode="redact",
                account_id="acct-test",
            )

    asyncio.run(_runner())
