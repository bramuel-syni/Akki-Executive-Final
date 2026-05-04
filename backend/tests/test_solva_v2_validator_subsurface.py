"""Phase 15.1 — validator sub-surface integration test.

The contract under test is in services/solva_v2/llm_adapter.py::validator_call:
    1. Validator gets its OWN Synisense pass (sub-surface 'solve_v2.validator')
       — not the same run_id as the synthesis call.
    2. The audit entry it emits carries shield_required=True with a NON-NULL
       synisense_run_id, and shield_bypassed_reason is None.
    3. If Synisense fails, validator_call refuses to call the validator LLM.

This test stubs the Synisense pipeline write + LLM validator wrapper. It
exercises the real validator_call codepath — no orchestrator, no Mongo
beyond the stubbed db.synisense_runs lookup.

Run:
    pytest /app/backend/tests/test_solva_v2_validator_subsurface.py -v
"""
from __future__ import annotations

import hashlib
import os
import sys
import uuid

import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from services.solva_v2.llm_adapter import validator_call  # noqa: E402


SYNTH_TEXT = (
    "Q3 revenue missed by 14% [T:corpus]. A comparable mid-cap saw the same "
    "pattern [T:comparable]. The board may be avoiding the pricing question "
    "[T:speculation]."
)


@pytest.mark.asyncio
async def test_validator_uses_dedicated_subsurface(monkeypatch):
    """Synisense.run is called with surface='solve_v2.validator', and the
    audit entry comes back with the matching synisense_run_id."""
    captured = {"surfaces": [], "contents": []}

    fresh_run_id = f"syn-{uuid.uuid4().hex[:10]}"

    async def fake_syn_run(text, context_id, surface, mode, account_id):
        captured["surfaces"].append(surface)
        captured["contents"].append(text)
        return {"redacted_text": text, "shield_map_id": None, "surface": surface}

    async def fake_lookup(input_sha256, surface, account_id):
        # Sanity — the lookup MUST be on the validator sub-surface.
        assert surface == "solve_v2.validator"
        return fresh_run_id

    async def fake_validate(**kwargs):
        # The validator wrapper must receive the sub-surface, not the
        # generic 'solve_v2'.
        assert kwargs["surface"] == "solve_v2.validator"
        return {
            "verdict": "validated",
            "confidence": 88,
            "notes": ["unit-mock"],
            "validator_provider": "gemini",
            "validator_model": "gemini-2.5-flash",
        }

    monkeypatch.setattr(
        "services.solva_v2.llm_adapter._lookup_synisense_run_id", fake_lookup,
    )
    monkeypatch.setattr("services.synisense.run", fake_syn_run)
    monkeypatch.setattr("llm_service.validate_independent", fake_validate)

    result = await validator_call(
        content=SYNTH_TEXT,
        objective="Synthesis grounding integrity",
        layer="synthesis",
        turn_id="t-validator",
        account_id="acct-x",
        context_id="ctx-x",
    )
    audit = result["audit_entry"]
    validation = result["validation"]

    # Surface used: validator sub-surface, exactly once.
    assert captured["surfaces"] == ["solve_v2.validator"]
    assert captured["contents"] == [SYNTH_TEXT]

    # Audit shape per the hardening contract.
    assert audit["engine"] == "validator"
    assert audit["engine_version"] == "validator@phase11"
    assert audit["layer"] == "synthesis"
    assert audit["shield_required"] is True
    assert audit["synisense_run_id"] == fresh_run_id
    assert audit["shield_bypassed_reason"] is None
    assert audit["output"]["validator_verdict"] == "validated"
    assert audit["output"]["validator_provider"] == "gemini"
    assert audit["output"]["content_length"] == len(SYNTH_TEXT)

    # Verdict propagated.
    assert validation["verdict"] == "validated"
    assert validation["confidence"] == 88


