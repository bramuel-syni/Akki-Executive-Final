"""Phase Y — `<StrategicRow>` primitive structural lockdown
(2026-02 fork-resume).

The shared row primitive at `components/strategic_row/StrategicRow.jsx`
is the single source of truth for the row layout consumed by:
  • Monitor goal rows (Strategic Goals listing)  → see test_monitor_row_uses_primitive.py
  • Task Manager cards (TaskListing)              → see test_task_card_uses_primitive.py

These guards lock the primitive's public surface — slots, data
attributes, accessibility, default behaviour — so future consumers
cannot accidentally diverge.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

PRIMITIVE = REPO / "frontend" / "src" / "components" / "strategic_row" / "StrategicRow.jsx"


# ─────────────────────────────────────────────────────────────────
# A. Source-level structural contract
# ─────────────────────────────────────────────────────────────────


def test_primitive_file_exists():
    """The primitive must live at the canonical path so future consumers
    import via `@/components/strategic_row/StrategicRow`."""
    assert PRIMITIVE.is_file(), (
        f"<StrategicRow> primitive must exist at {PRIMITIVE!s}. "
        f"Phase Y locks this path so consumers don't drift."
    )


def test_primitive_default_export_is_strategic_row():
    src = PRIMITIVE.read_text(encoding="utf-8")
    assert re.search(r"export\s+default\s+function\s+StrategicRow\b", src), (
        "<StrategicRow> must be the default export of StrategicRow.jsx."
    )


def test_primitive_named_export_score_bar():
    """The ScoreBar sub-component is exposed as a named export so
    Monitor's StrategicGoalsPanel can re-import it where it already
    has bespoke score-bar usage (e.g. drawer thumbnails)."""
    src = PRIMITIVE.read_text(encoding="utf-8")
    assert re.search(r"export\s+function\s+ScoreBar\b", src), (
        "ScoreBar must be a named export so existing consumers can "
        "re-use the bar-only sub-component without copy-pasting."
    )


def test_primitive_declares_all_slots():
    """The primitive's signature must accept every slot the spec calls
    for. Defaults must keep the primitive usable when consumers omit a
    slot."""
    src = PRIMITIVE.read_text(encoding="utf-8")
    required_props = (
        "categoryChip",
        "statusChip",
        "title",
        "rightSideScores",
        "metadataChildren",
        "description",
        "onClick",
        "testId",
        "isLast",
    )
    for prop in required_props:
        assert prop in src, (
            f"<StrategicRow> must accept the {prop!r} slot/prop per spec."
        )


def test_primitive_root_carries_strategic_row_data_attribute():
    """Every rendered row must declare `data-strategic-row="true"` on
    its root container so consumers (Monitor + Task Manager) share a
    single CSS selector for runtime probes."""
    src = PRIMITIVE.read_text(encoding="utf-8")
    assert 'data-strategic-row="true"' in src, (
        "<StrategicRow> root must declare `data-strategic-row=\"true\"`."
    )


def test_primitive_metadata_row_carries_data_attribute():
    src = PRIMITIVE.read_text(encoding="utf-8")
    assert 'data-strategic-row-metadata="true"' in src, (
        "Metadata sub-row must declare `data-strategic-row-metadata=\"true\"`."
    )


def test_primitive_scores_carry_data_attribute():
    src = PRIMITIVE.read_text(encoding="utf-8")
    assert 'data-strategic-row-scores="true"' in src, (
        "Right-anchored scores wrapper must declare "
        "`data-strategic-row-scores=\"true\"`."
    )


def test_primitive_description_carries_data_attribute():
    src = PRIMITIVE.read_text(encoding="utf-8")
    assert 'data-strategic-row-description="true"' in src, (
        "Description slot must declare "
        "`data-strategic-row-description=\"true\"`."
    )


# ─────────────────────────────────────────────────────────────────
# B. Accessibility contract
# ─────────────────────────────────────────────────────────────────


def test_primitive_clickable_row_is_keyboard_accessible():
    """When onClick is provided, the row must be focusable (`tabIndex`),
    expose `role="button"`, and respond to Enter / Space keys."""
    src = PRIMITIVE.read_text(encoding="utf-8")
    assert 'role={clickable ? "button" : undefined}' in src, (
        "Clickable row must expose role=button."
    )
    assert 'tabIndex={clickable ? 0 : undefined}' in src, (
        "Clickable row must expose tabIndex=0 for keyboard focus."
    )
    assert '"Enter"' in src and '" "' in src, (
        "Clickable row must respond to Enter and Space keys."
    )


# ─────────────────────────────────────────────────────────────────
# C. Wave 4.2.followup.2 compliance — no silent-fail opacity syntax
# ─────────────────────────────────────────────────────────────────


def test_primitive_no_silent_fail_opacity_syntax():
    """The primitive must NEVER use the silent-fail
    `bg-[var(--token)]/N` opacity-modifier syntax that broke under
    hex CSS vars. Allowed: Tailwind short names (`bg-ned-purple/N`)
    or full hex literals (`bg-[#6B46C1]/N`)."""
    src = PRIMITIVE.read_text(encoding="utf-8")
    bad = re.compile(r"(bg|border|text|ring)-\[var\(--[a-z-]+\)\]/\d")
    offenders = [
        f"line {n}: {line.strip()[:120]}"
        for n, line in enumerate(src.splitlines(), 1)
        if bad.search(line)
    ]
    assert not offenders, (
        "Wave 4.2.followup.2 silent-fail syntax in <StrategicRow>:\n  - "
        + "\n  - ".join(offenders)
    )
