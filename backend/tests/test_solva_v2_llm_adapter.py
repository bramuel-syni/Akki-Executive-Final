"""Unit test — Solva v2 LLM adapter always runs Synisense first.

This test is the POC's load-bearing safety check: it proves that no LLM call
can reach `llm_service.call_llm` without the prompt passing through
`services.synisense.run` first, and that the resulting audit entry carries a
`synisense_run_id`.

Both dependencies are monkey-patched so the test is hermetic — no real
Synisense engine, no real LLM. Uses `asyncio.run()` inside a sync test to
match the convention already used in this repo's pytest suite.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest
from dotenv import load_dotenv

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
load_dotenv("/app/backend/.env")

from services.solva_v2 import llm_adapter  # noqa: E402


def test_synisense_runs_before_llm(monkeypatch):
    call_order = []

    async def fake_syn_run(**kwargs):
        call_order.append(("synisense", kwargs.get("surface"), kwargs.get("mode"), kwargs.get("text", "")[:20]))
        return {
            "redacted_text": "REDACTED " + (kwargs.get("text") or "")[:50],
            "spans": [],
            "stats": {"elapsed_ms": 5},
            "shield_map_id": None,
        }

    async def fake_call_llm_with_tier(**kwargs):
        call_order.append(("llm", kwargs.get("surface"), kwargs["call_args"]["user_query"][:30]))
        return (
            {
                "response": "Mock LLM reply.",
                "model": "claude-sonnet-4-5-20250929",
                "tier": "standard",
                "mode": "live",
            },
            {"downgraded": False, "served_tier": "standard"},
        )

    async def fake_find_one(*args, **kwargs):
        call_order.append(("syn_run_lookup",))
        return {"id": "fake-run-id-abc123"}

    monkeypatch.setattr("services.synisense.run", fake_syn_run)
    monkeypatch.setattr("llm_tier_quota.call_llm_with_tier", fake_call_llm_with_tier)

    # Motor collections do not accept arbitrary setattr; patch the adapter's
    # helper directly so the run_id lookup is hermetic.
    async def fake_lookup(input_sha256, surface, account_id):
        call_order.append(("syn_run_lookup",))
        return "fake-run-id-abc123"

    monkeypatch.setattr(llm_adapter, "_lookup_synisense_run_id", fake_lookup)

    async def _runner():
        return await llm_adapter.shielded_call(
            engine="llm_primary",
            layer="framing",
            turn_id="turn-xyz",
            prompt="Raw user intent carrying PII like alice@example.com.",
            system_override="You are Solva.",
            tier="standard",
            surface="solve_v2",
            account_id="acct-1",
            session_id="sess-1",
        )

    result = asyncio.run(_runner())

    event_types = [e[0] for e in call_order]
    assert event_types[0] == "synisense", f"First call must be Synisense, got {event_types}"
    assert "llm" in event_types
    syn_idx = event_types.index("synisense")
    llm_idx = event_types.index("llm")
    assert syn_idx < llm_idx, "LLM called before Synisense — contract violation."

    llm_call = next(e for e in call_order if e[0] == "llm")
    assert llm_call[2].startswith("REDACTED"), f"LLM did not receive redacted prompt: {llm_call}"

    syn_call = next(e for e in call_order if e[0] == "synisense")
    assert syn_call[1] == "solve_v2"
    assert syn_call[2] == "redact"

    assert result.synisense_run_id == "fake-run-id-abc123"
    assert result.reasoning_audit_entry["synisense_run_id"] == "fake-run-id-abc123"
    assert result.reasoning_audit_entry["engine"] == "llm_primary"
    assert result.reasoning_audit_entry["layer"] == "framing"
    assert result.reasoning_audit_entry["input_hash"]
    assert len(result.reasoning_audit_entry["input_hash"]) == 64


def test_adapter_refuses_when_synisense_fails(monkeypatch):
    async def boom(**kwargs):
        raise RuntimeError("synisense exploded")

    monkeypatch.setattr("services.synisense.run", boom)

    async def _runner():
        await llm_adapter.shielded_call(
            engine="llm_primary",
            layer="framing",
            turn_id="t1",
            prompt="anything",
            system_override=None,
            tier="standard",
            surface="solve_v2",
            account_id="acct",
            session_id="s1",
        )

    with pytest.raises(RuntimeError, match="Synisense unavailable"):
        asyncio.run(_runner())