@pytest.mark.asyncio
async def test_validator_run_id_is_distinct_from_upstream_synthesis_run_id(monkeypatch):
    """The fresh-pass property: validator's run_id MUST NOT equal whatever
    the synthesis layer used. We assert the validator's lookup was done on
    'solve_v2.validator' and that we returned a different id from the one
    we tagged for synthesis."""
    upstream_synthesis_run_id = "syn-upstream-synthesis-12345"
    validator_run_id = "syn-validator-99999"

    async def fake_syn_run(text, context_id, surface, mode, account_id):
        return {"redacted_text": text, "shield_map_id": None, "surface": surface}

    async def fake_lookup(input_sha256, surface, account_id):
        # If the orchestrator slipped and queried the synthesis surface,
        # we'd return upstream_synthesis_run_id. The contract is: validator
        # MUST query its own sub-surface.
        if surface == "solve_v2.validator":
            return validator_run_id
        return upstream_synthesis_run_id

    async def fake_validate(**kwargs):
        return {
            "verdict": "qualified",
            "confidence": 60,
            "notes": [],
            "validator_provider": "gemini",
            "validator_model": "gemini-2.5-flash",
        }

    monkeypatch.setattr(
        "services.solva_v2.llm_adapter._lookup_synisense_run_id", fake_lookup,
    )
    monkeypatch.setattr("services.synisense.run", fake_syn_run)
    monkeypatch.setattr("llm_service.validate_independent", fake_validate)

    result = await validator_call(
        content=SYNTH_TEXT, objective=None,
        layer="synthesis", turn_id="t-x",
        account_id="acct-x", context_id="ctx-x",
    )
    assert result["audit_entry"]["synisense_run_id"] == validator_run_id
    assert result["audit_entry"]["synisense_run_id"] != upstream_synthesis_run_id


@pytest.mark.asyncio
async def test_validator_refuses_call_when_synisense_unavailable(monkeypatch):
    """Synisense outage → validator_call raises RuntimeError. The validator
    LLM must NOT be invoked."""
    validator_called = {"flag": False}

    async def fake_syn_run(text, context_id, surface, mode, account_id):
        raise RuntimeError("Synisense is on fire")

    async def fake_validate(**kwargs):
        validator_called["flag"] = True
        return {"verdict": "validated", "confidence": 0, "notes": []}

    monkeypatch.setattr("services.synisense.run", fake_syn_run)
    monkeypatch.setattr("llm_service.validate_independent", fake_validate)

    with pytest.raises(RuntimeError) as excinfo:
        await validator_call(
            content=SYNTH_TEXT, objective=None,
            layer="synthesis", turn_id="t-x",
            account_id="acct-x", context_id="ctx-x",
        )
    assert "Synisense unavailable for validator" in str(excinfo.value)
    assert validator_called["flag"] is False


@pytest.mark.asyncio
async def test_validator_input_hash_is_sha256_of_synthesis_content(monkeypatch):
    """The fresh pass hashes the SYNTHESIS OUTPUT text, not the original
    user input. Guard against the orchestrator accidentally feeding the
    user query into the validator."""
    seen_basis = {}

    async def fake_syn_run(text, context_id, surface, mode, account_id):
        return {"redacted_text": text, "shield_map_id": None}

    async def fake_lookup(input_sha256, surface, account_id):
        seen_basis["sha"] = input_sha256
        return f"syn-{input_sha256[:8]}"

    async def fake_validate(**kwargs):
        return {
            "verdict": "validated", "confidence": 99, "notes": [],
            "validator_provider": "gemini", "validator_model": "gemini-2.5-flash",
        }

    monkeypatch.setattr(
        "services.solva_v2.llm_adapter._lookup_synisense_run_id", fake_lookup,
    )
    monkeypatch.setattr("services.synisense.run", fake_syn_run)
    monkeypatch.setattr("llm_service.validate_independent", fake_validate)

    expected_sha = hashlib.sha256(SYNTH_TEXT.encode("utf-8")).hexdigest()
    await validator_call(
        content=SYNTH_TEXT, objective=None,
        layer="synthesis", turn_id="t-x",
        account_id="acct-x", context_id="ctx-x",
    )
    assert seen_basis["sha"] == expected_sha
