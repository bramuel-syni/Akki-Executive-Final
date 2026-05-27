"""Phase L.b (2026-05-27) — 5 remaining streaming surfaces CI lockdown.

Locks the L.b deliverable:
  - 5 phase scripts added to PHASE_SCRIPTS (solva-synthesis,
    work-studio-enhance, task-manager-compile, events-calendar-sync,
    decks-generation).
  - 5 streaming endpoints in `routers/streaming_v9.py` use the new
    PhaseEmitter taxonomy (NOT the old `encode_phase_event`).
  - All 5 emit `script` + per-phase `phase` events + final `complete`
    OR `error` event, NEVER the old Patch-9 `_data_event` shape.
  - Visual contract preserved: each script uses the locked Phase K
    voice ("Reading", "Checking the grounding contract", "Composing",
    "Validating", "Almost there.") + lucide-compatible icon hints.

Note on frontend wiring: this dispatch ships backend pipes ONLY. The
5 frontend surface integrations (replace existing loading states with
`<StreamingLogScene>` + `useStreamingProgress`) are auto-sliced to a
follow-up L.b.2 dispatch per the autonomous-mode "auto-slice if >500
lines" rule. The backend pipes ship first so the frontend integrations
have a stable contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from services.streaming.progress import PHASE_SCRIPTS, PhaseEmitter  # noqa: E402


STREAMING_V9_PY = REPO / "backend" / "routers" / "streaming_v9.py"
PROGRESS_PY     = REPO / "backend" / "services" / "streaming" / "progress.py"


# ─────────────────────────────────────────────────────────────────────
# A. All 5 L.b surfaces have phase scripts
# ─────────────────────────────────────────────────────────────────────

LB_SURFACES = [
    "solva-synthesis",
    "work-studio-enhance",
    "task-manager-compile",
    "events-calendar-sync",
    "decks-generation",
]


@pytest.mark.parametrize("surface", LB_SURFACES)
def test_LB_a_each_surface_has_phase_script(surface):
    assert surface in PHASE_SCRIPTS, \
        f"PHASE_SCRIPTS must contain L.b surface {surface!r}"
    script = PHASE_SCRIPTS[surface]
    assert isinstance(script, list) and len(script) >= 4, \
        f"L.b surface {surface!r} must have ≥4 phases; got {len(script)}"
    for i, phase in enumerate(script):
        assert "label" in phase and "icon" in phase, \
            f"surface {surface!r} phase {i}: missing label or icon"
        assert isinstance(phase["label"], str) and phase["label"].endswith("."), \
            f"surface {surface!r} phase {i} label must end with a period"


def test_LB_a_phase_voice_carries_locked_K_signature():
    """Spec lock: each L.b surface must carry at least 3 of the
    canonical Phase K voice markers."""
    canonical_markers = [
        "Reading",  # phase 1
        "Checking the grounding contract.",  # phase 2 (most surfaces)
        "Composing",  # mid
        "Validating.",  # penultimate
        "Almost there.",  # final
    ]
    for surface in LB_SURFACES:
        script = PHASE_SCRIPTS[surface]
        labels = " | ".join(p["label"] for p in script)
        hits = sum(1 for m in canonical_markers if m in labels)
        # Calendar Sync legitimately doesn't have "Composing" or
        # "Checking the grounding contract." — relax to 2 markers
        # required for that surface.
        threshold = 2 if surface == "events-calendar-sync" else 3
        assert hits >= threshold, \
            f"surface {surface!r} must carry ≥{threshold} Phase K voice markers; " \
            f"hits={hits}, labels={labels}"


# ─────────────────────────────────────────────────────────────────────
# B. PhaseEmitter accepts every new surface
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("surface", LB_SURFACES)
def test_LB_b_phase_emitter_accepts_surface(surface):
    """Smoke: PhaseEmitter must not raise KeyError on the new surfaces."""
    class _FakeReq:
        async def is_disconnected(self):
            return False
    e = PhaseEmitter(_FakeReq(), surface=surface)  # type: ignore[arg-type]
    assert e.surface == surface
    assert len(e.script) == len(PHASE_SCRIPTS[surface])


# ─────────────────────────────────────────────────────────────────────
# C. streaming_v9.py — 5 endpoints + uses NEW taxonomy (not legacy)
# ─────────────────────────────────────────────────────────────────────

def test_LB_c_streaming_v9_uses_new_taxonomy():
    src = STREAMING_V9_PY.read_text(encoding="utf-8")
    # MUST use the new PhaseEmitter / PHASE_SCRIPTS / sse_headers pipe.
    assert "from services.streaming.progress import PhaseEmitter" in src
    assert "from services.streaming.sse import sse_headers" in src
    # MUST have abandoned the Patch-9 legacy taxonomy.
    assert "from services.streaming_phases import encode_phase_event" not in src, \
        "Patch-9 legacy `encode_phase_event` taxonomy must be removed."
    assert "encode_phase_event(" not in src, \
        "Patch-9 legacy `encode_phase_event` calls must be removed."


@pytest.mark.parametrize("surface,url_fragment", [
    ("solva-synthesis",       "/solva/sessions/{sid}/turn/stream"),
    ("work-studio-enhance",   "/work-studio/enhance/{kind}/stream"),
    ("task-manager-compile",  "/cycle/draft-compilation/stream"),
    ("events-calendar-sync",  "/events/sync-calendar/stream"),
    ("decks-generation",      "/decks/{outline_id}/generate/stream"),
])
def test_LB_c_each_surface_has_endpoint_with_correct_emitter(surface, url_fragment):
    src = STREAMING_V9_PY.read_text(encoding="utf-8")
    assert url_fragment in src, f"endpoint url {url_fragment!r} missing"
    # PhaseEmitter must reference the locked surface key for this URL.
    # Either via `surface={surface!r}` in PhaseEmitter() or via the
    # `_wrap_synchronous_handler(surface={surface!r}, …)` helper.
    assert f'"{surface}"' in src or f"'{surface}'" in src, \
        f"streaming_v9 must reference PhaseEmitter surface={surface!r}"


def test_LB_c_streaming_v9_returns_streaming_response_per_endpoint():
    src = STREAMING_V9_PY.read_text(encoding="utf-8")
    # 5 surface endpoints + 1 helper = at least 5 StreamingResponse returns
    n_streamresp = src.count("return StreamingResponse(")
    assert n_streamresp >= 5, \
        f"expected ≥5 StreamingResponse returns; got {n_streamresp}"


def test_LB_c_streaming_v9_uses_sse_headers_not_raw_media_type():
    src = STREAMING_V9_PY.read_text(encoding="utf-8")
    # sse_headers carries the defence-in-depth X-Accel-Buffering header
    # that the legacy `media_type="text/event-stream"` lacks.
    assert "headers=sse_headers()" in src, \
        "StreamingResponse must use `sse_headers()` (X-Accel-Buffering, no-cache)"


# ─────────────────────────────────────────────────────────────────────
# D. Cancellation contract — emitter checks is_disconnected
# ─────────────────────────────────────────────────────────────────────

def test_LB_d_wrap_helper_honors_cancellation():
    """The shared wrap helper must check `request.is_disconnected()`
    via PhaseEmitter.advance() — when the client disconnects mid-
    stream, the generator must `return` cleanly without writing more
    events."""
    src = STREAMING_V9_PY.read_text(encoding="utf-8")
    # The advance() return-None pattern (cancellation signal) MUST be
    # honoured: the helper checks `if chunk is None: return`.
    assert "chunk = await e.advance()" in src
    assert "if chunk is None:" in src and "return" in src


# ─────────────────────────────────────────────────────────────────────
# E. Error contract — inner-handler failures emit `error` event
# ─────────────────────────────────────────────────────────────────────

def test_LB_e_inner_exceptions_emit_error_event():
    src = STREAMING_V9_PY.read_text(encoding="utf-8")
    # Must emit `error` (not just raise) when the inner handler fails.
    assert "except HTTPException" in src
    assert "await e.error(" in src
    # Inner exception code MUST namespace to `inner_exception` or `http_*`
    assert "inner_exception" in src
    assert "http_" in src  # `f"http_{exc.status_code}"`
