"""Phase L.b.2 (2026-05-27) — Frontend wiring for the 5 L.b SSE
surfaces CI lockdown.

L.b.2 ships frontend wiring only: each surface gets the locked
`<StreamingLogScene>` component driven by `usePhasedTimer` (NOT
`useStreamingProgress`, intentionally — the L.b backend SSE pipes
have signature mismatches with the inner handlers for 4/5 surfaces
which would have required reopening L.b. The visual contract is
identical; a future L.b.3 dispatch can swap the timer for SSE).

Locks:
  - StreamingLogScene icon map carries the 4 new L.b icons.
  - Frontend mirror of PHASE_SCRIPTS lives in `data/phaseScripts.js`
    with all 5 surfaces + labels matching backend verbatim.
  - usePhasedTimer hook ships with the locked state shape.
  - 5 surface call sites each:
      * Import StreamingLogScene + usePhasedTimer
      * Invoke `lbStart` with the locked surface key
      * Render `<StreamingLogScene surfaceId="streaming-log-…">`
      * Use the kebab-case testid pattern `streaming-log-<surface>`
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from services.streaming.progress import PHASE_SCRIPTS  # noqa: E402


SCENE_JSX      = REPO / "frontend" / "src" / "components" / "transitions" / "StreamingLogScene.jsx"
SCRIPTS_JS     = REPO / "frontend" / "src" / "data" / "phaseScripts.js"
TIMER_JS       = REPO / "frontend" / "src" / "hooks" / "usePhasedTimer.js"
PREPARING_JSX  = REPO / "frontend" / "src" / "components" / "solva" / "flow" / "PreparingInterstitial.jsx"
ENHANCE_JSX    = REPO / "frontend" / "src" / "components" / "studio" / "EnhanceModal.jsx"
CYCLE_JSX      = REPO / "frontend" / "src" / "pages" / "Cycle.jsx"
EVENTS_JSX     = REPO / "frontend" / "src" / "pages" / "Events.jsx"
DECKS_JSX      = REPO / "frontend" / "src" / "pages" / "Decks.jsx"


LB_SURFACES = [
    "solva-synthesis",
    "work-studio-enhance",
    "task-manager-compile",
    "events-calendar-sync",
    "decks-generation",
]


# ─────────────────────────────────────────────────────────────────────
# A. StreamingLogScene icon map covers the L.b additions
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("icon_key", ["scale", "calendar", "download", "presentation"])
def test_LB2_a_scene_icon_map_carries_lb_icons(icon_key):
    src = SCENE_JSX.read_text(encoding="utf-8")
    assert f'"{icon_key}":' in src, \
        f"StreamingLogScene ICON_MAP must declare {icon_key!r}"


def test_LB2_a_scene_imports_new_lucide_icons():
    src = SCENE_JSX.read_text(encoding="utf-8")
    # All 4 new lucide imports must be present (icon names are PascalCase).
    for name in ("Scale", "Calendar", "Download", "Presentation"):
        assert name in src, \
            f"StreamingLogScene must import lucide-react icon {name!r}"


# ─────────────────────────────────────────────────────────────────────
# B. Frontend mirror of PHASE_SCRIPTS — parity with backend
# ─────────────────────────────────────────────────────────────────────

def test_LB2_b_frontend_scripts_file_exists_with_5_surfaces():
    src = SCRIPTS_JS.read_text(encoding="utf-8")
    for surface in LB_SURFACES:
        assert f'"{surface}":' in src, \
            f"frontend phaseScripts.js must declare surface {surface!r}"


@pytest.mark.parametrize("surface", LB_SURFACES)
def test_LB2_b_frontend_labels_match_backend_verbatim(surface):
    src = SCRIPTS_JS.read_text(encoding="utf-8")
    for phase in PHASE_SCRIPTS[surface]:
        label = phase["label"]
        # The labels are embedded as JS string literals.
        assert label in src, \
            f"frontend phaseScripts.js missing label {label!r} for surface {surface!r}"


# ─────────────────────────────────────────────────────────────────────
# C. usePhasedTimer hook ships with the locked state shape
# ─────────────────────────────────────────────────────────────────────

def test_LB2_c_timer_hook_exposes_locked_api():
    src = TIMER_JS.read_text(encoding="utf-8")
    # The hook MUST return start/complete/error/cancel/reset/state to
    # match useStreamingProgress's swap-in contract.
    for name in ("start", "complete", "error", "cancel", "reset", "state"):
        assert f"return {{" in src and name in src, \
            f"usePhasedTimer must expose {name!r}"
    # State keys mirroring useStreamingProgress.
    for key in ("surface", "phases", "activeIndex", "completedIndexes",
                "result", "error", "status"):
        assert key in src, f"usePhasedTimer state shape missing {key!r}"
    # Status enum compatibility.
    for status in ("idle", "streaming", "complete", "error", "cancelled"):
        assert f'"{status}"' in src, f"status enum missing {status!r}"


def test_LB2_c_timer_hook_imports_lb_scripts():
    src = TIMER_JS.read_text(encoding="utf-8")
    assert "LB_PHASE_SCRIPTS" in src, \
        "usePhasedTimer must read from the locked frontend script map"
    assert '@/data/phaseScripts' in src or '/data/phaseScripts' in src


# ─────────────────────────────────────────────────────────────────────
# D. Each surface call site wires StreamingLogScene + usePhasedTimer
# ─────────────────────────────────────────────────────────────────────

SURFACE_TO_FILE = {
    "solva-synthesis":      PREPARING_JSX,
    "work-studio-enhance":  ENHANCE_JSX,
    "task-manager-compile": CYCLE_JSX,
    "events-calendar-sync": EVENTS_JSX,
    "decks-generation":     DECKS_JSX,
}


@pytest.mark.parametrize("surface,path", SURFACE_TO_FILE.items())
def test_LB2_d_surface_imports_streaming_log_and_timer(surface, path):
    src = path.read_text(encoding="utf-8")
    assert "StreamingLogScene" in src, \
        f"{path.name} must import StreamingLogScene for surface {surface!r}"
    assert "usePhasedTimer" in src, \
        f"{path.name} must use usePhasedTimer for surface {surface!r}"


@pytest.mark.parametrize("surface,path", SURFACE_TO_FILE.items())
def test_LB2_d_surface_starts_timer_with_locked_key(surface, path):
    src = path.read_text(encoding="utf-8")
    # Call sites use `lbStart("<surface>", { stepMs: N })` OR
    # `start("<surface>", { stepMs: N })` for the standalone interstitial.
    assert f'"{surface}"' in src, \
        f"{path.name} must call start() with the locked surface key {surface!r}"


@pytest.mark.parametrize("surface,path", SURFACE_TO_FILE.items())
def test_LB2_d_surface_renders_streaming_log_scene_with_kebab_testid(surface, path):
    src = path.read_text(encoding="utf-8")
    locked_testid = f"streaming-log-{surface}"
    assert locked_testid in src, \
        f"{path.name} must render <StreamingLogScene surfaceId=\"{locked_testid}\" /> " \
        f"(kebab-case, surface-keyed)"


# ─────────────────────────────────────────────────────────────────────
# E. PreparingInterstitial migration (replaces line-fade UI)
# ─────────────────────────────────────────────────────────────────────

def test_LB2_e_preparing_no_longer_uses_legacy_fade_lines():
    """The pre-L.b.2 implementation used a 3-line fade rotation
    (`Looking across what you've shared.` etc.). Those literals must
    not appear in the new file — only the StreamingLogScene + phase
    script flow."""
    src = PREPARING_JSX.read_text(encoding="utf-8")
    legacy_phrases = [
        "Looking across what you've shared.",
        "Checking against your evidence.",
        "Composing the synthesis.",
    ]
    for phrase in legacy_phrases:
        assert phrase not in src, \
            f"PreparingInterstitial must not carry legacy line {phrase!r} after L.b.2"


def test_LB2_e_preparing_keeps_solva_preparing_testid():
    """The default `solva-preparing` testid must stay so callers and
    downstream tests (Phase I + Phase K Solva test suite) still match."""
    src = PREPARING_JSX.read_text(encoding="utf-8")
    assert 'testId = "solva-preparing"' in src or 'solva-preparing' in src
