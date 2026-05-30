"""Sprint M.1c (2026-02 dispatch 7) — marketing-assets-guard CI lockdown."""
from __future__ import annotations
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
WF = REPO / ".github" / "workflows" / "marketing-assets-guard.yml"

EXPECTED_PATHS = [
    "frontend/src/website/**",
    "frontend/src/components/marketing/**",
    "frontend/public/marketing/**",
    "docs/marketing_assets.md",
    "backend/tests/test_phase_m0a_marketing_assets.py",
    ".github/workflows/marketing-assets-guard.yml",
]


def test_m1c_workflow_exists():
    assert WF.exists()


def test_m1c_workflow_triggers_and_invokes_m0a_pytest():
    src = WF.read_text(encoding="utf-8")
    assert "pull_request:" in src and "push:" in src
    assert "branches: [main]" in src
    missing = [p for p in EXPECTED_PATHS if f'"{p}"' not in src]
    assert not missing, f"Trigger paths missing: {missing}"
    assert "python3 -m pytest backend/tests/test_phase_m0a_marketing_assets.py" in src
    assert "|| true" not in src
