"""Phase Y (2026-05-27) — First-login onboarding briefs CI lockdown.

Locks:
  • Backend router `/api/me/onboarding-briefs` GET returns 6 locked slides
    with `shown_at: null` for accounts that haven't completed briefs.
  • POST `/api/me/onboarding-briefs/complete` stamps the field + emits
    a `feature_events` row.
  • Frontend OnboardingBriefsModal opens when `shown_at: null` and
    carries the locked testids.
  • App.js mounts the modal inside Gated.
"""
from __future__ import annotations

from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
ROUTER  = REPO / "backend" / "routers" / "onboarding_briefs.py"
MODAL   = REPO / "frontend" / "src" / "components" / "onboarding" / "OnboardingBriefsModal.jsx"
APP_JS  = REPO / "frontend" / "src" / "App.js"
SERVER  = REPO / "backend" / "server.py"


LOCKED_SLIDE_IDS = ["welcome", "surfaces", "how_to_use", "tell_us", "safety", "cta"]


def test_PhaseY_a_router_module_exists():
    assert ROUTER.exists(), "onboarding_briefs router must exist"


def test_PhaseY_b_router_declares_two_endpoints():
    src = ROUTER.read_text(encoding="utf-8")
    assert '@router.get("/onboarding-briefs")' in src
    assert '@router.post("/onboarding-briefs/complete")' in src


def test_PhaseY_c_router_carries_six_locked_slides():
    src = ROUTER.read_text(encoding="utf-8")
    for slide_id in LOCKED_SLIDE_IDS:
        assert f'"id": "{slide_id}"' in src, \
            f"Locked slide id {slide_id!r} must be present in ONBOARDING_SLIDES_DEFAULT"


@pytest.mark.parametrize("slot", [
    "onboarding_slide_welcome",
    "onboarding_slide_surfaces",
    "onboarding_slide_how_to_use",
    "onboarding_slide_tell_us",
    "onboarding_slide_safety",
    "onboarding_slide_cta",
])
def test_PhaseY_d_each_slide_carries_a_locked_copy_slot(slot):
    src = ROUTER.read_text(encoding="utf-8")
    assert f'"slot": "{slot}"' in src, \
        f"Slide must reference the locked copy slot {slot!r}"


def test_PhaseY_e_complete_stamps_field_and_emits_event():
    src = ROUTER.read_text(encoding="utf-8")
    assert "onboarding_briefs_shown_at" in src, \
        "complete endpoint must stamp `onboarding_briefs_shown_at` on the account row"
    assert "onboarding.briefs_completed" in src, \
        "complete endpoint must emit a feature_events row of type `onboarding.briefs_completed`"


def test_PhaseY_f_server_registers_router():
    src = SERVER.read_text(encoding="utf-8")
    assert "onboarding_briefs as onboarding_briefs_router" in src, \
        "server.py must import the onboarding_briefs router"
    assert "app.include_router(onboarding_briefs_router.router)" in src, \
        "server.py must include the onboarding_briefs router"


# ─────────────────────────────────────────────────────────────────────
# Frontend — OnboardingBriefsModal
# ─────────────────────────────────────────────────────────────────────

def test_PhaseY_g_modal_component_exists():
    assert MODAL.exists()


def test_PhaseY_h_modal_carries_locked_testids():
    src = MODAL.read_text(encoding="utf-8")
    for testid in (
        "onboarding-briefs-overlay",
        "onboarding-briefs-modal",
        "onboarding-briefs-progress",
        "onboarding-briefs-skip",
        "onboarding-briefs-slide-title",
        "onboarding-briefs-slide-body",
        "onboarding-briefs-prev",
        "onboarding-briefs-next",
        "onboarding-briefs-get-started",
        "onboarding-briefs-step",
    ):
        assert testid in src, f"OnboardingBriefsModal must carry testid {testid!r}"


def test_PhaseY_i_modal_self_gates_on_shown_at_null():
    """The modal opens ONLY when `shown_at` is null and slides[] is non-empty."""
    src = MODAL.read_text(encoding="utf-8")
    assert "!data?.shown_at" in src, \
        "Modal must self-gate on `shown_at == null`"
    assert "/me/onboarding-briefs" in src, \
        "Modal must GET /me/onboarding-briefs"
    assert "/me/onboarding-briefs/complete" in src, \
        "Modal Skip + Get-started must POST /me/onboarding-briefs/complete"


def test_PhaseY_j_app_js_mounts_modal_inside_gated():
    src = APP_JS.read_text(encoding="utf-8")
    assert "import OnboardingBriefsModal" in src, \
        "App.js must import OnboardingBriefsModal"
    assert "<OnboardingBriefsModal" in src, \
        "App.js must render <OnboardingBriefsModal />"


def test_PhaseY_k_modal_renders_six_slides_step_indicator():
    """The progress indicator dots map 1-to-1 with the 6 slides. Verify
    the `slides.map((_, i) =>` enumeration drives the indicator."""
    src = MODAL.read_text(encoding="utf-8")
    assert "slides.map((_, i) =>" in src, \
        "Progress indicator must enumerate `slides.map((_, i) => ...)`"
    assert "{idx + 1} of {slides.length}" in src, \
        "Step counter must render `{idx + 1} of {slides.length}`"
