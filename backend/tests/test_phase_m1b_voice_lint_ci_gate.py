"""Sprint M.1b (2026-02 fork-resume v3 dispatch 6) — CI pre-merge
voice-lint gate self-test.

Mirrors the pattern of `test_requirements_guard.py` — the workflow
file itself cannot silently disappear or drift. Asserts:

  * Workflow YAML exists at the expected path.
  * Trigger paths include every customer-copy surface ZZ.* / M.0 / M.1a
    closed against drift.
  * Workflow invokes `scripts/lint_voice.py`.
  * The scanner itself returns 0 across the live surface.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
WF = REPO / ".github" / "workflows" / "voice-lint.yml"
EXPECTED_TRIGGER_PATHS = [
    "frontend/src/website/**",
    "frontend/src/components/marketing/**",
    "frontend/src/copy/**",
    "docs/WEBSITE_BRIEF_V3.md",
    "docs/cohort_pricing.md",
    "docs/marketing_assets.md",
    "scripts/lint_voice.py",
    "backend/services/two_pass.py",
    ".github/workflows/voice-lint.yml",
]


def test_m1b_workflow_file_exists():
    assert WF.exists(), f"Voice-lint CI workflow missing: {WF}"


def test_m1b_workflow_triggers_on_pull_request_and_push():
    src = WF.read_text(encoding="utf-8")
    assert "on:" in src
    assert "pull_request:" in src
    assert "push:" in src
    assert "branches: [main]" in src


def test_m1b_workflow_covers_every_surface_path():
    src = WF.read_text(encoding="utf-8")
    missing = [p for p in EXPECTED_TRIGGER_PATHS if f'"{p}"' not in src]
    assert not missing, (
        f"Workflow trigger paths missing required surface entries: {missing}"
    )


def test_m1b_workflow_invokes_lint_voice_script():
    src = WF.read_text(encoding="utf-8")
    assert "python3 scripts/lint_voice.py" in src


def test_m1b_workflow_has_no_baseline_carveout():
    """The CI gate must not import or reference BASELINE_KNOWN_HITS —
    zero-hit invariant is permanent. Any reintroduction of a baseline
    carve-out at CI level would silently re-open drift."""
    src = WF.read_text(encoding="utf-8")
    assert "BASELINE_KNOWN_HITS" not in src
    assert "--allow-baseline" not in src
    assert "|| true" not in src  # never swallow failures


def test_m1b_lint_voice_script_returns_zero_on_live_surface():
    """Re-run the scanner from the repo root and confirm exit code 0."""
    result = subprocess.run(
        [sys.executable, "scripts/lint_voice.py"],
        cwd=str(REPO), capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, (
        f"voice-lint scanner returned {result.returncode}:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "clean across customer-copy surfaces" in result.stdout
