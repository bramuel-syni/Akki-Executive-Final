"""Phase B Home Cleanup — wire-check invariants.

DEPRECATED — Phase I.1 archived Home2.jsx (2026-05-27).

Home2.jsx is now at `frontend/src/_archived/Home2.jsx` and no longer
mounts on any active route — the active-context branch of AppHome
renders the new `CompanyHome.jsx` (Phase I.1 layout shell). The
Phase B cleanup invariants documented here were preserved in the
archived file but the live app no longer renders Home2, so running
these tests against it is irrelevant. The whole module is skipped.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Phase I.1 archived Home2.jsx; Phase B cleanup tests no longer apply."
)

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "akki_dev")
os.environ.setdefault("JWT_SECRET", "x" * 64)

REPO = Path(__file__).resolve().parents[2]
HOME2 = REPO / "frontend" / "src" / "pages" / "home" / "Home2.jsx"


def _read(p: Path) -> str:
    assert p.exists(), f"missing source file: {p}"
    return p.read_text(encoding="utf-8")


# ── (a) — greeting band restructure ──────────────────────────────
def test_phase_b_back_to_portfolio_above_company_name():
    src = _read(HOME2)
    back_idx = src.find('data-testid="home2-back-to-portfolio"')
    name_idx = src.find('data-testid="home2-company-name"')
    assert back_idx != -1, "back-to-portfolio testid missing"
    assert name_idx != -1, "company-name testid missing"
    assert back_idx < name_idx, (
        "Phase B item #1: 'Back to portfolio' must render ABOVE the "
        "company name in source order (also enforces DOM order at render)."
    )


def test_phase_b_triple_line_spacing_between_back_and_name():
    """Triple line-spacing realised as mt-12 (3em ≈ 48px at default
    16px root) on the company-name element."""
    src = _read(HOME2)
    # Anchor on the company-name <p> and check the className includes
    # mt-12 (Tailwind 3rem ≈ 3× the default line-height).
    idx = src.find('data-testid="home2-company-name"')
    pre = src[max(0, idx - 400):idx]
    assert "mt-12" in pre, (
        "Company name must have mt-12 (≈3× line-spacing) above it"
    )


def test_phase_b_company_name_size_1_2x():
    """Company name token size up 20% — pre-Phase-B size was 11px
    (defined by the `.akki-overline` CSS class). 11 × 1.2 = 13.2px →
    rounded down to 13px integer. Applied via inline `style` to win
    against the .akki-overline rule's 11px declaration."""
    src = _read(HOME2)
    idx = src.find('data-testid="home2-company-name"')
    pre = src[max(0, idx - 400):idx]
    assert 'style={{ fontSize: "13px" }}' in pre, (
        "Company name must carry inline style fontSize: 13px "
        "(11px × 1.2 = 13.2 → 13px) to override the .akki-overline "
        "default of 11px."
    )


# ── (b) — plate redesign ─────────────────────────────────────────
def test_phase_b_plate_column_60pct():
    """Plate column ≈60% — grid changed from 3fr/2fr → 2fr/3fr,
    putting the plate (right column) at 3/5 = 60% of the row width."""
    src = _read(HOME2)
    assert "min-[1100px]:grid-cols-[2fr_3fr]" in src, (
        "Hero-plate grid must use 2fr_3fr (plate = 3/5 = 60% width)."
    )
    assert "min-[1100px]:grid-cols-[3fr_2fr]" not in src, (
        "Old 3fr_2fr ratio must be removed."
    )


def test_phase_b_plate_order_and_labels():
    """Plate tiles render in this exact order: drafts_ready,
    compile_ready, pulse_critical, open_questions, documents_to_review."""
    src = _read(HOME2)
    order_start = src.find("const PLATE_ORDER = [")
    assert order_start != -1, "PLATE_ORDER const missing"
    block = src[order_start: order_start + 600]
    expected = [
        '"drafts_ready"',
        '"compile_ready"',
        '"pulse_critical"',
        '"open_questions"',
        '"documents_to_review"',
    ]
    last_pos = -1
    for key in expected:
        pos = block.find(key)
        assert pos != -1, f"PLATE_ORDER missing tile: {key}"
        assert pos > last_pos, (
            f"PLATE_ORDER out of order: '{key}' must follow previous"
        )
        last_pos = pos


