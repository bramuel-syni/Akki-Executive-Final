"""Solva v2 — Slice 5 (2026-05-29) Pre-mortem frontend render.

Source-strict guards on `PreMortemSlide.jsx`:
  • Locked DOM contract (data-solva-v2-slide=true + kind="pre_mortem"
    + slide-state attribute + footer via SlideShell)
  • Locked failure-kind chip opacity inside Wave 4.2.followup.2 allowlist
  • Per-failure machine-readable testid via data-solva-v2-failure-kind
  • Observational counter_action callout block ('Counter ·')
  • Triggering signals rendered as `→` bulletted list
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SLIDE = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "slides" / "PreMortemSlide.jsx"
ORCH = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SolvaArtefactV2.jsx"


def test_pre_mortem_slide_file_exists():
    assert SLIDE.is_file()


def test_pre_mortem_slide_passes_correct_kind_to_shell():
    src = SLIDE.read_text(encoding="utf-8")
    assert 'kind="pre_mortem"' in src


def test_pre_mortem_slide_threads_slide_state():
    """Per Slice 3b contract — every slide forwards slideState to
    SlideShell so the loading→ready transition fires for the new
    pre_mortem slide too."""
    src = SLIDE.read_text(encoding="utf-8")
    assert "slideState," in src
    assert "slideState={slideState}" in src


def test_pre_mortem_slide_emits_locked_testids():
    src = SLIDE.read_text(encoding="utf-8")
    for tid in (
        "solva-v2-pre-mortem-title",
        "solva-v2-pre-mortem-list",
    ):
        assert f'data-testid="{tid}"' in src


def test_pre_mortem_slide_carries_per_failure_machine_id_attribute():
    """Each failure card must carry `data-solva-v2-failure-kind={fm.failure_kind}`
    so tests can probe by canonical id."""
    src = SLIDE.read_text(encoding="utf-8")
    assert "data-solva-v2-failure-kind={fm.failure_kind}" in src
    assert "data-solva-v2-failure-index={idx}" in src


def test_failure_kind_chip_uses_allowlisted_opacity_steps():
    """Wave 4.2.followup.2 — chip opacity must be inside the allowlist
    {5,10,15,20,25,30,40,50,60,70,75,80,90,95,100}."""
    src = SLIDE.read_text(encoding="utf-8")
    chip_opacities = re.findall(r"bg-ned-purple/(\d+)", src)
    assert chip_opacities, "Expected at least one bg-ned-purple/N chip background"
    allowed = {5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95, 100}
    for o in chip_opacities:
        assert int(o) in allowed, (
            f"bg-ned-purple/{o} is OUTSIDE Wave 4.2.followup.2 allowlist"
        )


def test_failure_card_emits_narrative_signals_counter_blocks():
    """Each failure card must render: failure_narrative paragraph,
    triggering_signals list, optional counter_action block, source
    citation footer."""
    src = SLIDE.read_text(encoding="utf-8")
    # Narrative testid template
    assert "solva-v2-failure-narrative-${fm.failure_kind}" in src
    # Triggering signals testid template
    assert "solva-v2-failure-signals-${fm.failure_kind}" in src
    # Counter action testid template
    assert "solva-v2-failure-counter-${fm.failure_kind}" in src


def test_counter_action_block_uses_observational_label():
    """Per Slice 5 contract the counter callout must read 'Counter ·'
    NOT 'Action ·' or 'Recommendation ·' — Solva NAMES the failure
    mode and observes the counter, never instructs."""
    src = SLIDE.read_text(encoding="utf-8")
    assert "Counter ·" in src


def test_pre_mortem_slide_imports_into_orchestrator():
    """SolvaArtefactV2 must import + mount PreMortemSlide so the new
    slide reaches the deck."""
    src = ORCH.read_text(encoding="utf-8")
    assert "import PreMortemSlide" in src
    assert "<PreMortemSlide" in src


def test_pre_mortem_slide_positioned_between_pathway_and_decision_logic():
    """In composeSlides() the pre_mortem block must appear AFTER
    pathway and BEFORE decision_logic — the locked deck order."""
    src = ORCH.read_text(encoding="utf-8")
    pathway_idx = src.find('kind: "pathway"')
    pre_mortem_idx = src.find('kind: "pre_mortem"')
    decision_idx = src.find('kind: "decision_logic"')
    assert pathway_idx > 0
    assert pre_mortem_idx > 0
    assert decision_idx > 0
    assert pathway_idx < pre_mortem_idx < decision_idx, (
        f"Deck order broken — pathway={pathway_idx}, "
        f"pre_mortem={pre_mortem_idx}, decision_logic={decision_idx}"
    )


def test_no_imperative_phrasing_in_slide_intro():
    """The slide's static intro must read observationally — no 'You
    should' / 'Must' phrasings even in static copy."""
    src = SLIDE.read_text(encoding="utf-8")
    forbidden = (
        "You should",
        "you should",
        "You must",
        "you must",
        "You need to",
        "you need to",
    )
    for f in forbidden:
        assert f not in src, f"Forbidden imperative {f!r} found in PreMortemSlide.jsx"
