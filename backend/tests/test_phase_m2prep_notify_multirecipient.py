"""Sprint M.2-prep (2026-02 fork-resume v3 dispatch 10) — Multi-recipient
FOUNDER_NOTIFY_EMAIL wire-up.

The cohort_applications M.0c scaffold only supported a single founder
notify address. User supplied two addresses + asked for comma-separated
support so future additions don't require a code change.
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock

import pytest

from routers.cohort_applications import (
    _notify_founder,
    _parse_founder_recipients,
)


# ── parser unit tests ─────────────────────────────────────────────────


def test_m2prep_parse_two_recipients():
    out = _parse_founder_recipients("bramuel@syni.ai,mugwe.marion@syni.ai")
    assert out == ["bramuel@syni.ai", "mugwe.marion@syni.ai"]


def test_m2prep_parse_strips_whitespace():
    out = _parse_founder_recipients("bramuel@syni.ai , mugwe.marion@syni.ai")
    assert out == ["bramuel@syni.ai", "mugwe.marion@syni.ai"]


def test_m2prep_parse_filters_empties():
    out = _parse_founder_recipients(", , bramuel@syni.ai , ,")
    assert out == ["bramuel@syni.ai"]


def test_m2prep_parse_empty_string():
    assert _parse_founder_recipients("") == []
    assert _parse_founder_recipients(None or "") == []


def test_m2prep_parse_single_recipient():
    out = _parse_founder_recipients("solo@syni.ai")
    assert out == ["solo@syni.ai"]


# ── SendGrid call tests ───────────────────────────────────────────────


APP_ROW = {
    "id": "m2prep-test-id-001",
    "name": "Test Applicant",
    "email": "applicant@example.com",
    "organisation": "TestCo",
    "role": "CFO",
    "use_case": "Calmer board pack workflow.",
    "referral_source": "twitter",
}


def _extract_to_emails(send_call) -> list[str]:
    """Pull the To addresses out of the Mail object passed to send()."""
    mail = send_call.args[0]
    addrs: list[str] = []
    for p in (mail.personalizations or []):
        for t in (p.tos or []):
            if isinstance(t, dict):
                if t.get("email"):
                    addrs.append(t["email"])
            else:
                if getattr(t, "email", None):
                    addrs.append(t.email)
    return addrs


def test_m2prep_sendgrid_called_with_both_addresses(monkeypatch):
    """Submit with comma-separated env → SendGrid Mail receives BOTH
    To addresses. Asserts the recipient list contains both verbatim."""
    monkeypatch.setenv(
        "FOUNDER_NOTIFY_EMAIL", "bramuel@syni.ai,mugwe.marion@syni.ai",
    )
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.fake-key-for-test")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "akki@syni.ai")
    mock_client = MagicMock()
    mock_client.send.return_value = MagicMock(status_code=202)
    with patch("sendgrid.SendGridAPIClient", return_value=mock_client):
        _notify_founder(APP_ROW)
    assert mock_client.send.call_count == 1, "expected exactly one SendGrid send"
    addrs = _extract_to_emails(mock_client.send.call_args)
    assert "bramuel@syni.ai" in addrs
    assert "mugwe.marion@syni.ai" in addrs
    assert len(addrs) == 2


def test_m2prep_sendgrid_handles_whitespace_separated(monkeypatch):
    """`bramuel@syni.ai , mugwe.marion@syni.ai` (spaces around comma)
    still resolves to two clean addresses."""
    monkeypatch.setenv(
        "FOUNDER_NOTIFY_EMAIL", "bramuel@syni.ai , mugwe.marion@syni.ai",
    )
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.fake-key-for-test")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "akki@syni.ai")
    mock_client = MagicMock()
    mock_client.send.return_value = MagicMock(status_code=202)
    with patch("sendgrid.SendGridAPIClient", return_value=mock_client):
        _notify_founder(APP_ROW)
    addrs = _extract_to_emails(mock_client.send.call_args)
    assert addrs == ["bramuel@syni.ai", "mugwe.marion@syni.ai"]


def test_m2prep_empty_env_no_sendgrid_no_500(monkeypatch, caplog):
    """FOUNDER_NOTIFY_EMAIL unset / empty → no SendGrid call, warning
    logged with reason=sendgrid_or_founder_email_unset, no exception."""
    monkeypatch.delenv("FOUNDER_NOTIFY_EMAIL", raising=False)
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.fake")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "akki@syni.ai")
    mock_client = MagicMock()
    with patch("sendgrid.SendGridAPIClient", return_value=mock_client):
        with caplog.at_level("WARNING"):
            _notify_founder(APP_ROW)  # must not raise
    assert mock_client.send.call_count == 0
    assert any(
        "cohort_application_notify_skipped" in rec.message
        for rec in caplog.records
    ), f"expected notify_skipped warning; got: {[r.message for r in caplog.records]}"


def test_m2prep_audit_log_has_recipient_count(monkeypatch, caplog):
    """The notify_sent audit log entry carries recipient_count = 2."""
    monkeypatch.setenv(
        "FOUNDER_NOTIFY_EMAIL", "bramuel@syni.ai,mugwe.marion@syni.ai",
    )
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.fake-key-for-test")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "akki@syni.ai")
    mock_client = MagicMock()
    mock_client.send.return_value = MagicMock(status_code=202)
    with patch("sendgrid.SendGridAPIClient", return_value=mock_client):
        with caplog.at_level("INFO"):
            _notify_founder(APP_ROW)
    sent_records = [
        r for r in caplog.records
        if "cohort_application_notify_sent" in r.message
    ]
    assert sent_records, "expected cohort_application_notify_sent log entry"
    # The structured payload is rendered after the prefix via %s — verify
    # recipient_count = 2 surfaces in the message.
    assert "'recipient_count': 2" in sent_records[0].message


# ── Source-strict + voice locks ───────────────────────────────────────


def test_m2prep_source_uses_to_list_not_single_to():
    """The source uses `to_emails=[To(addr) for addr in recipients]`,
    not the legacy `to_emails=To(to_email)` single-recipient form."""
    from pathlib import Path
    src = (
        Path(__file__).resolve().parent.parent / "routers" / "cohort_applications.py"
    ).read_text(encoding="utf-8")
    assert "to_emails=[To(addr) for addr in recipients]" in src
    assert "to_emails=To(to_email)" not in src


def test_m2prep_audit_message_is_voice_clean():
    """The audit log strings should not introduce any banned vocabulary."""
    from pathlib import Path
    src = (
        Path(__file__).resolve().parent.parent / "routers" / "cohort_applications.py"
    ).read_text(encoding="utf-8")
    for bad in ["empower", "seamless", "AI-powered", "leverage",
                "lightning-fast", "blazing", "synergy"]:
        assert bad.lower() not in src.lower(), (
            f"banned vocab in cohort_applications.py: {bad!r}"
        )
