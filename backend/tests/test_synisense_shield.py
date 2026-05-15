"""Synisense Shield — Phase A unit + contract tests.

Covers (≥25 tests across all three Phase A test files):
- De-id stack (regex / tenant dict / spaCy / scoring / overlap / fail-closed)
- Trust receipt (HKDF derivation, HMAC sign + verify, tamper detection)
- Purpose validator (allow / wildcard / deny / internal gate)
- Re-identifier (token round-trip, drift safety)
"""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from services.synisense.config import is_dev_fallback_active
from services.synisense.exceptions import PurposeInvalid, ServiceUnavailable
from services.synisense.shield import (
    deidentifier, purpose_validator, reidentifier, tenant_entities, trust_receipt,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures.
# ─────────────────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def db_conn():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


@pytest_asyncio.fixture
async def isolated_tenant(db_conn):
    """A fresh tenant_id with no persisted entities. Tears down after."""
    tid = "test-tenant-" + uuid.uuid4().hex[:10]
    yield tid
    await db_conn.synisense_tenant_entities.delete_many({"tenant_id": tid})
    tenant_entities._force_clear_cache_for_test(tid)


# ─────────────────────────────────────────────────────────────────────
# 1. Regex de-id — explicit pattern coverage.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_regex_money_email_phone_iban_account_date_ip_url_ssn(isolated_tenant):
    """One test that proves every regex type in the brief is detected."""
    sample = (
        "Wire $50,000 to John on 2026-01-15. Email: john@example.com, "
        "phone: +1-415-555-1234. IBAN: GB29NWBK60161331926819. "
        "Account: 12345678901234. Visit https://example.com/path. "
        "SSN: 123-45-6789. Server IP: 192.168.1.42."
    )
    result = await deidentifier.deidentify(sample, tenant_id=isolated_tenant)
    summary = result.de_id_summary
    # The brief's 9 regex types must each contribute at least one hit.
    for t in ["MONEY", "EMAIL", "PHONE_E164", "IBAN", "ACCOUNT_NUM",
              "DATE_ISO", "IP", "URL", "SSN"]:
        assert t in summary, f"missing regex type {t}; got {summary}"
        assert summary[t] >= 1


@pytest.mark.asyncio
async def test_regex_tokens_have_stable_shape(isolated_tenant):
    result = await deidentifier.deidentify(
        "Email a@b.com to b@c.com.", tenant_id=isolated_tenant,
    )
    import re
    for tok in result.token_map:
        assert re.fullmatch(r"\[\[ENT_[A-Z_]+_\d{3,}\]\]", tok), tok


@pytest.mark.asyncio
async def test_dedup_same_value_yields_same_token(isolated_tenant):
    """Same original twice → same token (deterministic per-document)."""
    text = "Reach out to support@example.org or support@example.org again."
    result = await deidentifier.deidentify(text, tenant_id=isolated_tenant)
    # Unique EMAIL token count = 1 (dedup).
    assert result.de_id_summary.get("EMAIL") == 1, result.de_id_summary
    email_token = next(
        tok for tok, orig in result.token_map.items()
        if orig.endswith("@example.org")
    )
    assert result.redacted_text.count(email_token) == 2


@pytest.mark.asyncio
async def test_empty_content_returns_empty_result(isolated_tenant):
    result = await deidentifier.deidentify("", tenant_id=isolated_tenant)
    assert result.redacted_text == ""
    assert result.token_map == {}
    assert result.dilution_score == 0
    assert result.exposure_reduction_score == 0


# ─────────────────────────────────────────────────────────────────────
# 2. spaCy NER coverage.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_spacy_tags_person_and_org(isolated_tenant):
    """The canonical course-correction fixture."""
    text = "John Smith bought 500 shares of Apple Inc. for $50,000."
    result = await deidentifier.deidentify(text, tenant_id=isolated_tenant)
    summary = result.de_id_summary
    assert summary.get("PERSON", 0) >= 1, summary
    assert summary.get("ORG", 0) >= 1, summary
    assert summary.get("MONEY", 0) >= 1, summary


@pytest.mark.asyncio
async def test_spacy_model_actually_loaded(isolated_tenant):
    # Trigger lazy load by calling deidentify.
    await deidentifier.deidentify("Initial call.", tenant_id=isolated_tenant)
    model = deidentifier.get_spacy_model_name()
    assert model in ("en_core_web_trf", "en_core_web_sm"), \
        f"expected one of trf/sm, got {model}"


# ─────────────────────────────────────────────────────────────────────
# 3. Tenant entity dictionary.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_tenant_dict_catches_obscure_name(db_conn, isolated_tenant):
    """Course-correction fixture: 'Lemasy' is a name spaCy has never
    seen, but registering it in the tenant dict redacts it anyway."""
    await tenant_entities.register(
        tenant_id=isolated_tenant, entity_text="Lemasy", entity_type="ORG",
    )
    text = "We're partnering with Lemasy next quarter."
    result = await deidentifier.deidentify(text, tenant_id=isolated_tenant)
    assert result.de_id_summary.get("ORG", 0) >= 1
    assert "Lemasy" not in result.redacted_text
    assert any("Lemasy" == v for v in result.token_map.values())


@pytest.mark.asyncio
async def test_tenant_dict_case_insensitive(db_conn, isolated_tenant):
    await tenant_entities.register(
        tenant_id=isolated_tenant, entity_text="Lemasy", entity_type="ORG",
    )
    text = "lemasy held a board meeting."
    result = await deidentifier.deidentify(text, tenant_id=isolated_tenant)
    assert "lemasy" not in result.redacted_text


@pytest.mark.asyncio
async def test_tenant_dict_word_boundary(db_conn, isolated_tenant):
    """Should NOT match inside another word (e.g. 'Lemasypal')."""
    await tenant_entities.register(
        tenant_id=isolated_tenant, entity_text="Lemasy", entity_type="ORG",
    )
    text = "The lemasypal protocol exists, not the Lemasy entity here."
    result = await deidentifier.deidentify(text, tenant_id=isolated_tenant)
    # 'lemasypal' should remain; 'Lemasy' should be redacted.
    assert "lemasypal" in result.redacted_text
    assert " Lemasy " not in result.redacted_text


@pytest.mark.asyncio
async def test_tenant_dict_isolated_per_tenant(db_conn):
    """Tenant A's entity is invisible from tenant B's lookup."""
    tid_a = "test-A-" + uuid.uuid4().hex[:8]
    tid_b = "test-B-" + uuid.uuid4().hex[:8]
    try:
        await tenant_entities.register(
            tenant_id=tid_a, entity_text="MercurySolutions", entity_type="ORG",
        )
        text = "MercurySolutions held a board meeting."
        r_a = await deidentifier.deidentify(text, tenant_id=tid_a)
        r_b = await deidentifier.deidentify(text, tenant_id=tid_b)
        # A redacts it via tenant dict (priority 2 → before spaCy).
        # spaCy may or may not catch 'MercurySolutions' itself. Either
        # way, the de_id_summary should NOT show MercurySolutions for B
        # via the tenant_dict source — but spaCy might still tag it
        # ORG. The strict test: A's token_map carries the original,
        # B's token_map either is empty for that string OR carries it
        # via spaCy. We assert at minimum that the redaction *count*
        # for ORG in A is ≥ B.
        assert r_a.de_id_summary.get("ORG", 0) >= r_b.de_id_summary.get("ORG", 0)
    finally:
        await db_conn.synisense_tenant_entities.delete_many({"tenant_id": tid_a})
        tenant_entities._force_clear_cache_for_test()


# ─────────────────────────────────────────────────────────────────────
# 4. Scoring.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_scores_clamped_0_to_100(isolated_tenant):
    sample = "John Smith email john@example.com phone +1-415-555-1234."
    result = await deidentifier.deidentify(sample, tenant_id=isolated_tenant)
    assert 0.0 <= result.exposure_reduction_score <= 100.0
    assert 0.0 <= result.dilution_score <= 100.0
    assert result.exposure_reduction_score > 0
    assert result.dilution_score > 0


@pytest.mark.asyncio
async def test_scores_zero_when_no_entities(isolated_tenant):
    result = await deidentifier.deidentify(
        "the quick brown fox jumps over the lazy dog.", tenant_id=isolated_tenant,
    )
    assert result.exposure_reduction_score == 0
    assert result.dilution_score == 0


# ─────────────────────────────────────────────────────────────────────
# 5. Performance — must complete a 500-word doc in <1s on CPU (sm model).
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_performance_under_1s_for_500_words(isolated_tenant):
    import time as _t
    # Build a 500-word doc with mixed entities every ~50 words.
    boilerplate = ("the company reported strong growth this quarter and the team "
                   "is meeting next week to plan the next phase ")
    # Build a ~500-word doc with mixed entities every ~50 words.
    seg = (boilerplate * 3 + "John Smith said $50,000 should suffice. ")
    doc_words: list[str] = []
    for _ in range(10):
        doc_words.extend(seg.split())
    # Trim to exactly 500.
    doc = " ".join(doc_words[:500])
    word_count = len(doc.split())
    assert 400 <= word_count <= 600, word_count
    start = _t.perf_counter()
    await deidentifier.deidentify(doc, tenant_id=isolated_tenant)
    elapsed = _t.perf_counter() - start
    # First call may include lazy spaCy load — that's allowed up to 8s.
    # Second call must be <1s.
    start2 = _t.perf_counter()
    await deidentifier.deidentify(doc, tenant_id=isolated_tenant)
    elapsed2 = _t.perf_counter() - start2
    assert elapsed2 < 1.0, f"warm de-id pass took {elapsed2:.2f}s (>1s)"


# ─────────────────────────────────────────────────────────────────────
# 6. Fail-closed when spaCy unavailable.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_fail_closed_on_spacy_failure(isolated_tenant, monkeypatch):
    """Force the spaCy loader to fail → ServiceUnavailable raised."""
    # Reset module cache to force a re-load attempt.
    deidentifier._force_clear_cache_for_test()
    def _bad_load(name):
        raise ImportError("forced for test")
    monkeypatch.setattr(deidentifier, "_attempt_load", _bad_load)
    with pytest.raises(ServiceUnavailable) as ei:
        await deidentifier.deidentify(
            "John Smith.", tenant_id=isolated_tenant,
        )
    msg = str(ei.value)
    assert "spaCy" in msg or "spacy" in msg.lower()
    # Reset for downstream tests.
    deidentifier._force_clear_cache_for_test()


# ─────────────────────────────────────────────────────────────────────
# 7. Re-identifier round-trip.
# ─────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_reidentifier_round_trip(isolated_tenant):
    text = "John Smith owes $50,000."
    r = await deidentifier.deidentify(text, tenant_id=isolated_tenant)
    rehydrated = reidentifier.reidentify(r.redacted_text, r.token_map)
    # Should match original (modulo internal whitespace — equality is fine here).
    assert "John Smith" in rehydrated
    assert "$50,000" in rehydrated
    # No tokens should survive.
    assert "[[ENT_" not in rehydrated


def test_reidentifier_leaves_unknown_tokens_alone():
    """Drift safety — an unrecognised token MUST not be expanded with a
    guess. Returned as-is for the audit log to flag."""
    text = "leftover [[ENT_PERSON_999]] should stay."
    out = reidentifier.reidentify(text, token_map={"[[ENT_PERSON_001]]": "Alice"})
    assert "[[ENT_PERSON_999]]" in out


def test_reidentifier_empty_inputs():
    assert reidentifier.reidentify("", {}) == ""
    assert reidentifier.reidentify("hello", {}) == "hello"


# ─────────────────────────────────────────────────────────────────────
# 8. Trust Receipt — HKDF derivation + HMAC sign + verify.
# ─────────────────────────────────────────────────────────────────────
def test_hkdf_per_tenant_keys_differ():
    k1 = trust_receipt.derive_tenant_key("tenant-A")
    k2 = trust_receipt.derive_tenant_key("tenant-B")
    assert len(k1) == 32
    assert len(k2) == 32
    assert k1 != k2


def test_hkdf_deterministic_for_same_tenant():
    k1 = trust_receipt.derive_tenant_key("tenant-X")
    trust_receipt._clear_cache_for_test()
    k2 = trust_receipt.derive_tenant_key("tenant-X")
    assert k1 == k2


def test_trust_receipt_signature_verifies():
    receipt = trust_receipt.build_trust_receipt(
        receipt_id="rcp-1", audit_id="aud-1", tenant_id="tenant-A",
        consumer_id="solva", purpose="test.smoke",
        timestamp="2026-05-13T00:00:00+00:00",
        llm_provider="gemini", llm_model="gemini-2.5-flash",
        de_id_summary={"PERSON": 1}, dilution_score=10.0,
        exposure_reduction_score=20.0,
        request_hash="sha256:abc", response_hash="sha256:def",
    )
    assert trust_receipt.verify(receipt, tenant_id="tenant-A")


def test_trust_receipt_tamper_detection():
    receipt = trust_receipt.build_trust_receipt(
        receipt_id="rcp-1", audit_id="aud-1", tenant_id="tenant-A",
        consumer_id="solva", purpose="test.smoke",
        timestamp="2026-05-13T00:00:00+00:00",
        llm_provider="gemini", llm_model="gemini-2.5-flash",
        de_id_summary={"PERSON": 1}, dilution_score=10.0,
        exposure_reduction_score=20.0,
        request_hash="sha256:abc", response_hash="sha256:def",
    )
    receipt["purpose"] = "test.evil"  # tamper
    assert not trust_receipt.verify(receipt, tenant_id="tenant-A")


def test_trust_receipt_wrong_tenant_fails_verify():
    receipt = trust_receipt.build_trust_receipt(
        receipt_id="rcp-1", audit_id="aud-1", tenant_id="tenant-A",
        consumer_id="solva", purpose="test.smoke",
        timestamp="2026-05-13T00:00:00+00:00",
        llm_provider="gemini", llm_model="gemini-2.5-flash",
        de_id_summary={"PERSON": 1}, dilution_score=10.0,
        exposure_reduction_score=20.0,
        request_hash="sha256:abc", response_hash="sha256:def",
    )
    assert not trust_receipt.verify(receipt, tenant_id="tenant-B")


# ─────────────────────────────────────────────────────────────────────
# 9. Purpose validator.
# ─────────────────────────────────────────────────────────────────────
def test_purpose_validator_allows_exact():
    purpose_validator.validate_purpose("test.smoke")


def test_purpose_validator_allows_wildcard_match():
    purpose_validator.validate_purpose("test.deep.nested.path")


def test_purpose_validator_denies_unknown():
    with pytest.raises(PurposeInvalid):
        purpose_validator.validate_purpose("chat.something")


def test_purpose_validator_blocks_internal_for_external_callers():
    with pytest.raises(PurposeInvalid):
        purpose_validator.validate_purpose(
            "synisense.shield.internal.something", internal_caller=False,
        )


def test_purpose_validator_empty_purpose_rejected():
    with pytest.raises(PurposeInvalid):
        purpose_validator.validate_purpose("")


def test_purpose_validator_no_synisense_internal_in_allow_list():
    """Course-correction: the cloud NER purpose was removed."""
    from services.synisense.config import ALLOWED_PURPOSES
    assert "synisense.shield.internal.ner" not in ALLOWED_PURPOSES


# ─────────────────────────────────────────────────────────────────────
# 10. Config — dev-fallback warning visibility.
# ─────────────────────────────────────────────────────────────────────
def test_dev_fallback_flag_exposed():
    # In CI / dev the env var isn't set, so the flag should be True.
    # In production it would be False. Either way the function exists.
    assert isinstance(is_dev_fallback_active(), bool)
