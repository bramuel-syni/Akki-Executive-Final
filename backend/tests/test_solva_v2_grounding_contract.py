"""Unit tests — Solva v2 grounding contract parser.

The parser IS the contract. If the parser breaks, the contract breaks. These
tests pin the behaviour: tier vocabulary, missing-marker detection, malformed-
marker detection, empty / question-only bodies.
"""
from __future__ import annotations

import sys
import os
import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.solva_v2 import parse, TIER_NAMES, summarise_tier_distribution, input_hash
from services.solva_v2.grounding_contract import CONTRACT_VERSION


def test_tier_vocabulary_is_locked():
    assert TIER_NAMES == [
        "corpus",
        "comparable",
        "domain_prior",
        "user_assertion",
        "speculation",
    ]


def test_each_valid_tier_parses_as_its_own_claim():
    """All five tier names must round-trip cleanly."""
    body = (
        "Revenue slipped 14% last quarter [T:corpus]. "
        "A comparable mid-cap bank found onboarding friction [T:comparable]. "
        "The board may resist pricing change [T:domain_prior]. "
        "The CEO claimed macro headwinds were decisive [T:user_assertion]. "
        "The real cause may be mix shift [T:speculation]."
    )
    res = parse(body)
    assert res.valid, f"expected valid parse, got untagged={res.untagged_sentences} malformed={res.malformed_markers}"
    assert len(res.claims) == 5
    assert sorted(c.tier for c in res.claims) == sorted(TIER_NAMES)
    # confidence_* stay null in 15.0
    for c in res.claims:
        assert c.confidence_band is None
        assert c.confidence_pct is None


def test_missing_tier_label_flags_untagged_and_invalidates():
    body = (
        "Revenue slipped 14% last quarter [T:corpus]. "
        "Pricing is likely the cause. "  # <-- no marker
        "The board met quarterly [T:corpus]."
    )
    res = parse(body)
    assert not res.valid
    assert len(res.untagged_sentences) == 1
    assert "Pricing is likely the cause." in res.untagged_sentences[0]


def test_malformed_marker_is_caught():
    body = (
        "Revenue slipped 14% last quarter [T:corpus]. "
        "The rate changed [T:made_up_tier]. "
        "Finished [T:corpus]."
    )
    res = parse(body)
    assert not res.valid
    assert len(res.malformed_markers) == 1
    assert res.malformed_markers[0]["bad_tier"] == "made_up_tier"


def test_multiple_claims_mixed_tiers():
    body = (
        "Q3 revenue missed by 18% [T:corpus]. "
        "Two comparables show onboarding as the cause [T:comparable]. "
        "Boards often misdiagnose macro as root cause [T:domain_prior]. "
        "What does the activation dashboard show?"  # question — no marker needed
    )
    res = parse(body)
    assert res.valid
    assert len(res.claims) == 3
    dist = summarise_tier_distribution(res.claims)
    assert dist["corpus"] == 1
    assert dist["comparable"] == 1
    assert dist["domain_prior"] == 1
    assert dist["user_assertion"] == 0
    assert dist["speculation"] == 0


def test_empty_and_question_only_bodies_parse_as_valid_with_zero_claims():
    assert parse("").valid is True
    assert parse("").claims == []
    # Question-only body: no assertive sentences, so trivially valid.
    res = parse("What does the dashboard show? Is this mix or price?")
    assert res.valid
    assert res.claims == []


def test_strip_keeps_claim_text_intact_without_marker():
    body = "Revenue slipped 14% [T:corpus]."
    res = parse(body)
    assert len(res.claims) == 1
    assert "[T:" not in res.claims[0].text
    assert res.claims[0].text.endswith("slipped 14%")
    assert res.stripped_text == "Revenue slipped 14% ."


def test_short_connective_sentences_do_not_require_markers():
    """Sentences under 12 chars (e.g. 'Done.') are treated as connective text
    and do not require a marker. This prevents the parser from flagging
    natural prose rhythm as a contract violation."""
    body = (
        "Done. "
        "Revenue slipped 14% last quarter [T:corpus]. "
        "Next."
    )
    res = parse(body)
    assert res.valid
    assert len(res.claims) == 1


def test_longer_untagged_sentence_is_flagged_even_if_connective_looking():
    """Sentences of 12+ chars MUST carry a marker. This is the contract."""
    body = (
        "Three main points. "  # 18 chars - above the 12-char threshold
        "Revenue slipped 14% [T:corpus]."
    )
    res = parse(body)
    assert not res.valid
    assert any("Three main points" in s for s in res.untagged_sentences)


def test_input_hash_is_deterministic_and_differs_for_different_input():
    a = input_hash("hello world")
    b = input_hash("hello world")
    c = input_hash("hello worlD")
    assert a == b
    assert a != c
    assert len(a) == 64  # sha256 hex


def test_contract_version_is_stable_tag():
    assert CONTRACT_VERSION == "solva_v2_grounding@1.0"
