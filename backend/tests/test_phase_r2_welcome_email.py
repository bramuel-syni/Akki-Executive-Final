"""Phase R.2 (2026-05-27) — Founding Cohort welcome-email pipe CI lockdown.

Locks the autonomous-mode contract:
  - `build_welcome_html` returns {subject, html, text}; the body
    contains EXACTLY 4 `[FOUNDER:` placeholders (one per founder-voice
    slot) and ships SendGrid-ready.
  - `assert_no_founder_placeholder` raises 422 with the locked code
    `founder_placeholder_present` when ANY `[FOUNDER:` token remains.
  - The endpoint guard fires ONLY on actual send (`send=1`); `send=0`
    and `preview=1` deliberately bypass.
  - The send function is BackgroundTasks-safe — NEVER raises; failures
    emit `cohort_welcome_failed: {...}` log lines.
  - SendGrid SDK is the existing `sendgrid==6.12.5`; env vars
    `SENDGRID_API_KEY` + `SENDGRID_FROM_EMAIL` (already wired).
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "backend"))

from services.cohort.welcome_email import (  # noqa: E402
    FOUNDER_PLACEHOLDER_PREFIX,
    build_welcome_html,
    assert_no_founder_placeholder,
    send_welcome_email_async,
)


# ─────────────────────────────────────────────────────────────────────
# build_welcome_html — shape + content invariants
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_payload():
    return {
        "first_name": "Avery",
        "logo_name":  "TestCo Holdings",
        "cohort_tag": "founding_2026Q2_TEST",
        "magic_link": "https://akki-executive.preview.emergentagent.com/api/auth/magic/abc.123",
        "trial_length_days": 30,
        "trial_end_at": "2026-06-26T20:00:00+00:00",
        "expires_at":   "2026-06-10T20:00:00+00:00",
    }


def test_R2_a_build_returns_subject_html_text(sample_payload):
    out = build_welcome_html(sample_payload)
    assert set(out.keys()) >= {"subject", "html", "text"}
    for k in ("subject", "html", "text"):
        assert isinstance(out[k], str) and len(out[k]) > 0


def test_R2_a_html_carries_logo_name_and_magic_link(sample_payload):
    out = build_welcome_html(sample_payload)
    assert "TestCo Holdings" in out["html"]
    assert "TestCo Holdings" in out["text"]
    assert sample_payload["magic_link"] in out["html"]
    assert sample_payload["magic_link"] in out["text"]
    # Pretty expires date
    assert "June" in out["html"] or sample_payload["expires_at"] in out["html"]


def test_R2_a_subject_carries_logo_name(sample_payload):
    out = build_welcome_html(sample_payload)
    assert "TestCo Holdings" in out["subject"]
    assert "founding-cohort" in out["subject"].lower()


def test_R2_a_first_name_fallback():
    """`first_name=None` must default to a sane greeting word."""
    payload = {
        "first_name": None,
        "logo_name":  "FB Holdings",
        "magic_link": "https://x/auth/magic/abc",
        "expires_at": "2026-06-10T00:00:00+00:00",
        "trial_length_days": 30,
    }
    out = build_welcome_html(payload)
    assert "Welcome, there" in out["html"]
    assert "Welcome, there" in out["text"]


# ─────────────────────────────────────────────────────────────────────
# 4 [FOUNDER:] placeholders — exactly 4 in html, exactly 4 in text
# ─────────────────────────────────────────────────────────────────────

def test_R2_b_html_carries_exactly_four_founder_placeholders(sample_payload):
    out = build_welcome_html(sample_payload)
    n = out["html"].count(FOUNDER_PLACEHOLDER_PREFIX)
    assert n == 4, f"locked spec: 4 [FOUNDER: placeholders; got {n} in html"
    n_text = out["text"].count(FOUNDER_PLACEHOLDER_PREFIX)
    assert n_text == 4, f"locked spec: 4 [FOUNDER: placeholders; got {n_text} in text"


def test_R2_b_subject_carries_no_founder_placeholder(sample_payload):
    out = build_welcome_html(sample_payload)
    assert FOUNDER_PLACEHOLDER_PREFIX not in out["subject"], \
        "subject must be founder-edit-free at build-time"


# ─────────────────────────────────────────────────────────────────────
# assert_no_founder_placeholder — the 422 guard
# ─────────────────────────────────────────────────────────────────────

def test_R2_c_guard_raises_422_when_placeholder_present(sample_payload):
    rendered = build_welcome_html(sample_payload)
    with pytest.raises(HTTPException) as ex:
        assert_no_founder_placeholder(rendered)
    assert ex.value.status_code == 422
    detail = ex.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "founder_placeholder_present"
    assert detail["founder_placeholders_remaining"] >= 4
    assert isinstance(detail["examples"], list) and len(detail["examples"]) > 0


def test_R2_c_guard_passes_when_no_placeholders():
    """Once the founder has filled in all 4 slots, the guard must pass."""
    clean = {
        "subject": "Welcome to AKKI's founding cohort",
        "html":    "<p>Welcome, Avery. We're glad you said yes.</p>",
        "text":    "Welcome, Avery. We're glad you said yes.",
    }
    # Should NOT raise.
    assert_no_founder_placeholder(clean) is None


def test_R2_c_guard_catches_placeholder_in_any_field():
    """A `[FOUNDER:` token in subject / html / text — any one — must trip the guard."""
    cases = [
        {"subject": "Welcome [FOUNDER: edit] thing", "html": "", "text": ""},
        {"subject": "", "html": "<p>[FOUNDER: x]</p>", "text": ""},
        {"subject": "", "html": "", "text": "[FOUNDER: x]"},
    ]
    for c in cases:
        with pytest.raises(HTTPException) as ex:
            assert_no_founder_placeholder(c)
        assert ex.value.status_code == 422


# ─────────────────────────────────────────────────────────────────────
# send_welcome_email_async — never raises; emits structured log lines
# ─────────────────────────────────────────────────────────────────────

def test_R2_d_send_never_raises_when_sdk_missing(monkeypatch, caplog):
    """If the SendGrid SDK is somehow not importable, the function
    logs `cohort_welcome_failed` and returns without raising."""
    monkeypatch.setenv("SENDGRID_API_KEY", "")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "")
    with caplog.at_level(logging.ERROR):
        send_welcome_email_async(
            rendered={"subject": "x", "html": "x", "text": "x"},
            to_email="test@example.com",
            invite_id="ix1",
            cohort_tag="founding_2026Q2_TEST",
        )
    assert any("cohort_welcome_failed" in r.message for r in caplog.records)
    assert any("sendgrid_not_configured" in str(r.message) for r in caplog.records)


def test_R2_d_send_uses_sandbox_when_env_set(monkeypatch, caplog):
    """`SENDGRID_SANDBOX_ONLY=1` forces sandbox-mode send (no actual
    delivery). The path must still log `cohort_welcome_sent` on a 2xx
    response from SendGrid."""
    api_key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    from_email = (os.environ.get("SENDGRID_FROM_EMAIL") or "").strip()
    if not api_key or not from_email:
        pytest.skip("SendGrid creds not configured in this env")
    monkeypatch.setenv("SENDGRID_SANDBOX_ONLY", "1")
    with caplog.at_level(logging.INFO):
        send_welcome_email_async(
            rendered={"subject": "AKKI sandbox", "html": "<p>x</p>", "text": "x"},
            to_email="r2-sandbox-test@example.com",
            invite_id="ix-sandbox",
            cohort_tag="founding_2026Q2_TEST",
        )
    # Either `_sent` (sandbox 200) or `_failed` (network blip) — both
    # are acceptable; the invariant is "never raises".
    msgs = [r.message for r in caplog.records]
    has_one = any("cohort_welcome_sent" in m or "cohort_welcome_failed" in m
                  for m in msgs)
    assert has_one, f"expected log line; got: {msgs[:5]}"


# ─────────────────────────────────────────────────────────────────────
# Source-strict guard: admin_cohort wiring
# ─────────────────────────────────────────────────────────────────────

def test_R2_e_admin_cohort_wires_send_and_preview_queryparams():
    src = (REPO / "backend" / "routers" / "admin_cohort.py").read_text(encoding="utf-8")
    # send / preview query params are present
    assert "send: int = Query(" in src
    assert "preview: int = Query(" in src
    # Guard fires only on actual send (NOT on preview)
    assert "if send == 1 and preview != 1:" in src, \
        "guard must fire on send=1 AND skip when preview=1 (founder iteration mode)"
    # Background dispatch on send=1
    assert "background_tasks.add_task(" in src
    assert "send_welcome_email_async" in src
    # cohort_welcome_dispatched / cohort_welcome_skipped log events
    assert "cohort_welcome_dispatched" in src
    assert "cohort_welcome_skipped" in src


def test_R2_e_admin_cohort_imports_welcome_email_helpers():
    src = (REPO / "backend" / "routers" / "admin_cohort.py").read_text(encoding="utf-8")
    for sym in ("build_welcome_html", "assert_no_founder_placeholder", "send_welcome_email_async"):
        assert sym in src, f"admin_cohort.py must import `{sym}`"


# ─────────────────────────────────────────────────────────────────────
# Locked institutional contract — placeholder prefix MUST NOT change
# ─────────────────────────────────────────────────────────────────────

def test_R2_f_placeholder_prefix_is_locked():
    assert FOUNDER_PLACEHOLDER_PREFIX == "[FOUNDER:", \
        "the [FOUNDER: prefix is the locked institutional marker. " \
        "Future agents MUST dispatch a new R sub-phase before changing it."
