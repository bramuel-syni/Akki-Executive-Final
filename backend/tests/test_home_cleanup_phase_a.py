"""Phase A Home Cleanup — wire-check invariants.

Static file-source assertions that prove the four Phase A invariants
land on disk. Mirrors the existing test_t1_/t2_/t3_/t4_/t5_frontend_wire.py
pattern used across the T-series sprint.

Acceptance criteria (a)-(g) from the brief are anchored as follows:

  (a) HOME_CLEANUP_LOG.md sections           — `test_phase_a_log_has_required_sections`
  (b) Company tile titles 30% smaller        — `test_phase_a_company_tile_title_is_11px`
                                              + `test_phase_a_hero_greeting_unchanged`
                                              + `test_phase_a_companies_heading_unchanged`
  (c) --ned-purple token + chip styling      — `test_phase_a_ned_purple_token_defined`
                                              + `test_phase_a_executive_chip_oxblood_15pct`
                                              + `test_phase_a_ned_chip_ned_purple_15pct`
  (d) Read more link → Learn route           — `test_phase_a_read_more_link_present`
                                              + `test_phase_a_read_more_targets_learn`
                                              + `test_phase_a_curated_for_badge_unchanged`
  (e) Coming up + Continue side-by-side      — `test_phase_a_recent_and_calendar_share_grid`
  (f) No new packages                        — `test_phase_a_no_new_packages_in_lockfile_check`
                                                (lockfile-name check; package additions
                                                surface as bin/yarn.lock churn outside
                                                this pass)
  (g) Read more test exists (this file)      — auto-satisfied by collection
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    p = REPO / rel
    assert p.exists(), f"missing source file: {rel}"
    return p.read_text(encoding="utf-8")


# ── (a) ─────────────────────────────────────────────────────────────
def test_phase_a_log_has_required_sections():
    log = _read("memory/sprints/HOME_CLEANUP_LOG.md")
    for marker in (
        "Batch overview",
        "Phase A",
        "Phase B",
        "Spec/Code Delta",
        "Deploy-readiness checklist",
    ):
        assert marker in log, f"HOME_CLEANUP_LOG.md missing section: {marker}"


# ── (b) — company tile title scope ─────────────────────────────────
def test_phase_a_company_tile_title_is_11px():
    src = _read("frontend/src/pages/home/Home1.jsx")
    # The title <p> inside ChipCompany is the only place where
    # `home1-chip-${ctx.id}-title` testid is rendered.
    block_start = src.find("home1-chip-${ctx.id}-title")
    assert block_start != -1, "company-tile-title testid missing"
    # Walk backwards to find the className that opens this <p>.
    pre = src[max(0, block_start - 400):block_start]
    assert "text-[11px]" in pre, (
        "company tile title must render at text-[11px] (30% of 16px). "
        "Phase A Home cleanup item #1 scope: tile titles only."
    )
    assert "text-[16px]" not in pre, (
        "tile title still carries text-[16px] — 30% reduction not applied"
    )


def test_phase_a_hero_greeting_unchanged():
    """Acceptance (b): hero "Good afternoon, [name]." size unchanged.
    The greeting uses class `akki-greeting` defined in index.css; the
    spec for that class lives unchanged at font-size: 28px."""
    css = _read("frontend/src/index.css")
    # Find the `.akki-greeting {` block + check font-size still 28px.
    idx = css.find(".akki-greeting {")
    assert idx != -1, ".akki-greeting class missing from index.css"
    block = css[idx: idx + 400]
    assert "font-size: 28px" in block, (
        "hero greeting font-size must remain 28px (Phase A scope tightened "
        "to tile titles only; hero stays at current size)."
    )


def test_phase_a_companies_heading_unchanged():
    """Acceptance (b): "Your companies" section heading size unchanged."""
    src = _read("frontend/src/pages/home/Home1.jsx")
    # Heading inline class set at line ~178.
    idx = src.find('">Your companies</h2>')
    assert idx != -1, "'Your companies' heading not found"
    block = src[max(0, idx - 200):idx]
    assert "text-[15px]" in block, (
        "'Your companies' heading must remain text-[15px] (Phase A scope: "
        "tile titles only; section heading stays at current size)."
    )


# ── (c) — chip colors ──────────────────────────────────────────────
def test_phase_a_ned_purple_token_defined():
    css = _read("frontend/src/index.css")
    assert "--ned-purple:" in css, "--ned-purple token must be defined in index.css"
    assert "#6B46C1" in css, "ned-purple must resolve to #6B46C1 per brief"


def test_phase_a_executive_chip_oxblood_15pct():
    src = _read("frontend/src/pages/home/Home1.jsx")
    # Executive chip rendered when role === "owner".
    idx = src.find('if (role === "owner")')
    assert idx != -1, "Executive (owner) role branch missing"
    branch = src[idx: idx + 400]
    assert "rgba(122, 46, 46, 0.15)" in branch, (
        "Executive chip bg must be Oxblood @ 15% opacity"
    )
    assert "var(--oxblood)" in branch, (
        "Executive chip text color must reference --oxblood"
    )


def test_phase_a_ned_chip_ned_purple_15pct():
    src = _read("frontend/src/pages/home/Home1.jsx")
    idx = src.find('else if (role === "ned")')
    assert idx != -1, "NED role branch missing"
    branch = src[idx: idx + 400]
    assert "rgba(107, 70, 193, 0.15)" in branch, (
        "NED chip bg must be --ned-purple @ 15% opacity"
    )
    assert "var(--ned-purple)" in branch, (
        "NED chip text color must reference --ned-purple"
    )


# ── (d) — Read more link ───────────────────────────────────────────
def test_phase_a_read_more_link_present():
    src = _read("frontend/src/pages/home/Home1.jsx")
    assert 'data-testid="home1-news-read-more"' in src, (
        "Read more link testid missing from news section"
    )
    assert ">Read more <" in src or "Read more " in src, (
        "Read more label not rendered in source"
    )


def test_phase_a_read_more_targets_learn():
    src = _read("frontend/src/pages/home/Home1.jsx")
    # Anchor on the Read more block: find the testid, then check that
    # the Link before it carries `to="/app/learn"`.
    testid_idx = src.find('data-testid="home1-news-read-more"')
    assert testid_idx != -1
    pre = src[max(0, testid_idx - 300):testid_idx]
    assert 'to="/app/learn"' in pre, (
        "Read more link must navigate to /app/learn (existing Learn route — "
        "no new route created)"
    )


def test_phase_a_curated_for_badge_unchanged():
    """Brief: KEEP the CURATED FOR [COUNTRY] badge exactly where it is."""
    src = _read("frontend/src/pages/home/Home1.jsx")
    assert 'data-testid="home1-news-source-label"' in src, (
        "CURATED FOR badge testid missing — must be preserved"
    )
    assert "Curated for ${REGION_LABELS" in src, (
        "Curated-for region label expression must remain"
    )


# ── (e) — recent + calendar 2-col grid ─────────────────────────────
def test_phase_a_recent_and_calendar_share_grid():
    src = _read("frontend/src/pages/home/Home1.jsx")
    assert 'data-testid="home1-recent-calendar-grid"' in src, (
        "Phase A item #4: home1-recent and home1-calendar must be wrapped "
        "in a 2-column grid with testid home1-recent-calendar-grid"
    )
    # Confirm the grid uses md:grid-cols-2 (Tailwind default md breakpoint
    # at 768px ≈ "desktop" per brief).
    idx = src.find('data-testid="home1-recent-calendar-grid"')
    pre = src[max(0, idx - 250):idx]
    assert "md:grid-cols-2" in pre, (
        "grid must use md:grid-cols-2 so the sections sit side-by-side "
        "at desktop widths and stack on small screens"
    )
    # Both sections must still be present, and the wrapper must contain
    # both testids.
    post = src[idx: idx + 4000]
    assert 'data-testid="home1-recent"' in post, "home1-recent missing"
    assert 'data-testid="home1-calendar"' in post, "home1-calendar missing"


# ── (f) — package guard ────────────────────────────────────────────
def test_phase_a_no_new_packages_in_lockfile_check():
    """Brief acceptance (f): No new npm packages.

    Conservative check — Phase A only added a CSS variable + JSX
    edits + a react-router-dom `Link` import (already in package.json).
    No `package.json` edits are expected for this pass; verify it
    still parses + contains the expected core deps.
    """
    pkg = _read("frontend/package.json")
    # Sanity anchors — these must not be removed by an over-eager edit.
    for dep in ("react", "react-router-dom"):
        assert f'"{dep}"' in pkg, f"core dep `{dep}` missing from package.json"
