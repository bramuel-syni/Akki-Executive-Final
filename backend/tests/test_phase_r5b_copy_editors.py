"""Phase R.5.b (2026-05-27) — Founder copy editors + Day-16 banner CI lockdown.

Locks the autonomous-mode contract for R.5.b (R.5.b.1 scope):
  - 5 founder-fillable slots: welcome_email, feedback_thanks,
    day_16_banner, early_access_opt_in, special_ask.
  - Slot field schemas locked (welcome_email = subject+html+text,
    etc.).
  - Save guard refuses persistence if `[FOUNDER:` literal remains in
    ANY text-bearing field; returns 422 with locked
    `founder_placeholder_present` code + per-field `dirty_fields[]`
    windows.
  - Consumers (welcome_email + feedback_thanks + EarlyAccessOptIn +
    Day16Banner) consult the override row + overlay non-empty fields
    on top of their default templates.
  - Day-16 banner renders ONLY when `trial_status === "soft_warning"`,
    dismissable per-session via sessionStorage.
  - Cohort copy editor page at /app/admin/cohort/copy with one
    `SlotEditor` per slot + per-field local + server validation.

NOT in this dispatch (auto-sliced to R.5.b.2):
  - Special-ask tracker (collection + day-14 trigger + modal)
  - Cohort console drill-down: special-ask status column
  - Cohort console: aggregate per-logo special-ask completion %
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from services.cohort.copy_overrides import (  # noqa: E402
    KNOWN_SLOTS, SLOT_FIELDS,
    overlay_slot, assert_save_clean, slot_field_list,
)


ADMIN_COHORT_PY  = REPO / "backend" / "routers" / "admin_cohort.py"
TRIAL_STATUS_PY  = REPO / "backend" / "routers" / "trial_status.py"
WELCOME_EMAIL_PY = REPO / "backend" / "services" / "cohort" / "welcome_email.py"
FEEDBACK_PY      = REPO / "backend" / "routers" / "feedback.py"
EDITOR_JSX       = REPO / "frontend" / "src" / "pages" / "admin" / "CohortCopyEditor.jsx"
BANNER_JSX       = REPO / "frontend" / "src" / "components" / "cohort" / "Day16Banner.jsx"
EARLY_JSX        = REPO / "frontend" / "src" / "pages" / "EarlyAccessOptIn.jsx"
APP_JS           = REPO / "frontend" / "src" / "App.js"


# ─────────────────────────────────────────────────────────────────────
# A. Slot taxonomy LOCKED
# ─────────────────────────────────────────────────────────────────────

def test_R5b_a_five_locked_slots():
    assert KNOWN_SLOTS == frozenset({
        "welcome_email", "feedback_thanks", "day_16_banner",
        "early_access_opt_in", "special_ask",
    }), "R.5.b locked to exactly 5 founder-fillable slots"


@pytest.mark.parametrize("slot,expected", [
    ("welcome_email",       ["subject", "html", "text"]),
    ("feedback_thanks",     ["subject", "html", "text"]),
    ("day_16_banner",       ["heading", "body"]),
    ("early_access_opt_in", ["heading", "body", "thanks_body", "signoff"]),
    ("special_ask",         ["modal_heading", "modal_body",
                             "email_subject", "email_body"]),
])
def test_R5b_a_slot_field_schemas_locked(slot, expected):
    assert SLOT_FIELDS[slot] == expected


# ─────────────────────────────────────────────────────────────────────
# B. Save guard
# ─────────────────────────────────────────────────────────────────────

def test_R5b_b_assert_save_clean_rejects_founder_placeholder():
    with pytest.raises(HTTPException) as ex:
        assert_save_clean(
            slot="welcome_email",
            fields={
                "subject": "Welcome",
                "html":    "<p>Hi [FOUNDER: edit here] friend</p>",
                "text":    "Hi friend",
            },
        )
    assert ex.value.status_code == 422
    detail = ex.value.detail
    assert detail["code"] == "founder_placeholder_present"
    assert detail["slot"] == "welcome_email"
    assert any(d["field"] == "html" for d in detail["dirty_fields"])


def test_R5b_b_assert_save_clean_accepts_clean_copy():
    """Clean copy must pass (returns None, no exception)."""
    assert_save_clean(
        slot="welcome_email",
        fields={
            "subject": "Welcome to AKKI",
            "html":    "<p>Hi friend, it means a lot.</p>",
            "text":    "Hi friend, it means a lot.",
        },
    )


def test_R5b_b_assert_save_clean_catches_placeholder_in_any_field():
    """Catch in subject OR html OR text equivalently."""
    for field in ("subject", "html", "text"):
        clean = {"subject": "x", "html": "y", "text": "z"}
        clean[field] = f"a [FOUNDER: leak] b"
        with pytest.raises(HTTPException) as ex:
            assert_save_clean(slot="welcome_email", fields=clean)
        assert ex.value.status_code == 422


# ─────────────────────────────────────────────────────────────────────
# C. overlay_slot — preserves defaults, overrides non-empty fields
# ─────────────────────────────────────────────────────────────────────

def test_R5b_c_overlay_preserves_defaults_when_no_override():
    default = {"subject": "Default subject", "html": "default html", "text": "default text"}
    out = overlay_slot(default_payload=default, override_row=None, slot="welcome_email")
    assert out == default


def test_R5b_c_overlay_replaces_only_non_empty_override_fields():
    default = {"subject": "Default", "html": "default html", "text": "default text"}
    override = {"slot": "welcome_email", "subject": "Founder subject", "html": "", "text": None}
    out = overlay_slot(default_payload=default, override_row=override, slot="welcome_email")
    assert out["subject"] == "Founder subject"
    assert out["html"]    == "default html"  # empty override preserved default
    assert out["text"]    == "default text"


def test_R5b_c_overlay_does_not_mutate_default():
    default = {"subject": "Original", "html": "x", "text": "y"}
    override = {"slot": "welcome_email", "subject": "New"}
    overlay_slot(default_payload=default, override_row=override, slot="welcome_email")
    assert default["subject"] == "Original", "overlay must not mutate the default dict"


# ─────────────────────────────────────────────────────────────────────
# D. Endpoint wiring — source-strict
# ─────────────────────────────────────────────────────────────────────

def test_R5b_d_admin_cohort_exposes_copy_editor_endpoints():
    src = ADMIN_COHORT_PY.read_text(encoding="utf-8")
    assert '@router.get("/copy")' in src
    assert '@router.put("/copy/{slot}")' in src
    assert "save_slot_override" in src
    assert "list_all_slots" in src
    assert "unknown_slot" in src
    assert "unknown_field" in src


def test_R5b_d_trial_status_exposes_user_visible_copy():
    """The EarlyAccessOptIn + Day16Banner pages need a read endpoint
    to fetch overrides. Email slots stay superadmin-only."""
    src = TRIAL_STATUS_PY.read_text(encoding="utf-8")
    assert '@router.get("/copy/{slot}")' in src
    assert "_USER_VISIBLE_SLOTS" in src
    assert '"early_access_opt_in"' in src
    assert '"day_16_banner"' in src


def test_R5b_d_admin_cohort_overlays_welcome_email_override():
    src = ADMIN_COHORT_PY.read_text(encoding="utf-8")
    # The issue_invite handler must consult the override BEFORE the guard fires.
    assert 'get_slot_override("welcome_email")' in src
    assert "overlay_slot(" in src


def test_R5b_d_feedback_router_overlays_feedback_thanks():
    src = FEEDBACK_PY.read_text(encoding="utf-8")
    assert 'get_slot_override("feedback_thanks")' in src
    assert "overlay_slot(" in src


# ─────────────────────────────────────────────────────────────────────
# E. Editor page — source-strict
# ─────────────────────────────────────────────────────────────────────

def test_R5b_e_editor_page_has_testids():
    src = EDITOR_JSX.read_text(encoding="utf-8")
    for tid in (
        "cohort-copy-editor-page",
    ):
        assert tid in src, f"editor must carry testid {tid!r}"
    # Per-slot testid pattern
    assert "copy-editor-slot-${slot}" in src
    # Per-field input testid pattern
    assert "copy-editor-field-${slot}-${field}" in src
    # Per-slot save button testid pattern
    assert "copy-editor-save-${slot}" in src
    # Per-field error testid pattern
    assert "copy-editor-error-${slot}-${field}" in src


def test_R5b_e_editor_disables_save_when_placeholder_dirty():
    """Client-side mirror of the server guard — save button must be
    disabled while any field still contains `[FOUNDER:`."""
    src = EDITOR_JSX.read_text(encoding="utf-8")
    assert "containsPlaceholder" in src
    assert "dirtyFields" in src
    assert "disabled={dirtyFields.length > 0" in src or "disabled={dirtyFields.length>0" in src


def test_R5b_e_editor_handles_server_422_dirty_fields():
    """The server returns `dirty_fields[]` on 422 — the editor must
    render those inline so the founder sees exactly where the
    leak is."""
    src = EDITOR_JSX.read_text(encoding="utf-8")
    assert "founder_placeholder_present" in src
    assert "dirty_fields" in src
    assert "serverErrors" in src


def test_R5b_e_app_js_wires_copy_editor_route():
    src = APP_JS.read_text(encoding="utf-8")
    assert "CohortCopyEditor" in src
    assert 'path="/app/admin/cohort/copy"' in src


# ─────────────────────────────────────────────────────────────────────
# F. Day-16 banner
# ─────────────────────────────────────────────────────────────────────

def test_R5b_f_banner_renders_only_when_soft_warning():
    src = BANNER_JSX.read_text(encoding="utf-8")
    assert 'trial.status !== "soft_warning"' in src, \
        "Banner must early-return when trial.status != soft_warning"
    # Banner is dismissable but stored per-session (not localStorage)
    # so the banner re-appears on next browser-session.
    assert "sessionStorage" in src
    assert "STORAGE_KEY" in src


def test_R5b_f_banner_consumes_override_copy():
    src = BANNER_JSX.read_text(encoding="utf-8")
    assert "/me/copy/day_16_banner" in src
    # Default ships with [FOUNDER: ...] placeholders until the editor
    # writes a clean override.
    assert "[FOUNDER:" in src


def test_R5b_f_banner_has_required_testids():
    src = BANNER_JSX.read_text(encoding="utf-8")
    for tid in (
        "day-16-banner",
        "day-16-banner-heading",
        "day-16-banner-body",
        "day-16-banner-cta",
        "day-16-banner-dismiss",
    ):
        assert tid in src, f"Day-16 banner must carry testid {tid!r}"


def test_R5b_f_banner_wired_into_gated_above_children():
    """The banner must render at the top of every Gated route,
    BEFORE children so it sits at the top of the page."""
    src = APP_JS.read_text(encoding="utf-8")
    assert "Day16Banner" in src
    assert "<Day16Banner />" in src
    # Must be placed inside Gated, BEFORE {children} —
    # take a 1500-char window starting from the Gated definition.
    g = src.find("function Gated")
    gated_body = src[g:g + 1500]
    banner_pos = gated_body.find("Day16Banner />")
    children_pos = gated_body.find("{children}")
    assert banner_pos > 0
    assert children_pos > 0
    assert banner_pos < children_pos, \
        "Day16Banner must render BEFORE {children} inside Gated"


# ─────────────────────────────────────────────────────────────────────
# G. EarlyAccessOptIn consumes the override
# ─────────────────────────────────────────────────────────────────────

def test_R5b_g_early_access_consumes_override():
    src = EARLY_JSX.read_text(encoding="utf-8")
    assert "/me/copy/early_access_opt_in" in src
    # Defaults still ship with [FOUNDER:] placeholders until the founder
    # saves clean copy (so locked users see *something* before R.5.b
    # editor has been used).
    assert "[FOUNDER:" in src
    # Heading + body + thanks_body + signoff must all be data-driven now.
    for field in ("heading", "body", "thanks_body", "signoff"):
        assert f"copy.{field}" in src, f"early-access page must render {{copy.{field}}}"
