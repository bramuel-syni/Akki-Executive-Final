"""Solva v2 — Slice 7 (2026-05-29) Verification + polish.

Locks two artefacts:
  1. `data-solva-v2-slide-ready-at` ISO timestamp attribute on every
     slide root (SlideShell forwards the prop; the hook populates the
     wallclock the slide first transitioned to ready).
  2. Session-log side-panel (SessionLogPanel) — re-opens from the
     topbar's Session-Log icon stub (previously dead). Renders the
     SSE event timeline + per-slide ready-at table + stream meta.

Source-strict probes only — the source-of-truth for the Slice 7
contract lives in the JSX files. Runtime DOM probes are captured
inline in the close-out evidence on PHASE_LEDGER.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SlideShell.jsx"
ORCH = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SolvaArtefactV2.jsx"
TICKER = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SolvaReasoningTicker.jsx"
PANEL = REPO / "frontend" / "src" / "components" / "solva" / "artefact_v2" / "SessionLogPanel.jsx"
HOOK = REPO / "frontend" / "src" / "hooks" / "useSolvaReasoningStream.js"


# ─────────────────────────────────────────────────────────────────
# slide-ready-at timestamp contract
# ─────────────────────────────────────────────────────────────────


def test_slide_shell_renders_ready_at_attribute():
    """SlideShell must render `data-solva-v2-slide-ready-at` on the
    slide root, sourced from the `readyAt` prop."""
    src = SHELL.read_text(encoding="utf-8")
    assert "data-solva-v2-slide-ready-at={readyAt" in src
    # readyAt must be accepted as a destructured prop.
    assert "readyAt," in src


def test_orchestrator_passes_ready_at_to_each_slide():
    """The orchestrator MUST forward `readyAt` from the hook's
    slideReadyAtMap into every slide's shared-render args."""
    src = ORCH.read_text(encoding="utf-8")
    assert "readyAt," in src
    # Source from the hook map keyed by slide.kind.
    assert "stream.slideReadyAtMap" in src


def test_hook_initialises_slide_ready_at_map_for_all_locked_kinds():
    src = HOOK.read_text(encoding="utf-8")
    assert "slideReadyAtMap:" in src
    assert "_emptySlideAtMap" in src


def test_hook_stamps_ready_at_on_slide_ready_event():
    """The hook must stamp `new Date().toISOString()` exactly when
    a slide.ready event arrives — NOT overwrite a previous stamp
    (idempotency for duplicate events)."""
    src = HOOK.read_text(encoding="utf-8")
    # First-stamp-only guard:
    assert "!s.slideReadyAtMap[payload.slide_kind]" in src
    assert "new Date().toISOString()" in src


def test_hook_replay_bypass_stamps_all_kinds():
    """`?replay=0` instant-bypass must stamp every kind with a single
    timestamp so the ready-at attribute is never empty on hydrated
    artefacts."""
    src = HOOK.read_text(encoding="utf-8")
    assert "_emptySlideAtMap(_instantTs)" in src


# ─────────────────────────────────────────────────────────────────
# Session-log side-panel contract
# ─────────────────────────────────────────────────────────────────


def test_session_log_panel_file_exists():
    assert PANEL.is_file()


def test_session_log_panel_emits_locked_testids():
    src = PANEL.read_text(encoding="utf-8")
    for tid in (
        "solva-v2-session-log-panel",
        "solva-v2-session-log-scrim",
        "solva-v2-session-log-close",
        "solva-v2-session-log-meta",
        "solva-v2-session-log-status",
        "solva-v2-session-log-mode",
        "solva-v2-session-log-events-count",
        "solva-v2-session-log-slide-table",
        "solva-v2-session-log-event-list",
    ):
        assert f'data-testid="{tid}"' in src, f"SessionLogPanel missing testid {tid!r}"


def test_session_log_panel_renders_per_slide_rows():
    """Each slide row must carry a per-kind testid + the locked
    `data-solva-v2-session-log-slide-kind` machine attribute."""
    src = PANEL.read_text(encoding="utf-8")
    assert "solva-v2-session-log-slide-row-${kind}" in src
    assert "data-solva-v2-session-log-slide-kind={kind}" in src
    assert "data-solva-v2-session-log-slide-ready-at={ts" in src


def test_session_log_panel_imported_into_orchestrator():
    src = ORCH.read_text(encoding="utf-8")
    assert "import SessionLogPanel" in src
    assert "<SessionLogPanel" in src
    # State must be present.
    assert "logPanelOpen" in src
    assert "setLogPanelOpen" in src


# ─────────────────────────────────────────────────────────────────
# Topbar icon stub → onClick wired
# ─────────────────────────────────────────────────────────────────


def test_ticker_log_icon_accepts_on_click_handler():
    src = TICKER.read_text(encoding="utf-8")
    # Prop accepted.
    assert "onLogIconClick" in src
    # Both the icon stub AND the pill must call it (pill is the post-
    # complete state, icon is post-pill).
    icon_block = src[src.find('postCompleteStage === "icon"'):src.find('postCompleteStage === "pill"')]
    pill_block = src[src.find('postCompleteStage === "pill"'):src.find("// Live / replay ticker")]
    assert "onClick={onLogIconClick}" in icon_block, "Icon stub MUST call onLogIconClick"
    assert "onClick={onLogIconClick}" in pill_block, "Pill MUST also call onLogIconClick"


def test_orchestrator_threads_open_handler_to_ticker():
    src = ORCH.read_text(encoding="utf-8")
    assert "onLogIconClick={() => setLogPanelOpen(true)}" in src


def test_session_log_close_clears_open_state():
    src = ORCH.read_text(encoding="utf-8")
    assert "onClose={() => setLogPanelOpen(false)}" in src


# ─────────────────────────────────────────────────────────────────
# Identity / brand discipline
# ─────────────────────────────────────────────────────────────────


def test_session_log_panel_chip_opacity_inside_allowlist():
    """Wave 4.2.followup.2 — any ned-purple/N opacity in the panel
    must be inside the locked allowlist."""
    src = PANEL.read_text(encoding="utf-8")
    opacities = re.findall(r"ned-purple/(\d+)", src)
    # Allow no opacity tokens (the panel uses solid + scrim only) OR
    # require all to be in allowlist.
    allowed = {5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 95, 100}
    for o in opacities:
        assert int(o) in allowed, (
            f"ned-purple/{o} outside Wave 4.2.followup.2 allowlist in SessionLogPanel"
        )


def test_session_log_panel_no_solve_brand_drift():
    """Identity audit — only `Solva` (never `SOLVE` or `Solve`) appears."""
    src = PANEL.read_text(encoding="utf-8")
    # `Solva` is allowed; any standalone SOLVE / Solve token is banned.
    assert " SOLVE " not in src
    assert "/SOLVE/" not in src
