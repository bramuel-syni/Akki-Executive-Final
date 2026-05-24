"""Synisense Shield — reidentifier PII-class skip list (Fork A, 2026-05-24).

Asserts the user-visible reply renders the placeholder string for hard-
PII classes (CREDIT_CARD, SSN, API_KEY, UK_NI_NUMBER, IBAN, EMAIL,
PHONE_E164, IP, ACCOUNT_NUM) and still rehydrates contextual classes
(PERSON, ORG, MONEY, DATE_ISO, URL, …) so users keep working continuity.

Companion to `test_pan_detection.py` (which covers the de-id side).

Run independently:
    pytest tests/test_reidentifier_skip_list.py -v
"""
from __future__ import annotations

import sys

import pytest

sys.path.insert(0, "/app/backend")
from services.synisense.shield import deidentifier, reidentifier  # noqa: E402

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────
# Pure reidentifier behaviour — token_map fixtures only, no LLM.
# ─────────────────────────────────────────────────────────────────────
async def test_credit_card_last4_visible_placeholder():
    """A CREDIT_CARD token resolves to `[PAYMENT_CARD_••••<last4>]`
    in the user-visible reply, NOT the raw PAN."""
    out = reidentifier.reidentify(
        "Your card [[ENT_CREDIT_CARD_001]] was charged.",
        {"[[ENT_CREDIT_CARD_001]]": "4356789800057689"},
    )
    assert "4356789800057689" not in out
    assert "[PAYMENT_CARD_••••7689]" in out, out


async def test_account_num_last4_visible_placeholder():
    """A Luhn-INVALID 16-digit (falls to ACCOUNT_NUM) still surfaces as
    a redacted placeholder in the user-visible reply."""
    out = reidentifier.reidentify(
        "Account [[ENT_ACCOUNT_NUM_001]] referenced.",
        {"[[ENT_ACCOUNT_NUM_001]]": "4356789000056785"},
    )
    assert "4356789000056785" not in out
    assert "[ACCOUNT_NUM_••••6785]" in out, out


async def test_ssn_last4_visible_placeholder():
    out = reidentifier.reidentify(
        "SSN on file: [[ENT_SSN_001]]",
        {"[[ENT_SSN_001]]": "123-45-6789"},
    )
    assert "123-45-6789" not in out
    assert "[SSN_••••6789]" in out, out


async def test_api_key_redacted_no_partial_leak():
    """API_KEY uses the `redacted` strategy — NO portion of the token
    is allowed to leak (no prefix, no suffix, no length cue)."""
    api_key = "AKIAIOSFODNN7EXAMPLE"
    out = reidentifier.reidentify(
        "Rotate [[ENT_API_KEY_001]] immediately.",
        {"[[ENT_API_KEY_001]]": api_key},
    )
    assert api_key not in out
    assert "[API_KEY_REDACTED]" in out, out
    # Defence-in-depth — assert no 5+ character substring of the key
    # survives anywhere in the output (catches accidental prefix/suffix
    # leaks if someone changes the strategy later).
    for i in range(len(api_key) - 5):
        chunk = api_key[i:i + 5]
        assert chunk not in out, f"API key chunk {chunk!r} leaked: {out!r}"


async def test_uk_ni_redacted_no_last4_leak():
    """UK NI numbers carry too much info in their last 4 chars (1
    letter + 3 digits = ~30 possibilities), so they use `redacted`
    not `last4`. Assert no partial leak."""
    ni = "AB123456C"
    out = reidentifier.reidentify(
        "His [[ENT_UK_NI_NUMBER_001]] is on file.",
        {"[[ENT_UK_NI_NUMBER_001]]": ni},
    )
    assert ni not in out
    assert "[UK_NI_REDACTED]" in out, out
    # Last 4 chars of NI must NOT appear together.
    assert ni[-4:] not in out, out


async def test_email_redacted_no_domain_leak():
    out = reidentifier.reidentify(
        "Contact [[ENT_EMAIL_001]] for billing.",
        {"[[ENT_EMAIL_001]]": "john.doe@example.com"},
    )
    assert "john.doe@example.com" not in out
    assert "@example.com" not in out  # domain leak guard
    assert "[EMAIL_REDACTED]" in out, out


async def test_phone_last4_visible_placeholder():
    out = reidentifier.reidentify(
        "Call [[ENT_PHONE_E164_001]] today.",
        {"[[ENT_PHONE_E164_001]]": "+1-415-555-1234"},
    )
    assert "+1-415-555-1234" not in out
    assert "[PHONE_••••1234]" in out, out


async def test_iban_last4_visible_placeholder():
    out = reidentifier.reidentify(
        "Wire to [[ENT_IBAN_001]]",
        {"[[ENT_IBAN_001]]": "GB82WEST12345698765432"},
    )
    assert "GB82WEST12345698765432" not in out
    assert "[IBAN_••••5432]" in out, out


async def test_ip_address_redacted():
    out = reidentifier.reidentify(
        "Block traffic from [[ENT_IP_001]].",
        {"[[ENT_IP_001]]": "203.0.113.42"},
    )
    assert "203.0.113.42" not in out
    assert "[IP_REDACTED]" in out, out


