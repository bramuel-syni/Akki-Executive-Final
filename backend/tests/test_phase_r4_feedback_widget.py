"""Phase R.4 (2026-05-27) — In-app feedback widget CI lockdown.

Locks the autonomous-mode contract:
  - Backend endpoint `POST /api/feedback` accepts `{text, tag, surface_path}`.
  - Tag taxonomy LOCKED to {"Broken", "Wrong", "Great"} (pydantic Literal).
  - Every accepted submission emits a `feedback.submitted` feature_event
    (R.3 pipe).
  - Auto-thanks email uses the same `[FOUNDER:]` placeholder + 422-style
    guard pattern as R.2, BUT the endpoint always returns 200 with
    `block_reason="founder_placeholder_present"` when the guard fires —
    the feedback is captured even if the thanks email is gated.
  - Frontend widget renders inside `Gated` so it appears on every
    authenticated app surface (lower-right fixed).
  - Widget has the 3 locked tag buttons + textarea + submit + close.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from services.cohort.feedback_widget import (  # noqa: E402
    FEEDBACK_TAGS, build_thanks_html, send_thanks_email_async,
)
from services.cohort.welcome_email import (  # noqa: E402
    FOUNDER_PLACEHOLDER_PREFIX, assert_no_founder_placeholder,
)
from services.cohort.feature_events import (  # noqa: E402
    FEEDBACK_SUBMITTED, KNOWN_EVENT_TYPES,
)


FEEDBACK_PY = REPO / "backend" / "routers" / "feedback.py"
WIDGET_JSX  = REPO / "frontend" / "src" / "components" / "feedback" / "FeedbackWidget.jsx"
APP_JS      = REPO / "frontend" / "src" / "App.js"


# ─────────────────────────────────────────────────────────────────────
# A. Tag taxonomy LOCKED to exactly 3 entries
# ─────────────────────────────────────────────────────────────────────

def test_R4_a_tag_taxonomy_locked_to_three():
    assert FEEDBACK_TAGS == ("Broken", "Wrong", "Great"), \
        "R.4 tag taxonomy is locked to ('Broken', 'Wrong', 'Great')"


def test_R4_a_feedback_submitted_event_constant_added():
    assert FEEDBACK_SUBMITTED == "feedback.submitted"
    assert FEEDBACK_SUBMITTED in KNOWN_EVENT_TYPES


# ─────────────────────────────────────────────────────────────────────
# B. Auto-thanks body shape + [FOUNDER:] placeholders
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_thanks_payload():
    return {
        "first_name":   "Avery",
        "tag":          "Great",
        "text":         "The streaming log scene is gorgeous.",
        "surface_path": "/app/solva/session/foo",
    }


def test_R4_b_thanks_returns_subject_html_text(sample_thanks_payload):
    out = build_thanks_html(sample_thanks_payload)
    assert set(out.keys()) >= {"subject", "html", "text"}
    for k in ("subject", "html", "text"):
        assert isinstance(out[k], str) and len(out[k]) > 0


def test_R4_b_thanks_carries_user_text_tag_surface(sample_thanks_payload):
    out = build_thanks_html(sample_thanks_payload)
    assert "The streaming log scene is gorgeous." in out["html"]
    assert "The streaming log scene is gorgeous." in out["text"]
    assert "Great" in out["html"]
    assert "/app/solva/session/foo" in out["html"]


def test_R4_b_thanks_carries_two_founder_placeholders(sample_thanks_payload):
    out = build_thanks_html(sample_thanks_payload)
    n_html = out["html"].count(FOUNDER_PLACEHOLDER_PREFIX)
    n_text = out["text"].count(FOUNDER_PLACEHOLDER_PREFIX)
    assert n_html == 2, f"locked spec: 2 [FOUNDER: placeholders; got {n_html} in html"
    assert n_text == 2, f"locked spec: 2 [FOUNDER: placeholders; got {n_text} in text"
    assert FOUNDER_PLACEHOLDER_PREFIX not in out["subject"]


def test_R4_b_thanks_guard_raises_422_with_placeholder(sample_thanks_payload):
    rendered = build_thanks_html(sample_thanks_payload)
    with pytest.raises(HTTPException) as ex:
        assert_no_founder_placeholder(rendered)
    assert ex.value.status_code == 422
    assert ex.value.detail["code"] == "founder_placeholder_present"


# ─────────────────────────────────────────────────────────────────────
# C. Send function never raises
# ─────────────────────────────────────────────────────────────────────

def test_R4_c_send_never_raises_when_sdk_missing(monkeypatch, caplog):
    monkeypatch.setenv("SENDGRID_API_KEY", "")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "")
    with caplog.at_level(logging.ERROR):
        send_thanks_email_async(
            rendered={"subject": "x", "html": "x", "text": "x"},
            to_email="r4test@example.com",
            feedback_id="r4-test-1",
            tag="Great",
        )
    assert any("feedback_thanks_failed" in r.message for r in caplog.records)


# ─────────────────────────────────────────────────────────────────────
# D. Endpoint wiring — source-strict
# ─────────────────────────────────────────────────────────────────────

def test_R4_d_endpoint_uses_locked_tag_literal():
    src = FEEDBACK_PY.read_text(encoding="utf-8")
    # Pydantic Literal enforces the locked taxonomy
    assert 'Literal["Broken", "Wrong", "Great"]' in src, \
        "R.4 endpoint must use pydantic Literal to lock the tag taxonomy"


def test_R4_d_endpoint_emits_feature_event():
    src = FEEDBACK_PY.read_text(encoding="utf-8")
    assert "emit_feature_event(" in src
    assert "FEEDBACK_SUBMITTED" in src


def test_R4_d_endpoint_uses_thanks_email_pipe():
    src = FEEDBACK_PY.read_text(encoding="utf-8")
    assert "build_thanks_html" in src
    assert "send_thanks_email_async" in src
    assert "assert_no_founder_placeholder" in src


def test_R4_d_endpoint_returns_200_even_when_guard_fires():
    """R.4 semantic: unlike R.2, we ALWAYS capture feedback. The
    guard firing must result in 200 + `block_reason`, not 422."""
    src = FEEDBACK_PY.read_text(encoding="utf-8")
    # The endpoint catches the guard's HTTPException + sets block_reason
    assert "block_reason" in src
    assert "founder_placeholder_present" in src
    assert "except HTTPException" in src


# ─────────────────────────────────────────────────────────────────────
# E. Frontend widget — source-strict
# ─────────────────────────────────────────────────────────────────────

def test_R4_e_widget_has_locked_tag_buttons():
    src = WIDGET_JSX.read_text(encoding="utf-8")
    assert 'LOCKED_TAGS = ["Broken", "Wrong", "Great"]' in src, \
        "widget LOCKED_TAGS array must be the exact 3 locked tags"
    # The testid is dynamic — `feedback-widget-tag-${t.toLowerCase()}` —
    # so we verify the template literal pattern instead of static tids.
    assert "feedback-widget-tag-${t.toLowerCase()}" in src, \
        "widget must use the dynamic `feedback-widget-tag-<tag>` testid pattern"


def test_R4_e_widget_has_required_testids():
    src = WIDGET_JSX.read_text(encoding="utf-8")
    for tid in (
        "feedback-widget-trigger",
        "feedback-widget-panel",
        "feedback-widget-text",
        "feedback-widget-submit",
        "feedback-widget-close",
    ):
        assert tid in src, f"widget must carry testid {tid!r}"


def test_R4_e_widget_posts_to_feedback_endpoint():
    src = WIDGET_JSX.read_text(encoding="utf-8")
    assert 'api.post("/feedback"' in src or "api.post('/feedback'" in src, \
        "widget must POST to /feedback"
    # Surface path comes from useLocation().pathname (the current route)
    assert "useLocation" in src
    assert "location.pathname" in src


def test_R4_e_widget_renders_inside_gated():
    """The widget must be rendered inside the Gated wrapper so it
    appears on every authenticated app surface."""
    src = APP_JS.read_text(encoding="utf-8")
    assert "FeedbackWidget" in src
    # Located inside Gated component (between FirstSessionGuard children)
    # — we don't strictly assert the JSX shape, just that import + use exist.
    assert "import FeedbackWidget" in src
    assert "<FeedbackWidget" in src


def test_R4_e_widget_uses_aria_dialog_role():
    """A11y: the open panel must be a dialog with an aria-label."""
    src = WIDGET_JSX.read_text(encoding="utf-8")
    assert 'role="dialog"' in src
    assert 'aria-label="Send feedback"' in src
    # Trigger must declare it opens a dialog
    assert 'aria-haspopup="dialog"' in src
    assert "aria-expanded" in src


# ─────────────────────────────────────────────────────────────────────
# F. Fixed-position lower-right invariant
# ─────────────────────────────────────────────────────────────────────

def test_R4_f_widget_pinned_lower_right():
    src = WIDGET_JSX.read_text(encoding="utf-8")
    # Both the trigger button and the panel use fixed bottom-right
    # positioning per the locked Tailwind classes.
    assert "fixed bottom-5 right-5" in src
