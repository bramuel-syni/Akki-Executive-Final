"""Wave8.followup.3 (2026-02 fork-resume) — promote orthogonality
wire-test to pre-deploy CI gate.

Locks:
    1. Makefile exposes a `deploy-check` target that runs
       `pytest -m runtime_playwright`.
    2. The GitHub Actions production deploy workflow has a
       `deploy-check` job that runs BEFORE `deploy` (job dependency).
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def test_w8_f3_makefile_has_deploy_check_target():
    src = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "deploy-check:" in src, (
        "Makefile must expose a `deploy-check` target"
    )
    assert "pytest -m runtime_playwright" in src, (
        "deploy-check target must run `pytest -m runtime_playwright`"
    )
    # Target must be in .PHONY so it always runs.
    phony_line = next(
        (l for l in src.splitlines() if l.startswith(".PHONY")),
        "",
    )
    assert "deploy-check" in phony_line, (
        "deploy-check must be in the .PHONY declaration"
    )


def test_w8_f3_deploy_workflow_runs_deploy_check_before_deploy():
    p = REPO / ".github" / "workflows" / "deploy.yml"
    assert p.exists(), "deploy.yml workflow missing"
    src = p.read_text(encoding="utf-8")
    # Pre-deploy gate job exists.
    assert "deploy-check:" in src, (
        "deploy.yml must define a `deploy-check:` job"
    )
    # That job runs `make deploy-check`.
    assert "make deploy-check" in src, (
        "deploy-check job must invoke `make deploy-check`"
    )
    # The `deploy` job must depend on `deploy-check` via `needs:`.
    deploy_block_match = re.search(
        r"^\s*deploy:\s*\n(?:[\s\S]+?)needs:\s*\[(.*?)\]",
        src,
        re.MULTILINE,
    )
    assert deploy_block_match, (
        "deploy job's `needs:` list not found — Wave8.followup.3 "
        "requires `needs: [build, deploy-check]` or similar."
    )
    needs_list = deploy_block_match.group(1)
    assert "deploy-check" in needs_list, (
        f"deploy job must depend on deploy-check (current needs: "
        f"{needs_list!r})"
    )


def test_w8_f3_runtime_playwright_marker_pinned_to_orthogonality_test():
    """Sanity guard — make sure Z-slice-6 still carries the
    runtime_playwright marker (the whole gate is meaningless if the
    test stops registering under the marker)."""
    p = REPO / "backend" / "tests" / "test_phase_z_slice_6_orthogonality_wire.py"
    src = p.read_text(encoding="utf-8")
    assert "pytest.mark.runtime_playwright" in src
