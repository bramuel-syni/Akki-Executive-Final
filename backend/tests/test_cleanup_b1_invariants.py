"""Cleanup B1 invariants — pins the archive moves from 2026-05-26.

Each test fails against `v-pre-cleanup-bucket-1` and passes post-cleanup.
"""
from __future__ import annotations

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
BE_TESTS_ARCHIVE = REPO / "backend" / "tests" / "_archived_coverage_loss"


# ---------------------------------------------------------------------------
# B1.1 — SolvaLanding page archived
# ---------------------------------------------------------------------------
def test_b1_solva_landing_page_archived():
    """The unreachable pages/SolvaLanding.jsx is gone from the live tree
    and present in the archive."""
    live = FE_SRC / "pages" / "SolvaLanding.jsx"
    archived = FE_ARCHIVE / "pages" / "SolvaLanding.jsx.archived"
    assert not live.exists(), f"live page must be archived: {live}"
    assert archived.exists(), f"archive missing: {archived}"


# ---------------------------------------------------------------------------
# B1.2 — SandboxV2 page archived
# ---------------------------------------------------------------------------
def test_b1_sandbox_v2_page_archived():
    live = FE_SRC / "pages" / "SandboxV2.jsx"
    archived = FE_ARCHIVE / "pages" / "SandboxV2.jsx.archived"
    assert not live.exists(), f"live page must be archived: {live}"
    assert archived.exists(), f"archive missing: {archived}"


# ---------------------------------------------------------------------------
# B1.3 — /legacy-sandbox routes removed from App.js
# ---------------------------------------------------------------------------
def test_b1_legacy_sandbox_routes_removed():
    app_js = (FE_SRC / "App.js").read_text(encoding="utf-8")
    assert 'path="/legacy-sandbox"' not in app_js, (
        "legacy-sandbox route must be removed from App.js"
    )
    # No live lazy import / element binding (the only SandboxV2 mention
    # allowed is inside a /* ... */ comment block documenting the archive).
    assert 'import("@/pages/SandboxV2")' not in app_js, (
        "SandboxV2 lazy import must be removed from App.js"
    )
    assert "<SandboxV2" not in app_js, (
        "no live <SandboxV2 /> JSX may remain in App.js"
    )


# ---------------------------------------------------------------------------
# B1.4 — Cycle components (9 files) archived
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,subdir", [
    ("ReportsTab.jsx", "cycle"),
    ("CycleTracker.jsx", "cycle"),
    ("ReviewInboxCard.jsx", "cycle"),
    ("NedInboxTile.jsx", "cycle"),
    ("CycleStrip.jsx", "cycle"),
    ("CyclePhaseSheet.jsx", "cycle"),
    ("ActionsTab.jsx", "cycle/tabs"),
    ("BoardpackTab.jsx", "cycle/tabs"),
    ("MinutesTab.jsx", "cycle/tabs"),
    ("SignalsTab.jsx", "cycle/tabs"),
])
def test_b1_cycle_components_archived(name: str, subdir: str):
    live = FE_SRC / "components" / subdir / name
    archived = FE_ARCHIVE / "components" / subdir / f"{name}.archived"
    assert not live.exists(), f"live component must be archived: {live}"
    assert archived.exists(), f"archive missing: {archived}"


# ---------------------------------------------------------------------------
# B1.5 — Solo orphan components archived
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("name,subdir", [
    ("AllLensesModal.jsx", "lens"),
    ("DepthOfferCard.jsx", "depth"),
    ("StreamingShell.jsx", "streaming"),
])
def test_b1_solo_components_archived(name: str, subdir: str):
    live = FE_SRC / "components" / subdir / name
    archived = FE_ARCHIVE / "components" / subdir / f"{name}.archived"
    assert not live.exists(), f"live component must be archived: {live}"
    assert archived.exists(), f"archive missing: {archived}"


# ---------------------------------------------------------------------------
# B1.6 — test_iter22_billing_schedule.py archived
# ---------------------------------------------------------------------------
def test_b1_test_iter22_archived():
    live = REPO / "backend" / "tests" / "test_iter22_billing_schedule.py"
    archived = BE_TESTS_ARCHIVE / "test_iter22_billing_schedule.py.archived"
    assert not live.exists(), f"contradicting Stripe test must be archived: {live}"
    assert archived.exists(), f"archive missing: {archived}"


# ---------------------------------------------------------------------------
# B1.7 — /api/help/features now serves AKKI_PRODUCT_SPEC.md
# ---------------------------------------------------------------------------
def test_b1_help_route_serves_product_spec():
    """The endpoint must serve the canonical product spec, not the
    deprecated AKKI_FEATURES_AND_FUNCTIONALITY.md."""
    from fastapi.testclient import TestClient
    from server import app

    client = TestClient(app)
    r = client.get("/api/help/features")
    assert r.status_code == 200, r.text
    body = r.json()
    md = body["markdown"]
    # New: spec H1 present
    assert md.startswith("# AKKI Product Spec"), (
        f"expected '# AKKI Product Spec' H1, got start={md[:80]!r}"
    )
    # Anti-regression: legacy features-doc H1 absent
    assert "# AKKI — Features & Functionality" not in md, (
        "deprecated AKKI_FEATURES_AND_FUNCTIONALITY.md is still being served"
    )
    # Title field reflects the new H1
    assert body["title"] == "AKKI Product Spec", body["title"]
