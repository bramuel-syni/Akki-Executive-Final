"""Phase L.b.3 (2026-05-27) — Frontend wiring + backend pipe lock.

Post-L.b.3 the 5 L.b surfaces use `useStreamingProgress` (real
backend-driven SSE) NOT `usePhasedTimer` (the L.b.2 timer-driven
stepping stone). This file replaces the L.b.2 frontend-wiring lock.

Locks:
  - StreamingLogScene icon map carries the 4 new L.b icons.
  - Frontend mirror of PHASE_SCRIPTS lives in `data/phaseScripts.js`
    with all 5 surfaces + labels matching backend verbatim.
  - useStreamingProgress hook ships with the locked state shape +
    FormData passthrough support.
  - 5 surface call sites each:
      * Import StreamingLogScene + useStreamingProgress
      * NOT import usePhasedTimer
      * Fire `.stream(<streaming URL>, opts)` against the locked
        streaming endpoint
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
HOOK_JS        = REPO / "frontend" / "src" / "hooks" / "useStreamingProgress.js"
PREPARING_JSX  = REPO / "frontend" / "src" / "components" / "solva" / "flow" / "PreparingInterstitial.jsx"
SOLVA_PAGE_JSX = REPO / "frontend" / "src" / "pages" / "SolvaSession.jsx"
ENHANCE_JSX    = REPO / "frontend" / "src" / "components" / "studio" / "EnhanceModal.jsx"
CYCLE_JSX      = REPO / "frontend" / "src" / "pages" / "Cycle.jsx"
EVENTS_JSX     = REPO / "frontend" / "src" / "pages" / "Events.jsx"
DECKS_JSX      = REPO / "frontend" / "src" / "pages" / "Decks.jsx"
STREAMING_PY   = REPO / "backend" / "routers" / "streaming_v9.py"
CYCLE_MGR_PY   = REPO / "backend" / "routers" / "cycle_manager.py"


LB_SURFACES = [
    "solva-synthesis",
    "work-studio-enhance",
    "task-manager-compile",
    "events-calendar-sync",
    "decks-generation",
]


# ─────────────────────────────────────────────────────────────────────
# A. StreamingLogScene icon map covers the L.b additions (unchanged)
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("icon_key", ["scale", "calendar", "download", "presentation"])
def test_LB3_a_scene_icon_map_carries_lb_icons(icon_key):
    src = SCENE_JSX.read_text(encoding="utf-8")
    assert f'"{icon_key}":' in src, \
        f"StreamingLogScene ICON_MAP must declare {icon_key!r}"


def test_LB3_a_scene_imports_new_lucide_icons():
    src = SCENE_JSX.read_text(encoding="utf-8")
    for name in ("Scale", "Calendar", "Download", "Presentation"):
        assert name in src, \
            f"StreamingLogScene must import lucide-react icon {name!r}"


# ─────────────────────────────────────────────────────────────────────
# B. Frontend mirror of PHASE_SCRIPTS — parity with backend (unchanged)
# ─────────────────────────────────────────────────────────────────────

def test_LB3_b_frontend_scripts_file_exists_with_5_surfaces():
    src = SCRIPTS_JS.read_text(encoding="utf-8")
    for surface in LB_SURFACES:
        assert f'"{surface}":' in src, \
            f"frontend phaseScripts.js must declare surface {surface!r}"


@pytest.mark.parametrize("surface", LB_SURFACES)
def test_LB3_b_frontend_labels_match_backend_verbatim(surface):
    src = SCRIPTS_JS.read_text(encoding="utf-8")
    for phase in PHASE_SCRIPTS[surface]:
        label = phase["label"]
        assert label in src, \
            f"frontend phaseScripts.js missing label {label!r} for surface {surface!r}"


# ─────────────────────────────────────────────────────────────────────
# C. useStreamingProgress hook ships with the locked contract
#    (NOT the timer hook — L.b.3 swap landed)
# ─────────────────────────────────────────────────────────────────────

def test_LB3_c_hook_exposes_locked_api():
    src = HOOK_JS.read_text(encoding="utf-8")
    # Hook MUST return state + stream + cancel + reset for the L.b.3 swap.
    for name in ("stream", "cancel", "reset", "state"):
        assert name in src, \
            f"useStreamingProgress must expose {name!r}"
    for key in ("surface", "phases", "activeIndex", "completedIndexes",
                "result", "error", "status"):
        assert key in src, f"useStreamingProgress state shape missing {key!r}"
    for status in ("idle", "streaming", "complete", "error", "cancelled", "connecting"):
        assert f'"{status}"' in src, f"status enum missing {status!r}"


def test_LB3_c_hook_supports_formdata_bodies():
    """L.b.3 multipart Enhance flow requires FormData passthrough — no
    JSON.stringify + no manual Content-Type header (browser sets the
    multipart boundary)."""
    src = HOOK_JS.read_text(encoding="utf-8")
    assert "FormData" in src, \
        "useStreamingProgress must detect FormData bodies"
    assert "isFormData" in src or "instanceof FormData" in src, \
        "useStreamingProgress must branch on FormData via instanceof check"


# ─────────────────────────────────────────────────────────────────────
# D. Each surface call site wires StreamingLogScene + useStreamingProgress
#    and POSTs against the locked streaming endpoint
# ─────────────────────────────────────────────────────────────────────

SURFACE_TO_FILE = {
    "solva-synthesis":      PREPARING_JSX,
    "work-studio-enhance":  ENHANCE_JSX,
    "task-manager-compile": CYCLE_JSX,
    "events-calendar-sync": EVENTS_JSX,
    "decks-generation":     DECKS_JSX,
}

# The DRIVER (file that owns the stream() POST) — separate from the
# visual surface for Solva, where SolvaSession.jsx fires the POST and
# PreparingInterstitial.jsx renders the state prop.
SURFACE_TO_DRIVER = {
    "solva-synthesis":      SOLVA_PAGE_JSX,
    "work-studio-enhance":  ENHANCE_JSX,
    "task-manager-compile": CYCLE_JSX,
    "events-calendar-sync": EVENTS_JSX,
    "decks-generation":     DECKS_JSX,
}


@pytest.mark.parametrize("surface,path", SURFACE_TO_FILE.items())
def test_LB3_d_surface_renders_streaming_log_scene_with_kebab_testid(surface, path):
    src = path.read_text(encoding="utf-8")
    locked_testid = f"streaming-log-{surface}"
    assert locked_testid in src, \
        f"{path.name} must render <StreamingLogScene surfaceId=\"{locked_testid}\" /> " \
        f"(kebab-case, surface-keyed)"


@pytest.mark.parametrize("surface,path", SURFACE_TO_DRIVER.items())
def test_LB3_d_driver_imports_use_streaming_progress(surface, path):
    src = path.read_text(encoding="utf-8")
    assert "useStreamingProgress" in src, \
        f"{path.name} must import useStreamingProgress (driver for surface {surface!r})"


@pytest.mark.parametrize("surface,path", SURFACE_TO_DRIVER.items())
def test_LB3_d_driver_no_longer_uses_phased_timer(surface, path):
    """L.b.3 swap removes timer-driven dependency. Re-introducing it
    would silently revert to L.b.2 behaviour."""
    src = path.read_text(encoding="utf-8")
    assert "usePhasedTimer" not in src, \
        f"{path.name} must NOT import usePhasedTimer post-L.b.3 (timer-driven reverts the swap)"


# ─────────────────────────────────────────────────────────────────────
# E. PreparingInterstitial accepts a state prop (driven by parent)
# ─────────────────────────────────────────────────────────────────────

def test_LB3_e_preparing_accepts_state_prop():
    src = PREPARING_JSX.read_text(encoding="utf-8")
    # The post-L.b.3 component pulls state from props (parent drives
    # the streaming POST). The legacy in-component `usePhasedTimer`
    # call must be gone.
    assert "state" in src and "props" in src.lower() or "state }" in src or "state," in src, \
        "PreparingInterstitial must accept a state prop from parent"
    assert "usePhasedTimer" not in src, \
        "PreparingInterstitial must not still drive the timer directly"


def test_LB3_e_preparing_keeps_solva_preparing_testid():
    src = PREPARING_JSX.read_text(encoding="utf-8")
    assert 'testId = "solva-preparing"' in src or 'solva-preparing' in src


# ─────────────────────────────────────────────────────────────────────
# F. Backend streaming_v9 — 5 endpoints with reconciled adapters
# ─────────────────────────────────────────────────────────────────────

def test_LB3_f_backend_solva_stream_is_account_scoped():
    """Solva synthesis URL changed to account-scoped (matches legacy
    post_turn signature). Context-scoped URL would 404 from the
    frontend swap."""
    src = STREAMING_PY.read_text(encoding="utf-8")
    assert "/solva/v2/sessions/{sid}/turn/stream" in src, \
        "Solva streaming URL must be account-scoped"
    # Confirm dependency is account-only (NOT require_context_membership).
    # Find the solva_synthesis_stream block and inspect its decorator/signature.
    idx = src.find("solva_synthesis_stream")
    assert idx > 0
    block = src[idx:idx + 2000]
    assert "get_current_account" in block, \
        "solva_synthesis_stream must depend on get_current_account"


def test_LB3_f_backend_enhance_stream_accepts_multipart():
    src = STREAMING_PY.read_text(encoding="utf-8")
    idx = src.find("work_studio_enhance_stream")
    assert idx > 0
    block = src[idx:idx + 4000]
    assert "Form(...)" in block or "Form(default=" in block or "instructions: str = Form(" in block, \
        "work_studio_enhance_stream must declare Form() instructions field"
    assert "UploadFile" in block or "File(None)" in block, \
        "work_studio_enhance_stream must accept an UploadFile"


def test_LB3_f_backend_compile_uses_blocking_variant():
    """Task Manager Compile streaming wrap must call the L.b.3
    blocking variant, NOT the 202+job_id `draft_compilation`."""
    src = STREAMING_PY.read_text(encoding="utf-8")
    assert "draft_compilation_blocking" in src, \
        "Compile stream wrap must call draft_compilation_blocking"


def test_LB3_f_backend_blocking_compile_helper_exists():
    src = CYCLE_MGR_PY.read_text(encoding="utf-8")
    assert "async def draft_compilation_blocking" in src, \
        "cycle_manager must export draft_compilation_blocking"


def test_LB3_f_backend_calendar_sync_passes_me_kwarg():
    """Calendar sync inner expects `me=` not `ctx=` — adapter must
    bind correctly."""
    src = STREAMING_PY.read_text(encoding="utf-8")
    idx = src.find("events_calendar_sync_stream")
    assert idx > 0
    block = src[idx:idx + 2000]
    assert "me=" in block, \
        "events_calendar_sync_stream adapter must pass me=ctx['account']"


def test_LB3_f_backend_decks_stream_coerces_to_generate_in():
    """Decks inner expects `body: GenerateIn` not dict."""
    src = STREAMING_PY.read_text(encoding="utf-8")
    idx = src.find("decks_generation_stream")
    assert idx > 0
    block = src[idx:idx + 2000]
    assert "GenerateIn" in block, \
        "decks_generation_stream adapter must coerce body to GenerateIn"


# ─────────────────────────────────────────────────────────────────────
# G. 5 endpoints registered in the router
# ─────────────────────────────────────────────────────────────────────

EXPECTED_ROUTES = [
    "/solva/v2/sessions/{sid}/turn/stream",
    "/contexts/{context_id}/work-studio/enhance/{kind}/stream",
    "/contexts/{context_id}/cycle/draft-compilation/stream",
    "/contexts/{context_id}/events/sync-calendar/stream",
    "/contexts/{context_id}/decks/{outline_id}/generate/stream",
]


@pytest.mark.parametrize("route", EXPECTED_ROUTES)
def test_LB3_g_router_registers_route(route):
    src = STREAMING_PY.read_text(encoding="utf-8")
    assert route in src, f"streaming_v9 must register {route!r}"


# ─────────────────────────────────────────────────────────────────────
# H. Streaming endpoints can be imported + bind to FastAPI cleanly
# ─────────────────────────────────────────────────────────────────────

def test_LB3_h_streaming_router_imports_clean():
    """Importing the router must not raise — catches signature
    mismatches between adapters and inner handlers at boot time."""
    from routers import streaming_v9
    paths = {r.path for r in streaming_v9.router.routes}
    for route in EXPECTED_ROUTES:
        full = "/api" + route
        assert full in paths, f"FastAPI router missing {full!r}"
