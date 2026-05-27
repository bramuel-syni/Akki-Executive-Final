"""Phase R.5.a (2026-05-27) — Cohort console + day-counter enforcement CI lockdown.

Locks the autonomous-mode contract for R.5.a:
  - Funnel stages locked to ("Invited", "Activated", "Engaged", "Attached",
    "Committed"). Stage assignment rules baked into
    `_compute_funnel_stage_for_account`.
  - Day-counter thresholds locked: TRIAL_SOFT_WARNING_DAY=16,
    TRIAL_HARD_LOCK_DAY=22, TRIAL_TOTAL_DAYS=30.
  - 4 status strings: pending, active_trial, soft_warning, expired_hard_lock.
  - Time-window toggle: 7d / 28d / since_trial_start.
  - Admin endpoints: GET /api/admin/cohort/console (table),
    GET /api/admin/cohort/console/stages, GET /api/admin/cohort/console/account/{id}/timeline.
  - Self endpoints: GET /api/me/trial-status, POST /api/me/early-access-opt-in.
  - Frontend: HardLockGuard wraps Gated; EarlyAccessOptIn is the
    only unlocked route while expired_hard_lock; CohortConsole route
    wired at /app/admin/cohort.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from services.cohort.console import (  # noqa: E402
    FUNNEL_STAGES,
    TRIAL_SOFT_WARNING_DAY,
    TRIAL_HARD_LOCK_DAY,
    TRIAL_TOTAL_DAYS,
    _compute_trial_status,
    _resolve_window,
    aggregate_cohort_console,
)


ADMIN_COHORT_PY = REPO / "backend" / "routers" / "admin_cohort.py"
TRIAL_STATUS_PY = REPO / "backend" / "routers" / "trial_status.py"
CONSOLE_JSX     = REPO / "frontend" / "src" / "pages" / "admin" / "CohortConsole.jsx"
EARLY_JSX       = REPO / "frontend" / "src" / "pages" / "EarlyAccessOptIn.jsx"
HOOK_JS         = REPO / "frontend" / "src" / "hooks" / "useTrialStatus.js"
APP_JS          = REPO / "frontend" / "src" / "App.js"


# ─────────────────────────────────────────────────────────────────────
# A. Funnel-stage taxonomy LOCKED
# ─────────────────────────────────────────────────────────────────────

def test_R5a_a_five_funnel_stages_locked():
    assert FUNNEL_STAGES == (
        "Invited", "Activated", "Engaged", "Attached", "Committed",
    ), "R.5.a funnel stages locked at autonomous-queue dispatch"


def test_R5a_a_trial_thresholds_locked():
    assert TRIAL_SOFT_WARNING_DAY == 16
    assert TRIAL_HARD_LOCK_DAY == 22
    assert TRIAL_TOTAL_DAYS == 30


# ─────────────────────────────────────────────────────────────────────
# B. Day-counter computation
# ─────────────────────────────────────────────────────────────────────

def test_R5a_b_compute_trial_status_pending_when_no_start():
    s, d = _compute_trial_status(trial_start_at=None)
    assert s == "pending" and d == 0


def test_R5a_b_compute_trial_status_active_day_1():
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    s, d = _compute_trial_status(trial_start_at=now.isoformat(), now=now)
    assert s == "active_trial" and d == 1


def test_R5a_b_compute_trial_status_active_day_15():
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    start = now - timedelta(days=14, hours=12)  # well into day 15
    s, d = _compute_trial_status(trial_start_at=start.isoformat(), now=now)
    assert s == "active_trial" and d == 15


def test_R5a_b_compute_trial_status_soft_warning_day_16():
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    start = now - timedelta(days=15, hours=12)  # day 16
    s, d = _compute_trial_status(trial_start_at=start.isoformat(), now=now)
    assert s == "soft_warning" and d == 16


def test_R5a_b_compute_trial_status_hard_lock_day_22():
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    start = now - timedelta(days=21, hours=12)  # day 22
    s, d = _compute_trial_status(trial_start_at=start.isoformat(), now=now)
    assert s == "expired_hard_lock" and d == 22


def test_R5a_b_compute_trial_status_hard_lock_day_30_still_locked():
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    start = now - timedelta(days=29, hours=12)
    s, d = _compute_trial_status(trial_start_at=start.isoformat(), now=now)
    assert s == "expired_hard_lock"
    assert d == 30


# ─────────────────────────────────────────────────────────────────────
# C. Time-window resolution
# ─────────────────────────────────────────────────────────────────────

def test_R5a_c_window_7d_returns_7d_floor():
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    floor = _resolve_window(window="7d", trial_start_at=None, now=now)
    assert floor is not None
    floor_dt = datetime.fromisoformat(floor)
    delta_days = (now - floor_dt).total_seconds() / 86400.0
    assert 6.9 < delta_days < 7.1


def test_R5a_c_window_28d_returns_28d_floor():
    now = datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc)
    floor = _resolve_window(window="28d", trial_start_at=None, now=now)
    floor_dt = datetime.fromisoformat(floor)
    delta_days = (now - floor_dt).total_seconds() / 86400.0
    assert 27.9 < delta_days < 28.1


def test_R5a_c_window_since_trial_start_returns_trial_floor():
    floor = _resolve_window(
        window="since_trial_start",
        trial_start_at="2026-05-01T00:00:00+00:00",
    )
    assert floor == "2026-05-01T00:00:00+00:00"


# ─────────────────────────────────────────────────────────────────────
# D. aggregate_cohort_console — shape contract
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_R5a_d_aggregate_returns_locked_shape():
    out = await aggregate_cohort_console(cohort_tag="r5a-shape-test")
    assert set(out.keys()) >= {
        "cohort_tag", "window", "rows", "stage_counts", "totals", "as_of",
    }
    assert set(out["stage_counts"].keys()) == set(FUNNEL_STAGES)
    assert set(out["totals"].keys()) >= {
        "rows", "active_trials", "soft_warnings", "hard_locks",
    }
    assert out["window"] == "since_trial_start"
    assert out["cohort_tag"] == "r5a-shape-test"


# ─────────────────────────────────────────────────────────────────────
# E. admin_cohort + trial_status routers — source-strict wiring
# ─────────────────────────────────────────────────────────────────────

def test_R5a_e_admin_cohort_exposes_console_endpoints():
    src = ADMIN_COHORT_PY.read_text(encoding="utf-8")
    assert '@router.get("/console")' in src
    assert '@router.get("/console/account/{account_id}/timeline")' in src
    assert '@router.get("/console/stages")' in src
    # window query is regex-validated to the 3 locked values
    assert 'regex="^(7d|28d|since_trial_start)$"' in src
    assert "aggregate_cohort_console" in src
    assert "get_account_activity_timeline" in src


def test_R5a_e_trial_status_endpoints_exist():
    src = TRIAL_STATUS_PY.read_text(encoding="utf-8")
    assert '@router.get("/trial-status")' in src
    assert '@router.post("/early-access-opt-in")' in src
    assert '@router.get("/trial-status/by-account/{account_id}")' in src
    # Returns the locked output shape keys
    for key in ("trial_day", "trial_status", "trial_start_at",
                "soft_warning_at_day", "hard_lock_at_day", "locked"):
        assert key in src, f"trial_status endpoint missing key {key!r}"


# ─────────────────────────────────────────────────────────────────────
# F. Frontend hard-lock + console + early-access page
# ─────────────────────────────────────────────────────────────────────

def test_R5a_f_app_js_wires_hard_lock_guard():
    src = APP_JS.read_text(encoding="utf-8")
    assert "useTrialStatus" in src
    assert "HardLockGuard" in src
    assert "/app/early-access-opt-in" in src
    # Hard-lock guard redirects to the opt-in page when locked.
    assert "trial.locked" in src
    assert "<Navigate" in src and "early-access-opt-in" in src


def test_R5a_f_app_js_wires_cohort_console_route():
    src = APP_JS.read_text(encoding="utf-8")
    assert 'path="/app/admin/cohort"' in src
    assert "CohortConsole" in src


def test_R5a_f_cohort_console_page_has_locked_testids():
    src = CONSOLE_JSX.read_text(encoding="utf-8")
    # Static testids
    for tid in (
        "cohort-console-page",
        "cohort-console-table",
        "cohort-console-window-toggle",
        "cohort-console-tag-filter",
        "cohort-console-refresh",
        "cohort-console-drilldown",
        "cohort-console-drilldown-close",
    ):
        assert tid in src, f"CohortConsole must carry testid {tid!r}"
    # Window-toggle dynamic testid pattern
    assert "cohort-console-window-${w.value}" in src, \
        "CohortConsole must use dynamic window-toggle testid pattern"
    # Stage-count cards dynamic testid pattern
    assert "cohort-console-stage-count-${s.toLowerCase()}" in src, \
        "CohortConsole must use dynamic stage-count testid pattern"
    # All 5 stages must appear in the iteration array
    src_iter = src.split("[")[1] if "[" in src else src
    for stage in ("Invited", "Activated", "Engaged", "Attached", "Committed"):
        assert stage in src, f"CohortConsole must iterate the {stage} stage"


def test_R5a_f_early_access_page_has_testids_and_placeholder():
    src = EARLY_JSX.read_text(encoding="utf-8")
    for tid in (
        "early-access-opt-in-page",
        "early-access-opt-in-heading",
        "early-access-opt-in-note",
        "early-access-opt-in-submit",
        "early-access-opt-in-thanks",
    ):
        assert tid in src, f"EarlyAccessOptIn must carry testid {tid!r}"
    # The page is intentionally renderable with [FOUNDER:] placeholders
    # (R.5.b will add the editor). 4 placeholder slots expected (header
    # paragraph + thanks line + sign-off + thanks-body sentence).
    assert src.count("[FOUNDER:") >= 3, \
        "EarlyAccessOptIn must ship with ≥3 [FOUNDER:] founder-fillable copy slots"


def test_R5a_f_use_trial_status_hook_polls_every_60s():
    src = HOOK_JS.read_text(encoding="utf-8")
    assert "/me/trial-status" in src
    assert "setInterval" in src
    assert "60_000" in src or "60000" in src, \
        "hook must poll every 60s so the hard-lock kicks in mid-session"
    # Hook exposes the locked state keys
    for k in ("locked", "day", "totalDays", "softWarningAt", "hardLockAt",
              "cohortTag", "refresh"):
        assert k in src, f"hook must expose `{k}`"


# ─────────────────────────────────────────────────────────────────────
# G. account.signed_up + calendar.sync.linked event constants wired
# ─────────────────────────────────────────────────────────────────────

def test_R5a_g_account_signed_up_wired_at_auth_magic():
    src = (REPO / "backend" / "routers" / "auth_magic.py").read_text(encoding="utf-8")
    assert "ACCOUNT_SIGNED_UP" in src, \
        "auth_magic must emit ACCOUNT_SIGNED_UP on new-account creation"


def test_R5a_g_calendar_sync_linked_wired_at_oauth_google():
    src = (REPO / "backend" / "routers" / "oauth_google.py").read_text(encoding="utf-8")
    assert "CALENDAR_SYNC_LINKED" in src, \
        "oauth_google must emit CALENDAR_SYNC_LINKED on successful sync"
