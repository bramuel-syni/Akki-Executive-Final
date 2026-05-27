"""Phase L.a (2026-05-27) — Streaming Loader Architecture CI lockdown.

Per `/app/memory/sprints/PHASE_L_VISUAL_REFERENCE.md` (LOCKED visual spec).

This file locks the architecture invariants:
  A. Backend SSE pipe primitives exist + export the expected names.
  B. Phase scripts for the 2 L.a surfaces are present + non-empty.
  C. Solva Frame Audit endpoint accepts `?stream=1` query param.
  D. Work Studio Compile observer endpoint exists + reads phase_index.
  E. `_run_export` worker writes phase_index markers at 7 boundaries.
  F. Frontend `useStreamingProgress` uses fetch-SSE (not EventSource).
  G. Frontend `StreamingLogScene` honours the Claude-reference visual
     contract (sans-serif, NO monospace/terminal/progress-bar classes,
     `prefers-reduced-motion` query in index.css).
  H. The 2 surface UIs (FrameAuditScreen, ExportModal) import the
     hook + scene + open against the correct endpoints.
  I. `PHASE_L_VISUAL_REFERENCE.md` exists + carries the locked spec.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO / "backend"
FRONTEND = REPO / "frontend" / "src"

SSE_PY = BACKEND / "services" / "streaming" / "sse.py"
PROGRESS_PY = BACKEND / "services" / "streaming" / "progress.py"
WORK_STUDIO_EXPORT_PY = BACKEND / "routers" / "work_studio_export.py"
SOLVA_V2_PY = BACKEND / "routers" / "solva_v2.py"

HOOK_JS = FRONTEND / "hooks" / "useStreamingProgress.js"
SCENE_JSX = FRONTEND / "components" / "transitions" / "StreamingLogScene.jsx"
INDEX_CSS = FRONTEND / "index.css"
FRAME_AUDIT_JSX = FRONTEND / "components" / "solva" / "flow" / "FrameAuditScreen.jsx"
EXPORT_MODAL_JSX = FRONTEND / "components" / "studio" / "ExportModal.jsx"
VISUAL_REF_MD = REPO / "memory" / "sprints" / "PHASE_L_VISUAL_REFERENCE.md"


# =========================================================================
# A. Backend SSE primitives
# =========================================================================

def test_LA_a_sse_module_exports_helpers():
    src = SSE_PY.read_text(encoding="utf-8")
    assert "def sse_headers" in src
    assert "def encode_event" in src
    assert "class SSEStream" in src
    # Defence-in-depth headers for ingress that turn buffering on.
    assert "X-Accel-Buffering" in src
    assert "no-cache" in src.lower()


def test_LA_a_progress_module_exports_phase_emitter():
    src = PROGRESS_PY.read_text(encoding="utf-8")
    assert "class PhaseEmitter" in src
    assert "PHASE_SCRIPTS" in src
    assert "def script_event" in src
    assert "async def advance" in src
    assert "async def complete" in src
    assert "async def error" in src


# =========================================================================
# B. Phase scripts for the 2 L.a surfaces
# =========================================================================

def test_LA_b_phase_scripts_contain_both_la_surfaces():
    src = PROGRESS_PY.read_text(encoding="utf-8")
    assert '"solva-frame-audit"' in src, "Solva Frame Audit phase script missing"
    assert '"work-studio-compile"' in src, "Work Studio Compile phase script missing"


def test_LA_b_phase_scripts_use_phase_K_voice():
    """Spec: phase labels carry the Phase K voice ('Reading your X',
    'Checking the grounding contract', 'Composing', 'Validating',
    'Almost there')."""
    src = PROGRESS_PY.read_text(encoding="utf-8")
    # Common voice markers across L.a surfaces
    assert "Checking the grounding contract" in src
    assert "Composing" in src
    assert "Validating" in src


# =========================================================================
# C. Solva Frame Audit endpoint streaming branch
# =========================================================================

def test_LA_c_solva_frame_audit_accepts_stream_query():
    src = SOLVA_V2_PY.read_text(encoding="utf-8")
    # The endpoint declares `stream: int = Query(default=0)` on the
    # frame-audit POST.
    assert re.search(r"async def run_frame_audit\([\s\S]*?stream: int = Query", src), \
        "frame-audit POST must accept `stream` query param"
    # The endpoint must instantiate PhaseEmitter with the locked surface.
    assert 'PhaseEmitter(request, surface="solva-frame-audit")' in src
    # Returns StreamingResponse with sse_headers().
    assert "StreamingResponse" in src
    assert "sse_headers()" in src


# =========================================================================
# D. Work Studio Compile observer endpoint + phase instrumentation
# =========================================================================

def test_LA_d_work_studio_compile_stream_endpoint_exists():
    src = WORK_STUDIO_EXPORT_PY.read_text(encoding="utf-8")
    # New observer endpoint
    assert re.search(
        r'@router\.get\(\s*"/contexts/\{context_id\}/work-studio/exports/\{export_id\}/stream"',
        src,
    ), "stream observer endpoint missing"
    # Reads phase_index marker
    assert "phase_index" in src
    # Uses PhaseEmitter with locked surface
    assert 'PhaseEmitter(request, surface="work-studio-compile")' in src


def test_LA_e_run_export_writes_seven_phase_markers():
    """The background worker must stamp phase_index at every L.a phase
    boundary. The streaming observer translates these into SSE events."""
    src = WORK_STUDIO_EXPORT_PY.read_text(encoding="utf-8")
    assert "async def _set_export_phase" in src, "phase-marker helper missing"
    # All 7 phase indexes must be written
    expected_phase_calls = [
        (0, "Reading the cycle inputs."),
        (1, "Checking the grounding contract."),
        (2, "Drafting the outline."),
        (3, "Composing."),
        (4, "Rendering the artefact."),
        (5, "Validating."),
        (6, "Almost there."),
    ]
    for idx, label in expected_phase_calls:
        assert f"_set_export_phase(export_id, {idx}," in src, \
            f"_run_export must call _set_export_phase with phase_index={idx} ({label!r})"
        assert label in src, f"phase label {label!r} missing"


# =========================================================================
# F. Frontend hook uses fetch-SSE (not EventSource)
# =========================================================================

def test_LA_f_hook_uses_fetch_not_eventsource():
    """Phase L.a decision: useStreamingProgress switched from
    EventSource → fetch because EventSource is GET-only and Solva
    frame-audit is POST. CI guard ensures we don't slip back."""
    src = HOOK_JS.read_text(encoding="utf-8")
    assert "new EventSource(" not in src, \
        "Phase L.a hook must use fetch (not EventSource)"
    assert "ReadableStream" in src or ".getReader(" in src, \
        "Phase L.a hook must read fetch response body as a stream"
    # The 4 Phase L event types must be parsed
    for ev in ("script", "phase", "complete", "error"):
        assert f'"{ev}"' in src, f"hook must handle SSE event type {ev!r}"


