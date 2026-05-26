"""Redeploy-cleanup invariants — pins the Bucket-2 archives from 2026-05-26.

Each test fails against `v-pre-redeploy-cleanup` and passes post-cleanup.
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

REPO = Path(__file__).resolve().parents[2]
FE_SRC = REPO / "frontend" / "src"
FE_ARCHIVE = FE_SRC / "_archived_legacy"
BE = REPO / "backend"
BE_ARCHIVE = BE / "_archived_legacy"
BE_TESTS_ARCHIVE = BE / "tests" / "_archived_coverage_loss"


# ---------------------------------------------------------------------------
# RC.1 — Plays backend router archived
# ---------------------------------------------------------------------------
def test_rc_plays_router_archived():
    live = BE / "routers" / "plays.py"
    archived = BE_ARCHIVE / "routers" / "plays.py.archived"
    assert not live.exists(), f"live router must be archived: {live}"
    assert archived.exists(), f"archive missing: {archived}"
    # `from routers import plays` must now raise ImportError.
    with pytest.raises(ImportError):
        importlib.import_module("routers.plays")


# ---------------------------------------------------------------------------
# RC.2 — Plays frontend pages archived
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("page", ["PlaysLibrary.jsx", "PlayView.jsx"])
def test_rc_plays_pages_archived(page: str):
    live = FE_SRC / "pages" / page
    archived = FE_ARCHIVE / "pages" / f"{page}.archived"
    assert not live.exists(), f"live page must be archived: {live}"
    assert archived.exists(), f"archive missing: {archived}"


# ---------------------------------------------------------------------------
# RC.3 — components/plays/ directory removed
# ---------------------------------------------------------------------------
def test_rc_plays_components_dir_removed():
    plays_dir = FE_SRC / "components" / "plays"
    assert not plays_dir.exists(), (
        f"components/plays/ must be removed after archive: {plays_dir}"
    )
    # Archives present.
    for name in ("PreBoardStages.jsx", "BoardPackStages.jsx"):
        arch = FE_ARCHIVE / "components" / "plays" / f"{name}.archived"
        assert arch.exists(), f"archive missing: {arch}"


# ---------------------------------------------------------------------------
# RC.4 — App.js no longer imports / routes Plays
# ---------------------------------------------------------------------------
def test_rc_plays_routes_unmounted_appjs():
    app_js = (FE_SRC / "App.js").read_text(encoding="utf-8")
    assert 'import("@/pages/PlaysLibrary")' not in app_js
    assert 'import("@/pages/PlayView")' not in app_js
    assert '<PlaysLibrary' not in app_js
    assert '<PlayView' not in app_js
    assert 'path="/app/plays"' not in app_js


# ---------------------------------------------------------------------------
# RC.5 — /api/plays/library is unreachable
# ---------------------------------------------------------------------------
def test_rc_plays_router_unmounted_server():
    from fastapi.testclient import TestClient
    from server import app

    client = TestClient(app)
    r = client.get("/api/plays/library")
    assert r.status_code == 404, (
        f"plays router should be unmounted, got {r.status_code}: {r.text[:200]}"
    )


# ---------------------------------------------------------------------------
# RC.6 — Plays test files moved to _archived_coverage_loss
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name", [
    "test_iter24_plays.py",
    "test_iter25_plays_slice2.py",
])
def test_rc_plays_tests_archived(name: str):
    live = BE / "tests" / name
    archived = BE_TESTS_ARCHIVE / f"{name}.archived"
    assert not live.exists(), f"live test must be archived: {live}"
    assert archived.exists(), f"archive missing: {archived}"


# ---------------------------------------------------------------------------
# RC.7 — cycle_config router archived + /api/contexts/.../cycle-config 404s
# ---------------------------------------------------------------------------
def test_rc_cycle_config_router_archived():
    live = BE / "routers" / "cycle_config.py"
    archived = BE_ARCHIVE / "routers" / "cycle_config.py.archived"
    assert not live.exists(), f"live router must be archived: {live}"
    assert archived.exists(), f"archive missing: {archived}"
    with pytest.raises(ImportError):
        importlib.import_module("routers.cycle_config")


def test_rc_cycle_config_endpoints_unmounted():
    from fastapi.testclient import TestClient
    from server import app

    client = TestClient(app)
    r = client.get("/api/contexts/x/cycle-config")
    assert r.status_code == 404, (
        f"cycle-config GET should be unmounted, got {r.status_code}"
    )


# ---------------------------------------------------------------------------
# RC.8 — CycleSettings page + useCycleConfig hook archived
# ---------------------------------------------------------------------------
def test_rc_cycle_settings_chain_archived():
    page_live = FE_SRC / "pages" / "CycleSettings.jsx"
    hook_live = FE_SRC / "hooks" / "useCycleConfig.js"
    page_arch = FE_ARCHIVE / "pages" / "CycleSettings.jsx.archived"
    hook_arch = FE_ARCHIVE / "hooks" / "useCycleConfig.js.archived"
    assert not page_live.exists()
    assert not hook_live.exists()
    assert page_arch.exists()
    assert hook_arch.exists()

    app_js = (FE_SRC / "App.js").read_text(encoding="utf-8")
    assert 'import("@/pages/CycleSettings")' not in app_js
    assert '<CycleSettings' not in app_js
    assert 'path="/app/settings/cycle"' not in app_js


# ---------------------------------------------------------------------------
# RC.9 — cycle.py docstring header documents canonical-vs-pre-spec families
# ---------------------------------------------------------------------------
def test_rc_cycle_py_docstring_present():
    cycle_py = (BE / "routers" / "cycle.py").read_text(encoding="utf-8")
    # Top-of-file docstring must reference the provenance trace + classify
    # endpoint families. We assert by anchor strings (not exact wording).
    assert "POST-CLEANUP-B2 STATUS NOTE" in cycle_py
    assert "PROVENANCE_TRACE_PLAYS_CYCLE.md" in cycle_py
    assert "CANONICAL" in cycle_py
    assert "PRE-SPEC" in cycle_py
    assert "do not extend" in cycle_py.lower()


# ---------------------------------------------------------------------------
# RC.10 — routers/agenda.py is NOT archived (escalated per brief)
# ---------------------------------------------------------------------------
def test_rc_agenda_router_preserved():
    """agenda.py serves /agenda-evolution (Home AgendaEvolutionCard) —
    NOT Plays-related despite filename adjacency. Has live consumers.
    Must remain on disk per the brief's `if used elsewhere, leave and
    escalate` conditional."""
    live = BE / "routers" / "agenda.py"
    archived = BE_ARCHIVE / "routers" / "agenda.py.archived"
    assert live.exists(), f"agenda.py must remain on disk: {live}"
    assert not archived.exists(), (
        f"agenda.py must NOT be archived (escalate, not archive): {archived}"
    )
