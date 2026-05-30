"""Sprint M.0b — voice lint scanner regression baseline.

The Sprint M.0b spec from the user:

  > Pytest: scan-test that asserts current marketing pages PASS the lint
  > (so the existing site stays compliant). This may surface latent
  > violations — if it does, log them in PHASE_LEDGER as `M.0b-followup`
  > rather than fixing now.

The 18 latent hits surfaced on the first lint run (logged in PHASE_LEDGER
as `M.0b-followup`) are baselined here. The test fails ONLY if new
violations land beyond the baseline — i.e. it guards regressions
without blocking the prep slice on the existing tech debt.

When Sprint M.1 rewrites the marketing surfaces (or M.0b-followup
cleans them up), drop the matching entries from `BASELINE_KNOWN_HITS`.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(REPO / "scripts"))
from lint_voice import scan, DEFAULT_TARGETS  # noqa: E402

# 2026-02 dispatch 5 — M.1a cleared all 18 latent customer-copy
# violations with editorial recasts. Baseline is now empty; voice
# lint enforces strict compliance across the surface.
BASELINE_KNOWN_HITS = set()


def test_m0b_voice_lint_no_new_violations():
    hits = scan(DEFAULT_TARGETS)
    actual = {(str(path.relative_to(REPO)), word.lower()) for path, _ln, word, _snip in hits}
    new_violations = actual - BASELINE_KNOWN_HITS
    assert not new_violations, (
        f"New customer-copy banned-vocab violations beyond the M.0b baseline: "
        f"{sorted(new_violations)}. Fix or update BASELINE_KNOWN_HITS with "
        "rationale in PHASE_LEDGER."
    )


def test_m0b_baseline_still_relevant():
    """If a baselined violation has been cleaned up upstream, fail so the
    baseline is trimmed (otherwise it silently rots)."""
    hits = scan(DEFAULT_TARGETS)
    actual = {(str(path.relative_to(REPO)), word.lower()) for path, _ln, word, _snip in hits}
    stale = BASELINE_KNOWN_HITS - actual
    assert not stale, (
        f"Baseline rows that no longer surface — trim them from "
        f"BASELINE_KNOWN_HITS: {sorted(stale)}"
    )


def test_m0b_senior_in_late_additions_section():
    brief = (REPO / "docs" / "WEBSITE_BRIEF_V3.md").read_text(encoding="utf-8")
    assert "## 1.3.1 Late additions (post-launch)" in brief
    assert "senior (in customer-facing copy)" in brief
