"""
Phase AA-slice-6 (2026-05-27) — Probability-bar fill refinement.

Locks the brand-purple three-band scheme (Wave 4.2.followup.2 migrated
to Tailwind-config short names because the `bg-[var(--ned-purple)]/N`
opacity-modifier syntax silently failed on hex CSS vars):
  • ≥70% → `bg-[var(--ned-purple)]`        (strong — full opacity, raw CSS var ok)
  • 40-69% → `bg-ned-purple/60`             (mid)
  • <40%  → `bg-ned-purple/30`              (muted)
  • null  → `bg-ned-purple/15`              (placeholder)

Anti-regression: no `bg-slate-*` greys in the probability bar
helper (Wave 4.2 brand-purple-only rule).
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TASKS_PANEL = REPO_ROOT / "frontend" / "src" / "components" / "monitor" / "TasksInitiativesPanel.jsx"


def _probability_bar_class_block() -> str:
    src = TASKS_PANEL.read_text(encoding="utf-8")
    m = re.search(
        r'function\s+probabilityBarClass\s*\([^)]*\)\s*\{(.+?)\n\}',
        src,
        re.DOTALL,
    )
    assert m, "probabilityBarClass function not found"
    return m.group(1)


def test_aa6_high_band_locked() -> None:
    body = _probability_bar_class_block()
    # The ≥70 band returns the full-strength purple (no opacity modifier,
    # so the raw CSS var is fine here).
    pattern = r'value\s*>=\s*70.*?return\s+"bg-\[var\(--ned-purple\)\]"'
    assert re.search(pattern, body, re.DOTALL), (
        '≥70% band must return `"bg-[var(--ned-purple)]"`.'
    )


def test_aa6_mid_band_locked() -> None:
    body = _probability_bar_class_block()
    # Wave 4.2.followup.2 — short name only (silent-fail trap on hex var).
    pattern = r'value\s*>=\s*40.*?return\s+"bg-ned-purple/60"'
    assert re.search(pattern, body, re.DOTALL), (
        '40-69% band must return `"bg-ned-purple/60"` '
        '(Tailwind-config short name — Wave 4.2.followup.2).'
    )


def test_aa6_low_band_locked() -> None:
    body = _probability_bar_class_block()
    pattern = r'return\s+"bg-ned-purple/30"'
    assert re.search(pattern, body, re.DOTALL), (
        'Low (<40%) band must return `"bg-ned-purple/30"` '
        '(Tailwind-config short name — Wave 4.2.followup.2).'
    )


def test_aa6_null_placeholder_locked() -> None:
    body = _probability_bar_class_block()
    pattern = r'return\s+"bg-ned-purple/15"'
    assert re.search(pattern, body, re.DOTALL), (
        'Null value must return `"bg-ned-purple/15"` placeholder '
        '(still purple, not grey — Wave 4.2 rule; short name per '
        'Wave 4.2.followup.2).'
    )


def test_aa6_no_greys_in_probability_helper() -> None:
    """Anti-regression — `bg-slate-*` / `bg-gray-*` must NOT appear
    inside the probability bar helper. This is the institutional
    Wave 4.2 "no grey capsules" rule applied to the probability
    bar specifically."""
    body = _probability_bar_class_block()
    assert "bg-slate-" not in body, (
        "Probability-bar helper must NOT contain `bg-slate-*` — "
        "Wave 4.2 brand-purple-only rule."
    )
    assert "bg-gray-" not in body, (
        "Probability-bar helper must NOT contain `bg-gray-*` — "
        "Wave 4.2 brand-purple-only rule."
    )


def test_aa6_no_silent_fail_opacity_syntax_in_helper() -> None:
    """Wave 4.2.followup.2 — `bg-[var(--ned-purple)]/N` is the silent-
    fail trap. The helper must use Tailwind-config short names with
    opacity (`bg-ned-purple/N`). Raw `bg-[var(--ned-purple)]` (no
    opacity modifier) is fine."""
    body = _probability_bar_class_block()
    bad = re.search(r"bg-\[var\(--ned-purple\)\]/\d", body)
    assert bad is None, (
        "Probability-bar helper must NOT use the silent-fail "
        "`bg-[var(--ned-purple)]/N` syntax. Use `bg-ned-purple/N` "
        "(Tailwind-config short name) instead."
    )