def test_LA_f_hook_state_shape():
    src = HOOK_JS.read_text(encoding="utf-8")
    for key in ("phases", "activeIndex", "completedIndexes", "status", "result", "error"):
        assert key in src, f"hook state must expose `{key}`"
    for status_val in ("idle", "connecting", "streaming", "complete", "error", "cancelled"):
        assert f'"{status_val}"' in src, f"hook status must include `{status_val}`"


# =========================================================================
# G. Frontend visual contract — Claude reference, NOT terminal
# =========================================================================

def test_LA_g_scene_uses_lucide_not_monospace():
    """Phase L visual lock: lucide-react icons, sans-serif. NO
    monospace, NO 'terminal'/'console' class names, NO progress bars."""
    src = SCENE_JSX.read_text(encoding="utf-8")
    assert 'from "lucide-react"' in src, "must use lucide-react icons"
    # Forbidden visual signatures (monospace / terminal / progress-bar)
    forbidden = ["font-mono", "terminal", "console-log", "<progress", "progressbar",
                 "typewriter", "single-line-fade"]
    for f in forbidden:
        assert f.lower() not in src.lower(), \
            f"Phase L visual lock — forbidden token {f!r} present in StreamingLogScene"


def test_LA_g_scene_renders_progressive_reveal_with_checkmark():
    src = SCENE_JSX.read_text(encoding="utf-8")
    # PhaseLine status handling
    assert "completed" in src
    assert "active" in src
    # CheckSquare = the locked completion icon
    assert "CheckSquare" in src
    # NO upcoming phases shown
    assert "visibleIndexes" in src, \
        "scene must render only completed + active phases (no upcoming)"


