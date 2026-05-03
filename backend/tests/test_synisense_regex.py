"""Phase 12.1 unit tests — regex recogniser layer.

Each regex pattern is exercised against labelled fixture strings.
Scope doc requirement: known-hard cases including co-ref-ish phrasing
and nested deals are covered at the Presidio / LLM layer integration
test, not here — the regex layer is deliberately narrow and
high-precision.
"""
import sys
sys.path.insert(0, "/app/backend")

from services.synisense.regex_recognisers import scan


def test_email_detected():
    hits = scan("Email director@acme.co.uk before noon.")
    assert any(h["entity_type"] == "EMAIL_ADDRESS" for h in hits)


def test_phone_detected():
    hits = scan("Call +44 20 7123 4567 today.")
    assert any(h["entity_type"] == "PHONE_NUMBER" for h in hits)


def test_iban_detected():
    hits = scan("IBAN is GB33BUKB20201555555555 on file.")
    assert any(h["entity_type"] == "IBAN_CODE" for h in hits)


def test_ssn_detected():
    hits = scan("SSN 123-45-6789 is confidential.")
    assert any(h["entity_type"] == "US_SSN" for h in hits)


def test_ip_and_url_together():
    hits = scan("Tunnel https://vpn.acme.com through 10.0.0.5 only.")
    types = {h["entity_type"] for h in hits}
    assert "URL" in types
    assert "IP_ADDRESS" in types


def test_no_overlaps():
    hits = scan(
        "Two tokens: john@acme.com and another: jane@beta.io, both at 10.0.0.1."
    )
    # Spans are non-overlapping by contract.
    sorted_hits = sorted(hits, key=lambda h: h["start"])
    for a, b in zip(sorted_hits, sorted_hits[1:]):
        assert a["end"] <= b["start"]


def test_empty_is_empty():
    assert scan("") == []
    assert scan("  ") == []


def test_regex_shape_contract():
    hits = scan("user@acme.com")
    assert hits and set(hits[0].keys()) >= {
        "start", "end", "entity_type", "source", "confidence", "match_text",
    }
    assert hits[0]["source"] == "regex"
    assert hits[0]["confidence"] == 1.0
