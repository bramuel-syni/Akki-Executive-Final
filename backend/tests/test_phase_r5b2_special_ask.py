"""Phase R.5.b.2 (2026-05-27) — Special-ask tracker + cohort console additions CI lockdown.

Locks the autonomous-mode contract:
  - Day-14 trigger creates a row exactly once per account (on-read).
  - Status taxonomy locked: pending → partial → complete (referral
    name + email both filled).
  - Modal renders ONLY when `trial_status.special_ask_surface === true`.
  - Server returns `special_ask_surface` flag inline on
    `/api/me/trial-status` so the frontend never makes a 2nd RTT.
  - Cohort console drill-down endpoint carries the `special_ask` row
    alongside the timeline.
  - Aggregate endpoint `/console/special-asks?cohort_tag=…` returns
    the locked output shape.
  - `feature_events` constants: special_ask.surfaced, .submitted, .dismissed.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from services.cohort.special_ask import (  # noqa: E402
    SPECIAL_ASK_TRIGGER_DAY,
    compute_status,
    get_or_mint_special_ask,
    get_special_ask,
    save_special_ask,
    aggregate_cohort_special_asks,
)


TRIAL_STATUS_PY  = REPO / "backend" / "routers" / "trial_status.py"
ADMIN_COHORT_PY  = REPO / "backend" / "routers" / "admin_cohort.py"
MODAL_JSX        = REPO / "frontend" / "src" / "components" / "cohort" / "SpecialAskModal.jsx"
HOOK_JS          = REPO / "frontend" / "src" / "hooks" / "useTrialStatus.js"
APP_JS           = REPO / "frontend" / "src" / "App.js"
CONSOLE_JSX      = REPO / "frontend" / "src" / "pages" / "admin" / "CohortConsole.jsx"


# ─────────────────────────────────────────────────────────────────────
# A. Locked threshold + status taxonomy
# ─────────────────────────────────────────────────────────────────────

def test_R5b2_a_trigger_day_locked():
    assert SPECIAL_ASK_TRIGGER_DAY == 14


def test_R5b2_a_status_pending_when_no_fields():
    assert compute_status(
        referral_name=None, referral_email=None,
        case_study_consent=None, testimonial_text=None,
    ) == "pending"


def test_R5b2_a_status_complete_only_when_both_referrals():
    assert compute_status(
        referral_name="Jane", referral_email="jane@example.com",
        case_study_consent=None, testimonial_text=None,
    ) == "complete"


def test_R5b2_a_status_partial_when_referral_missing_email():
    assert compute_status(
        referral_name="Jane", referral_email=None,
        case_study_consent=True, testimonial_text=None,
    ) == "partial"


def test_R5b2_a_status_partial_when_only_testimonial():
    assert compute_status(
        referral_name=None, referral_email=None,
        case_study_consent=None, testimonial_text="Saved my Tuesday.",
    ) == "partial"


def test_R5b2_a_status_partial_when_only_consent():
    assert compute_status(
        referral_name=None, referral_email=None,
        case_study_consent=True, testimonial_text=None,
    ) == "partial"


# ─────────────────────────────────────────────────────────────────────
# B. Day-14 trigger — mint exactly once, no-op below 14
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_R5b2_b_trigger_no_mint_below_day_14():
    """Day 13 must NOT mint a row."""
    from core import db
    acct = "r5b2-trigger-test-1"
    await db.cohort_special_asks.delete_many({"account_id": acct})
    out = await get_or_mint_special_ask(
        account_id=acct, cohort_tag="r5b2-test", trial_day=13,
    )
    assert out is None
    rows = await db.cohort_special_asks.find(
        {"account_id": acct}, {"_id": 0},
    ).to_list(length=2)
    assert rows == []


@pytest.mark.asyncio
async def test_R5b2_b_trigger_mints_on_day_14():
    from core import db
    acct = "r5b2-trigger-test-2"
    await db.cohort_special_asks.delete_many({"account_id": acct})
    out = await get_or_mint_special_ask(
        account_id=acct, cohort_tag="r5b2-test", trial_day=14,
    )
    assert out is not None
    assert out["status"] == "pending"
    assert out["account_id"] == acct
    assert out["cohort_tag"] == "r5b2-test"
    await db.cohort_special_asks.delete_many({"account_id": acct})


@pytest.mark.asyncio
async def test_R5b2_b_trigger_idempotent_no_duplicate_mint():
    """Second call on day 15 must return the same row, not mint a new one."""
    from core import db
    acct = "r5b2-trigger-test-3"
    await db.cohort_special_asks.delete_many({"account_id": acct})
    r1 = await get_or_mint_special_ask(
        account_id=acct, cohort_tag="r5b2-test", trial_day=14,
    )
    r2 = await get_or_mint_special_ask(
        account_id=acct, cohort_tag="r5b2-test", trial_day=15,
    )
    assert r1["id"] == r2["id"], "Re-trigger must return the same row"
    n = await db.cohort_special_asks.count_documents({"account_id": acct})
    assert n == 1
    await db.cohort_special_asks.delete_many({"account_id": acct})


# ─────────────────────────────────────────────────────────────────────
# C. save_special_ask — status flips correctly + persists
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_R5b2_c_save_partial_then_complete():
    from core import db
    acct = "r5b2-save-test-1"
    await db.cohort_special_asks.delete_many({"account_id": acct})
    # Day-14 trigger first
    await get_or_mint_special_ask(account_id=acct, cohort_tag="x", trial_day=14)
    # Partial save (just name)
    row1 = await save_special_ask(
        account_id=acct, referral_name="Jane", referral_email=None,
        case_study_consent=None, testimonial_text=None,
    )
    assert row1["status"] == "partial"
    assert row1["referral_name"] == "Jane"
    assert row1["captured_at"] is not None
    # Complete save (add email)
    row2 = await save_special_ask(
        account_id=acct, referral_name="Jane", referral_email="jane@example.com",
        case_study_consent=True, testimonial_text="It works.",
    )
    assert row2["status"] == "complete"
    assert row2["referral_email"] == "jane@example.com"
    assert row2["case_study_consent"] is True
    await db.cohort_special_asks.delete_many({"account_id": acct})


# ─────────────────────────────────────────────────────────────────────
# D. aggregate_cohort_special_asks — locked output shape
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_R5b2_d_aggregate_locked_shape():
    out = await aggregate_cohort_special_asks(cohort_tag="r5b2-agg-empty")
    assert set(out.keys()) >= {
        "cohort_tag", "total_invitees", "total_asks",
        "status_counts", "complete_pct",
    }
    assert set(out["status_counts"].keys()) == {"pending", "partial", "complete"}


# ─────────────────────────────────────────────────────────────────────
# E. trial_status endpoint — surface flag + endpoint wiring
# ─────────────────────────────────────────────────────────────────────

def test_R5b2_e_trial_status_carries_special_ask_surface_flag():
    src = TRIAL_STATUS_PY.read_text(encoding="utf-8")
    assert "special_ask_surface" in src, \
        "/api/me/trial-status must surface the day-14 trigger flag"
    assert "special_ask_at_day" in src
    assert "get_or_mint_special_ask" in src


def test_R5b2_e_special_ask_endpoints_wired():
    src = TRIAL_STATUS_PY.read_text(encoding="utf-8")
    assert '@router.get("/special-ask")' in src
    assert '@router.post("/special-ask")' in src
    assert '@router.post("/special-ask/dismiss")' in src
    assert '@router.post("/special-ask/surface-ack")' in src


def test_R5b2_e_event_constants_added():
    src = TRIAL_STATUS_PY.read_text(encoding="utf-8")
    for ev in ('"special_ask.surfaced"', '"special_ask.submitted"',
               '"special_ask.dismissed"'):
        assert ev in src, f"event constant {ev} missing"


# ─────────────────────────────────────────────────────────────────────
# F. Cohort console additions
# ─────────────────────────────────────────────────────────────────────

def test_R5b2_f_drilldown_carries_special_ask_row():
    src = ADMIN_COHORT_PY.read_text(encoding="utf-8")
    # Drilldown endpoint returns `special_ask` alongside timeline.
    assert "special_ask" in src
    assert "get_special_ask(" in src


def test_R5b2_f_aggregate_endpoint_exists():
    src = ADMIN_COHORT_PY.read_text(encoding="utf-8")
    assert '@router.get("/console/special-asks")' in src
    assert "aggregate_cohort_special_asks" in src


# ─────────────────────────────────────────────────────────────────────
# G. Frontend — modal + hook + console
# ─────────────────────────────────────────────────────────────────────

def test_R5b2_g_modal_renders_only_when_surface_flag_true():
    src = MODAL_JSX.read_text(encoding="utf-8")
    assert "specialAskSurface" in src, \
        "modal must consume the hook's specialAskSurface flag"
    assert "if (!open) return null" in src


def test_R5b2_g_modal_has_required_testids():
    src = MODAL_JSX.read_text(encoding="utf-8")
    for tid in (
        "special-ask-modal-overlay",
        "special-ask-modal",
        "special-ask-modal-close",
        "special-ask-modal-body",
        "special-ask-referral-name",
        "special-ask-referral-email",
        "special-ask-case-study-consent",
        "special-ask-testimonial",
        "special-ask-submit",
        "special-ask-remind-later",
    ):
        assert tid in src, f"modal must carry testid {tid!r}"


def test_R5b2_g_modal_submit_disabled_without_referral():
    """The Save button must be disabled until BOTH referral_name AND
    referral_email are filled."""
    src = MODAL_JSX.read_text(encoding="utf-8")
    assert "canSave = refName.trim().length > 0 && refEmail.trim().length > 0" in src
    assert "disabled={!canSave" in src


def test_R5b2_g_modal_remind_later_emits_dismiss():
    """Clicking 'Remind me later' must POST /me/special-ask/dismiss."""
    src = MODAL_JSX.read_text(encoding="utf-8")
    assert '/me/special-ask/dismiss' in src
    # Session-storage dismiss persistence so the modal doesn't immediately
    # re-open in the same browser session
    assert "SESSION_DISMISS_KEY" in src
    assert "sessionStorage" in src


def test_R5b2_g_hook_exposes_special_ask_surface():
    src = HOOK_JS.read_text(encoding="utf-8")
    assert "specialAskSurface" in src
    assert "special_ask_surface" in src  # backend field name


def test_R5b2_g_modal_wired_into_gated():
    src = APP_JS.read_text(encoding="utf-8")
    assert "SpecialAskModal" in src
    assert "<SpecialAskModal" in src


def test_R5b2_g_cohort_console_renders_special_ask_aggregate():
    src = CONSOLE_JSX.read_text(encoding="utf-8")
    for tid in (
        "cohort-console-special-ask-aggregate",
        "cohort-console-sa-completed",
        "cohort-console-sa-invited",
        "cohort-console-sa-progress-bar",
        "cohort-console-referral-filters",
    ):
        assert tid in src, f"cohort console must carry testid {tid!r}"
    # Filter chips use a dynamic testid template
    assert 'cohort-console-referral-filter-${f.value || "all"}' in src
    # All 4 chip values must appear in the chips array
    for v in ('null', '"has_referral"', '"missing_referral"', '"pending_ask"'):
        assert f"value: {v}," in src, f"console must declare chip value={v}"


def test_R5b2_g_cohort_console_drilldown_shows_special_ask_status():
    src = CONSOLE_JSX.read_text(encoding="utf-8")
    # Status badge testid
    assert "cohort-console-drilldown-special-ask" in src
    # And the not-asked-yet fallback testid
    assert "cohort-console-drilldown-special-ask-none" in src