# ─────────────────────────────────────────────────────────────────────
# Contextual classes — MUST still rehydrate. Regression guards.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "entity_type,original",
    [
        ("PERSON",   "Bramuel"),
        ("ORG",      "KPMG"),
        ("GPE",      "London"),
        ("PRODUCT",  "Office 365"),
        ("NORP",     "British"),
        ("FAC",      "Heathrow Terminal 5"),
        ("EVENT",    "Q4 board meeting"),
        ("LAW",      "GDPR Article 22"),
        ("DATE_ISO", "2026-02-15"),
        ("MONEY",    "$1,200.00"),
        ("URL",      "https://akki.syni.ai"),
    ],
)
async def test_contextual_classes_still_rehydrate(entity_type, original):
    """Contextual classes (PERSON, ORG, etc.) MUST still substitute back
    to the original — that's continuity, the user wants to see their
    own names back in the LLM reply."""
    token = f"[[ENT_{entity_type}_001]]"
    text  = f"Context: {token} appears in the reply."
    out = reidentifier.reidentify(text, {token: original})
    assert original in out, (
        f"contextual class {entity_type!r} failed to rehydrate; "
        f"original={original!r} not in output={out!r}"
    )
    assert token not in out, (
        f"raw token {token!r} survived rehydration: {out!r}"
    )


# ─────────────────────────────────────────────────────────────────────
# Mixed message — Fork A scenario from the user brief.
# ─────────────────────────────────────────────────────────────────────
async def test_mixed_message_pii_redacted_contextual_rehydrated():
    """A reply mixing hard-PII tokens (CREDIT_CARD, API_KEY) with
    contextual tokens (PERSON, ORG) must render with placeholders for
    the PII and real names for the contextual entities."""
    token_map = {
        "[[ENT_CREDIT_CARD_001]]": "4356789800057689",
        "[[ENT_API_KEY_001]]":     "AKIAIOSFODNN7EXAMPLE",
        "[[ENT_PERSON_001]]":      "Bramuel",
        "[[ENT_ORG_001]]":         "KPMG",
    }
    text = (
        "Reply: [[ENT_PERSON_001]] left card [[ENT_CREDIT_CARD_001]] at "
        "[[ENT_ORG_001]]; rotate key [[ENT_API_KEY_001]]."
    )
    out = reidentifier.reidentify(text, token_map)
    # Hard PII redacted
    assert "4356789800057689" not in out
    assert "AKIAIOSFODNN7EXAMPLE" not in out
    assert "[PAYMENT_CARD_••••7689]" in out, out
    assert "[API_KEY_REDACTED]" in out, out
    # Contextual rehydrated
    assert "Bramuel" in out, out
    assert "KPMG" in out, out


async def test_unknown_token_left_as_is():
    """A token that ISN'T in the token map (drift / hostile LLM
    response) is left bare so smoke tests can catch it."""
    out = reidentifier.reidentify(
        "Unknown drift: [[ENT_PERSON_999]] in the wild.",
        {"[[ENT_PERSON_001]]": "Bramuel"},  # different counter
    )
    assert "[[ENT_PERSON_999]]" in out


async def test_empty_inputs_safe():
    assert reidentifier.reidentify("", {}) == ""
    assert reidentifier.reidentify("hello", {}) == "hello"
    assert reidentifier.reidentify("", {"[[ENT_X_001]]": "y"}) == ""


# ─────────────────────────────────────────────────────────────────────
# End-to-end — deidentify → simulated LLM echo → reidentify.
# Verifies the Fork A behavior across the full Shield round-trip.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "user_input,must_not_appear,must_appear",
    [
        # Scenario A from the brief
        (
            "Bramuel left his card no 4356789800057689 in KPMG head office.",
            ["4356789800057689"],
            ["[PAYMENT_CARD_••••7689]", "Bramuel", "KPMG"],
        ),
        # Scenario B from the brief (Luhn-invalid 16-digit → ACCOUNT_NUM)
        (
            "Bramuel, Marion and Brian are meeting about card number 4356789000056785 at KPMG",
            ["4356789000056785"],
            ["[ACCOUNT_NUM_••••6785]", "Bramuel", "Marion", "KPMG"],
        ),
        # Scenario C from the brief
        (
            "John's SSN is 123-45-6789 and AWS key is AKIAIOSFODNN7EXAMPLE",
            ["123-45-6789", "AKIAIOSFODNN7EXAMPLE"],
            ["[SSN_••••6789]", "[API_KEY_REDACTED]"],
        ),
    ],
)
async def test_round_trip_redacts_pii_keeps_context(
    user_input, must_not_appear, must_appear,
):
    """Full Shield round-trip: de-id the user input, simulate an LLM
    that perfectly echoes the redacted form back, re-id, then assert
    the final user-visible string redacts hard PII and keeps context."""
    de_id = await deidentifier.deidentify(user_input, tenant_id="test-tenant")

    # Simulate: the LLM has been given the redacted text and responded
    # by repeating it verbatim (worst-case for "leak" perception —
    # exactly what Claude did in the user's screenshot).
    llm_echo = de_id.redacted_text

    final = reidentifier.reidentify(llm_echo, de_id.token_map)

    for leak in must_not_appear:
        assert leak not in final, (
            f"hard PII {leak!r} leaked in final user-visible reply: "
            f"{final!r}"
        )
    for required in must_appear:
        assert required in final, (
            f"expected token/name {required!r} missing from final reply: "
            f"{final!r}"
        )


async def test_round_trip_audit_summary_still_includes_pii():
    """REGRESSION: the audit `de_id_summary` MUST still report the PII
    classes — only the user-VISIBLE rendering changes. The audit trail
    must continue showing CREDIT_CARD / SSN / API_KEY counts."""
    user_input = (
        "Bramuel left his card no 4356789800057689 in KPMG head office. "
        "His SSN is 123-45-6789 and his AWS key is AKIAIOSFODNN7EXAMPLE."
    )
    de_id = await deidentifier.deidentify(user_input, tenant_id="test-tenant")
    summary = de_id.de_id_summary
    assert summary.get("CREDIT_CARD", 0) >= 1, summary
    assert summary.get("SSN", 0) >= 1, summary
    assert summary.get("API_KEY", 0) >= 1, summary