def test_phase_b_plate_tile_labels_verbatim():
    src = _read(HOME2)
    # Each title string must appear verbatim somewhere in CARD_CONFIG.
    for label in (
        "Drafts Ready For You",
        "Reports Ready to Compile",
        "New Pulse Updates",
        "Open Questions",
        "Documents to Review",
    ):
        assert label in src, f"Missing tile label: {label}"


def test_phase_b_old_tiles_absent():
    """Old tile titles must be GONE from CARD_CONFIG."""
    src = _read(HOME2)
    # Anchor on the CARD_CONFIG const so we only check inside it
    # (the comment block above mentions the legacy tile names for
    # provenance — we want to confirm they don't appear as ACTIVE
    # title strings, e.g., `title: "Pulse alerts"`).
    cfg_idx = src.find("const CARD_CONFIG = {")
    assert cfg_idx != -1
    cfg_end = src.find("};", cfg_idx)
    cfg = src[cfg_idx: cfg_end]
    for legacy in (
        'title: "Pulse alerts"',
        'title: "Sign-offs needed"',
        'title: "Cycles closing this week"',
        'title: "Compile report"',
        'title: "Open questions"',
        'title: "Solva sessions waiting"',
    ):
        assert legacy not in cfg, (
            f"Old plate tile must be removed from CARD_CONFIG: {legacy}"
        )


def test_phase_b_no_fake_data_documents_to_review():
    src = _read(HOME2)
    # The disabled href must remain `null` so onCardClick no-ops the
    # navigation rather than faking a route.
    idx = src.find('documents_to_review:')
    assert idx != -1
    tile_block = src[idx: idx + 400]
    assert "href: null" in tile_block, (
        "documents_to_review tile must keep href: null until wired "
        "(no fake data / no fake destination)"
    )


# ── (c) — Coming up section ──────────────────────────────────────
def test_phase_b_coming_up_section_present():
    src = _read(HOME2)
    assert 'data-testid="home2-coming-up"' in src, (
        "Coming up section testid missing"
    )
    assert "Coming up" in src, "Coming up heading text missing"
    assert "No upcoming items in the next 14 days." in src, (
        "empty-state copy must be verbatim per brief"
    )


def test_phase_b_coming_up_in_left_column():
    """Coming up section must sit INSIDE the home2-hero-block div
    (left column) — not in the right column or the footer."""
    src = _read(HOME2)
    hero_idx = src.find('data-testid="home2-hero-block"')
    plate_idx = src.find('data-testid="home2-plate-block"')
    coming_idx = src.find('data-testid="home2-coming-up"')
    assert hero_idx < coming_idx < plate_idx, (
        "Coming up must render INSIDE the left hero block "
        "(between hero-block testid and plate-block testid)."
    )


# ── (d) — Running / Sitting tiles removed ───────────────────────
def test_phase_b_running_and_sitting_tiles_removed():
    src = _read(HOME2)
    for tid in (
        'data-testid="home2-footer-split"',
        'data-testid="home2-footer-running"',
        'data-testid="home2-footer-boards"',
    ):
        assert tid not in src, (
            f"Footer-split tile testid must be removed: {tid}"
        )
    # Body copy from the legacy tiles must also be gone.
    assert "Work Studio · Cycle Manager · Briefings." not in src
    assert "NED inbox · pending packs · open questions." not in src


def test_phase_b_whats_new_header_and_empty_state_preserved():
    src = _read(HOME2)
    # Brief: header + caught-up empty-state stay.
    assert "What's new since your last visit" in src
    assert "You're all caught up since your last visit." in src
    assert 'data-testid="home2-whats-new"' in src


# ── (e) — Backend insights includes the new counts ───────────────
def test_phase_b_insights_endpoint_includes_new_counts():
    """/home/insights must include drafts_ready + documents_to_review
    in its `insights` map. We exercise the endpoint indirectly via
    server import; full HTTP exercise is covered by the existing
    home-insights tests once a fixture context is present."""
    home_py = (REPO / "backend" / "routers" / "home.py").read_text("utf-8")
    assert '"drafts_ready":' in home_py
    assert '"documents_to_review":' in home_py
    assert "_count_drafts_ready" in home_py
    assert "_count_documents_to_review" in home_py


def test_phase_b_coming_up_endpoint_defined():
    home_py = (REPO / "backend" / "routers" / "home.py").read_text("utf-8")
    assert '/contexts/{context_id}/home/coming-up' in home_py
    assert "horizon_days" in home_py
    assert 'kind": "cycle_close"' in home_py or "kind\": \"cycle_close\"" in home_py