def test_LA_g_index_css_carries_streaming_log_animations():
    css = INDEX_CSS.read_text(encoding="utf-8")
    assert "akki-streaming-log-fade" in css, \
        "Phase L 200ms fade-in keyframe missing"
    assert "akki-streaming-log-pulse" in css, \
        "Phase L active-pulse keyframe missing"
    # Reduced-motion compliance
    assert "prefers-reduced-motion" in css, \
        "Phase L must respect prefers-reduced-motion"
    # Reduced-motion block must reference the streaming-log animations
    rm_block_idx = css.find("prefers-reduced-motion")
    rm_block = css[rm_block_idx:rm_block_idx + 400]
    assert ".streaming-log-line" in rm_block or "akki-streaming-log" in rm_block, \
        "prefers-reduced-motion block must disable streaming-log animations"


# =========================================================================
# H. The 2 surface UIs are wired
# =========================================================================

def test_LA_h_frame_audit_screen_wires_streaming_log_scene():
    src = FRAME_AUDIT_JSX.read_text(encoding="utf-8")
    assert "useStreamingProgress" in src
    assert "StreamingLogScene" in src
    # Must hit the streaming endpoint, not the legacy POST
    assert "frame-audit?stream=1" in src, \
        "FrameAuditScreen must use ?stream=1 query param on the POST"
    # The locked Phase L surface id
    assert "streaming-log-solva-frame-audit" in src
    # Legacy ContextLoadingScene must NOT be present (would short-circuit
    # the streaming UX with a synthetic timer)
    assert "ContextLoadingScene" not in src, \
        "Legacy ContextLoadingScene must be removed from FrameAuditScreen"


def test_LA_h_export_modal_wires_streaming_log_scene():
    src = EXPORT_MODAL_JSX.read_text(encoding="utf-8")
    assert "useStreamingProgress" in src
    assert "StreamingLogScene" in src
    # Must open the observer stream endpoint
    assert "work-studio/exports/${data.export_id}/stream" in src, \
        "ExportModal must open the observer stream endpoint on submit"
    # The locked Phase L surface id
    assert "streaming-log-work-studio-compile" in src
    # Legacy generic running-spinner copy must be gone
    assert "About 30\u201360 seconds. Pass 1 reasoning" not in src, \
        "Legacy generic running copy must be replaced by the streaming log"


# =========================================================================
# I. Visual reference doc is the source of truth
# =========================================================================

def test_LA_i_visual_reference_doc_exists_and_carries_lock():
    md = VISUAL_REF_MD.read_text(encoding="utf-8")
    assert "LOCKED" in md, "Visual reference must declare itself LOCKED"
    # Key spec terms
    for term in ("multi-line", "progressive reveal", "sans-serif", "muted",
                 "checkmark", "reduced motion", "subtle"):
        assert term.lower() in md.lower(), \
            f"Phase L visual reference must mention {term!r}"
    # Surface table linkage
    assert "PHASE_SCRIPTS" in md
    assert "StreamingLogScene" in md
    assert "useStreamingProgress" in md
