"""Demo-blocker patch (2026-02) — payment-card / SSN / API-key / UK NI
regex layer with Luhn validation on PANs.

Verifies the Shield deidentifier's new regex layer catches the four
PII families demanded by the demo brief, and that Luhn-invalid 16-digit
strings don't false-positive into the CREDIT_CARD bucket.

Run independently:
    pytest tests/test_pan_detection.py -v
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "/app/backend")
from services.synisense.shield import deidentifier  # noqa: E402

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────
# 1. CREDIT_CARD — Luhn-valid PAN must be detected.
# ─────────────────────────────────────────────────────────────────────
async def test_luhn_valid_pan_is_detected_as_credit_card():
    """The demo-trigger 16-digit Luhn-valid PAN redacts as CREDIT_CARD,
    NOT as the generic ACCOUNT_NUM fallback."""
    text = "Bramuel left his card no 4356789800057689 in KPMG head office."
    out = await deidentifier.deidentify(text, tenant_id="demo-tenant")
    assert "4356789800057689" not in out.redacted_text, (
        "PAN must NOT survive in redacted text"
    )
    assert "[[ENT_CREDIT_CARD_001]]" in out.redacted_text, (
        f"Expected CREDIT_CARD token, got: {out.redacted_text!r}"
    )
    assert out.de_id_summary.get("CREDIT_CARD", 0) >= 1, out.de_id_summary
    assert out.de_id_summary.get("ACCOUNT_NUM", 0) == 0, (
        "Luhn-valid PAN should claim the CREDIT_CARD label and NOT also "
        "appear as an ACCOUNT_NUM hit"
    )


async def test_credit_card_with_separator_variants_detected():
    """Same PAN with space and dash separators also redacts."""
    for variant in (
        "4356 7898 0005 7689",
        "4356-7898-0005-7689",
        "4356 7898-0005 7689",
    ):
        text = f"Card: {variant}"
        out = await deidentifier.deidentify(text, tenant_id="demo-tenant")
        assert out.de_id_summary.get("CREDIT_CARD", 0) >= 1, (
            f"variant {variant!r} not detected: {out.redacted_text!r}"
        )
        assert "4356" not in out.redacted_text or "0005" not in out.redacted_text, (
            f"PAN digits leaked for {variant!r}: {out.redacted_text!r}"
        )


# ─────────────────────────────────────────────────────────────────────
# 2. Negative — Luhn-invalid 16-digit must NOT fire CREDIT_CARD.
# ─────────────────────────────────────────────────────────────────────
async def test_luhn_invalid_16_digit_string_does_not_fire_credit_card():
    """A random 16-digit number (e.g. order id) fails Luhn and must
    NOT be tagged CREDIT_CARD. It still redacts (as ACCOUNT_NUM) so
    sensitive long digit runs aren't leaked, but the LABEL must be
    correct — the audit panel renders the label verbatim."""
    text = "Order number 1234567890123456 was processed."
    out = await deidentifier.deidentify(text, tenant_id="demo-tenant")
    assert out.de_id_summary.get("CREDIT_CARD", 0) == 0, (
        "Luhn-invalid 16-digit must NOT be tagged CREDIT_CARD; "
        f"summary: {out.de_id_summary!r}"
    )
    assert out.de_id_summary.get("ACCOUNT_NUM", 0) == 1, (
        "Luhn-invalid 16-digit should still be redacted as ACCOUNT_NUM"
    )
    assert "1234567890123456" not in out.redacted_text


# ─────────────────────────────────────────────────────────────────────
# 3. SSN, UK NI, API_KEY — three families demanded by the demo brief.
# ─────────────────────────────────────────────────────────────────────
async def test_us_ssn_detected():
    out = await deidentifier.deidentify(
        "Her SSN is 123-45-6789 on file.", tenant_id="demo-tenant",
    )
    assert "123-45-6789" not in out.redacted_text
    assert out.de_id_summary.get("SSN", 0) >= 1, out.de_id_summary


async def test_uk_ni_number_detected():
    """UK National Insurance numbers follow the QQ123456C shape with
    HMRC-disallowed prefix letters filtered out. `AB123456C` uses a
    valid prefix (Q, D, F, I, U, V are excluded per HMRC rules)."""
    out = await deidentifier.deidentify(
        "His NI number is AB123456C, please file it.",
        tenant_id="demo-tenant",
    )
    assert "AB123456C" not in out.redacted_text
    assert out.de_id_summary.get("UK_NI_NUMBER", 0) >= 1, out.de_id_summary


@pytest.mark.parametrize(
    "api_key_sample",
    [
        "AKIAIOSFODNN7EXAMPLE",
        "sk_test_4eC39HqLyjWDarjtT1zdp7dc",
        "ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ1234567890",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4iLCJpYXQiOjE1MTYyMzkwMjJ9.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        "xoxb-1234567890-abcdefghijklmnopqrstuvwxyz",
        "sk-proj-abcdefghijklmnopqrstuvwxyz1234567890",
    ],
)
async def test_api_key_families_detected(api_key_sample):
    """Each of the API-key families in the regex alternation must be
    redacted out of the message."""
    out = await deidentifier.deidentify(
        f"My token is {api_key_sample} please rotate it.",
        tenant_id="demo-tenant",
    )
    assert out.de_id_summary.get("API_KEY", 0) >= 1, (
        f"API_KEY not detected for {api_key_sample!r}; "
        f"summary={out.de_id_summary!r} text={out.redacted_text!r}"
    )
    # The sample must NOT survive verbatim. We check a structural
    # signature (the most-unique 16+ chars in the middle of the key)
    # rather than the whole string to avoid false-fail on a prefix
    # like "sk-" that legitimately appears outside the redacted span.
    distinctive_chunk = api_key_sample[8:24]
    assert distinctive_chunk not in out.redacted_text, (
        f"API key body leaked: {out.redacted_text!r}"
    )


# ─────────────────────────────────────────────────────────────────────
# 4. End-to-end — the brief's verification string covers ALL families.
# ─────────────────────────────────────────────────────────────────────
async def test_demo_verification_string_covers_pan_ssn_api_key():
    """The exact verification string from the demo brief redacts at
    minimum: 1 CREDIT_CARD + 1 SSN + 1 API_KEY."""
    text = (
        "Bramuel left his card no 4356789800057689 in KPMG head office. "
        "His SSN is 123-45-6789 and his AWS key is AKIAIOSFODNN7EXAMPLE."
    )
    out = await deidentifier.deidentify(text, tenant_id="demo-tenant")
    summary = out.de_id_summary
    assert summary.get("CREDIT_CARD", 0) >= 1, summary
    assert summary.get("SSN", 0) >= 1, summary
    assert summary.get("API_KEY", 0) >= 1, summary
    # And none of the raw PII strings survive.
    for leaked in (
        "4356789800057689",
        "123-45-6789",
        "AKIAIOSFODNN7EXAMPLE",
    ):
        assert leaked not in out.redacted_text, (
            f"raw PII leaked into redacted output: {leaked!r}"
        )


# ─────────────────────────────────────────────────────────────────────
# 5. The Luhn helper itself — sanity-check the implementation.
# ─────────────────────────────────────────────────────────────────────
async def test_luhn_helper_valid_and_invalid():
    """Inline sanity assertions on the Luhn helper. Async-wrapped so
    the file-level `pytestmark = pytest.mark.asyncio` stays happy."""
    cases = [
        ("4356789800057689", True),   # demo trigger
        ("4242424242424242", True),   # Stripe test card
        ("4111111111111111", True),   # classic Visa test
        ("5555555555554444", True),   # MasterCard test
        ("378282246310005",  True),   # Amex test (15-digit)
        ("1234567890123456", False),  # Luhn-invalid 16-digit
        ("0000000000000000", True),   # technically Luhn-valid (all zero)
        ("abcd",             False),  # not digits
        ("",                 False),  # empty
    ]
    for pan, expected in cases:
        assert deidentifier._luhn_valid(pan) is expected, (
            f"luhn({pan!r}) returned wrong value (expected {expected})"
        )
